# src/bookieskit/orchestration/gate.py
"""Cheap wake-decision for the continuous orchestrator.

Pure logic only — the CLI gathers the inputs (a Slack Web API read + a gh
queue check) cheaply and calls these, so the expensive ``claude -p`` cycle
fires only when there is genuinely something to do.
"""


def new_ticket_waiting(newest_human_ts: str | None,
                       watermark_ts: str | None) -> bool:
    """True if a #tickets human message is newer than the watermark."""
    if newest_human_ts is None:
        return False
    if watermark_ts is None:
        return True
    return float(newest_human_ts) > float(watermark_ts)


def thread_reply_waiting(thread_messages: list[dict]) -> bool:
    """True if the NEWEST message in a design thread is from a human (the agent
    owes a reply). Slack tags bot messages with ``bot_id``. ``thread_messages``
    is oldest-first (as gh/Slack ``conversations.replies`` returns)."""
    msgs = [m for m in thread_messages if m.get("type") == "message"]
    if not msgs:
        return False
    return not msgs[-1].get("bot_id")


def _is_bot(user: dict | None) -> bool:
    return bool(user and user.get("type") == "Bot")


def pr_reply_waiting(comments: list[dict], reviews: list[dict]) -> bool:
    """True if the newest actionable event on a PR is from a human (the loop
    owes a response). Actionable = any conversation comment, or a review that
    requested changes or carries a non-empty body. A bare APPROVED/COMMENTED
    review with no text is ignored, so a plain approval never triggers a reply.
    Stateless: the App's own reply is authored by a Bot and becomes the newest
    event, flipping the state off — no watermark needed.
    ``comments`` carry ``created_at``; ``reviews`` carry ``submitted_at``. Both
    timestamps are ISO-8601 UTC (lexically sortable)."""
    events: list[tuple[str, bool]] = []
    for c in comments:
        events.append((c.get("created_at", ""), _is_bot(c.get("user"))))
    for r in reviews:
        body = (r.get("body") or "").strip()
        if r.get("state") == "CHANGES_REQUESTED" or body:
            events.append((r.get("submitted_at", ""), _is_bot(r.get("user"))))
    if not events:
        return False
    events.sort(key=lambda e: e[0])
    return not events[-1][1]  # newest event authored by a human


def should_run(*, queue_actionable: bool, new_ticket: bool,
               designing_reply: bool, pr_reply: bool = False) -> bool:
    """Wake the agent iff any wake-signal is set."""
    return bool(queue_actionable or new_ticket or designing_reply or pr_reply)
