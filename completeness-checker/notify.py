"""Slack notification for experiment completeness flags."""

import requests


LABSTEP_EXPERIMENT_URL = "https://app.labstep.com/experiment/{workflow_id}"


def format_experiment_message(experiment, flags):
    """Format a Slack message for a single flagged experiment."""
    lines = [f"*{experiment['id']}* \"{experiment['name']}\" — missing sections"]

    for flag in flags:
        section = flag["section"]
        wc = flag["word_count"]
        if section == "protocol":
            lines.append("• No protocol attached")
        elif wc == 0:
            lines.append(f"• {section.title()}: empty (0 words)")
        else:
            lines.append(f"• {section.title()}: only {wc} words")

    lines.append(f"Author: {experiment['author']} | Completed: {experiment['date']}")
    url = LABSTEP_EXPERIMENT_URL.format(workflow_id=experiment["workflow_id"])
    lines.append(f"<{url}|View on Labstep>")

    return "\n".join(lines)


def format_summary_message(count):
    """Format a summary message when too many experiments are flagged."""
    return f"*{count} experiments* have incomplete documentation. Review the full report in GitHub Actions."


def send_slack_notification(webhook_url, message):
    """Post a message to Slack via incoming webhook."""
    requests.post(webhook_url, json={"text": message}, timeout=10)
