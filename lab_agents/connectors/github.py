"""GitHub connector — scan neurogenomics org repos for activity.

Uses PyGithub to interact with the GitHub API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from lab_agents.config import Config

logger = logging.getLogger(__name__)


@dataclass
class RepoActivity:
    """Activity summary for a single repository."""

    name: str
    url: str
    description: str
    last_push: datetime | None
    days_since_push: int | None
    recent_commits: int = 0  # commits in last 30 days
    open_issues: int = 0
    open_prs: int = 0
    has_readme: bool = True
    contributors_30d: list[str] = field(default_factory=list)
    is_private: bool = False


@dataclass
class OrgSummary:
    """Summary of all activity across the org."""

    total_repos: int = 0
    active_repos: list[RepoActivity] = field(default_factory=list)
    quiet_repos: list[RepoActivity] = field(default_factory=list)
    repos_missing_readme: list[str] = field(default_factory=list)
    contributor_activity: dict[str, int] = field(default_factory=dict)


class GitHubConnector:
    """Connects to GitHub API and scans org repos."""

    def __init__(self, token: str | None = None, org: str | None = None):
        self.token = token or Config.GITHUB_TOKEN
        self.org = org or Config.GITHUB_ORG
        self._gh = None

    def connect(self) -> bool:
        """Authenticate with GitHub. Returns True on success."""
        try:
            from github import Github

            self._gh = Github(self.token)
            # Verify connection
            self._gh.get_organization(self.org)
            logger.info("Connected to GitHub org: %s", self.org)
            return True
        except Exception as e:
            logger.error("Failed to connect to GitHub: %s", e)
            return False

    def scan_org(self, days: int = 30) -> OrgSummary:
        """Scan all repos in the org for activity in the last N days."""
        if not self._gh:
            if not self.connect():
                return OrgSummary()

        try:
            org = self._gh.get_organization(self.org)
            repos = org.get_repos(type="all", sort="pushed", direction="desc")

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            quiet_threshold = datetime.now(timezone.utc) - timedelta(
                days=Config.QUIET_PROJECT_THRESHOLD
            )

            summary = OrgSummary()
            contributor_commits: dict[str, int] = {}

            for repo in repos:
                summary.total_repos += 1
                activity = self._get_repo_activity(repo, cutoff)

                if activity.last_push and activity.last_push >= cutoff:
                    summary.active_repos.append(activity)
                elif activity.last_push and activity.last_push < quiet_threshold:
                    summary.quiet_repos.append(activity)

                if not activity.has_readme:
                    summary.repos_missing_readme.append(activity.name)

                # Aggregate contributor activity
                for contributor in activity.contributors_30d:
                    contributor_commits[contributor] = (
                        contributor_commits.get(contributor, 0) + 1
                    )

            summary.contributor_activity = contributor_commits
            logger.info(
                "Scanned %d repos: %d active, %d quiet",
                summary.total_repos,
                len(summary.active_repos),
                len(summary.quiet_repos),
            )
            return summary

        except Exception as e:
            logger.error("Failed to scan org: %s", e)
            return OrgSummary()

    def get_student_activity(self, username: str, days: int = 30) -> dict:
        """Get commit activity for a specific student across all repos."""
        if not self._gh:
            if not self.connect():
                return {}

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        activity = {"username": username, "repos": [], "total_commits": 0}

        try:
            org = self._gh.get_organization(self.org)
            for repo in org.get_repos():
                try:
                    commits = repo.get_commits(
                        author=username, since=cutoff
                    )
                    count = commits.totalCount
                    if count > 0:
                        activity["repos"].append(
                            {"name": repo.name, "commits": count}
                        )
                        activity["total_commits"] += count
                except Exception:
                    continue

        except Exception as e:
            logger.error("Failed to get activity for %s: %s", username, e)

        return activity

    def _get_repo_activity(self, repo, cutoff: datetime) -> RepoActivity:
        """Extract activity metrics for a single repo."""
        last_push = repo.pushed_at
        if last_push and last_push.tzinfo is None:
            last_push = last_push.replace(tzinfo=timezone.utc)

        days_since = None
        if last_push:
            days_since = (datetime.now(timezone.utc) - last_push).days

        # Get recent commits
        recent_commits = 0
        contributors = []
        try:
            commits = repo.get_commits(since=cutoff)
            for commit in commits:
                recent_commits += 1
                author = commit.author
                if author and author.login not in contributors:
                    contributors.append(author.login)
                if recent_commits > 100:  # cap to avoid rate limits
                    break
        except Exception:
            pass

        # Check README
        has_readme = True
        try:
            repo.get_readme()
        except Exception:
            has_readme = False

        return RepoActivity(
            name=repo.name,
            url=repo.html_url,
            description=repo.description or "",
            last_push=last_push,
            days_since_push=days_since,
            recent_commits=recent_commits,
            open_issues=repo.open_issues_count,
            open_prs=0,  # would need separate API call
            has_readme=has_readme,
            contributors_30d=contributors,
            is_private=repo.private,
        )
