"""SQLite metadata catalog linking experiments across LabStep, GitHub, and RDS.

Schema links experiment_id to labstep_url, raw_data path, github repo,
results path, researcher, project, and status flags. This is the "don't
move data, index it" principle in action.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lab_agents.config import Config

logger = logging.getLogger(__name__)


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    labstep_id INTEGER,
    labstep_url TEXT,
    name TEXT NOT NULL,
    researcher TEXT,
    project TEXT,
    created_at TEXT,
    updated_at TEXT,

    -- Data locations (null = not yet linked)
    raw_data_rds_path TEXT,
    github_repo TEXT,
    results_path TEXT,

    -- Status flags
    has_raw_data INTEGER DEFAULT 0,
    has_protocol INTEGER DEFAULT 0,
    has_analysis_code INTEGER DEFAULT 0,
    has_results INTEGER DEFAULT 0,
    has_writeup INTEGER DEFAULT 0,

    -- Quality flags
    code_version_controlled INTEGER DEFAULT 0,
    data_has_readme INTEGER DEFAULT 0,

    UNIQUE(labstep_id)
);

CREATE TABLE IF NOT EXISTS repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    full_name TEXT UNIQUE,
    url TEXT,
    description TEXT,
    last_push TEXT,
    has_readme INTEGER DEFAULT 1,
    recent_commits INTEGER DEFAULT 0,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS rds_directories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    name TEXT,
    has_readme INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0,
    total_size_mb REAL DEFAULT 0,
    contains_fastq INTEGER DEFAULT 0,
    contains_bam INTEGER DEFAULT 0,
    last_modified TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS quality_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,       -- 'labstep', 'github', 'rds'
    entity_id TEXT,             -- experiment_id, repo name, directory path
    entity_name TEXT,
    issue_type TEXT NOT NULL,   -- 'missing_data', 'no_readme', 'stale', etc.
    description TEXT,
    researcher TEXT,
    first_seen TEXT,
    resolved_at TEXT,
    url TEXT
);
"""


class MetadataCatalog:
    """SQLite-based metadata catalog for lab data governance."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or Config.CATALOG_DB
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> bool:
        """Initialize database connection and create tables."""
        try:
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(CREATE_TABLES_SQL)
            logger.info("Catalog connected: %s", self.db_path)
            return True
        except Exception as e:
            logger.error("Failed to connect catalog: %s", e)
            return False

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        return self._conn  # type: ignore

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # --- Experiment operations ---

    def upsert_experiment(self, **kwargs) -> int:
        """Insert or update an experiment record."""
        now = datetime.now(timezone.utc).isoformat()
        kwargs["updated_at"] = now

        labstep_id = kwargs.get("labstep_id")
        if labstep_id:
            existing = self.conn.execute(
                "SELECT id FROM experiments WHERE labstep_id = ?",
                (labstep_id,),
            ).fetchone()
            if existing:
                sets = ", ".join(f"{k} = ?" for k in kwargs)
                values = list(kwargs.values()) + [existing["id"]]
                self.conn.execute(
                    f"UPDATE experiments SET {sets} WHERE id = ?", values
                )
                self.conn.commit()
                return existing["id"]

        if "created_at" not in kwargs:
            kwargs["created_at"] = now

        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" * len(kwargs))
        cursor = self.conn.execute(
            f"INSERT INTO experiments ({cols}) VALUES ({placeholders})",
            list(kwargs.values()),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore

    def get_experiments(self, **filters) -> list[dict]:
        """Query experiments with optional filters."""
        query = "SELECT * FROM experiments"
        conditions = []
        values = []
        for key, val in filters.items():
            conditions.append(f"{key} = ?")
            values.append(val)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"

        rows = self.conn.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    # --- Quality issue operations ---

    def log_issue(
        self,
        source: str,
        entity_id: str,
        entity_name: str,
        issue_type: str,
        description: str,
        researcher: str = "",
        url: str = "",
    ) -> int:
        """Log a quality issue. Deduplicates by source+entity_id+issue_type."""
        existing = self.conn.execute(
            """SELECT id FROM quality_issues
               WHERE source = ? AND entity_id = ? AND issue_type = ?
               AND resolved_at IS NULL""",
            (source, entity_id, issue_type),
        ).fetchone()

        if existing:
            return existing["id"]

        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """INSERT INTO quality_issues
               (source, entity_id, entity_name, issue_type, description,
                researcher, first_seen, url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (source, entity_id, entity_name, issue_type, description,
             researcher, now, url),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore

    def resolve_issue(self, issue_id: int):
        """Mark a quality issue as resolved."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE quality_issues SET resolved_at = ? WHERE id = ?",
            (now, issue_id),
        )
        self.conn.commit()

    def get_open_issues(self, source: str | None = None) -> list[dict]:
        """Get all unresolved quality issues."""
        query = "SELECT * FROM quality_issues WHERE resolved_at IS NULL"
        values: list = []
        if source:
            query += " AND source = ?"
            values.append(source)
        query += " ORDER BY first_seen ASC"

        rows = self.conn.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    # --- Repo operations ---

    def upsert_repo(self, **kwargs):
        """Insert or update a repo record."""
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        existing = self.conn.execute(
            "SELECT id FROM repos WHERE full_name = ?",
            (kwargs.get("full_name", ""),),
        ).fetchone()

        if existing:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values()) + [existing["id"]]
            self.conn.execute(f"UPDATE repos SET {sets} WHERE id = ?", values)
        else:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            self.conn.execute(
                f"INSERT INTO repos ({cols}) VALUES ({placeholders})",
                list(kwargs.values()),
            )
        self.conn.commit()

    # --- Statistics ---

    def get_summary_stats(self) -> dict:
        """Get summary statistics for the catalog."""
        stats = {}
        stats["total_experiments"] = self.conn.execute(
            "SELECT COUNT(*) FROM experiments"
        ).fetchone()[0]
        stats["experiments_missing_data"] = self.conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE has_raw_data = 0"
        ).fetchone()[0]
        stats["total_repos"] = self.conn.execute(
            "SELECT COUNT(*) FROM repos"
        ).fetchone()[0]
        stats["open_issues"] = self.conn.execute(
            "SELECT COUNT(*) FROM quality_issues WHERE resolved_at IS NULL"
        ).fetchone()[0]
        return stats
