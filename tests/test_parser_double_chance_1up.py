"""Parser tests for Double Chance 1UP — Full Time.

1UP pays out early: if a team in your selection goes a goal ahead at any
point before full time, the bet settles as a winner immediately. Double
Chance 1UP applies that early-payout rule to the three double-chance
selections (1X / X2 / 12) rather than to a straight 1X2.

Coverage is **BetPawa and SportyBet only**, and every id/label below was
lifted from a real captured payload — never guessed:

  - BetPawa: marketType.id ``80000`` "Double Chance 1UP - FT", prices named
    ``1X`` / ``X2`` / ``12`` — the same outcome vocabulary as the plain
    ``Double Chance - FT`` (4693). Captured in-region as
    ``betpawa/double_chance_1up_ft.json`` (event 36552873, Sydney FC Youth –
    Rockdale Ilinden FC).
  - SportyBet: id ``60110`` "Double Chance - 1UP", outcomes
    ``Home or Draw`` / ``Home or Away`` / ``Draw or Away`` — again the same
    labels as its plain Double Chance (id 10). Present in the existing
    ``sportybet/wc_nf.json`` World Cup capture.

Deliberately left unmapped, each with live evidence rather than assumption:

  - MSport, Betway, Betika: probed live in-region over a pool of upcoming
    football events. All three expose a plain 1X2 1UP but **no** Double
    Chance 1UP.
  - Bet9ja: its full ``wc_nf.json`` / ``prematch.json`` captures carry
    ``1X2 1UP`` and team-win ``1UP/2UP`` markets but no double-chance
    variant.
  - SportPesa: not probed — the market list needs an Akamai session cookie
    the offline harness cannot supply, consistent with its other ``—`` rows.
"""

import json
from pathlib import Path

from bookieskit.markets.parser import parse_markets

_FIXTURES = Path(__file__).parent / "fixtures" / "event_info"


def _markets(book: str, fixture: str = "prematch.json"):
    payload = json.loads(
        (_FIXTURES / book / fixture).read_text(encoding="utf-8")
    )
    return parse_markets(payload, platform=book)


# --- BetPawa ---------------------------------------------------------------


def test_betpawa_double_chance_1up_ft():
    # marketType.id=80000 "Double Chance 1UP - FT"; prices 1X / X2 / 12.
    markets = _markets("betpawa", "double_chance_1up_ft.json")
    m = next(m for m in markets if m.canonical_id == "double_chance_1up_ft")
    assert m.lines is None
    names = {o.canonical_name: o for o in m.outcomes}
    assert set(names) == {"home_draw", "draw_away", "home_away"}
    # From the fixture: 1X=1.68, X2=1.16, 12=1.01.
    assert names["home_draw"].odds == 1.68
    assert names["home_draw"].platform_name == "1X"
    assert names["draw_away"].odds == 1.16
    assert names["draw_away"].platform_name == "X2"
    assert names["home_away"].odds == 1.01
    assert names["home_away"].platform_name == "12"


def test_betpawa_double_chance_1up_is_distinct_from_plain_double_chance():
    # 80000 and 4693 share an outcome vocabulary; they must stay separate
    # markets with different prices, not collapse into one another.
    markets = _markets("betpawa", "double_chance_1up_ft.json")
    one_up = next(
        m for m in markets if m.canonical_id == "double_chance_1up_ft"
    )
    plain = next(m for m in markets if m.canonical_id == "double_chance_ft")
    assert one_up.outcomes != plain.outcomes
    one_up_odds = {o.canonical_name: o.odds for o in one_up.outcomes}
    plain_odds = {o.canonical_name: o.odds for o in plain.outcomes}
    # Early payout is strictly more valuable to the punter, so 1UP prices
    # are shorter than the plain equivalents on every selection.
    for key in ("home_draw", "draw_away", "home_away"):
        assert one_up_odds[key] < plain_odds[key]


# --- SportyBet -------------------------------------------------------------


def test_sportybet_double_chance_1up_ft():
    # id=60110 "Double Chance - 1UP"; outcomes Home or Draw / Home or Away /
    # Draw or Away.
    markets = _markets("sportybet", "wc_nf.json")
    m = next(m for m in markets if m.canonical_id == "double_chance_1up_ft")
    assert m.lines is None
    names = {o.canonical_name: o for o in m.outcomes}
    assert set(names) == {"home_draw", "draw_away", "home_away"}
    # From the fixture: Home or Draw=1.77, Home or Away=1.22,
    # Draw or Away=1.14.
    assert names["home_draw"].odds == 1.77
    assert names["home_away"].odds == 1.22
    assert names["draw_away"].odds == 1.14


def test_sportybet_double_chance_1up_not_confused_with_1x2_1up():
    # 60110 (Double Chance - 1UP) and 60200 (1X2 - 1UP) are adjacent ids on
    # the same event; each must resolve to its own canonical.
    markets = _markets("sportybet", "wc_nf.json")
    dc_1up = next(
        m for m in markets if m.canonical_id == "double_chance_1up_ft"
    )
    x2_1up = next(m for m in markets if m.canonical_id == "1x2_1up_ft")
    assert {o.canonical_name for o in dc_1up.outcomes} == {
        "home_draw",
        "draw_away",
        "home_away",
    }
    assert {o.canonical_name for o in x2_1up.outcomes} == {
        "home",
        "draw",
        "away",
    }


# --- Books that do not offer it -------------------------------------------


def test_books_without_double_chance_1up_do_not_emit_it():
    # Live-probed (MSport/Betway/Betika) or full-capture-checked (Bet9ja):
    # a plain 1X2 1UP exists, a double-chance 1UP does not. Guards against a
    # future mapping accidentally binding one of these books' 1X2 1UP id.
    for book, fixture in (
        ("msport", "wc_nf.json"),
        ("bet9ja", "wc_nf.json"),
        ("betway", "wc_nf.json"),
    ):
        markets = _markets(book, fixture)
        assert not [
            m for m in markets if m.canonical_id == "double_chance_1up_ft"
        ], f"{book} unexpectedly resolved double_chance_1up_ft"
