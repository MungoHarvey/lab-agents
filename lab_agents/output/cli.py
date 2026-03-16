"""CLI output — human-readable terminal output for testing.

Used with --dry-run to preview digests before posting to Slack.
"""

from __future__ import annotations


def format_digest(
    quality_findings: list[dict],
    heartbeats: list,
    summary_stats: dict,
) -> str:
    """Format findings and heartbeats as plain text for terminal output."""
    lines: list[str] = []

    lines.append("=" * 60)
    lines.append("  LAB DATA GOVERNANCE DIGEST")
    lines.append("=" * 60)
    lines.append("")

    # Summary stats
    lines.append(
        f"Experiments indexed: {summary_stats.get('total_experiments', 0)}"
    )
    lines.append(f"Repos tracked: {summary_stats.get('total_repos', 0)}")
    lines.append(f"Open issues: {summary_stats.get('open_issues', 0)}")
    lines.append("")

    # Quality issues
    warnings = [f for f in quality_findings if f.get("severity") == "warning"]
    infos = [f for f in quality_findings if f.get("severity") == "info"]

    if warnings:
        lines.append(f"QUALITY ISSUES ({len(warnings)} warnings)")
        lines.append("-" * 40)
        for f in warnings:
            entity = f.get("entity", "?")
            msg = f.get("message", "")
            researcher = f.get("researcher", "")
            source = f.get("source", "")
            prefix = f"  [{source}]" if source else "  "
            line = f"{prefix} {entity}"
            if researcher:
                line += f" ({researcher})"
            line += f": {msg}"
            lines.append(line)
        lines.append("")

    if infos:
        lines.append(f"INFO ({len(infos)} items)")
        lines.append("-" * 40)
        for f in infos:
            lines.append(
                f"  [{f.get('source', '')}] {f.get('entity', '')}: "
                f"{f.get('message', '')}"
            )
        lines.append("")

    # Heartbeat
    if heartbeats:
        lines.append("PROJECT ACTIVITY")
        lines.append("-" * 40)

        active = [h for h in heartbeats if h.status == "active"]
        quiet = [h for h in heartbeats if h.status == "quiet"]

        if active:
            lines.append("  Active:")
            for h in active:
                lines.append(f"    * {h.name}: {h.details}")
        if quiet:
            lines.append("  Quiet:")
            for h in quiet:
                lines.append(f"    * {h.name}: {h.details}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
