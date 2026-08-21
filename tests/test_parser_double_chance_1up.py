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

Left unmapped for the other five books — but the evidence is **not** equally
strong, and the difference matters. A scan that surfaces no 1UP market of any
kind proves nothing about the double-chance variant; only a scan that clearly
sees the book's own 1UP markets can be read as "the DC variant is absent":

  - MSport — **not offered**. Live probe: 10 events, 7,749 distinct market
    strings, ``1x2 - 1UP`` present, no double-chance variant.
  - Betway — **not offered**. Live probe: 10 events, 34,605 strings,
    ``1X2 (1Up)`` present, no double-chance variant.
  - Bet9ja — **offered**, key ``S_DC1X21`` ("DC 1X2 1UP"). Its outcome
    suffixes are counter-intuitive and were taken verbatim from Bet9ja's own
    ``D.TRANS`` catalogue (``bet9ja/dc_1x2_1up_catalogue.json``):
    ``11`` = "1X - 1UP", ``X1`` = "X2 - 1UP", ``121`` = "12 - 1UP".
    **``X1`` means X2, not 1X** — transcribing these by analogy rather than
    from the payload would silently swap two selections.
  - Betika — **unknown**, not absent. Its scans show no 1UP market at all
    (live: 10 events but only 210 distinct strings), which is the signature
    of the truncated no-cookie market fetch tracked by #31 rather than
    evidence of absence. Re-probe once #31 lands.
  - SportPesa — **unknown**. Not probed; the market list needs an Akamai
    session cookie the offline harness cannot supply, consistent with its
    other ``—`` rows.
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


# --- Bet9ja ----------------------------------------------------------------


def _bet9ja_catalogue():
    return json.loads(
        (_FIXTURES / "bet9ja" / "dc_1x2_1up_catalogue.json").read_text(
            encoding="utf-8"
        )
    )


def test_bet9ja_declares_dc_1x2_1up_in_its_catalogue():
    """Bet9ja's D.TRANS catalogue is the authority for key + labels.

    The market was missed on the first pass because D.TRANS entries are
    ``M#``-prefixed, so a regex scanning for bare quoted ``"S_..."`` keys
    never saw it.
    """
    trans = _bet9ja_catalogue()["D"]["TRANS"]
    assert trans["M#S_DC1X21"]["NAME"] == "DC 1X2 1UP"
    assert trans["M#S_DC1X21_11"] == "1X - 1UP"
    assert trans["M#S_DC1X21_X1"] == "X2 - 1UP"
    assert trans["M#S_DC1X21_121"] == "12 - 1UP"


def test_bet9ja_dc_1up_outcome_suffixes_are_not_the_obvious_ones():
    """Guard the swap hazard: X1 is X2 (draw_away), NOT 1X (home_draw)."""
    from bookieskit.markets.registry import MarketRegistry

    m = MarketRegistry().get_by_canonical("double_chance_1up_ft")
    assert m.bet9ja_key == "S_DC1X21"
    assert m.outcomes["home_draw"].bet9ja == "11"
    assert m.outcomes["draw_away"].bet9ja == "X1"
    assert m.outcomes["home_away"].bet9ja == "121"


def test_bet9ja_dc_1up_parses_from_odds_keys():
    """End-to-end parse using Bet9ja's real key format.

    The odds values are synthetic: S_DC1X21 is declared in Bet9ja's
    catalogue but was priced on 0 of 160 live events sampled on
    2026-08-21, so no capture carries real prices for it yet. The KEYS are
    real, which is what this test pins -- that ``S_DC1X21_<suffix>``
    resolves to the right canonical outcome.
    """
    payload = {
        "R": "OK",
        "D": {
            "O": {
                "S_DC1X21_11": 1.22,
                "S_DC1X21_X1": 1.55,
                "S_DC1X21_121": 1.08,
            }
        },
    }
    markets = parse_markets(payload, platform="bet9ja")
    m = next(m for m in markets if m.canonical_id == "double_chance_1up_ft")
    names = {o.canonical_name: o.odds for o in m.outcomes}
    assert names == {"home_draw": 1.22, "draw_away": 1.55, "home_away": 1.08}
