"""Pure ChatOps helpers: turn Slack #tickets messages into work items and
``approve`` commands, authorize/guard merges, and format Slack-mrkdwn replies.

No I/O except ``load_config`` (reads the committed allowlist file). Everything
else is deterministic and offline-tested; the orchestrate skill reads Slack via
the MCP and the ``chatops`` CLI does the gh side.
"""

import json
import re
from dataclasses import dataclass

from bookieskit.orchestration.workitem import WorkItem

_APPROVE_RE = re.compile(r"^\s*approve\s+#?(\d+)\s*$", re.IGNORECASE)
_OK_CHECK_STATES = {"SUCCESS", "NEUTRAL", "SKIPPED"}


@dataclass
class ApproveCommand:
    """A parsed ``approve <pr>`` command."""

    pr: int


def ticket_signature(ts: str) -> str:
    """Dedup key for a Slack-filed ticket (one per source message ts)."""
    return f"directed:slack:{ts}"


def build_ticket(author: str, ts: str, title: str, summary: str) -> WorkItem:
    """A stream:directed WorkItem from a #tickets request, attributed to the
    Slack author. ``ts`` is the source message timestamp (the dedup anchor)."""
    body = (
        f"{summary}\n\n"
        f"_Requested by {author} via Slack #tickets (ts {ts})._"
    )
    return WorkItem(
        signature=ticket_signature(ts),
        stream="stream:directed",
        title=title,
        summary=body,
        meta={"requester": author, "slack_ts": ts},
    )


def parse_command(text: str) -> ApproveCommand | None:
    """Recognize ``approve <pr>`` (optional ``#``). Anything else -> None."""
    match = _APPROVE_RE.match(text)
    return ApproveCommand(pr=int(match.group(1))) if match else None


def is_authorized(author: str, approvers: tuple[str, ...]) -> bool:
    """True if the Slack author is in the approver allowlist."""
    return author in approvers


def checks_pass(rollup: list[dict]) -> bool:
    """True only when there is at least one check and every check concluded
    SUCCESS/NEUTRAL/SKIPPED (an empty rollup is treated as NOT green)."""
    if not rollup:
        return False
    for check in rollup:
        # A null/absent conclusion (an in-progress check) resolves to "" and
        # fails the membership test — by design: not green until all done.
        state = (check.get("conclusion") or check.get("state") or "").upper()
        if state not in _OK_CHECK_STATES:
            return False
    return True


def closing_issue_numbers(pr_view: dict) -> list[int]:
    """Issue numbers the PR will close (gh ``closingIssuesReferences``)."""
    refs = pr_view.get("closingIssuesReferences") or []
    return [r["number"] for r in refs if "number" in r]


def load_config(path) -> dict:
    """Read the committed ChatOps config: approver IDs + #tickets channel."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def queued(number: int, title: str) -> str:
    """Reply for a newly-queued stream:directed ticket."""
    return f":inbox_tray: Queued *#{number}* — {title} (stream:directed)"


def merged(pr: int, number: int) -> str:
    return f":rocket: Merged PR #{pr} — closes #{number}."


def rejected(pr: int, reason: str) -> str:
    return f":no_entry: Can't merge PR #{pr} — {reason}."
