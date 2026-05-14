"""Tests for the shared ``betika_first_match`` helper.

Consolidated from three near-duplicate implementations that previously
lived in ``event_info.py``, ``markets/parser.py``, and inline in
``matching/extractor.py``. These tests pin the contract that all three
call sites now share.
"""

from bookieskit.bookmakers._betika_shape import betika_first_match


def test_dict_wrapped_shape_returns_first_match():
    response = {"data": [{"match_id": "A"}, {"match_id": "B"}], "meta": {}}
    assert betika_first_match(response) == {"match_id": "A"}


def test_bare_list_shape_returns_first_match():
    response = [{"match_id": "A"}, {"match_id": "B"}]
    assert betika_first_match(response) == {"match_id": "A"}


def test_empty_dict_returns_none():
    assert betika_first_match({}) is None


def test_empty_list_returns_none():
    assert betika_first_match([]) is None


def test_dict_with_empty_data_returns_none():
    assert betika_first_match({"data": []}) is None


def test_dict_with_null_data_returns_none():
    assert betika_first_match({"data": None}) is None


def test_dict_with_non_list_data_returns_none():
    assert betika_first_match({"data": "not a list"}) is None


def test_list_with_non_dict_first_element_returns_none():
    assert betika_first_match(["not a dict"]) is None


def test_unsupported_type_returns_none():
    assert betika_first_match(None) is None
    assert betika_first_match(42) is None
    assert betika_first_match("string") is None
