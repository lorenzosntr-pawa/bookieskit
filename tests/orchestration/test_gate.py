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
