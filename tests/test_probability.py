"""Tests for true/void probability extraction across all 5 platforms."""

import json
from pathlib import Path

import pytest

from bookieskit.markets import parse_markets
from bookieskit.markets.parser import (
    ProbabilityMode,  # noqa: F401  (Task 9 re-exports it)
)
from bookieskit.markets.types import Outcome

FIXTURES = Path(__file__).parent / "fixtures" / "event_info"


def _load(platform: str, phase: str = "prematch") -> dict:
    with open(FIXTURES / platform / f"{phase}.json", encoding="utf-8") as f:
        return json.load(f)


def test_outcome_has_optional_probability_fields():
    """Outcome gains two optional float|None fields, default None."""
    o = Outcome(canonical_name="home", odds=2.41, platform_name="1")
    assert o.true_probability is None
    assert o.void_probability is None


def test_outcome_accepts_probability_kwargs():
    o = Outcome(
        canonical_name="home",
        odds=2.41,
        platform_name="1",
        true_probability=0.395274,
        void_probability=0.0,
    )
    assert o.true_probability == 0.395274
    assert o.void_probability == 0.0


def test_outcome_is_still_frozen():
    o = Outcome(canonical_name="home", odds=2.41, platform_name="1")
    with pytest.raises(AttributeError):
        o.true_probability = 0.5  # type: ignore[misc]


def test_parse_markets_default_off_leaves_probabilities_none():
    """Default mode must not populate probabilities — backward compatible."""
    d = _load("sportybet")
    markets = parse_markets(d, platform="sportybet")
    assert markets, "expected SportyBet prematch fixture to yield markets"
    first_market = next((m for m in markets if m.canonical_id == "1x2_ft"), None)
    assert first_market is not None
    assert first_market.outcomes
    o = first_market.outcomes[0]
    assert o.true_probability is None
    assert o.void_probability is None


def test_parse_markets_accepts_probability_kwarg_without_error():
    """The new keyword must be accepted by all 5 platforms (even ones that
    don't support probability extraction yet — their parsers must silently
    accept the kwarg)."""
    d = _load("sportybet")
    parse_markets(d, platform="sportybet", probability="off")
    parse_markets(d, platform="sportybet", probability="true")
    parse_markets(d, platform="sportybet", probability="with_void")
    # Same for the other 4 platforms — they accept the kwarg.
    parse_markets(_load("msport"), platform="msport", probability="with_void")
    parse_markets(_load("betpawa"), platform="betpawa", probability="with_void")
    parse_markets(_load("betway"), platform="betway", probability="with_void")
    parse_markets(_load("bet9ja"), platform="bet9ja", probability="with_void")
