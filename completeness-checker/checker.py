"""Main orchestration: fetch, score, notify."""

import json
import os
import sys
import time

from dotenv import load_dotenv

from parser import extract_sections
from scorer import score_experiment
from fetcher import fetch_completed_experiments, get_experiment_state
from notify import format_experiment_message, format_summary_message, send_slack_notification

NOTIFIED_FILE = os.path.join(os.path.dirname(__file__), "last_checked.json")
MAX_INDIVIDUAL_NOTIFICATIONS = 10


def load_notified(path):
    """Load set of experiment IDs already notified."""
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return set(json.load(f))


def save_notified(path, notified):
    """Save set of notified experiment IDs."""
    with open(path, "w") as f:
        json.dump(sorted(notified), f, indent=2)


def run_check(experiments, base_url, headers, webhook_url, notified_path=None):
    """Run completeness check on a list of experiment metadata dicts.

    Args:
        experiments: list of dicts from fetch_completed_experiments()
        base_url: Labstep API base URL
        headers: API auth headers
        webhook_url: Slack webhook URL
        notified_path: path to last_checked.json

    Returns:
        list of flagged experiment dicts (with 'flags' key added)
    """
    if notified_path is None:
        notified_path = NOTIFIED_FILE

    already_notified = load_notified(notified_path)
    newly_flagged = []

    for exp in experiments:
        if exp["id"] in already_notified:
            continue

        try:
            pm_state = get_experiment_state(exp["workflow_id"], base_url, headers)
        except Exception as e:
            print(f"Warning: could not fetch state for {exp['id']}: {e}")
            continue

        sections = extract_sections(pm_state) if pm_state else {}
        result = score_experiment(sections, exp["protocol_count"])

        if result["flags"]:
            exp["flags"] = result["flags"]
            exp["scores"] = result["scores"]
            newly_flagged.append(exp)

    # Send notifications
    if newly_flagged and webhook_url:
        if len(newly_flagged) > MAX_INDIVIDUAL_NOTIFICATIONS:
            send_slack_notification(webhook_url, format_summary_message(len(newly_flagged)))
        else:
            for exp in newly_flagged:
                send_slack_notification(webhook_url, format_experiment_message(exp, exp["flags"]))
                time.sleep(0.5)

    # Update notified list
    new_ids = {exp["id"] for exp in newly_flagged}
    all_notified = already_notified | new_ids
    save_notified(notified_path, all_notified)

    return newly_flagged


def main():
    load_dotenv()
    api_key = os.environ.get("LABSTEP_API_KEY")
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    if not api_key:
        print("Error: LABSTEP_API_KEY not set")
        sys.exit(1)
    if not webhook_url:
        print("Error: SLACK_WEBHOOK_URL not set")
        sys.exit(1)

    import labstep
    from labstep.service.config import configService

    user = labstep.authenticate(apikey=api_key)
    base_url = configService.getHost()
    headers = {"apikey": api_key}

    print("Fetching completed experiments...")
    experiments = fetch_completed_experiments(user)
    print(f"Found {len(experiments)} completed experiments")

    flagged = run_check(
        experiments=experiments,
        base_url=base_url,
        headers=headers,
        webhook_url=webhook_url,
    )

    print(f"Flagged {len(flagged)} experiments with incomplete documentation")

    # Write report
    report_path = os.path.join(os.path.dirname(__file__), "report.json")
    with open(report_path, "w") as f:
        json.dump(flagged, f, indent=2, default=str)
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
