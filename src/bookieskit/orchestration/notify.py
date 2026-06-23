"""Pure Slack-mrkdwn message formatters for the agent-company cockpit.

No I/O: each function returns the message *text*. The orchestrate skill (or the
``notify`` CLI) produces the text; the agent posts it via the Slack MCP
``post_message`` tool. Keeping these pure makes them offline-testable in CI,
where no Slack MCP is connected.
"""


def _humanize_stream(stream: str) -> str:
    """``stream:directed`` -> ``directed`` (leave a bare value unchanged)."""
    return stream.removeprefix("stream:")


def cycle_started(number: int, title: str, stream: str) -> str:
    return (
        f":hammer: *Cycle started* — #{number} "
        f"[{_humanize_stream(stream)}] {title}"
    )


def cycle_pr(number: int, title: str, pr_url: str) -> str:
    return (
        f":white_check_mark: *PR opened* for #{number} {title} — "
        f"{pr_url} (awaiting review)"
    )


def cycle_blocked(number: int, title: str, reason: str) -> str:
    return f":no_entry: *#{number} blocked* — {title}: {reason}"


def cycle_empty() -> str:
    return ":zzz: Queue empty — nothing to do this cycle."


def canary_digest(
    opened: list[str], updated: list[str], closed: list[str], sport: str
) -> str:
    """Drift digest for ``#canary-alerts``. Returns ``""`` when nothing changed
    (the caller skips posting an empty digest)."""
    if not (opened or updated or closed):
        return ""
    lines = [
        f":warning: *Canary ({sport})* — {len(opened)} new, "
        f"{len(updated)} persisting, {len(closed)} recovered"
    ]
    lines += [f"• opened: {s}" for s in opened]
    lines += [f"• still drifting: {s}" for s in updated]
    lines += [f"• recovered: {s}" for s in closed]
    return "\n".join(lines)


def release_announcement(tag: str, current: str, new: str) -> str:
    return f":package: *Released {tag}* ({current} → {new})"
