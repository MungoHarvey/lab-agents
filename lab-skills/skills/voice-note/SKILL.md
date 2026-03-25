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
