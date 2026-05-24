# Lab-Agents

A shared AI coding-agent environment for the Imperial College London Neurogenomics lab, with integrated access to Labstep (lab notebook), OneDrive/SharePoint (shared data files), and external scientific AI platforms.

Compatible with any agent that supports the [Agent Skills](https://github.com/anthropics/skills) standard — [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [OpenCode](https://github.com/opencode-ai/opencode), [GitHub Copilot](https://github.com/features/copilot), and others.

> **Tool layer lives in [`neurogenomics/lab-mcp`](https://github.com/neurogenomics/lab-mcp).** This repo holds the *agent* layer — skills, APM config, OpenClaw workspace. The underlying clients and MCP servers (Labstep today, SharePoint / Slack / HPC later) live in `lab-mcp` and are consumed here via `pip install lab-mcp`.

## Repository Structure

```
lab-agents/
├── .github/skills/          # Skills for GitHub Copilot (all 8 skills)
├── lab-skills/skills/       # Skills for Claude Code / OpenCode via APM (all 8 skills)
├── lab-skills/.apm/         # APM context and instructions loaded into every agent session
├── openclaw-workspace/      # OpenClaw agent persona and workspace config (see below)
├── completeness-checker/    # Automated Labstep experiment completeness checker (see below)
├── support/                 # Shared assets (Experiment Summary Word template)
└── docs/planning/           # Feature plans and design specs
```

> **Two skill directories**: `.github/skills/` is where GitHub Copilot looks for skills. `lab-skills/skills/` is the APM-managed package installed by Claude Code and OpenCode. Both contain the same 8 skills — always update both when editing a skill.

## Quick Start

### Prerequisites
- An AI coding agent CLI (e.g. [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [OpenCode](https://github.com/opencode-ai/opencode), [GitHub Copilot](https://github.com/features/copilot))
- [APM](https://github.com/microsoft/apm) installed
- Labstep API key

### Setup

1. Install with APM:
   ```bash
   apm install neurogenomics/lab-agents/lab-skills
   apm compile --target all
   ```
2. Add your Labstep API key to `.env`:
   ```bash
   LABSTEP_API_KEY=your_key_here
   ```
3. Install the shared Labstep client:
   ```bash
   uv tool install "lab-mcp @ git+https://github.com/neurogenomics/lab-mcp.git"
   ```
   This puts four commands on your PATH: `labstep`, `labstep-preflight`, `labstep-mirror`, `labstep-mcp`.
4. Verify credentials:
   ```bash
   labstep-preflight
   ```
   You should see `"stage": "ready"`.
5. Launch your agent from the repo directory and ask what skills are available.

## Skills

Eight skills are available. Each lives in both `.github/skills/<name>/` and `lab-skills/skills/<name>/`.

### 1. labstep

Query, create, and manage experiments, protocols, inventory, and other entities in the Labstep electronic lab notebook.

```
> Show me the last 10 experiments
> What protocols are linked to SK543?
> Search for experiments mentioning "lysis buffer"
> List all resources tagged "antibody"
```

### 2. labstep-sentiment

Summarise key findings and researcher thoughts from Labstep experiments. Export to Excel.

```
> Summarise findings from all experiments in January 2026
> What were the key results from the IVT optimisation experiments?
> Give me a research summary across all lysis buffer experiments
> Export experiment summaries to Excel
```

### 3. nucleic-acid-analysis

Read and extract RNA quantification data (Qubit, TapeStation, qPCR) from experiment folders on OneDrive.

```
> What are the Qubit concentrations for SK443?
> Show me the TapeStation results for SK134
> Compare RNA Qubit yields between SK443 and SK447
> Compare HiScribe vs RiboMax RNA yields across all IVT experiments
> Are there any TapeStation warnings or alerts in SK172?
> What are the TapeStation peak sizes for each sample in SK297?
```

### 4. read-from-sharepoint

Read-only access to lab data files from synced OneDrive (SharePoint) folders. Auto-discovers all shared libraries, or set `DATA_DIR` to your data folder.

```
> List all experiment folders in the scRNA-seq library
> Find the experiment folder for SK457
> What files are in the SK443 folder?
> Show me the Metadata.xlsx for SK297
```

### 5. experiment-summary

Generate a filled-in Experiment Summary `.docx` from Labstep metadata and OneDrive QC data. User-invocable via `/experiment-summary`.

```
> /experiment-summary SK443
> Write up an experiment summary for SK297
> Generate the experiment summary for "IVT kit comparison"
```

### 6. pptx

Generate and modify PowerPoint presentations from data or text.

```
> Create a slide deck summarising the IVT optimisation results
> Add a slide with the Qubit bar chart to my presentation
> Read the contents of results_deck.pptx
```

### 7. lab-note

Process voice notes, photos, and data files delivered via Telegram or Slack, then post them to the correct Labstep experiment with context-aware descriptions (transcription via Fireworks Whisper).

```
> [sends audio recording] Post this note to SK592
> [sends image] Attach this EVOS image to SK550
> [sends data file] Upload this to the right experiment
```

**Dependencies**: `FIREWORKS_API_KEY` in `.env`, ffmpeg, Pillow, pandas.

### 8. edison-platform

Run Edison Scientific tasks via `edison-client` — cited literature synthesis, experimental dataset analysis, novelty checks, and cheminformatics.

```
> Search the literature for CRISPR delivery methods in primary neurons
> Analyse this RNA-seq dataset for differentially expressed pathways
> Check the novelty of our IVT optimisation approach
> What ADMET properties does this molecule have?
```

**Dependencies**: `EDISON_API_KEY` in `.env`, `uv pip install edison-client`.

---

## lab-mcp CLI reference

The [`lab-mcp`](https://github.com/neurogenomics/lab-mcp) package provides one canonical client for all Labstep access. Three interfaces, one codebase.

### CLI

```bash
labstep experiments                       # list ALL (auto-paginates)
labstep experiments --search "lysis buffer"
labstep experiments -n 5                  # cap results
labstep experiment SK592                  # detail by SK number
labstep reagents SK592                    # inventory fields
labstep protocols --search "buffer prep"
labstep resources --search "antibody"
labstep --json experiments                # machine-readable output
```

### MCP server (for agent tool-calling)

```bash
claude mcp add labstep labstep-mcp
```

Or in an MCP JSON config (Claude Desktop, OpenCode, etc.):
```json
{ "mcpServers": { "labstep": { "command": "labstep-mcp" } } }
```

### Python library

```python
from lab_mcp.labstep import LabstepClient

client = LabstepClient()
rows = client.list_experiments(search_query="lysis", count=None)  # all pages
detail = client.find_experiment_by_sk("SK592")
client.add_experiment_comment(detail["id"], "Reviewed 2026-04-24")
```

### Credentials

Resolved in order:
1. `LABSTEP_API_KEY` environment variable
2. `~/.config/lab-mcp/credentials.json` — `{"api_key": "lsp_..."}`
3. `~/Projects/lab-agents/.env` (legacy fallback)

---

## Other Components

### openclaw-workspace/

Configuration for [OpenClaw](https://openclaw.dev) — an agent persona layer that gives the assistant a persistent identity, soul, and heartbeat. The lab's OpenClaw persona is *A Cat Named Glia*. If you're not using OpenClaw, this directory can be ignored.

### completeness-checker/

A Python tool that runs on GitHub Actions every weekday at 09:00 UTC. It fetches all completed Labstep experiments, scores them for documentation completeness (aims, methods, discussion, protocols), and posts a Slack notification for any that are missing required sections.

**Required secrets** (set in GitHub repository settings):
- `LABSTEP_API_KEY`
- `SLACK_WEBHOOK_URL`

To run manually: `python completeness-checker/checker.py` (needs both env vars set).

### support/

Contains `Experiment Summary Template.docx` — the Word template used by the `experiment-summary` skill to generate filled-in experiment write-ups.

---

## Links

- [Neurogenomics Lab GitHub](https://github.com/neurogenomics)
- [Labstep API Docs](https://apidoc.labstep.com)
- [Edison Scientific Docs](https://docs.edisonscientific.com/)
- [Agent Skills Spec](https://github.com/anthropics/skills)
- [APM (Agent Package Manager)](https://github.com/microsoft/apm)
