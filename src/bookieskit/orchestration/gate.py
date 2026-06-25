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


# Hidden footer the loop appends to every PR reply it posts. This is what makes
# self-resolution identity-INDEPENDENT: if App-minting ever fails and the cycle
# falls back to the owner's login, its reply is authored by a User — but the
# marker still identifies it as the loop's, so the gate won't treat it as a
# human comment and re-fire forever. Kept out of the rendered text via HTML
# comment syntax.
LOOP_REPLY_MARKER = "<!-- bookieskit-loop-reply -->"


def _is_bot(user: dict | None) -> bool:
    return bool(user and user.get("type") == "Bot")


def _is_loop(user: dict | None, body: str | None) -> bool:
    """An event is the loop's own (not a human owed a reply) if it was authored
    by a Bot OR carries the loop reply marker (the fallback-identity guard)."""
    return _is_bot(user) or LOOP_REPLY_MARKER in (body or "")


def pr_reply_waiting(comments: list[dict], reviews: list[dict]) -> bool:
    """True if the newest actionable event on a PR is from a human (the loop
    owes a response). Actionable = any conversation comment, or a review that
    requested changes or carries a non-empty body. A bare APPROVED/COMMENTED
    review with no text is ignored, so a plain approval never triggers a reply.
    Stateless: the loop's own reply (a Bot, or any comment carrying
    LOOP_REPLY_MARKER) becomes the newest event, flipping the state off — no
    watermark needed.
    ``comments`` carry ``created_at``; ``reviews`` carry ``submitted_at``. Both
    timestamps are ISO-8601 UTC (lexically sortable)."""
    events: list[tuple[str, bool]] = []
    for c in comments:
        events.append(
            (c.get("created_at", ""), _is_loop(c.get("user"), c.get("body")))
        )
    for r in reviews:
        body = (r.get("body") or "").strip()
        if r.get("state") == "CHANGES_REQUESTED" or body:
            events.append(
                (r.get("submitted_at", ""), _is_loop(r.get("user"), r.get("body")))
            )
    if not events:
        return False
    events.sort(key=lambda e: e[0])
    return not events[-1][1]  # newest event authored by a human


def should_run(*, queue_actionable: bool, new_ticket: bool,
               designing_reply: bool, pr_reply: bool = False) -> bool:
    """Wake the agent iff any wake-signal is set."""
    return bool(queue_actionable or new_ticket or designing_reply or pr_reply)
