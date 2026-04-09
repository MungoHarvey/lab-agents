---
description: Python coding standards for lab data scripts
applyTo: "**/*.py"
author: Jay Moore
version: 1.0.0
---

# Python Lab Code Standards

## Authentication Pattern

Use `get_labstep_apikey()` for Labstep authentication:
- Loads `.env` via `python-dotenv`
- Reads `LABSTEP_API_KEY` from environment

## OneDrive Data Access

- Use `find_onedrive_base()` to auto-detect OneDrive root per OS
- Libraries are auto-discovered from all subdirectories under the OneDrive base
- Alternatively, set `DATA_DIR` env var to point directly to your shared data folder
- Always use retry logic for cloud-synced files (up to 3 retries with 2s, 5s, 10s delays)

## Metadata Handling

- Use `find_column()` with fuzzy matching for Metadata.xlsx columns (handles Unicode µ vs u)
- Handle sentinel values in Qubit/TapeStation columns: TL, Too low, /, -, SK refs, dual-peak "X & Y"
- Three TapeStation assay schemas: HSRNA (pg/µl + RINe), HSD5000 (pg/µl), gDNA (ng/µl + DIN)
