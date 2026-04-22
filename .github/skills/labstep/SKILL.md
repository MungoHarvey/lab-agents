---
name: labstep
description: Interact with the Labstep electronic lab notebook via the shared lab-mcp client. Use when the user wants to create, read, or manage experiments, protocols, resources, inventory, or other Labstep entities.
---

# Labstep Skill

This is the AgentStore copy of the Labstep skill. All Labstep access goes through [`neurogenomics/lab-mcp`](https://github.com/neurogenomics/lab-mcp) — one canonical client shared across the lab, exposed as CLI, MCP server, and Python library.

## Install

```bash
pip install "lab-mcp @ git+https://github.com/neurogenomics/lab-mcp.git"
```

Credentials resolve from `LABSTEP_API_KEY` env var, `~/.config/lab-mcp/credentials.json`, or `~/Projects/lab-agents/.env` (legacy fallback).

Verify with `labstep-preflight` — exit `0` / `"stage": "ready"` means ready.

## Three interfaces, one client

### CLI (fast, for scripts and terminal users)

```bash
labstep experiments                       # list ALL (auto-paginates)
labstep experiments --search "lysis buffer"
labstep experiment SK592                  # detail by SK number
labstep reagents SK592
labstep protocols --search "buffer prep"
labstep resources --search "antibody"
labstep --json experiments                # machine-readable
```

### MCP server (for Claude Code / OpenCode / Desktop agents)

```bash
claude mcp add labstep labstep-mcp
```

Tools: session (`whoami`, workspaces), experiments (list / get / find-by-SK / create / edit / complete / lock / comment / tag / attach-protocol / add-file), protocols (list / get / create / edit / new-version), resources (list / get). See [`lab_mcp/labstep/mcp_server.py`](https://github.com/neurogenomics/lab-mcp/blob/main/src/lab_mcp/labstep/mcp_server.py) for the full surface.

### Python library

```python
from lab_mcp.labstep import LabstepClient

client = LabstepClient()
client.whoami()
rows = client.list_experiments(search_query="lysis", count=None)  # count=None fetches ALL pages
detail = client.find_experiment_by_sk("SK592")
client.add_experiment_comment(detail["id"], "Reviewed 2026-04-22")
```

## Read-only policy

By default, agents should describe a write before executing and confirm with the user. For automated pipelines (e.g. the `lab-note` skill), writes are allowed without interactive confirmation. The MCP server exposes every write operation labstepPy supports — use the minimum-privilege tool for the task.

## SK numbers

Experiments have identifiers like **SK592** in `custom_identifier`. The lab refers to experiments by SK number, not numeric ID. `client.find_experiment_by_sk("SK592")` and `labstep experiment SK592` resolve them directly.

## URL format

Canonical: `https://app.labstep.com/experiment-workflow/{id}`. `lab_mcp.labstep.bodies.experiment_url()` emits the right shape.

## Why the shared client

Before `lab-mcp`, this repo had three separate Labstep implementations (bulk mirror, CLI, preflight) plus `~/.claude/mcp-servers/labstep/` and `bulk-tipseq-summary/scripts/labstep-query.py`. Each had bugs the others didn't — silent pagination truncation, disabled TLS verification, wrong URL format. `lab-mcp` consolidates to one client with fixes landing once. See the [migration notes](https://github.com/neurogenomics/lab-mcp/blob/main/docs/migration.md).
