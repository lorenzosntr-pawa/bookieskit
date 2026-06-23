from bookieskit.orchestration.priority import STREAM_ORDER, next_work_item


def _issue(number, *labels):
    return {"number": number, "labels": [{"name": n} for n in labels]}


def test_stream_order_is_directed_maintenance_expansion_capability():
    assert STREAM_ORDER == (
        "stream:directed", "stream:maintenance",
        "stream:expansion", "stream:capability",
    )


def test_directed_beats_maintenance_even_if_newer():
    issues = [
        _issue(1, "stream:maintenance"),
        _issue(2, "stream:directed"),  # higher number but higher-priority stream
    ]
    assert next_work_item(issues)["number"] == 2


def test_fifo_within_a_stream_lowest_number_first():
    issues = [
        _issue(5, "stream:directed"),
        _issue(3, "stream:directed"),
        _issue(9, "stream:directed"),
    ]
    assert next_work_item(issues)["number"] == 3


def test_claimed_issues_are_skipped():
    issues = [
        _issue(1, "stream:directed", "status:claimed"),
        _issue(2, "stream:maintenance"),
    ]
    assert next_work_item(issues)["number"] == 2


def test_unknown_stream_sorts_last():
    issues = [
        _issue(1),  # no stream label
        _issue(2, "stream:capability"),
    ]
    assert next_work_item(issues)["number"] == 2


def test_none_when_empty_or_all_claimed():
    assert next_work_item([]) is None
    assert next_work_item([_issue(1, "stream:directed", "status:claimed")]) is None
