from bookieskit.orchestration import gate


def test_new_ticket_waiting():
    assert gate.new_ticket_waiting("1718900100.0", "1718900000.0") is True   # newer
    assert gate.new_ticket_waiting("1718900000.0", "1718900100.0") is False  # older
    assert gate.new_ticket_waiting("1718900000.0", None) is True             # no watermark yet
    assert gate.new_ticket_waiting(None, "1718900000.0") is False            # no message


def test_thread_reply_waiting_true_when_last_is_human():
    thread = [{"type": "message"}, {"type": "message", "bot_id": "B1"},
              {"type": "message"}]  # last is human -> agent owes reply
    assert gate.thread_reply_waiting(thread) is True


def test_thread_reply_waiting_false_when_last_is_bot():
    thread = [{"type": "message"}, {"type": "message", "bot_id": "B1"}]
    assert gate.thread_reply_waiting(thread) is False


def test_thread_reply_waiting_false_when_empty():
    assert gate.thread_reply_waiting([]) is False


def test_should_run_is_or_of_signals():
    assert gate.should_run(queue_actionable=True, new_ticket=False, designing_reply=False) is True
    assert gate.should_run(queue_actionable=False, new_ticket=True, designing_reply=False) is True
    assert gate.should_run(queue_actionable=False, new_ticket=False, designing_reply=True) is True
    assert gate.should_run(queue_actionable=False, new_ticket=False, designing_reply=False) is False


# ---------------------------------------------------------------------------
# pr_reply_waiting tests
# ---------------------------------------------------------------------------

def _c(ts, *, bot=False):
    return {"created_at": ts, "user": {"type": "Bot" if bot else "User"}}

def _r(ts, *, state="COMMENTED", body="", bot=False):
    return {"submitted_at": ts, "state": state, "body": body,
            "user": {"type": "Bot" if bot else "User"}}


def test_pr_reply_waiting_true_when_newest_comment_human():
    assert gate.pr_reply_waiting([_c("2026-06-25T10:00:00Z")], []) is True


def test_pr_reply_waiting_false_when_newest_is_bot_reply():
    comments = [_c("2026-06-25T10:00:00Z"), _c("2026-06-25T11:00:00Z", bot=True)]
    assert gate.pr_reply_waiting(comments, []) is False


def test_pr_reply_waiting_true_for_human_changes_requested_empty_body():
    reviews = [_r("2026-06-25T10:00:00Z", state="CHANGES_REQUESTED")]
    assert gate.pr_reply_waiting([], reviews) is True


def test_pr_reply_waiting_ignores_bare_approval():
    # a lone APPROVED review with no text is not actionable
    reviews = [_r("2026-06-25T10:00:00Z", state="APPROVED")]
    assert gate.pr_reply_waiting([], reviews) is False


def test_pr_reply_waiting_interleaves_comments_and_reviews_by_time():
    comments = [_c("2026-06-25T12:00:00Z")]                 # human, newest
    reviews = [_r("2026-06-25T11:00:00Z", body="looks ok", bot=True)]
    assert gate.pr_reply_waiting(comments, reviews) is True
    # now the bot comment is newest -> resolved
    comments2 = [_c("2026-06-25T10:00:00Z"), _c("2026-06-25T13:00:00Z", bot=True)]
    assert gate.pr_reply_waiting(comments2, reviews) is False


def test_pr_reply_waiting_false_when_empty():
    assert gate.pr_reply_waiting([], []) is False


def test_should_run_includes_pr_reply():
    assert gate.should_run(queue_actionable=False, new_ticket=False,
                           designing_reply=False, pr_reply=True) is True
    assert gate.should_run(queue_actionable=False, new_ticket=False,
                           designing_reply=False) is False  # default pr_reply=False
