"""Main orchestrator — runs all checks and outputs digest.

Usage:
    python -m lab_agents.digest                # Post to Slack
    python -m lab_agents.digest --dry-run      # Print to stdout only
    python -m lab_agents.digest --github-only   # Only GitHub checks
    python -m lab_agents.digest --labstep-only  # Only LabStep checks
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

from lab_agents.agents.heartbeat import generate_heartbeat
from lab_agents.agents.quality import QualityChecker
from lab_agents.catalog.metadata import MetadataCatalog
from lab_agents.config import Config
from lab_agents.output.cli import format_digest
from lab_agents.output.slack import SlackOutput, format_digest_blocks

logger = logging.getLogger(__name__)


def run_digest(
    dry_run: bool = False,
    github_only: bool = False,
    labstep_only: bool = False,
    rds_only: bool = False,
) -> dict:
    """Run the full digest pipeline.

    1. Connect to data sources
    2. Fetch recent data
    3. Run quality checks
    4. Generate heartbeat
    5. Output to Slack and/or CLI

    Returns summary dict of what was found.
    """
    # Initialize catalog
    catalog = MetadataCatalog()
    catalog.connect()
    checker = QualityChecker(catalog)

    labstep_experiments = None
    github_summary = None
    rds_result = None

    # --- Fetch data from connectors ---

    if not github_only and not rds_only:
        try:
            from lab_agents.connectors.labstep import LabStepConnector

            if Config.LABSTEP_API_KEY:
                ls = LabStepConnector()
                if ls.connect():
                    labstep_experiments = ls.get_recent_experiments(days=30)
                    logger.info(
                        "Fetched %d experiments from LabStep",
                        len(labstep_experiments),
                    )
            else:
                logger.warning("LABSTEP_API_KEY not set — skipping LabStep")
        except Exception as e:
            logger.error("LabStep connector failed: %s", e)

    if not labstep_only and not rds_only:
        try:
            from lab_agents.connectors.github import GitHubConnector

            if Config.GITHUB_TOKEN:
                gh = GitHubConnector()
                if gh.connect():
                    github_summary = gh.scan_org(days=30)
                    logger.info(
                        "Scanned %d repos from GitHub",
                        github_summary.total_repos,
                    )
            else:
                logger.warning("GITHUB_TOKEN not set — skipping GitHub")
        except Exception as e:
            logger.error("GitHub connector failed: %s", e)

    if not labstep_only and not github_only:
        try:
            from lab_agents.connectors.rds import RDSScanner

            if Config.RDS_PATH:
                rds = RDSScanner()
                if rds.is_available():
                    rds_result = rds.scan()
                    logger.info(
                        "Scanned %d RDS directories",
                        len(rds_result.directories),
                    )
            else:
                logger.info("RDS_PATH not set — skipping RDS scan")
        except Exception as e:
            logger.error("RDS scanner failed: %s", e)

    # --- Run quality checks ---
    findings = checker.run_all(
        labstep_experiments=labstep_experiments,
        github_summary=github_summary,
        rds_result=rds_result,
    )

    # --- Generate heartbeat ---
    heartbeats = generate_heartbeat(
        github_summary=github_summary,
        labstep_experiments=labstep_experiments,
        rds_result=rds_result,
    )

    # --- Output ---
    stats = catalog.get_summary_stats()

    # Always print CLI output
    cli_text = format_digest(findings, heartbeats, stats)
    print(cli_text)

    # Post to Slack unless dry-run
    if not dry_run:
        slack = SlackOutput()
        if slack.is_configured():
            blocks = format_digest_blocks(findings, heartbeats, stats)
            if slack.post_digest(blocks):
                logger.info("Digest posted to Slack")
            else:
                logger.error("Failed to post digest to Slack")
        else:
            logger.info("Slack not configured — CLI output only")

    catalog.close()

    return {
        "findings": len(findings),
        "heartbeats": len(heartbeats),
        "warnings": len([f for f in findings if f.get("severity") == "warning"]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Lab Data Governance Digest"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print to stdout only, don't post to Slack",
    )
    parser.add_argument(
        "--github-only",
        action="store_true",
        help="Only run GitHub checks",
    )
    parser.add_argument(
        "--labstep-only",
        action="store_true",
        help="Only run LabStep checks",
    )
    parser.add_argument(
        "--rds-only",
        action="store_true",
        help="Only run RDS scan",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    result = run_digest(
        dry_run=args.dry_run,
        github_only=args.github_only,
        labstep_only=args.labstep_only,
        rds_only=args.rds_only,
    )

    if result["warnings"] > 0:
        logger.info(
            "Digest complete: %d findings (%d warnings)",
            result["findings"],
            result["warnings"],
        )


if __name__ == "__main__":
    main()
