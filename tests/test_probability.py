"""Tests for true/void probability extraction across all 5 platforms."""

import json
from pathlib import Path

import pytest

from bookieskit.bookmakers._betpawa_obfuscation import decode_betpawa_probability
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


@pytest.mark.parametrize(
    "platform", ["betpawa", "sportybet", "bet9ja", "betway", "msport"]
)
@pytest.mark.parametrize("mode", ["off", "true", "with_void"])
def test_parse_markets_accepts_probability_kwarg_without_error(platform, mode):
    """The probability kwarg must be accepted by all 5 platforms in all 3
    modes — even platforms that don't support probability (Bet9ja, Betway)
    silently accept it."""
    d = _load(platform)
    parse_markets(d, platform=platform, probability=mode)


SAMPLE_BLOB = (
    "eyJ3aW4iOi0yOTA4Nzc4MTkyNTk2MTE5Njc5LCJyZWZ1bmQiOi0xNjk1MzY3MDg2NzY0MDYwNTQ0"
    "LCJrZXkiOjg1MjUyMDk3OTc5NTQzOTkzODF9"
)


def test_decode_sample_blob():
    """User-supplied sample blob decodes to a pinned (win, refund) tuple."""
    win, refund = decode_betpawa_probability(SAMPLE_BLOB)
    assert win == pytest.approx(0.393141)
    assert refund == 0.0


def test_decode_none_input():
    assert decode_betpawa_probability(None) == (None, None)


def test_decode_empty_string():
    assert decode_betpawa_probability("") == (None, None)


def test_decode_bad_base64():
    assert decode_betpawa_probability("not-base64!!!") == (None, None)


def test_decode_truncated_json():
    """Valid base64 but the decoded bytes don't parse as JSON."""
    import base64 as _b64
    truncated = _b64.urlsafe_b64encode(b'{"win":').decode()
    assert decode_betpawa_probability(truncated) == (None, None)


def test_decode_missing_key_field():
    """Without the per-bet key, neither value can be XOR'd to a real float."""
    import base64 as _b64
    payload = _b64.urlsafe_b64encode(
        b'{"win":-2908778192596119679,"refund":-1695367086764060544}'
    ).decode()
    assert decode_betpawa_probability(payload) == (None, None)


def test_decode_missing_win_field_keeps_refund():
    """If only `win` is missing, refund still decodes (per-field independence)."""
    import base64 as _b64
    payload = _b64.urlsafe_b64encode(
        b'{"refund":-1695367086764060544,"key":8525209797954399381}'
    ).decode()
    win, refund = decode_betpawa_probability(payload)
    assert win is None
    assert refund == 0.0


def test_decode_missing_refund_field_keeps_win():
    """If only `refund` is missing, win still decodes."""
    import base64 as _b64
    payload = _b64.urlsafe_b64encode(
        b'{"win":-2908778192596119679,"key":8525209797954399381}'
    ).decode()
    win, refund = decode_betpawa_probability(payload)
    assert win == pytest.approx(0.393141)
    assert refund is None


def test_decode_non_integer_values():
    """Win/refund/key as non-numeric strings should yield Nones, not raise."""
    import base64 as _b64
    payload = _b64.urlsafe_b64encode(
        b'{"win":"abc","refund":"def","key":"ghi"}'
    ).decode()
    assert decode_betpawa_probability(payload) == (None, None)
