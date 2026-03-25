---
name: voice-note
description: Transcribe lab voice notes from Telegram/Slack, clean and correct with experiment context, and post to Labstep
version: 0.1.0
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - ffmpeg
      env:
        - FIREWORKS_API_KEY
        - LABSTEP_API_KEY
      config: []
    always: false
    emoji: "🎤"
    os: [darwin, linux]
    install:
      - kind: pip
        package: labstep
        bins: []
      - kind: pip
        package: python-dotenv
        bins: []
      - kind: pip
        package: requests
        bins: []
---

# 🎤 Voice Note Transcriber

You are the **Voice Note Transcriber**, a skill that converts lab voice notes into clean, contextualised text and posts them to the matching Labstep experiment.

## When to Use This Skill

Route to this skill when:
- OpenClaw delivers raw audio bytes from a Telegram or Slack voice note
- The user asks to "transcribe a voice note" or "post voice note to Labstep"
- Audio data arrives with metadata containing `user` and `platform` fields

## Input

OpenClaw delivers:
- `audio_bytes`: Raw audio data (Opus/OGG, WAV, MP3, M4A, FLAC)
- `metadata.user`: Sender's display name (Telegram/Slack username)
- `metadata.platform`: Source platform ("telegram" or "slack")

## Output

A comment posted on the Labstep experiment thread:
```
🎤 {user} (via {platform}): {cleaned transcript}
```

## Pipeline

### Stage 0: Audio Pre-processing

Convert incoming audio to a format accepted by the Fireworks Whisper API.

**Accepted formats**: WAV, MP3, FLAC, OGG
**Common input**: Telegram sends Opus in OGG containers; Slack sends M4A/AAC.

```python
import subprocess
import tempfile
import os

def preprocess_audio(audio_bytes: bytes, source_format: str = "ogg") -> str:
    """
    Write raw audio bytes to a temp file. If not in a Whisper-accepted format,
    transcode to WAV using ffmpeg. Returns path to the processed audio file.
    """
    accepted = {"wav", "mp3", "flac", "ogg"}
    suffix = f".{source_format}"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        input_path = f.name

    if source_format.lower() in accepted:
        return input_path

    # Transcode to WAV
    output_path = input_path.rsplit(".", 1)[0] + ".wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path],
            capture_output=True, check=True
        )
    finally:
        os.unlink(input_path)

    return output_path
```

**Error handling**: If ffmpeg is not installed or transcoding fails, report the error and stop the pipeline.

### Stage 1: Transcribe with Fireworks Whisper

Send pre-processed audio to the Fireworks Whisper API.

```python
import os
import time
import requests
from dotenv import load_dotenv

def get_fireworks_apikey() -> str:
    load_dotenv()
    key = os.environ.get("FIREWORKS_API_KEY")
    if key:
        return key
    raise RuntimeError("No Fireworks API key found. Set FIREWORKS_API_KEY in .env")

def transcribe(audio_path: str) -> str:
    """
    Send audio file to Fireworks Whisper API. Retries up to 3 times
    on transient failures with delays of 2s, 5s, 10s.
    Returns the transcript text.
    """
    url = "https://audio-turbo.us-virginia-1.direct.fireworks.ai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {get_fireworks_apikey()}"}

    delays = [2, 5, 10]
    last_error = None

    for attempt in range(3):
        try:
            with open(audio_path, "rb") as f:
                resp = requests.post(
                    url,
                    headers=headers,
                    files={"file": f},
                    data={"model": "whisper-v3-turbo"},
                    timeout=60,
                )
            resp.raise_for_status()
            return resp.json()["text"]
        except (requests.RequestException, KeyError) as e:
            last_error = e
            if attempt < 2:
                time.sleep(delays[attempt])

    raise RuntimeError(f"Transcription failed after 3 attempts: {last_error}")
```

**Cleanup**: After transcription, delete the temporary audio file:
```python
os.unlink(audio_path)
```

### Stage 2: Extract SK Number

Multi-strategy extraction to find SK experiment number(s) in the transcript.

**Strategy 1 — Regex:**
```python
import re

def extract_sk_regex(transcript: str) -> list[str]:
    """Extract SK numbers via regex. Returns e.g. ['SK543', 'SK544']."""
    matches = re.findall(r'\bSK\s?(\d{3,})\b', transcript, re.IGNORECASE)
    return [f"SK{m}" for m in matches]
```

**Strategy 2 — LLM extraction:**

If regex finds nothing, use this prompt to extract spoken SK numbers:

```
You are extracting experiment SK numbers from a voice note transcript.
SK numbers are 3+ digit identifiers like SK543, SK1024, etc.
They may be spoken as:
- "S K five four three" or "S. K. 543"
- "experiment five forty three"
- "the five four three experiment"

Transcript:
{transcript}

Return ONLY a JSON array of SK numbers found, e.g. ["SK543", "SK544"].
If none found, return [].
```

**Strategy 3 — Labstep validation:**

Validate all candidates against real experiments:

```python
import labstep

def validate_sk_numbers(candidates: list[str], user) -> list[str]:
    """
    Check each candidate SK number against Labstep.
    Returns only those that match a real experiment's custom_identifier.
    """
    if not candidates:
        return []

    validated = []
    for sk in candidates:
        results = user.getExperiments(search_query=sk, count=5)
        for exp in results:
            if exp.custom_identifier and exp.custom_identifier.upper() == sk.upper():
                validated.append(sk)
                break
    return validated


def get_recent_sk_numbers(user, count: int = 20) -> list[str]:
    """
    Fetch recent experiment SK numbers for fuzzy matching.
    Useful when LLM extraction produces bare numbers without 'SK' prefix.
    """
    recent = user.getExperiments(count=count)
    return [
        exp.custom_identifier
        for exp in recent
        if exp.custom_identifier
    ]
```

**Fallback — no SK found:**

If all three strategies yield no match:

1. Save transcript to `voice-note-unmatched/{timestamp}_{user}.txt`
2. Reply via OpenClaw to the originating thread:
   `"Could not find an SK number in this voice note. Please reply with the SK number (e.g., SK543)."`
3. If the user replies with an SK number, resume from Stage 3
4. If no reply within 24 hours, transcript stays in the unmatched directory for manual review

```python
import os
from datetime import datetime

def save_unmatched(transcript: str, user: str) -> str:
    """Save transcript locally when no SK number is found."""
    os.makedirs("voice-note-unmatched", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"voice-note-unmatched/{ts}_{user}.txt"
    with open(path, "w") as f:
        f.write(transcript)
    return path
```
