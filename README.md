# Lab Agents

AI-powered lab data monitoring and quality governance for the Skene Lab (Imperial College / UKDRI).

## What it does

- **Indexes** all lab data across LabStep, GitHub, and RDS without moving it
- **Runs daily quality checks** — missing data, unversioned code, incomplete experiments
- **Posts digests** to Slack so nothing falls through cracks
- **Tracks project dependencies** and flags at-risk deliverables

## Architecture

```
Layer 3: OUTPUT (Slack digest, vault updates, CLI reports)
    ↑
Layer 2: INTELLIGENCE (agents that analyze, cross-reference, alert)
    ↑
Layer 1: DATA CONNECTORS (LabStep API, GitHub API, RDS scanner)
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run daily digest (dry run — prints to stdout)
python -m lab_agents.digest --dry-run

# Run daily digest (posts to Slack)
python -m lab_agents.digest
```

## Components

| Module | Purpose |
|--------|---------|
| `connectors/labstep.py` | Poll LabStep experiments, check completeness |
| `connectors/github.py` | Scan neurogenomics org repos for activity |
| `connectors/rds.py` | Index sequencing directories on RDS |
| `catalog/metadata.py` | SQLite metadata catalog linking all sources |
| `agents/quality.py` | Data governance quality checks |
| `agents/heartbeat.py` | Project activity heartbeat |
| `output/slack.py` | Slack bot for digests and alerts |
| `output/cli.py` | CLI output for testing |
| `digest.py` | Main orchestrator — runs all checks, outputs digest |

## Configuration

All config via environment variables (see `.env.example`).

| Variable | Required | Description |
|----------|----------|-------------|
| `LABSTEP_API_KEY` | Yes | LabStep API key (bot account or personal) |
| `GITHUB_TOKEN` | Yes | GitHub PAT with org:read scope |
| `SLACK_BOT_TOKEN` | No | Slack bot OAuth token |
| `SLACK_CHANNEL` | No | Channel ID for digests (default: `#lab-data-governance`) |
| `RDS_PATH` | No | Path to RDS mount (if accessible) |
| `CATALOG_DB` | No | SQLite path (default: `~/.lab-agents/catalog.db`) |

## Security

- **Read-only** bot accounts for all services
- Raw data NEVER sent to cloud LLMs
- All code in public repo for transparency
- API keys via `.env` with `chmod 600`

## License

MIT
