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


def should_run(*, queue_actionable: bool, new_ticket: bool,
               designing_reply: bool) -> bool:
    """Wake the agent iff any wake-signal is set."""
    return bool(queue_actionable or new_ticket or designing_reply)
