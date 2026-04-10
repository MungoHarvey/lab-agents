---
name: labstep-sentiment
description: Summarise findings and researcher thoughts from Labstep experiments. Use when the user wants a research summary of experiments, key findings, or researcher observations across experiments.
---

# Labstep Experiment Research Summary Skill

Summarise the key findings and researcher thoughts from experiments stored in Labstep. The primary rich text content lives in the `state` field of the **root sub-experiment**, accessible via the REST API directly (not via labstepPy).

## Authentication

```python
import os, requests, labstep
from labstep.service.config import configService

def get_labstep_apikey() -> str:
    """Get Labstep API key from .env file or environment variable."""
    from dotenv import load_dotenv
    load_dotenv()
    key = os.environ.get("LABSTEP_API_KEY")
    if key:
        return key
    raise RuntimeError("No Labstep API key found. Set LABSTEP_API_KEY in .env")

api_key = get_labstep_apikey()
user = labstep.authenticate(apikey=api_key)
base = configService.getHost()          # https://api.labstep.com
headers = {"apikey": api_key}
```

## How to Get Rich Text Body Per Experiment

The rich text you see in the Labstep UI (aims, objectives, notes) is stored as a **ProseMirror JSON document** in the `state` field of the root sub-experiment. Access it via REST:

```python
import requests

def get_experiment_body(workflow_id, headers, base):
    """Fetch the plain-text body of an experiment workflow."""
    # 1. Get the workflow to find the root experiment ID
    wf = requests.get(f"{base}/api/generic/experiment-workflow/{workflow_id}", headers=headers).json()
    root = wf.get('root_experiment', {})
    root_id = root.get('id') if isinstance(root, dict) else None
    if not root_id:
        return ""

    # 2. Fetch the root experiment
    exp = requests.get(f"{base}/api/generic/experiment/{root_id}", headers=headers).json()
    state = exp.get('state')
    if not state:
        return ""

    # 3. Recursively extract plain text from ProseMirror doc
    return extract_text(state).strip()

def extract_text(node):
    """Recursively extract plain text from a ProseMirror node."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        text = node.get('text', '')
        if text:
            return text
        children = node.get('content', [])
        result = ''.join(extract_text(c) for c in children)
        if node.get('type') in ('paragraph', 'heading', 'blockquote', 'list_item', 'hard_break'):
            result += '\n'
        return result
    if isinstance(node, list):
        return ''.join(extract_text(n) for n in node)
    return ''
```

## What to Collect Per Experiment

Combine the rich text body with structured metadata:

```python
def get_experiment_text(e, headers, base):
    parts = [f"Name: {e.name}"]

    # Rich text body (aims, objectives, conclusions)
    body = get_experiment_body(e.id, headers, base)
    if body:
        parts.append(f"Body:\n{body}")

    # Structured data field values
    try:
        for field in e.getDataFields():
            label = getattr(field, 'label', '') or ''
            value = getattr(field, 'value', '') or ''
            if value:
                parts.append(f"{label}: {value}")
    except Exception:
        pass

    # Protocol names
    try:
        for protocol in e.getProtocols():
            if protocol.name:
                parts.append(f"Protocol: {protocol.name}")
    except Exception:
        pass

    return "\n".join(parts)
```

## Research Summary Approach

For each experiment, produce a concise research summary with two components:

**Findings** — A 1–3 sentence summary of the key scientific results or observations. What was measured, what was observed, what conditions were tested. Focus on data and outcomes, not judgement.

**Researcher Thoughts** — A 1–3 sentence summary capturing the researcher's own interpretation, next steps, or reflections as expressed in the notes. Include any stated plans for follow-up, optimisation ideas, or open questions. If the body text is sparse, note what can be inferred from the experiment name and protocols used.

## Output Format

```python
results = []
for e in experiments:
    text = get_experiment_text(e, headers, base)
    findings, researcher_thoughts = summarise_experiment(text)
    results.append({
        'id': e.id,
        'custom_identifier': getattr(e, 'custom_identifier', ''),
        'name': e.name,
        'author': e.author.get('name', '') if isinstance(e.author, dict) else '',
        'created_at': (e.created_at or '')[:10],
        'findings': findings,
        'researcher_thoughts': researcher_thoughts,
        'body_text': text[:500],
    })
```

## Excel Export

```python
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Research Summary"
headers = ["ID", "Custom ID", "Name", "Author", "Created At", "Findings", "Researcher Thoughts", "Body Text"]
ws.append(headers)

header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
for cell in ws[1]:
    cell.fill = header_fill
    cell.font = Font(bold=True, color="FFFFFF")
    cell.alignment = Alignment(horizontal="center")

for row in results:
    ws.append([row['id'], row['custom_identifier'], row['name'], row['author'],
               row['created_at'], row['findings'], row['researcher_thoughts'],
               row['body_text']])

for col in ws.columns:
    w = max((len(str(c.value)) if c.value else 0) for c in col)
    ws.column_dimensions[col[0].column_letter].width = min(w + 2, 60)

wb.save('research_summary.xlsx')  # saves to working directory
```

## Notes

- The `state` field is only on the **root sub-experiment** (`is_root=True`), not on the workflow object itself
- This requires **2 REST calls per experiment** (workflow → root experiment), so batch carefully
- `state` is `None` for experiments with no body written — fall back to name-based inference
- The ProseMirror doc contains headings, paragraphs, tables, bullet lists — all extracted as plain text
