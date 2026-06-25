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


def test_inactive_statuses_are_skipped():
    # claimed / in-review / blocked are all NOT actionable — the loop must not
    # re-pick an item it has already claimed, sent to review, or parked.
    for status in ("status:claimed", "status:in-review", "status:blocked"):
        issues = [
            _issue(1, "stream:directed", status),  # higher priority but inactive
            _issue(2, "stream:maintenance"),
        ]
        assert next_work_item(issues)["number"] == 2, status


def test_in_review_item_is_not_repicked():
    # Regression: a directed item left in-review (claimed dropped) must NOT be
    # returned again, or the next cycle would build a duplicate.
    issues = [_issue(8, "stream:directed", "status:in-review")]
    assert next_work_item(issues) is None


def test_unknown_stream_sorts_last():
    issues = [
        _issue(1),  # no stream label
        _issue(2, "stream:capability"),
    ]
    assert next_work_item(issues)["number"] == 2


def test_none_when_empty_or_all_claimed():
    assert next_work_item([]) is None
    assert next_work_item([_issue(1, "stream:directed", "status:claimed")]) is None


def test_designing_items_are_not_built():
    issues = [_issue(1, "stream:directed", "status:designing"),
              _issue(2, "stream:maintenance")]
    assert next_work_item(issues)["number"] == 2  # designing skipped


def test_ready_items_are_buildable():
    issues = [_issue(5, "stream:directed", "status:ready")]
    assert next_work_item(issues)["number"] == 5  # ready is actionable
