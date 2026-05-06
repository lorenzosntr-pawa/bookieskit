"""Unit tests for bookieskit.event_info — pure-data, bound to captured fixtures."""

import json
from datetime import datetime, timezone
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
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        li.minute = 5  # type: ignore[misc]


def test_mode_alias_is_literal():
    # Mode is Literal["prematch","live"] — runtime check is type-only,
    # but the symbol must exist and be importable.
    assert Mode is not None
