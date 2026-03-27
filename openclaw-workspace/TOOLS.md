# TOOLS.md - Local Notes

## HARD RULES

- **NEVER install software.** No pip install, apt install, npm install, or any other package installation. Everything you need is already here.
- **NEVER use local whisper.** Always use the Fireworks API for transcription.

## Voice / Audio Transcription

When you receive a voice message or audio file, transcribe it using the Fireworks Whisper API:

```bash
# Find the most recent audio file
AUDIO_FILE=$(ls -t ~/.openclaw/media/inbound/*.oga ~/.openclaw/media/inbound/*.ogg ~/.openclaw/media/inbound/*.mp3 2>/dev/null | head -1)

# Transcribe with Fireworks Whisper API
curl -s -X POST "https://api.fireworks.ai/inference/v1/audio/transcriptions" \
  -H "Authorization: Bearer $FIREWORKS_API_KEY" \
  -F "file=@$AUDIO_FILE" \
  -F "model=whisper-v3"
```

The response JSON has a `text` field with the transcription. After transcribing:
1. Look for an SK number (e.g. SK543) in the transcript
2. If found, post to the Labstep experiment as a comment
3. If not found, reply with the transcription and ask which experiment to add it to

## Reading Files

To read Excel files (.xlsx), use pandas:
```bash
python3 -c "import pandas as pd; df = pd.read_excel('/path/to/file.xlsx'); print(df.to_string())"
```

To read CSV files:
```bash
python3 -c "import pandas as pd; df = pd.read_csv('/path/to/file.csv'); print(df.to_string())"
```

Uploaded files from Telegram are saved in `~/.openclaw/media/inbound/`. Check there for recent uploads.

**When the user sends a file, immediately read it with pandas — don't ask permission or say you can't.**
