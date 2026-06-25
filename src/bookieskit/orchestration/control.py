# src/bookieskit/orchestration/control.py
"""Durable pause marker for the autonomous orchestrator.

Pause state lives in GitHub (source of truth, owner-visible): a single open
Issue carrying the ``control:paused`` label. ``is_paused`` is what the cycle
checks before building; ``set_paused``/``clear_paused`` are driven by the Slack
``pause``/``resume`` commands.
"""

from bookieskit.orchestration.gh import GhRunner

PAUSE_LABEL = "control:paused"
_MARKER_TITLE = "Orchestrator: paused"


def _open_markers(gh: GhRunner) -> list[dict]:
    return gh.list_issues(state="open", labels=(PAUSE_LABEL,))


def is_paused(gh: GhRunner) -> bool:
    return bool(_open_markers(gh))


def set_paused(gh: GhRunner, *, reason: str, author: str) -> int:
    """Open (or re-comment) the pause marker. Returns its Issue number."""
    existing = _open_markers(gh)
    if existing:
        number = existing[0]["number"]
        gh.comment_issue(number, f"Re-paused by {author}: {reason}")
        return number
    return gh.create_issue(
        title=_MARKER_TITLE,
        body=f"Autonomous building paused by {author}.\n\nReason: {reason}",
        labels=(PAUSE_LABEL,),
    )


def clear_paused(gh: GhRunner, *, author: str) -> list[int]:
    """Close every open pause marker. Returns the numbers closed."""
    closed: list[int] = []
    for issue in _open_markers(gh):
        gh.close_issue(issue["number"], comment=f"Resumed by {author}")
        closed.append(issue["number"])
    return closed
