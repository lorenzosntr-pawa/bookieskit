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

_DESIGN_OK_RE = re.compile(r"^\s*design\s+ok\s+#?(\d+)\s*$", re.IGNORECASE)
_DESIGN_NO_RE = re.compile(r"^\s*design\s+no\s+#?(\d+)\s+(.*\S)\s*$", re.IGNORECASE)
_COUNCIL_RE = re.compile(r"^\s*council\s+#?(\d+)\s*$", re.IGNORECASE)
_APPROVE_RE = re.compile(r"^\s*approve\s+#?(\d+)\s*$", re.IGNORECASE)
_PAUSE_RE = re.compile(r"^\s*pause(?:\s+(.*\S))?\s*$", re.IGNORECASE)
_RESUME_RE = re.compile(r"^\s*resume\s*$", re.IGNORECASE)
_STATUS_RE = re.compile(r"^\s*status\s*$", re.IGNORECASE)
_OK_CHECK_STATES = {"SUCCESS", "NEUTRAL", "SKIPPED"}


@dataclass
class ApproveCommand:
    """A parsed ``approve <pr>`` command."""

    pr: int


@dataclass
class PauseCommand:
    """A parsed ``pause [reason]`` command."""

    reason: str = ""


@dataclass
class ResumeCommand:
    """A parsed ``resume`` command."""

    pass


@dataclass
class DesignOkCommand:
    issue: int


@dataclass
class DesignChangesCommand:
    issue: int
    notes: str


@dataclass
class CouncilCommand:
    issue: int


@dataclass
class StatusCommand:
    pass


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


def parse_command(text: str):
    """Recognize an ``approve <pr>``, ``pause [reason]``, or ``resume`` command.
    Returns the matching command object, or None for anything else."""
    m = _DESIGN_OK_RE.match(text)
    if m:
        return DesignOkCommand(issue=int(m.group(1)))
    m = _DESIGN_NO_RE.match(text)
    if m:
        return DesignChangesCommand(issue=int(m.group(1)), notes=m.group(2).strip())
    m = _COUNCIL_RE.match(text)
    if m:
        return CouncilCommand(issue=int(m.group(1)))
    if _STATUS_RE.match(text):
        return StatusCommand()
    m = _APPROVE_RE.match(text)
    if m:
        return ApproveCommand(pr=int(m.group(1)))
    m = _PAUSE_RE.match(text)
    if m:
        return PauseCommand(reason=(m.group(1) or "").strip())
    if _RESUME_RE.match(text):
        return ResumeCommand()
    return None


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


def paused(reason: str) -> str:
    """Reply for a pause command."""
    tail = f" — {reason}" if reason else ""
    msg = ":double_vertical_bar: Orchestrator *paused*" + tail
    return f"{msg}. Autonomous building halted until `resume`."


def resumed() -> str:
    """Reply for a resume command."""
    return ":arrow_forward: Orchestrator *resumed*. Back to work next cycle."


def design_ready(issue: int) -> str:
    return (
        f":white_check_mark: Design for *#{issue}* approved — marked *ready to "
        "build*. I'll build it next cycle."
    )


def design_changes_ack(issue: int) -> str:
    return f":pencil: Got it — revising the design for *#{issue}*. I'll repost shortly."
