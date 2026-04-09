---
description: Lab-agents project overview, available skills, team workflows, and credentials
applyTo: "**/*"
author: Jay Moore
version: 1.0.0
---

# Lab-Agents Team Environment

## Overview

This is a shared agent environment for the Imperial Lab team. Agents have access to:
- **Labstep**: Lab notebook (read-write access)
- **OneDrive (SharePoint)**: Shared data files via synced OneDrive folders (strictly read-only)

## Available Skills

All skills are located in `.claude/skills/` and are auto-triggered based on context. Refer to each skill's `SKILL.md` for detailed usage:

### 1. **labstep**
- **Purpose**: Fetch and query Labstep experiments, protocols, and inventory
- **Trigger**: Questions about experiments, protocols, or lab records
- **Access**: Read-write (see Labstep Credentials below)

### 2. **labstep-sentiment**
- **Purpose**: Summarise key findings and researcher thoughts from lab notes
- **Trigger**: Questions about trends or patterns in experiment notes
- **Dependency**: Requires `labstep` skill access

### 3. **pptx**
- **Purpose**: Generate and modify PowerPoint presentations
- **Trigger**: Requests to create slides, generate reports, or present data
- **Scripts**: Includes `/scripts` subdirectory with helper utilities

### 4. **read-from-sharepoint**
- **Purpose**: Read-only access to lab data from synced OneDrive (SharePoint) folders
- **Trigger**: Any skill or task needing experiment data files
- **Data locations**: auto-detected per OS via `find_onedrive_base()`, or set `DATA_DIR` env var to point to your shared folder
- **Retry**: Files may need time to sync from cloud — retries up to 3 times with delays (2s, 5s, 10s)

### 5. **nucleic-acid-analysis**
- **Purpose**: Read and extract RNA quantification data (Qubit, TapeStation, qPCR)
- **Trigger**: Questions about RNA-seq datasets, QC metrics
- **Data source**: OneDrive folders (via `read-from-sharepoint`)

### 6. **experiment-summary**
- **Purpose**: Generate filled-in Experiment Summary .docx from lab data
- **Trigger**: `/experiment-summary` or "write up an experiment"
- **Data sources**: Labstep (metadata) + OneDrive (QC files)

### 7. **lab-note**
- **Purpose**: Process voice notes, photos, and data files from Telegram/Slack — post to Labstep experiments with context-aware descriptions
- **Trigger**: OpenClaw delivers audio, image, or file bytes; or user asks to post a note/photo/file to an experiment
- **Dependencies**: Fireworks Whisper API, Labstep, ffmpeg, Pillow, pandas

## Labstep Credentials

The `labstep` skill uses a service account with read-write access:
- **Account**: `lab-agent-readonly@imperial.ac.uk`
- **Permission level**: Workspace **Editor** role
- **API key location**: `.env` file (`LABSTEP_API_KEY`)

## Team Workflows

### Data Pipeline
1. Read experiment data directly from OneDrive synced folders (via `read-from-sharepoint` skill)
2. Query `nucleic-acid-analysis` or other analysis skills against OneDrive data
3. Use `pptx` skill to generate reports/presentations
4. All output files are saved locally in the working directory — Labstep writes (e.g., comments) happen automatically for automated pipelines; OneDrive is strictly read-only

### Lab Queries
1. Use `labstep` skill to fetch experiments/protocols
2. Use `labstep-sentiment` for trend analysis
3. Results can be read or written to (e.g., comments posted by automated skills)

## Contacting Admin

If you encounter issues with Labstep or OneDrive access:
- Check `.env` for valid `LABSTEP_API_KEY`
- Verify OneDrive sync status (System Settings > OneDrive)
- Report access errors to the lab tech lead

## Questions?

Each skill's `SKILL.md` file contains detailed documentation and examples.
