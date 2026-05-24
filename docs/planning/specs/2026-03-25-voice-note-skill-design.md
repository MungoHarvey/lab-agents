# Voice Note Transcription Skill — Design Spec

## Overview

A new skill (`voice-note`) that receives lab voice notes from Telegram and Slack via OpenClaw, transcribes them using the Fireworks Whisper API, extracts and validates an SK experiment number, uses Labstep experiment context to clean and correct the transcript, and posts the result as a comment on the corresponding Labstep experiment thread.

## Requirements

- **Input**: Raw audio bytes (Opus and other common formats) delivered by OpenClaw, with metadata including the sender's username and source platform (Telegram/Slack).
- **Transcription**: Fireworks Whisper API (`whisper-v3-turbo`).
- **SK extraction**: Multi-strategy — regex, LLM spoken-variant parsing, and validation against recent Labstep experiments. Prompt user if no confident match.
- **Context fetch**: Pull experiment metadata from Labstep (protocol steps, reagent names, gene names, data fields, recent comments) for the matched SK experiment.
- **Clean & correct**: LLM pass that removes filler words/hesitations, fixes domain-specific transcription errors using experiment context, and preserves speaker meaning without summarising.
- **Output**: Post a comment on the Labstep experiment thread. Format: `🎤 {user} (via {platform}): {cleaned transcript}`
- **Auto-post**: Comments are posted automatically — no confirmation gate. The Labstep service account has read-write access.

## Approach

**Two-Pass LLM Pipeline (Approach A)** — Whisper handles speech-to-text, LLM handles domain correction and cleanup. Single Whisper call keeps costs low; the LLM is better suited for context-aware corrections than Whisper's limited prompt parameter.

## Pipeline

### Stage 0: Audio Pre-processing

- Receive raw audio bytes + metadata from OpenClaw
- Detect audio format (Opus, OGG, WAV, MP3, M4A, etc.)
- If not in a Whisper-accepted format (WAV, MP3, FLAC, OGG), transcode using `ffmpeg` to WAV
- Telegram voice notes are typically Opus in OGG containers — these may need container re-wrapping or transcoding

**Dependency**: `ffmpeg` must be available on the system.

### Stage 1: Transcribe

- Send pre-processed audio to Fireworks Whisper API (`whisper-v3-turbo` endpoint)
- API key: `FIREWORKS_API_KEY` from `.env`
- Retry: up to 3 attempts with delays (2s, 5s, 10s) on transient failures
- Output: rough transcript text

### Stage 2: Extract SK Number

Multi-strategy extraction:

1. **Regex**: `\bSK\s?\d{3,}\b` (case-insensitive) — catches clean written forms ("SK543", "SK 543", "sk543")
2. **LLM extraction**: Parse spoken variants — "S K five four three", "experiment five forty three", "the five four three experiment", "S. K. 543"
3. **Labstep validation**: Fetch recent experiments (~20) and compare candidate numbers against actual `custom_identifier` values to confirm the SK number exists

**Multiple SK numbers**: If the voice note references multiple SK experiments, post the same cleaned transcript as a comment on each matched experiment.

**No SK match fallback**: If no confident match after all three strategies:

1. Save the transcript locally to `voice-note-unmatched/` with a timestamped filename
2. Reply to the originating Telegram/Slack thread via OpenClaw: "Could not find an SK number in this voice note. Please reply with the SK number (e.g., SK543)."
3. If the user replies with an SK number, resume the pipeline from Stage 3
4. If no reply within 24 hours, the transcript remains in the local unmatched directory for manual review

### Stage 3: Labstep Context Fetch

Using the confirmed SK number(s):

- Authenticate via `get_labstep_apikey()` (existing pattern)
- Look up experiment: `user.getExperiments(search_query="SK543", count=5)` then filter results by `custom_identifier` match (no direct lookup-by-identifier method exists)
- Pull: protocol body (ProseMirror JSON from `protocol-collection.last_version.state`), reagent/resource names, gene names, data fields, last 10 comments
- **Context budget** (~4000 tokens total, allocated as):
  - Protocol body: first 2000 characters (~500 tokens)
  - Reagent/resource names: all (typically small, ~200 tokens)
  - Data field names and values: all (~300 tokens)
  - Recent comments (last 10): first 500 characters each (~2000 tokens)
  - Gene names: all (~500 tokens)
  - If any section exceeds its allocation, truncate with `[...truncated]`
- This context is used as a reference vocabulary for Stage 4

### Stage 4: LLM Clean & Correct

Single Claude call (inline, using the agent's own context — no separate API key needed) with the rough transcript and Labstep context:

1. **Remove fillers**: "um", "uh", "like", "you know", "sort of", false starts, repeated words
2. **Fix domain terms**: Use experiment context to correct misheard scientific vocabulary (e.g., "see tip seek" → "scTIP-seq", "cube it" → "Qubit", "are I any" → "RNA")
3. **Preserve meaning**: No summarisation, no rewriting of tone. Keep the speaker's intent and phrasing intact — output should read like a tidy lab note, not a raw speech dump

### Stage 5: Post Comment to Labstep

- Call `exp.addComment(body)` on the matched experiment(s)
- Comment format:
  ```
  🎤 {user} (via {platform}): {cleaned transcript}
  ```
- No confirmation gate — comments are posted automatically

## Skill Structure

```
lab-skills/skills/voice-note/
└── SKILL.md
```

SKILL.md frontmatter:

```yaml
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
```

Documentation-driven skill following the same pattern as `labstep`, `nucleic-acid-analysis`, etc. Claude executes inline Python when triggered.

## Configuration

| Key | Location | Purpose |
|-----|----------|---------|
| `FIREWORKS_API_KEY` | `.env` | Fireworks Whisper API authentication |
| `LABSTEP_API_KEY` | `.env` | Labstep API authentication (existing) |

## Dependencies

- **labstep skill**: For experiment lookup, context fetch, and comment posting
- **OpenClaw**: Delivers raw audio bytes + sender metadata from Telegram/Slack
- **Fireworks API**: Whisper transcription service
- **ffmpeg**: Audio format detection and transcoding
- **python-dotenv**: API key loading (existing pattern)

## Error Handling

- **Transcription failure**: Retry up to 3 times (2s, 5s, 10s delays). If all fail, report error to user, do not post to Labstep.
- **No SK number found**: Prompt user to manually assign
- **SK number not in Labstep**: Show transcript and ask user to verify/correct the SK number
- **Labstep API failure**: Report error, save transcript locally as fallback
- **Audio format unsupported**: Attempt ffmpeg transcode; if that fails, report to user with the detected format
- **Audio too long**: No hard limit, but note that very long recordings (>10 min) will increase Whisper API costs

## Security

- `FIREWORKS_API_KEY` stored in `.env` (gitignored), never hardcoded
- No audio data persisted after processing unless explicitly requested

## Pre-Implementation: Update Access Policies

The Labstep service account has read-write permissions, but several project files still describe it as read-only. These must be updated:

- `CLAUDE.md` — Update "Labstep Credentials" section: change "Workspace Viewer role" to reflect write access; remove "confirm write" gate language
- `lab-skills/.apm/instructions/security-policies.instructions.md` — Update to reflect write-capable account
- `lab-skills/skills/labstep/SKILL.md` — Remove "read-only service account" restriction

## Post-Implementation

- Update `CLAUDE.md` to add voice-note as skill #7 in the Available Skills section
- Update `security-policies.instructions.md` to document the voice-note skill's auto-post behaviour
