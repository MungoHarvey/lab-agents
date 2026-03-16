"""Slack output — posts digests and alerts to a Slack channel.

Uses Slack Bolt SDK. Requires SLACK_BOT_TOKEN and SLACK_CHANNEL.

Setup: Create a Slack app at https://api.slack.com/apps with these scopes:
- chat:write
- chat:write.customize (for bot name/icon)
"""

from __future__ import annotations

import logging

from lab_agents.config import Config

logger = logging.getLogger(__name__)


class SlackOutput:
    """Posts formatted digests to Slack."""

    def __init__(self, token: str | None = None, channel: str | None = None):
        self.token = token or Config.SLACK_BOT_TOKEN
        self.channel = channel or Config.SLACK_CHANNEL
        self._client = None

    def is_configured(self) -> bool:
        """Check if Slack credentials are set."""
        return bool(self.token and self.channel)

    def connect(self) -> bool:
        """Initialize Slack client."""
        if not self.is_configured():
            logger.info("Slack not configured (no token or channel)")
            return False
        try:
            from slack_sdk import WebClient

            self._client = WebClient(token=self.token)
            # Test connection
            self._client.auth_test()
            logger.info("Connected to Slack")
            return True
        except Exception as e:
            logger.error("Failed to connect to Slack: %s", e)
            return False

    def post_digest(self, blocks: list[dict]) -> bool:
        """Post a Block Kit message to the channel."""
        if not self._client:
            if not self.connect():
                return False

        try:
            self._client.chat_postMessage(
                channel=self.channel,
                blocks=blocks,
                text="Lab Data Governance Digest",  # fallback for notifications
            )
            logger.info("Posted digest to %s", self.channel)
            return True
        except Exception as e:
            logger.error("Failed to post to Slack: %s", e)
            return False

    def post_text(self, text: str) -> bool:
        """Post a simple text message."""
        if not self._client:
            if not self.connect():
                return False

        try:
            self._client.chat_postMessage(
                channel=self.channel,
                text=text,
            )
            return True
        except Exception as e:
            logger.error("Failed to post to Slack: %s", e)
            return False


def format_digest_blocks(
    quality_findings: list[dict],
    heartbeats: list,
    summary_stats: dict,
) -> list[dict]:
    """Format findings and heartbeats into Slack Block Kit blocks."""
    blocks: list[dict] = []

    # Header
    blocks.append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Lab Data Governance Digest",
            },
        }
    )

    # Summary stats
    stats_text = (
        f"*Experiments indexed:* {summary_stats.get('total_experiments', 0)} | "
        f"*Repos:* {summary_stats.get('total_repos', 0)} | "
        f"*Open issues:* {summary_stats.get('open_issues', 0)}"
    )
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": stats_text},
        }
    )

    blocks.append({"type": "divider"})

    # Quality issues by severity
    warnings = [f for f in quality_findings if f.get("severity") == "warning"]
    if warnings:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*:warning: Quality Issues ({len(warnings)})*",
                },
            }
        )
        for finding in warnings[:10]:  # Cap at 10
            url = finding.get("url", "")
            entity = finding.get("entity", "?")
            msg = finding.get("message", "")
            researcher = finding.get("researcher", "")
            line = f"• *{entity}*"
            if researcher:
                line += f" ({researcher})"
            line += f": {msg}"
            if url:
                line += f" (<{url}|view>)"
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": line},
                }
            )

    # Project heartbeat
    if heartbeats:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*:heartbeat: Project Activity*",
                },
            }
        )

        active = [h for h in heartbeats if h.status == "active"]
        quiet = [h for h in heartbeats if h.status == "quiet"]

        if active:
            active_text = "\n".join(
                f"• :large_green_circle: *{h.name}* — {h.details}"
                for h in active[:10]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": active_text},
                }
            )

        if quiet:
            quiet_text = "\n".join(
                f"• :white_circle: *{h.name}* — {h.details}"
                for h in quiet[:10]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": quiet_text},
                }
            )

    return blocks
