"""Unit tests for bookieskit.event_info — pure-data, bound to captured fixtures."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bookieskit.event_info import (
    LiveInfo,
    Mode,
    Participants,
    extract_kickoff,
    extract_live_info,
    extract_participants,
    is_live_now,
)

FIXTURES = Path(__file__).parent / "fixtures" / "event_info"


def _load(platform: str, phase: str) -> dict:
    with open(FIXTURES / platform / f"{phase}.json", encoding="utf-8") as f:
        return json.load(f)


def test_dataclasses_construct_with_all_none():
    li = LiveInfo()
    assert li.minute is None
    assert li.period is None
    assert li.score_home is None
    assert li.score_away is None
    p = Participants()
    assert p.home is None
    assert p.away is None


def test_dataclasses_are_frozen():
    li = LiveInfo()
    with pytest.raises(AttributeError):
        li.minute = 5  # type: ignore[misc]


def test_mode_alias_is_literal():
    # Literal has no meaningful runtime identity, but get_args() exposes
    # its parameters — that's the strongest check available at runtime.
    from typing import get_args
    assert set(get_args(Mode)) == {"prematch", "live"}


def test_is_live_now_none_returns_false():
    assert is_live_now(None) is False


def test_is_live_now_past_kickoff_returns_true():
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert is_live_now(past) is True


def test_is_live_now_future_kickoff_returns_false():
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert is_live_now(future) is False


def test_is_live_now_exactly_now_returns_true():
    # `>=` boundary — at the exact kickoff instant, treat as live.
    now = datetime.now(timezone.utc)
    assert is_live_now(now) is True


def test_betpawa_kickoff_prematch():
    d = _load("betpawa", "prematch")
    k = extract_kickoff(d, "betpawa")
    assert k == datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_betpawa_kickoff_live():
    d = _load("betpawa", "live")
    k = extract_kickoff(d, "betpawa")
    assert k == datetime(2026, 5, 6, 6, 0, 0, tzinfo=timezone.utc)


def test_betpawa_participants_prematch():
    d = _load("betpawa", "prematch")
    p = extract_participants(d, "betpawa")
    assert p.home == "Wuhan Three Towns FC"
    assert p.away == "Qingdao Hainiu FC"


def test_betpawa_participants_live():
    d = _load("betpawa", "live")
    p = extract_participants(d, "betpawa")
    assert p.home == "FC Tokyo"
    assert p.away == "JEF United Chiba"


def test_betpawa_live_info_prematch_all_none():
    d = _load("betpawa", "prematch")
    li = extract_live_info(d, "betpawa")
    assert li == LiveInfo()


def test_betpawa_live_info_live():
    d = _load("betpawa", "live")
    li = extract_live_info(d, "betpawa")
    assert li.minute == 96
    assert li.period == "Second Half"
    assert li.score_home == 0
    assert li.score_away == 3
