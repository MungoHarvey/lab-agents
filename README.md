# Lab-Agents

A shared AI coding-agent environment for the Imperial College London Neurogenomics lab, with integrated access to Labstep (lab notebook), OneDrive/SharePoint (shared data files), and local data analysis tools.

Compatible with any agent that supports the [Agent Skills](https://github.com/anthropics/skills) standard — [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [OpenCode](https://github.com/opencode-ai/opencode), [GitHub Copilot](https://github.com/features/copilot), and others.

> **Tool layer lives in [`neurogenomics/lab-mcp`](https://github.com/neurogenomics/lab-mcp).** This repo holds the *agent* layer — skills, APM config, OpenClaw workspace. The underlying clients and MCP servers (Labstep today, SharePoint / Slack / HPC later) live in `lab-mcp` and are consumed here via `pip install lab-mcp`.

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

## Skills

### 1. labstep

Query experiments, protocols, inventory, and other entities from the Labstep electronic lab notebook (read-only).

```
> Show me the last 10 experiments
> What protocols are linked to SK543?
> Search for experiments mentioning "lysis buffer"
> List all resources tagged "antibody"
```

### 2. labstep-sentiment

Summarise key findings and researcher thoughts from Labstep experiments.

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

## Links

- [Neurogenomics Lab GitHub](https://github.com/neurogenomics)
- [Labstep API Docs](https://apidoc.labstep.com)
- [Agent Skills Spec](https://github.com/anthropics/skills)
- [APM (Agent Package Manager)](https://github.com/microsoft/apm)
