"""Queue: the durable work queue over GitHub Issues.

Dedup is by the ``signature`` stored in each issue's yaml meta block: a re-run
that finds an open issue with the same signature *updates* (comments) rather
than duplicating, and closes one whose work is done. Labels are ensured on
first use so the stream label always exists before an issue is filed.
"""

from bookieskit.orchestration.gh import GhRunner
from bookieskit.orchestration.labels import ensure_labels
from bookieskit.orchestration.workitem import WorkItem, parse_meta, render_body


class Queue:
    """Read/write the work queue (GitHub Issues), deduped by signature."""

    def __init__(self, gh: GhRunner, *, ensure: bool = True):
        self.gh = gh
        if ensure:
            ensure_labels(gh)

    def find_open_by_signature(self, signature: str) -> dict | None:
        for issue in self.gh.list_issues(state="open"):
            if parse_meta(issue.get("body", "")).get("signature") == signature:
                return issue
        return None

    def open_or_update(
        self, item: WorkItem, *, note: str
    ) -> tuple[int, str]:
        existing = self.find_open_by_signature(item.signature)
        if existing is not None:
            number = existing["number"]
            self.gh.comment_issue(number, note)
            return number, "updated"
        number = self.gh.create_issue(
            title=item.title,
            body=render_body(item),
            labels=(item.stream,),
        )
        return number, "opened"

    def close_by_signature(
        self, signature: str, *, reason: str
    ) -> int | None:
        existing = self.find_open_by_signature(signature)
        if existing is None:
            return None
        number = existing["number"]
        self.gh.close_issue(number, comment=reason)
        return number

    def list_open(self, *, stream: str | None = None) -> list[dict]:
        labels = (stream,) if stream else ()
        return self.gh.list_issues(state="open", labels=labels)

    def claim(self, number: int) -> None:
        """Mark an issue as being worked (adds status:claimed)."""
        self.gh.edit_issue(number, add_labels=["status:claimed"])

    def mark_in_review(self, number: int, pr_url: str) -> None:
        """Transition to in-review: add status:in-review, drop status:claimed,
        and comment the PR link."""
        self.gh.edit_issue(
            number,
            add_labels=["status:in-review"],
            remove_labels=["status:claimed"],
        )
        self.gh.comment_issue(number, f"PR: {pr_url}")

    def mark_blocked(self, number: int, *, reason: str) -> None:
        """Transition to blocked: add status:blocked, drop status:claimed, and
        comment the blocker (surfaced for the owner, never silently dropped)."""
        self.gh.edit_issue(
            number,
            add_labels=["status:blocked"],
            remove_labels=["status:claimed"],
        )
        self.gh.comment_issue(number, f"Blocked: {reason}")
