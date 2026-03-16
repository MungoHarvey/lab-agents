"""Configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


class Config:
    """All configuration from environment variables with sensible defaults."""

    # API keys
    LABSTEP_API_KEY: str = os.getenv("LABSTEP_API_KEY", "")
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL: str = os.getenv("SLACK_CHANNEL", "")

    # Paths
    RDS_PATH: str = os.getenv("RDS_PATH", "")
    CATALOG_DB: str = os.getenv(
        "CATALOG_DB", str(Path.home() / ".lab-agents" / "catalog.db")
    )

    # GitHub
    GITHUB_ORG: str = os.getenv("GITHUB_ORG", "neurogenomics")

    # Thresholds (days)
    MISSING_DATA_THRESHOLD: int = int(os.getenv("MISSING_DATA_THRESHOLD", "7"))
    STALE_ANALYSIS_THRESHOLD: int = int(os.getenv("STALE_ANALYSIS_THRESHOLD", "90"))
    STALE_WRITEUP_THRESHOLD: int = int(os.getenv("STALE_WRITEUP_THRESHOLD", "90"))
    QUIET_PROJECT_THRESHOLD: int = int(os.getenv("QUIET_PROJECT_THRESHOLD", "30"))

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required config items."""
        missing = []
        if not cls.LABSTEP_API_KEY:
            missing.append("LABSTEP_API_KEY")
        if not cls.GITHUB_TOKEN:
            missing.append("GITHUB_TOKEN")
        return missing
