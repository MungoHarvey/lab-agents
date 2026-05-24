---
name: edison-platform
description: Run Edison Scientific tasks via the edison-client Python SDK — literature synthesis (LITERATURE / LITERATURE_HIGH), experimental dataset analysis (ANALYSIS), novelty checks (PRECEDENT), and cheminformatics (MOLECULES). Use when the user needs a cited scientific answer, wants to upload data for Edison to analyse, or asks about EdisonClient / JobNames / run_tasks_until_done / PaperQA / Kosmos.
trigger: edison, EdisonClient, JobNames, run_tasks_until_done, edison-client, LITERATURE, ANALYSIS, PRECEDENT, MOLECULES, Kosmos, PaperQA, FutureHouse, EDISON_API_KEY
---

# Edison Platform

Python client for Edison Scientific. Dispatches scientific agents: literature synthesis, dataset analysis, novelty checks, cheminformatics.

## Setup

`EDISON_API_KEY` lives in the user's shell profile (e.g. `~/.zshrc`, `~/.bashrc`) or a `.env` loaded at runtime. Read from env — never hardcode.

```bash
uv pip install edison-client
```

## Minimal usage

```python
import os
from edison_client import EdisonClient, JobNames

client = EdisonClient(api_key=os.environ["EDISON_API_KEY"])
resp = client.run_tasks_until_done({
    "name": JobNames.LITERATURE,
    "query": "Which neglected diseases had a treatment developed by AI?",
})
```

## Agents at a glance

| JobName | Purpose |
|---|---|
| `LITERATURE` | Cited Q&A over 175M+ papers/trials/patents |
| `LITERATURE_HIGH` | High-reasoning mode (slower, SOTA) |
| `ANALYSIS` | Interprets uploaded experimental datasets |
| `PRECEDENT` | Novelty / "has anyone done this" check |
| `MOLECULES` | Cheminformatics: ADMET, retrosynthesis, ChEMBL |

Kosmos (autonomous end-to-end research) is platform-only, not API-exposed.

## Progressive disclosure — load on demand

Read only the file you need:

- **Tasks API** (methods, batching, continuation, async): [tasks.md](tasks.md)
- **File management** (upload, artifact retrieval for ANALYSIS): [files.md](files.md)
- **Query-writing guidance** (Kosmos-style best practices): [query-guide.md](query-guide.md)
- **Gotchas & troubleshooting**: [gotchas.md](gotchas.md)

## Docs

- Client: https://docs.edisonscientific.com/edison-client/quickstart
- Agents: https://docs.edisonscientific.com/agents
- Sitemap: https://docs.edisonscientific.com/sitemap.md
