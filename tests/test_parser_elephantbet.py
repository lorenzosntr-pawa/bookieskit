"""Parser tests for ElephantBet core soccer markets.

Ids and labels lifted from the captured fixture, never guessed:
  1X2 = 3, Over/Under = 29, BTTS = 7, Double Chance = 17.
Over/Under is parameterized by the outcome's `sbv` field, so a single
market id carries every line.
"""

import json
from pathlib import Path

from bookieskit.markets.parser import parse_markets

_FIXTURES = Path(__file__).parent / "fixtures" / "event_info"


def _markets(fixture: str = "prematch.json"):
    payload = json.loads(
        (_FIXTURES / "elephantbet" / fixture).read_text(encoding="utf-8")
    )
    return parse_markets(payload, platform="elephantbet")


def test_elephantbet_1x2_ft():
    m = next(m for m in _markets() if m.canonical_id == "1x2_ft")
    assert m.lines is None
    assert {o.canonical_name for o in m.outcomes} == {"home", "draw", "away"}
    assert all(isinstance(o.odds, float) for o in m.outcomes)
    # Pin the actual home price ("3.96" in the fixture) so a units or
    # string-coercion regression (e.g. odds landing as "3.96" instead of
    # 3.96, or a misplaced decimal) is caught.
    home = next(o for o in m.outcomes if o.canonical_name == "home")
    assert home.odds == 3.96


def test_elephantbet_double_chance_ft():
    m = next(m for m in _markets() if m.canonical_id == "double_chance_ft")
    assert {o.canonical_name for o in m.outcomes} == {
        "home_draw", "home_away", "draw_away",
    }


def test_elephantbet_btts_ft():
    m = next(m for m in _markets() if m.canonical_id == "btts_ft")
    assert {o.canonical_name for o in m.outcomes} == {"yes", "no"}


def test_elephantbet_over_under_ft_is_parameterized_by_sbv():
    m = next(m for m in _markets() if m.canonical_id == "over_under_ft")
    assert m.lines is not None
    assert 2.5 in m.lines
    names = {o.canonical_name for o in m.lines[2.5]}
    assert names == {"over", "under"}
