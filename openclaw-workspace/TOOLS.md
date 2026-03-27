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

The response JSON has a `text` field with the transcription. After transcribing, follow the **full pipeline** — do NOT post the raw transcript:

### Step 1: Separate command from content
The transcript often starts with an instruction to you (e.g., "OK, add a voice note to SK599."). Strip this — only the lab note content should be posted. If the entire transcript is just a command with no content, reply asking for the actual note.

### Step 2: Extract SK number
Look for an SK number (e.g. SK543, SK599) in the transcript using regex `SK\s?\d{3,}`. If not found, reply with the transcription and ask which experiment to add it to.

### Step 3: Fetch experiment context from Labstep
Before posting, fetch the experiment's metadata for domain vocabulary. This is critical for cleaning the transcript:

```bash
python3 -c "
import labstep, os, json
from dotenv import load_dotenv
load_dotenv()
user = labstep.authenticate(apikey=os.environ['LABSTEP_API_KEY'])
sk = 'SK___'  # Replace with the SK number from Step 2
results = user.getExperiments(search_query=sk, count=5)
exp = next((r for r in results if r.custom_identifier and r.custom_identifier.upper() == sk.upper()), None)
if exp:
    print('Name:', exp.name)
    try:
        protocols = exp.getProtocols()
        if protocols:
            state = getattr(protocols[0], 'state', None)
            body = json.dumps(state)[:1000] if isinstance(state, dict) else str(getattr(protocols[0], 'body', ''))[:1000]
            print('Protocol:', body)
    except: pass
    try:
        inv = exp.getInventoryFields() if hasattr(exp, 'getInventoryFields') else []
        print('Reagents:', [f.name for f in inv][:20])
    except: pass
    try:
        comments = exp.getComments()
        print('Recent comments:', [str(getattr(c, 'body', ''))[:200] for c in (comments[:5] if comments else [])])
    except: pass
"
```

### Step 4: Clean and contextualise the transcript
Using the experiment context from Step 3, rewrite the transcript as a tidy lab note:
- Remove filler words ("um", "uh", "like", false starts, repeated words)
- Fix domain terms using the experiment context (e.g., "see tip seek" → "scTIP-seq", "cube it" → "Qubit")
- **Preserve the speaker's meaning** — do NOT summarise or add information
- Output should read like a clean, professional lab note entry

### Step 5: Post to Labstep
Post the **cleaned** transcript (not the raw one) as a comment:

Format: `🎤 {user} (via {platform}): {cleaned transcript}`

If posting fails, reply with the error and the content that failed to post.

### Step 6: Reply with link
After posting, reply with a hyperlink to the experiment thread so the user can review:

Format: `Done — voice note added to **{SK}**: https://app.labstep.com/experiment-workflow/{experiment_id}`

The `experiment_id` is available as `exp.id` from the Labstep experiment object fetched in Step 3.

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
