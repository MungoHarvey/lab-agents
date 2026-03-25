---
description: Security and access control policies for lab data systems
applyTo: "**/*"
author: Jay Moore
version: 1.0.0
---

# Security & Access Control

## Labstep (Read-Write)

The Labstep service account (`lab-agent-readonly@imperial.ac.uk`) has read-write access.

- Automated pipelines (e.g., lab-note skill) may post comments without manual confirmation
- Manual interactive write operations (creating experiments, editing entries) should describe the change before executing
- API token is monitored

