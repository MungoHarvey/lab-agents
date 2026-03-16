"""Data governance quality checks.

Runs checks across all connectors and logs issues to the metadata catalog.

Quality checks:
1. Experiments on LabStep missing raw data after N days
2. Analysis code not version-controlled on GitHub
3. Missing README files on repos and RDS directories
4. Completed analyses not written up after N days
5. Novogene orders not downloaded to RDS (future)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from lab_agents.catalog.metadata import MetadataCatalog
from lab_agents.config import Config

logger = logging.getLogger(__name__)


class QualityChecker:
    """Runs quality checks across all data sources and logs findings."""

    def __init__(self, catalog: MetadataCatalog):
        self.catalog = catalog
        self.findings: list[dict] = []

    def run_all(
        self,
        labstep_experiments: list | None = None,
        github_summary=None,
        rds_result=None,
    ) -> list[dict]:
        """Run all quality checks and return findings.

        Accepts pre-fetched data from connectors to avoid redundant API calls.
        """
        self.findings = []

        if labstep_experiments:
            self._check_labstep(labstep_experiments)

        if github_summary:
            self._check_github(github_summary)

        if rds_result:
            self._check_rds(rds_result)

        logger.info("Quality check complete: %d findings", len(self.findings))
        return self.findings

    def _check_labstep(self, experiments: list):
        """Check LabStep experiments for completeness."""
        threshold = Config.MISSING_DATA_THRESHOLD
        cutoff = datetime.now(timezone.utc) - timedelta(days=threshold)

        for exp in experiments:
            # Record in catalog
            self.catalog.upsert_experiment(
                labstep_id=exp.id,
                name=exp.name,
                researcher=exp.author,
                has_raw_data=int(exp.has_data),
                has_protocol=int(exp.has_protocol),
                has_results=int(exp.has_results),
                labstep_url=exp.labstep_url,
            )

            # Check for missing data
            if not exp.has_data and exp.created_at < cutoff:
                days_old = (datetime.now(timezone.utc) - exp.created_at).days
                finding = {
                    "source": "labstep",
                    "type": "missing_data",
                    "severity": "warning",
                    "entity": exp.name,
                    "researcher": exp.author,
                    "message": f"No raw data after {days_old} days",
                    "url": exp.labstep_url,
                }
                self.findings.append(finding)
                self.catalog.log_issue(
                    source="labstep",
                    entity_id=str(exp.id),
                    entity_name=exp.name,
                    issue_type="missing_data",
                    description=finding["message"],
                    researcher=exp.author,
                    url=exp.labstep_url,
                )

            # Check for missing protocol
            if not exp.has_protocol:
                finding = {
                    "source": "labstep",
                    "type": "missing_protocol",
                    "severity": "info",
                    "entity": exp.name,
                    "researcher": exp.author,
                    "message": "No protocol attached",
                    "url": exp.labstep_url,
                }
                self.findings.append(finding)

    def _check_github(self, summary):
        """Check GitHub repos for quality issues."""
        # Repos missing README
        for repo_name in summary.repos_missing_readme:
            finding = {
                "source": "github",
                "type": "missing_readme",
                "severity": "warning",
                "entity": repo_name,
                "researcher": "",
                "message": f"Repo {repo_name} has no README",
                "url": f"https://github.com/{Config.GITHUB_ORG}/{repo_name}",
            }
            self.findings.append(finding)
            self.catalog.log_issue(
                source="github",
                entity_id=repo_name,
                entity_name=repo_name,
                issue_type="missing_readme",
                description=finding["message"],
                url=finding["url"],
            )

        # Quiet repos (no activity in QUIET_PROJECT_THRESHOLD days)
        for repo in summary.quiet_repos:
            if repo.days_since_push and repo.days_since_push > Config.QUIET_PROJECT_THRESHOLD:
                finding = {
                    "source": "github",
                    "type": "stale_repo",
                    "severity": "info",
                    "entity": repo.name,
                    "researcher": "",
                    "message": f"No activity in {repo.days_since_push} days",
                    "url": repo.url,
                }
                self.findings.append(finding)

        # Store repo metadata
        for repo in summary.active_repos + summary.quiet_repos:
            self.catalog.upsert_repo(
                name=repo.name,
                full_name=f"{Config.GITHUB_ORG}/{repo.name}",
                url=repo.url,
                description=repo.description,
                last_push=repo.last_push.isoformat() if repo.last_push else None,
                has_readme=int(repo.has_readme),
                recent_commits=repo.recent_commits,
            )

    def _check_rds(self, rds_result):
        """Check RDS directories for governance issues."""
        for dir_name in rds_result.dirs_missing_readme:
            finding = {
                "source": "rds",
                "type": "missing_readme",
                "severity": "warning",
                "entity": dir_name,
                "researcher": "",
                "message": f"RDS directory '{dir_name}' has no README",
                "url": "",
            }
            self.findings.append(finding)
            self.catalog.log_issue(
                source="rds",
                entity_id=dir_name,
                entity_name=dir_name,
                issue_type="missing_readme",
                description=finding["message"],
            )

        for dir_name in rds_result.orphan_data:
            finding = {
                "source": "rds",
                "type": "orphan_data",
                "severity": "warning",
                "entity": dir_name,
                "researcher": "",
                "message": f"Sequencing data in '{dir_name}' with no README",
                "url": "",
            }
            self.findings.append(finding)
