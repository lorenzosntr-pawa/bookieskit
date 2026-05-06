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


def test_betpawa_live_info_mode_prematch_overrides_live_data():
    """Explicit mode='prematch' suppresses live data even on a live fixture."""
    d = _load("betpawa", "live")
    li = extract_live_info(d, "betpawa", mode="prematch")
    assert li == LiveInfo()


def test_sportybet_kickoff_prematch():
    d = _load("sportybet", "prematch")
    k = extract_kickoff(d, "sportybet")
    assert k == datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_sportybet_kickoff_live():
    d = _load("sportybet", "live")
    k = extract_kickoff(d, "sportybet")
    assert k == datetime(2026, 5, 6, 6, 0, 0, tzinfo=timezone.utc)


def test_sportybet_participants_prematch():
    d = _load("sportybet", "prematch")
    p = extract_participants(d, "sportybet")
    assert p.home == "Wuhan Three Towns FC"
    assert p.away == "Qingdao Hainiu FC"


def test_sportybet_participants_live():
    d = _load("sportybet", "live")
    p = extract_participants(d, "sportybet")
    assert p.home == "FC Tokyo"
    assert p.away == "JEF United Chiba"


def test_sportybet_live_info_prematch_all_none():
    d = _load("sportybet", "prematch")
    li = extract_live_info(d, "sportybet")
    assert li == LiveInfo()


def test_sportybet_live_info_live():
    d = _load("sportybet", "live")
    li = extract_live_info(d, "sportybet")
    assert li.minute == 90
    assert li.period == "H2"
    assert li.score_home == 0
    assert li.score_away == 3


def test_bet9ja_kickoff_prematch_auto():
    d = _load("bet9ja", "prematch")
    k = extract_kickoff(d, "bet9ja")
    assert k == datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_bet9ja_kickoff_live_auto_returns_none():
    d = _load("bet9ja", "live")
    assert extract_kickoff(d, "bet9ja") is None


def test_bet9ja_participants_prematch_auto():
    d = _load("bet9ja", "prematch")
    p = extract_participants(d, "bet9ja")
    assert p.home == "Wuhan Three Towns"
    assert p.away == "Qingdao Hainiu FC"


def test_bet9ja_participants_live_auto_returns_none():
    d = _load("bet9ja", "live")
    p = extract_participants(d, "bet9ja")
    assert p == Participants()


def test_bet9ja_live_info_prematch_auto_all_none():
    d = _load("bet9ja", "prematch")
    li = extract_live_info(d, "bet9ja")
    assert li == LiveInfo()


def test_bet9ja_live_info_live_auto():
    d = _load("bet9ja", "live")
    li = extract_live_info(d, "bet9ja")
    assert li.minute == 91
    assert li.period == "2nd Half"
    assert li.score_home == 0
    assert li.score_away == 3


def test_bet9ja_explicit_mode_live_on_prematch_fixture_yields_nones():
    """User asserts live, but fixture is prematch shape — follow the mode,
    yield Nones where the live fields are absent. Must not raise."""
    d = _load("bet9ja", "prematch")
    assert extract_kickoff(d, "bet9ja", mode="live") is None
    assert extract_participants(d, "bet9ja", mode="live") == Participants()
    assert extract_live_info(d, "bet9ja", mode="live") == LiveInfo()


def test_bet9ja_explicit_mode_prematch_on_live_fixture_yields_nones():
    """User asserts prematch, but fixture is live shape — follow the mode,
    yield Nones where the prematch fields are absent. Must not raise."""
    d = _load("bet9ja", "live")
    assert extract_kickoff(d, "bet9ja", mode="prematch") is None
    assert extract_participants(d, "bet9ja", mode="prematch") == Participants()
    assert extract_live_info(d, "bet9ja", mode="prematch") == LiveInfo()


def test_bet9ja_explicit_mode_matches_auto_on_correct_fixture():
    d_pm = _load("bet9ja", "prematch")
    d_lv = _load("bet9ja", "live")
    assert extract_kickoff(d_pm, "bet9ja", mode="prematch") == \
           extract_kickoff(d_pm, "bet9ja")
    assert extract_live_info(d_lv, "bet9ja", mode="live") == \
           extract_live_info(d_lv, "bet9ja")
