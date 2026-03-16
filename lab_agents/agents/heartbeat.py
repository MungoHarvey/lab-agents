"""Project activity heartbeat — summarizes activity across all sources.

Generates weekly project summaries by cross-referencing LabStep experiments,
GitHub commits, and RDS data. Classifies projects as ACTIVE, QUIET, or ALERT.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from lab_agents.config import Config

logger = logging.getLogger(__name__)


@dataclass
class ProjectHeartbeat:
    """Activity summary for a single project."""

    name: str
    status: str  # "active", "quiet", "alert"
    github_commits: int = 0
    labstep_entries: int = 0
    rds_changes: int = 0
    days_since_activity: int = 0
    contributors: list[str] = field(default_factory=list)
    details: str = ""


def generate_heartbeat(
    github_summary=None,
    labstep_experiments: list | None = None,
    rds_result=None,
) -> list[ProjectHeartbeat]:
    """Generate project heartbeat from all data sources.

    Infers project activity from:
    - GitHub commit frequency and contributor list
    - LabStep experiment entries
    - RDS file modification dates
    """
    projects: dict[str, ProjectHeartbeat] = {}

    # GitHub activity
    if github_summary:
        for repo in github_summary.active_repos:
            name = repo.name
            if name not in projects:
                projects[name] = ProjectHeartbeat(name=name, status="active")

            projects[name].github_commits = repo.recent_commits
            projects[name].contributors = repo.contributors_30d

            details_parts = []
            if repo.recent_commits:
                details_parts.append(f"{repo.recent_commits} commits")
            if repo.contributors_30d:
                details_parts.append(
                    f"by {', '.join(repo.contributors_30d[:3])}"
                )
            projects[name].details = ", ".join(details_parts)

        for repo in github_summary.quiet_repos:
            name = repo.name
            if name not in projects:
                projects[name] = ProjectHeartbeat(name=name, status="quiet")
            projects[name].status = "quiet"
            projects[name].days_since_activity = repo.days_since_push or 0
            projects[name].details = (
                f"No activity in {repo.days_since_push or '?'} days"
            )

    # LabStep activity
    if labstep_experiments:
        for exp in labstep_experiments:
            # Try to match experiment to project by tags or name
            project_name = _guess_project(exp.name, getattr(exp, "tags", []))
            if project_name and project_name in projects:
                projects[project_name].labstep_entries += 1
            elif project_name:
                projects[project_name] = ProjectHeartbeat(
                    name=project_name,
                    status="active",
                    labstep_entries=1,
                    details=f"LabStep: {exp.name}",
                )

    # Classify status
    quiet_threshold = Config.QUIET_PROJECT_THRESHOLD
    for project in projects.values():
        total_activity = (
            project.github_commits
            + project.labstep_entries
            + project.rds_changes
        )
        if total_activity == 0 and project.days_since_activity > quiet_threshold:
            project.status = "quiet"
        elif total_activity > 0:
            project.status = "active"

    # Sort: active first, then quiet, then alert
    status_order = {"active": 0, "alert": 1, "quiet": 2}
    sorted_projects = sorted(
        projects.values(),
        key=lambda p: (status_order.get(p.status, 9), -p.github_commits),
    )

    return sorted_projects


def _guess_project(experiment_name: str, tags: list[str]) -> str | None:
    """Guess which project an experiment belongs to based on name/tags.

    This is a simple heuristic. Can be improved by maintaining a mapping
    in the metadata catalog.
    """
    name_lower = experiment_name.lower()

    # Known project keyword mapping
    KEYWORD_MAP = {
        "tip-seq": "TIP-seq",
        "tipseq": "TIP-seq",
        "sctip": "scTIP-seq",
        "fans": "FANS-enrichment",
        "cut&tag": "CUT&Tag",
        "cutnrun": "CUT&Run",
        "dynatag": "DynaTag",
        "rare disease": "Rare-Disease",
        "hpo": "Rare-Disease",
        "power analysis": "Power-Analysis",
        "borzoi": "Borzoi-ChIP",
        "alphagenome": "AlphaGenome-ChIP",
        "idr": "IDRpeaks",
    }

    for keyword, project in KEYWORD_MAP.items():
        if keyword in name_lower:
            return project

    # Check tags
    for tag in tags:
        tag_lower = tag.lower()
        for keyword, project in KEYWORD_MAP.items():
            if keyword in tag_lower:
                return project

    return None
