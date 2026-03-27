---
name: lab-note
description: Process voice notes, photos, and data files from Telegram/Slack — post to Labstep experiments with context-aware descriptions
version: 0.2.0
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
    emoji: "🔬"
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
      - kind: pip
        package: Pillow
        bins: []
      - kind: pip
        package: pandas
        bins: []
      - kind: pip
        package: openpyxl
        bins: []
---

# 🔬 Lab Note

You are the **Lab Note** skill, processing voice notes, photos, and data files from Telegram/Slack and posting them as comments on the matching Labstep experiment.

## When to Use This Skill

Route to this skill when:
- OpenClaw delivers raw audio bytes from a Telegram or Slack voice note
- OpenClaw delivers an image (photo of a gel, plate, microscope field, QC screenshot)
- OpenClaw delivers a data file (CSV, Excel)
- The user asks to "transcribe a voice note", "post a photo to Labstep", or "upload data to an experiment"
- Any media arrives with metadata containing `user` and `platform` fields

## Input

OpenClaw delivers one or more of:
- `audio_bytes`: Raw audio data (Opus/OGG, WAV, MP3, M4A, FLAC)
- `image_bytes`: Raw image data (PNG, JPG, HEIC, TIFF)
- `file_bytes`: Raw data file bytes (CSV, XLSX)
- `file_name`: Original filename (e.g., `SK543_qubit_results.csv`)
- `metadata.user`: Sender's display name (Telegram/Slack username)
- `metadata.platform`: Source platform ("telegram" or "slack")
- `metadata.caption`: Optional text the user typed alongside the media

## Output

A comment posted on the Labstep experiment thread. Format varies by media type:

**Voice note:**
```
🎤 {user} (via {platform}): {cleaned transcript}
```

**Photo:**
```
📸 {user} (via {platform}): {image description}
```
Photo file is attached to the comment.

**Data file:**
```
📄 {user} (via {platform}): {file summary}
```
Data file is attached to the comment.

**Mixed (voice + photo):**
```
🎤 {user} (via {platform}): {cleaned transcript}

📸 {image description}
```
Photo file is attached to the comment.

## Pipeline

### Stage 0: Media Classification and Pre-processing

Classify what OpenClaw delivered and pre-process each media type.

```python
def classify_media(audio_bytes=None, image_bytes=None, file_bytes=None, file_name=None) -> list[str]:
    """Return list of media types present: 'audio', 'image', 'file'."""
    types = []
    if audio_bytes:
        types.append("audio")
    if image_bytes:
        types.append("image")
    if file_bytes and file_name:
        types.append("file")
    return types
```

#### Audio Pre-processing

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
    except subprocess.CalledProcessError:
        if os.path.exists(output_path):
            os.unlink(output_path)
        raise
    finally:
        os.unlink(input_path)

    return output_path
```

#### Image Pre-processing

Save image bytes to a temp file, validate format, and resize if too large for upload.

```python
from PIL import Image
import io

def save_temp_image(image_bytes: bytes) -> str:
    """
    Write image bytes to a temp file. Validate it's a real image with Pillow.
    Resize if larger than 4MB to keep Labstep uploads fast.
    Returns path to the processed image file.
    """
    img = Image.open(io.BytesIO(image_bytes))

    # Resize large images
    if len(image_bytes) > 4 * 1024 * 1024:
        img.thumbnail((1500, 1500), Image.LANCZOS)

    # Normalize to RGB
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f, "PNG")
        return f.name
```

#### File Pre-processing

Save file bytes to a temp file preserving the original extension, and generate a preview.

```python
import pandas as pd

def save_temp_file(file_bytes: bytes, file_name: str) -> str:
    """Save file bytes to a temp file preserving the original extension."""
    ext = os.path.splitext(file_name)[1] or ".csv"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(file_bytes)
        return f.name

def generate_file_preview(file_path: str) -> dict:
    """
    Read a CSV or Excel file and return a preview dict with shape, columns,
    and first 10 rows as a markdown table.
    """
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext in (".csv", ".tsv"):
            df = pd.read_csv(file_path, nrows=100)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path, nrows=100)
        else:
            return {"columns": [], "n_rows": 0, "preview": f"Unsupported file type: {ext}"}
    except Exception as e:
        return {"columns": [], "n_rows": 0, "preview": f"Could not read file: {e}"}

    return {
        "columns": list(df.columns),
        "n_rows": len(df),
        "preview": df.head(10).to_markdown(index=False),
    }
```

**Error handling**: If image is corrupt or file is unreadable, report the error and stop the pipeline for that media type. Other media types in the same message continue processing.

### Stage 1: Audio Transcription

Send pre-processed audio to the Fireworks Whisper API. Images and files skip this stage — their content analysis happens at Stage 4 after experiment context is available.

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

### Stage 2: Extract SK Number

Multi-strategy extraction to find SK experiment number(s). Searches across ALL available text: transcript, caption, and filename.

```python
def gather_sk_text(raw_transcript: str = None, caption: str = None, file_name: str = None) -> str:
    """Combine all available text sources for SK extraction."""
    return " ".join(filter(None, [raw_transcript, caption, file_name]))
```

**Strategy 1 — Regex:**
```python
import re

def extract_sk_regex(text: str) -> list[str]:
    """Extract SK numbers via regex. Returns e.g. ['SK543', 'SK544']."""
    matches = re.findall(r'\bSK\s?(\d{3,})\b', text, re.IGNORECASE)
    return [f"SK{m}" for m in matches]
```

**Strategy 2 — LLM extraction:**

If regex finds nothing, use this prompt to extract spoken or implied SK numbers:

```
You are extracting experiment SK numbers from a lab note.
SK numbers are 3+ digit identifiers like SK543, SK1024, etc.

The note may contain:
- Voice transcript where SK is spoken: "S K five four three", "experiment five forty three"
- A filename like "SK543_qubit_results.csv"
- A caption like "results for 543"

Text:
{text}

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

**Strategy 4 — Image SK extraction (photos only):**

For photo-only messages with no caption or transcript, ask Claude vision if the image contains a visible SK number or experiment identifier (e.g., a handwritten label on a tube, a notebook page heading). This is executed inline by the agent viewing the image.

```
Does this lab photo contain any visible experiment identifiers (SK numbers)?
Look for labels, handwritten notes, screen text, or sample IDs.
Return ONLY a JSON array of SK numbers found, e.g. ["SK543"].
If none found, return [].
```

**Fallback — no SK found:**

If all strategies yield no match:

1. Reply via OpenClaw to the originating thread:
   `"Could not find an SK number in this note. Please reply with the SK number (e.g., SK543)."`
2. If the user replies with an SK number, resume from Stage 3
3. Do **not** save unmatched content locally — it stays in the agent's context until the user responds or the session ends

### Stage 3: Labstep Context Fetch

Fetch experiment metadata to build a domain vocabulary. Used for transcript correction, image description, and file summarization.

```python
import os
import json
import labstep
from dotenv import load_dotenv

def get_labstep_apikey() -> str:
    load_dotenv()
    key = os.environ.get("LABSTEP_API_KEY")
    if key:
        return key
    raise RuntimeError("No Labstep API key found. Set LABSTEP_API_KEY in .env")

def fetch_experiment_context(sk_number: str, user=None) -> tuple[dict, object]:
    """
    Fetch experiment metadata from Labstep for domain vocabulary.
    Returns a dict with protocol_body, reagents, data_fields, comments, gene_names.
    Accepts an optional pre-authenticated user to avoid redundant auth calls.

    Context budget: ~4000 tokens total.
    """
    if user is None:
        user = labstep.authenticate(apikey=get_labstep_apikey())

    # Look up experiment by SK number
    results = user.getExperiments(search_query=sk_number, count=5)
    exp = None
    for r in results:
        if r.custom_identifier and r.custom_identifier.upper() == sk_number.upper():
            exp = r
            break

    if not exp:
        raise ValueError(f"Experiment {sk_number} not found in Labstep")

    context = {"sk_number": sk_number, "experiment_name": exp.name}

    # Protocol body (~500 tokens budget → 2000 chars)
    # Note: Protocol body text lives on protocol-collection.last_version.state
    # (ProseMirror JSON), not on experiment-linked copies. Try both access patterns.
    try:
        protocols = exp.getProtocols()
        if protocols:
            proto = protocols[0]
            state = getattr(proto, 'state', None)
            if state:
                body = json.dumps(state) if isinstance(state, dict) else str(state)
            else:
                body = str(getattr(proto, 'body', '') or '')
            context["protocol_body"] = body[:2000] + ("[...truncated]" if len(body) > 2000 else "")
    except Exception:
        context["protocol_body"] = ""

    # Reagent/resource names (~200 tokens)
    try:
        inv_fields = exp.getInventoryFields() if hasattr(exp, 'getInventoryFields') else []
        context["reagents"] = [f.name for f in inv_fields][:30]
    except Exception:
        context["reagents"] = []

    # Data fields (~300 tokens) and gene names (~500 tokens)
    data_fields = []
    try:
        data_fields = exp.getDataFields()
        context["data_fields"] = [
            {"name": f.fieldName, "value": str(getattr(f, 'value', '') or '')[:100]}
            for f in data_fields
        ][:20]
    except Exception:
        context["data_fields"] = []

    # Recent comments (~2000 tokens → last 10, 500 chars each)
    try:
        comments = exp.getComments()
        context["recent_comments"] = [
            str(getattr(c, 'body', '') or '')[:500]
            for c in (comments[:10] if comments else [])
        ]
    except Exception:
        context["recent_comments"] = []

    # Gene names — extracted from data fields
    try:
        gene_fields = [
            str(getattr(f, 'value', '') or '')
            for f in data_fields
            if any(kw in (f.fieldName or '').lower() for kw in ['gene', 'target', 'primer'])
        ]
        context["gene_names"] = gene_fields[:20]
    except Exception:
        context["gene_names"] = []

    return context, exp
```

### Stage 4: Content Refinement

Each media type gets its own refinement step using experiment context.

#### Audio: LLM Clean & Correct (unchanged)

**Prompt template:**

```
You are cleaning a voice note transcript from a lab researcher. You have context
from their Labstep experiment to help correct domain-specific terms.

## Rules
1. Remove filler words: "um", "uh", "like", "you know", "sort of", false starts, repeated words
2. Fix domain terms using the experiment context below — correct misheard scientific
   vocabulary (e.g., "see tip seek" → "scTIP-seq", "cube it" → "Qubit", "are I any" → "RNA")
3. Preserve meaning: do NOT summarise, rewrite tone, or add information. Keep the
   speaker's intent and phrasing intact. Output should read like a tidy lab note.
4. Return ONLY the cleaned transcript text, nothing else.

## Experiment Context
- Experiment: {sk_number} — {experiment_name}
- Protocol: {protocol_body}
- Reagents: {reagents}
- Gene names: {gene_names}
- Data fields: {data_fields}
- Recent comments: {recent_comments}

## Raw Transcript
{transcript}

## Cleaned Transcript
```

This is executed inline as part of the agent's response — no separate API call needed.

#### Image: Claude Vision Description

The agent views the image inline and describes it using experiment context for domain vocabulary.

**Prompt template:**

```
You are describing a lab photo for experiment {sk_number} — {experiment_name}.

## Experiment Context
- Protocol: {protocol_body}
- Reagents: {reagents}
- Gene names: {gene_names}
- Data fields: {data_fields}

## Instructions
1. Identify what the image shows (gel, plate, microscope field, QC screenshot,
   equipment setup, notebook page, etc.)
2. Describe key observations using domain terminology from the experiment context
3. Note any quantitative details visible (band sizes, well positions, concentrations,
   fluorescence patterns)
4. Flag anything that looks anomalous or noteworthy
5. Keep to 2-5 sentences — this will become a Labstep comment

Return ONLY the description text, nothing else.
```

This is executed inline — the agent has vision capabilities and can view the image directly. No separate API call needed.

#### File: LLM Summarization

The agent reads the file preview and summarises it in context.

**Prompt template:**

```
You are summarising a data file uploaded for experiment {sk_number} — {experiment_name}.

## File Info
- Filename: {file_name}
- Shape: {n_rows} rows, {n_cols} columns
- Columns: {columns}

## First 10 Rows
{preview}

## Experiment Context
- Protocol: {protocol_body}
- Reagents: {reagents}
- Data fields: {data_fields}

## Instructions
1. Describe what the data contains and how it relates to the experiment
2. Note any key values, ranges, or patterns visible in the preview
3. Keep to 1-3 sentences

Return ONLY the summary text, nothing else.
```

### Stage 5: Post to Labstep

Post the refined content as a comment on the experiment thread, optionally with a file attachment.

```python
def post_lab_note_comment(exp, body: str, attachment_path: str = None) -> str:
    """
    Post comment to Labstep experiment, optionally with file attachment.
    Uses exp.addComment(body, filepath=) for inline file attachments.
    """
    if attachment_path:
        exp.addComment(body, filepath=attachment_path)
    else:
        exp.addComment(body)
    return body
```

For data files, also upload the file as a standalone attachment for easy download:

```python
def upload_file_to_experiment(exp, file_path: str):
    """Upload a standalone file to the experiment's file gallery."""
    exp.addFile(file_path)
```

After posting, reply to the user with a link to the experiment thread:

```
Done — voice note added to **{SK}**: https://app.labstep.com/experiment-workflow/{exp.id}/thread
```

The `exp.id` is the numeric experiment ID from the Labstep experiment object.

**Error handling**: If `addComment()` fails, report the error to the user via OpenClaw with the content that failed to post. Do not save locally.

## Full Pipeline

When triggered, classify media, process each type, then post combined results.

```python
def process_lab_note(
    audio_bytes: bytes = None,
    image_bytes: bytes = None,
    file_bytes: bytes = None,
    file_name: str = None,
    user_name: str = "",
    platform: str = "",
    caption: str = "",
    source_format: str = "ogg",
):
    """
    Full pipeline: classify → preprocess → extract SK → fetch context →
    refine → post comment.
    """
    media_types = classify_media(audio_bytes, image_bytes, file_bytes, file_name)

    if not media_types:
        return {"status": "error", "message": "No media received"}

    # Stage 0+1: Pre-process and produce raw content
    raw_transcript = None
    temp_image_path = None
    temp_file_path = None
    file_preview = None

    if "audio" in media_types:
        audio_path = preprocess_audio(audio_bytes, source_format)
        try:
            raw_transcript = transcribe(audio_path)
        finally:
            if os.path.exists(audio_path):
                os.unlink(audio_path)

    if "image" in media_types:
        temp_image_path = save_temp_image(image_bytes)

    if "file" in media_types:
        temp_file_path = save_temp_file(file_bytes, file_name)
        file_preview = generate_file_preview(temp_file_path)

    # Stage 2: SK extraction from all available text
    sk_text = gather_sk_text(raw_transcript, caption, file_name)
    # Authenticate once and reuse throughout the pipeline
    ls_user = labstep.authenticate(apikey=get_labstep_apikey())

    sk_numbers = extract_sk_regex(sk_text)

    if not sk_numbers:
        # Try LLM extraction (done inline by the agent — see Stage 2 prompt)
        # The agent parses the text for spoken/implied SK variants
        # and may cross-reference against recent experiments:
        recent_sks = get_recent_sk_numbers(ls_user)
        # For photo-only messages, agent also checks the image for visible SK numbers
        pass  # Agent fills in sk_numbers from LLM extraction + recent_sks

    validated = validate_sk_numbers(sk_numbers, ls_user)

    if not validated:
        # Reply via OpenClaw: "Could not find an SK number in this note.
        # Please reply with the SK number (e.g., SK543)."
        # Do not save locally — content stays in agent context until user responds.
        return {"status": "unmatched", "message": "No SK number found"}

    # Stages 3-5: For each matched experiment
    results = []
    for sk in validated:
        context, exp = fetch_experiment_context(sk, user=ls_user)

        # Stage 4: Refine content per media type (done inline by the agent)
        # Audio → cleaned transcript using clean/correct prompt
        # Image → description using vision prompt
        # File → summary using file summarization prompt
        cleaned_transcript = raw_transcript  # Placeholder — agent replaces
        image_description = None  # Placeholder — agent fills from vision
        file_summary = None  # Placeholder — agent fills from file preview

        # Stage 5: Build and post comment
        body_parts = []
        attachment_path = None

        if "audio" in media_types:
            body_parts.append(f"🎤 {user_name} (via {platform}): {cleaned_transcript}")

        if "image" in media_types:
            if body_parts:
                body_parts.append(f"\n📸 {image_description}")
            else:
                body_parts.append(f"📸 {user_name} (via {platform}): {image_description}")
            attachment_path = temp_image_path

        if "file" in media_types:
            if body_parts:
                body_parts.append(f"\n📄 {file_summary}")
            else:
                body_parts.append(f"📄 {user_name} (via {platform}): {file_summary}")
            # If no image is being attached, attach the data file instead
            if not attachment_path:
                attachment_path = temp_file_path

        body = "\n".join(body_parts)

        try:
            post_lab_note_comment(exp, body, attachment_path)

            # For data files, also upload as standalone file for easy download
            if "file" in media_types and temp_file_path:
                upload_file_to_experiment(exp, temp_file_path)

            results.append({"sk": sk, "status": "posted", "comment": body})
        except Exception as e:
            # Report error via OpenClaw — do not save locally
            results.append({"sk": sk, "status": "error", "body": body, "error": str(e)})

    # Cleanup temp files
    for path in [temp_image_path, temp_file_path]:
        if path and os.path.exists(path):
            os.unlink(path)

    return {"status": "complete", "results": results}
```

## Error Summary

| Error | Behaviour |
|-------|-----------|
| ffmpeg missing/fails | Stop audio processing, report to user |
| Whisper API fails (3 retries) | Stop audio processing, report to user |
| Image corrupt/unreadable | Skip image, process other media types |
| File unreadable | Skip file, process other media types |
| No SK number found | Reply via OpenClaw asking for SK number |
| SK not in Labstep | Show content, ask user to verify/correct |
| Labstep addComment fails | Report error via OpenClaw with the failed content |
| Labstep addFile fails | Log warning, comment still posted |
| Image too large (>4MB) | Auto-resize with Pillow before upload |
