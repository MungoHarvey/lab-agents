---
name: labstep
description: Interact with the Labstep electronic lab notebook via the shared lab-mcp client. Use when the user wants to create, read, or manage experiments, protocols, resources, inventory, or other Labstep entities.
trigger: labstep, experiment, protocol, inventory, reagent, SK number, custom identifier
---

# Labstep Skill

All Labstep access goes through [`neurogenomics/lab-mcp`](https://github.com/neurogenomics/lab-mcp) — one canonical Python client shared across the lab. You consume it as a CLI for scripting, an MCP server for agent tool-calls, or a library from Python.

## Install

```bash
pip install "lab-mcp @ git+https://github.com/neurogenomics/lab-mcp.git"
```

Credentials resolve from any of (in order):

1. `LABSTEP_API_KEY` environment variable
2. `~/.config/lab-mcp/credentials.json` → `{"api_key": "lsp_..."}`
3. `~/Projects/lab-agents/.env` (legacy fallback)

Verify with:

```bash
labstep-preflight
```

Exit code `0` and `"stage": "ready"` means you're good to go.

## CLI (preferred for agents doing read-only lookups)

Execute immediately — these are read-only.

```bash
# List ALL experiments (auto-paginates; no silent truncation)
labstep experiments

# Search
labstep experiments --search "lysis buffer"

# Cap results
labstep experiments -n 20

# Detail by SK number or numeric ID
labstep experiment SK592
labstep experiment 12345

# Reagents attached to an experiment
labstep reagents SK592

# Protocols / resources
labstep protocols --search "buffer prep"
labstep resources --search "antibody"

# Machine-readable output
labstep --json experiments
```

## MCP server (for agent tool-calling)

Register once:

```bash
claude mcp add labstep labstep-mcp
```

Or in an MCP JSON config (Claude Desktop, OpenCode, etc.):

```json
{ "mcpServers": { "labstep": { "command": "labstep-mcp" } } }
```

Exposed tools (≈ 23): session (`whoami`, workspaces), experiments (list / get / find-by-SK / list-reagents / create / edit / complete / lock / comment / tag / attach-protocol / add-file / list-files), protocols (list / get / create / edit / new-version), resources (list / get).

## Python library

```python
from lab_mcp.labstep import LabstepClient

client = LabstepClient()
rows = client.list_experiments(search_query="lysis", count=None)  # all
detail = client.find_experiment_by_sk("SK592")
```

## SK Numbers (custom identifiers)

Experiments carry identifiers like **SK592**, **SK591**, etc. (`custom_identifier`).

- Always display SK numbers when listing experiments.
- When the user says "SK592", use `labstep experiment SK592` or `client.find_experiment_by_sk("SK592")` — don't try to look it up by numeric ID.
- SK numbers are the lab's primary reference — use them in conversation.

## URL format

Canonical URL is `https://app.labstep.com/experiment-workflow/{experiment_id}`. The older `/experiment/{id}` form returns 404. `lab_mcp.labstep.bodies.experiment_url()` returns the right shape.

## Write operations

By default agents should confirm with the user before invoking write tools (`labstep_create_experiment`, `labstep_edit_experiment`, `labstep_add_experiment_comment`, `labstep_add_experiment_tag`, `labstep_attach_protocol`, `labstep_add_experiment_file`, protocol create/edit, etc.). For automated pipelines (e.g. the `lab-note` skill) writes are allowed without interactive confirmation.

## When to execute immediately

Run the CLI / MCP tool immediately, without asking permission, when:

- User asks about experiments, protocols, or lab inventory.
- User references an experiment by SK identifier (e.g. "SK592").
- User asks about a specific protocol by name.
- User asks "what did I do today/this week in the lab".

**Never make up experiment names or IDs.** Always fetch real data.

## Why this used to be three different scripts

This repo previously contained `labstep_mirror.py`, `lab-skills/scripts/labstep-query.py`, and `lab-skills/scripts/check_labstep.py`. Each had bugs the others didn't (silent pagination truncation, disabled TLS verification, wrong URL format). All three are replaced by `lab-mcp`, which has one test-covered client that every entry point shares. See the [migration notes](https://github.com/neurogenomics/lab-mcp/blob/main/docs/migration.md) for details.
