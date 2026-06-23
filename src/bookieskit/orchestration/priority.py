"""Pick the next work item from the open-issue queue.

Pure functions over the ``gh issue list --json number,title,body,labels,state``
issue-dict shape (``labels`` is a list of ``{"name": ...}``). The orchestrator
CLI's ``next`` subcommand calls ``next_work_item``; the orchestrate skill acts
on its result.
"""

STREAM_ORDER: tuple[str, ...] = (
    "stream:directed",
    "stream:maintenance",
    "stream:expansion",
    "stream:capability",
)
# Statuses that mean an issue is NOT actionable this cycle: already being
# worked (claimed), awaiting owner review (in-review), or parked (blocked).
# Skipping all three stops the loop re-picking an item it has already handled.
_INACTIVE_STATUSES = frozenset(
    {"status:claimed", "status:in-review", "status:blocked"}
)


def _label_names(issue: dict) -> set[str]:
    return {lb.get("name") for lb in issue.get("labels", [])}


def _stream_rank(issue: dict) -> int:
    names = _label_names(issue)
    for index, stream in enumerate(STREAM_ORDER):
        if stream in names:
            return index
    return len(STREAM_ORDER)  # unknown stream sorts last


def next_work_item(open_issues: list[dict]) -> dict | None:
    """Return the top actionable open issue, or None.

    Skips issues in any inactive status (claimed / in-review / blocked); orders
    the rest by STREAM_ORDER index then by issue number ascending (FIFO — lowest
    number is oldest).
    """
    candidates = [
        i for i in open_issues
        if not (_label_names(i) & _INACTIVE_STATUSES)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda i: (_stream_rank(i), i["number"]))
    return candidates[0]
