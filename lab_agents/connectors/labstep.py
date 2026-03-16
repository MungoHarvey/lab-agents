"""LabStep connector — poll experiments, check completeness.

Uses the labstepPy SDK to interact with LabStep's API.
Docs: https://github.com/Labstep/labstepPy
API examples: https://github.com/Labstep/labstep-api-examples
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from lab_agents.config import Config

logger = logging.getLogger(__name__)


@dataclass
class Experiment:
    """Parsed experiment from LabStep."""

    id: int
    name: str
    author: str
    created_at: datetime
    status: str  # "active", "completed", etc.
    has_data: bool = False
    has_protocol: bool = False
    has_results: bool = False
    labstep_url: str = ""
    tags: list[str] = field(default_factory=list)


class LabStepConnector:
    """Connects to LabStep API and extracts experiment metadata."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or Config.LABSTEP_API_KEY
        self._user = None

    def connect(self) -> bool:
        """Authenticate with LabStep. Returns True on success."""
        try:
            import labstep

            self._user = labstep.authenticate(self.api_key)
            logger.info("Connected to LabStep as %s", self._user.name)
            return True
        except Exception as e:
            logger.error("Failed to connect to LabStep: %s", e)
            return False

    def get_recent_experiments(self, days: int = 30) -> list[Experiment]:
        """Get experiments created in the last N days."""
        if not self._user:
            if not self.connect():
                return []

        try:
            experiments = self._user.getExperiments(count=100)
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            results = []
            for exp in experiments:
                created = _parse_datetime(exp.created_at)
                if created and created >= cutoff:
                    results.append(
                        Experiment(
                            id=exp.id,
                            name=exp.name or f"Experiment {exp.id}",
                            author=_get_author_name(exp),
                            created_at=created,
                            status=getattr(exp, "status", "active"),
                            has_data=_has_data_files(exp),
                            has_protocol=_has_protocol(exp),
                            has_results=_has_results(exp),
                            labstep_url=f"https://app.labstep.com/experiment/{exp.id}",
                            tags=_get_tags(exp),
                        )
                    )

            logger.info("Found %d experiments in last %d days", len(results), days)
            return results

        except Exception as e:
            logger.error("Failed to fetch experiments: %s", e)
            return []

    def get_experiments_missing_data(self, threshold_days: int = 7) -> list[Experiment]:
        """Find experiments older than threshold_days that lack raw data."""
        experiments = self.get_recent_experiments(days=90)
        cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)
        return [
            exp
            for exp in experiments
            if not exp.has_data and exp.created_at < cutoff
        ]

    def get_incomplete_experiments(self) -> list[Experiment]:
        """Find experiments missing protocol, data, or results."""
        experiments = self.get_recent_experiments(days=90)
        return [
            exp
            for exp in experiments
            if not (exp.has_data and exp.has_protocol and exp.has_results)
        ]


def _parse_datetime(value) -> datetime | None:
    """Parse LabStep datetime string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _get_author_name(exp) -> str:
    """Extract author name from experiment."""
    try:
        if hasattr(exp, "author") and exp.author:
            return getattr(exp.author, "name", str(exp.author))
    except Exception:
        pass
    return "Unknown"


def _has_data_files(exp) -> bool:
    """Check if experiment has attached data files."""
    try:
        files = exp.getFiles() if hasattr(exp, "getFiles") else []
        return len(files) > 0
    except Exception:
        return False


def _has_protocol(exp) -> bool:
    """Check if experiment references a protocol."""
    try:
        protocols = exp.getProtocols() if hasattr(exp, "getProtocols") else []
        return len(protocols) > 0
    except Exception:
        return False


def _has_results(exp) -> bool:
    """Check if experiment has results/completion markers."""
    try:
        # Check for tables, comments, or completion status
        tables = exp.getTables() if hasattr(exp, "getTables") else []
        if tables:
            return True
        return getattr(exp, "status", "") == "completed"
    except Exception:
        return False


def _get_tags(exp) -> list[str]:
    """Extract tags from experiment."""
    try:
        tags = exp.getTags() if hasattr(exp, "getTags") else []
        return [getattr(t, "name", str(t)) for t in tags]
    except Exception:
        return []
