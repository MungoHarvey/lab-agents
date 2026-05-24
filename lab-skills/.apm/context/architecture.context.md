---
description: Lab-agents project architecture and data pipeline
author: Jay Moore
version: 1.0.0
---

# Lab-Agents Architecture

## Overview

Shared agent environment for the Imperial Lab team. Agents interact with:
- **Labstep** — Electronic lab notebook (read-only API access)
- **OneDrive (SharePoint)** — Shared data files via locally-synced folders (strictly read-only)

## Skills

Both `.github/skills/` (GitHub Copilot) and `lab-skills/skills/` (APM / Claude Code / OpenCode) contain the same 8 skills. Always update both when editing a skill.

| Skill | Purpose |
|-------|---------|
| `labstep` | Fetch/query/write Labstep experiments, protocols, inventory |
| `labstep-sentiment` | Summarise key findings from lab notes; export to Excel |
| `pptx` | Generate/modify PowerPoint presentations |
| `read-from-sharepoint` | Read-only access to OneDrive synced folders |
| `nucleic-acid-analysis` | RNA quantification data (Qubit, TapeStation, qPCR) |
| `experiment-summary` | Generate Experiment Summary .docx from lab data |
| `lab-note` | Post voice notes / photos / files to Labstep via Telegram/Slack |
| `edison-platform` | Literature synthesis, dataset analysis, novelty checks, cheminformatics |

## Data Pipeline

1. Read experiment data from OneDrive synced folders (`read-from-sharepoint`)
2. Query analysis skills against OneDrive data (`nucleic-acid-analysis`)
3. Generate reports/presentations (`pptx`, `experiment-summary`)
4. All output saved locally — no write-back to OneDrive or Labstep without explicit confirmation

## Key Technical Details

- Protocol body text: `protocol-collection.last_version.state` (ProseMirror JSON)
- scRNA-seq (07) Metadata lacks RNA Qubit columns
- scTIP-seq (03) Metadata has full RNA QC
