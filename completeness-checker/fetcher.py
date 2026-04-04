"""Fetch experiments from Labstep API and filter to completed ones."""

import requests


def get_experiment_state(workflow_id, base_url, headers):
    """Fetch the ProseMirror state dict for an experiment workflow."""
    wf = requests.get(f"{base_url}/api/generic/experiment-workflow/{workflow_id}", headers=headers).json()
    root = wf.get("root_experiment", {})
    root_id = root.get("id") if isinstance(root, dict) else None
    if not root_id:
        return None
    exp = requests.get(f"{base_url}/api/generic/experiment/{root_id}", headers=headers).json()
    return exp.get("state")


def fetch_completed_experiments(user):
    """Fetch all experiments and return metadata dicts for completed ones."""
    experiments = user.getExperiments()
    results = []

    for exp in experiments:
        ended_at = getattr(exp, "ended_at", None)
        if not ended_at:
            continue

        eid = getattr(exp, "custom_identifier", "") or str(exp.id)
        name = getattr(exp, "name", "") or ""
        created = (getattr(exp, "created_at", "") or "")[:10]

        author_obj = getattr(exp, "author", None)
        if isinstance(author_obj, dict):
            author = author_obj.get("name", "")
        elif author_obj and hasattr(author_obj, "name"):
            author = author_obj.name
        else:
            author = ""

        try:
            protocols = exp.getProtocols()
            protocol_count = len(protocols)
        except Exception:
            protocol_count = 0

        results.append({
            "id": eid,
            "workflow_id": exp.id,
            "name": name,
            "author": author,
            "date": created,
            "protocol_count": protocol_count,
        })

    return results
