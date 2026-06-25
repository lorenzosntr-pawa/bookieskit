"""Parser tests for the football corner markets (1X2 + Over/Under).

All assertions run against the real captured fixtures — the market ids and
outcome labels were lifted from those payloads, never guessed. Coverage is
the five bookmakers whose captured fixtures expose corner markets: BetPawa,
SportyBet, MSport, Bet9ja and Betway (Betway's corner markets live in its
``2way_handicap_ft.json`` capture, not ``prematch.json``). SportPesa and
Betika have no corner data in their fixtures, so their mappings are left
empty (``—`` in the coverage matrix) pending a dedicated in-region probe.
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


# --- 1X2 corners (home/draw/away) ------------------------------------------


def test_betpawa_1x2_corners_ft():
    # marketType.id=1096787 "Corner Count 1X2 - FT", prices 1/X/2.
    markets = _markets("betpawa")
    m = next(m for m in markets if m.canonical_id == "1x2_corners_ft")
    assert m.lines is None
    names = {o.canonical_name: o for o in m.outcomes}
    assert set(names) == {"home", "draw", "away"}
    # From the fixture: 1=1.71, X=7.69, 2=2.48.
    assert names["home"].odds == 1.71
    assert names["home"].platform_name == "1"
    assert names["draw"].odds == 7.69
    assert names["away"].odds == 2.48


def test_sportybet_1x2_corners_ft():
    # id=162 "Corners 1X2", outcomes Home/Draw/Away.
    markets = _markets("sportybet")
    m = next(m for m in markets if m.canonical_id == "1x2_corners_ft")
    assert m.lines is None
    assert {o.canonical_name for o in m.outcomes} == {"home", "draw", "away"}


def test_msport_1x2_corners_ft():
    # id=162 "Corner 1x2", outcomes Home/Draw/Away.
    markets = _markets("msport")
    m = next(m for m in markets if m.canonical_id == "1x2_corners_ft")
    assert m.lines is None
    assert {o.canonical_name for o in m.outcomes} == {"home", "draw", "away"}


def test_bet9ja_1x2_corners_ft():
    # Key S_TEAMCORNER ("Corners - 1X2", most corners FT) — odds keys
    # S_TEAMCORNER_1/_X/_2. PR #20 left this None; #22 maps it after the
    # fixture metadata (D.MK/D.TRANS) confirmed it as full-time 1X2.
    markets = _markets("bet9ja")
    m = next(m for m in markets if m.canonical_id == "1x2_corners_ft")
    assert m.lines is None
    names = {o.canonical_name: o for o in m.outcomes}
    assert set(names) == {"home", "draw", "away"}
    # From the fixture: 1=1.7, X=8.3, 2=2.26.
    assert names["home"].odds == 1.7
    assert names["draw"].odds == 8.3
    assert names["away"].odds == 2.26


def test_betway_1x2_corners_ft():
    # Market name "Corner 1X2" in the 2way_handicap_ft.json capture;
    # team-name outcomes resolved via __HOME__/Draw/__AWAY__ sentinels.
    markets = _markets("betway", "2way_handicap_ft.json")
    m = next(m for m in markets if m.canonical_id == "1x2_corners_ft")
    assert m.lines is None
    names = {o.canonical_name: o for o in m.outcomes}
    assert set(names) == {"home", "draw", "away"}
    # From the fixture: home(CF Cruz Azul)=1.29, Draw=9.6, away(Pumas)=4.2.
    assert names["home"].odds == 1.29
    assert names["draw"].odds == 9.6
    assert names["away"].odds == 4.2


# --- Over/Under corners (parameterized) ------------------------------------


def test_betpawa_over_under_corners_ft():
    # marketType.id=1096783 "Total Corners Over/Under - FT".
    # handicap field is line*4: 30->7.5, 34->8.5, ...
    markets = _markets("betpawa")
    m = next(m for m in markets if m.canonical_id == "over_under_corners_ft")
    assert m.outcomes == []
    assert m.lines is not None
    assert 7.5 in m.lines
    line = {o.canonical_name: o for o in m.lines[7.5]}
    assert set(line) == {"over", "under"}
    # From the fixture: Over=1.24, Under=3.19 at line 7.5.
    assert line["over"].odds == 1.24
    assert line["under"].odds == 3.19


def test_sportybet_over_under_corners_ft():
    # id=166 "Corners - Over/Under", specifier total=N, desc "Over 7.5".
    markets = _markets("sportybet")
    m = next(m for m in markets if m.canonical_id == "over_under_corners_ft")
    assert m.outcomes == []
    assert m.lines is not None
    assert any(
        {"over", "under"}.issubset({o.canonical_name for o in outs})
        for outs in m.lines.values()
    )


def test_msport_over_under_corners_ft():
    # id=166 "Corners O/U", specifiers total=N, description "Over 7.5".
    markets = _markets("msport")
    m = next(m for m in markets if m.canonical_id == "over_under_corners_ft")
    assert m.outcomes == []
    assert m.lines is not None
    assert any(
        {"over", "under"}.issubset({o.canonical_name for o in outs})
        for outs in m.lines.values()
    )


def test_bet9ja_over_under_corners_ft():
    # Odds keys S_OUCORNERS@<line>_O / _U (lines 8.5/9.5/10.5 in fixture).
    markets = _markets("bet9ja")
    m = next(m for m in markets if m.canonical_id == "over_under_corners_ft")
    assert m.outcomes == []
    assert m.lines is not None
    assert any(
        {"over", "under"}.issubset({o.canonical_name for o in outs})
        for outs in m.lines.values()
    )


def test_betway_over_under_corners_ft():
    # Market name "Total Corners" (parameterized) in 2way_handicap_ft.json.
    markets = _markets("betway", "2way_handicap_ft.json")
    m = next(m for m in markets if m.canonical_id == "over_under_corners_ft")
    assert m.outcomes == []
    assert m.lines is not None
    # From the fixture: line 9.5 has Over=1.87, Under=1.71.
    assert 9.5 in m.lines
    line = {o.canonical_name: o for o in m.lines[9.5]}
    assert set(line) == {"over", "under"}
    assert line["over"].odds == 1.87
    assert line["under"].odds == 1.71


# --- Books without captured corner data resolve nothing --------------------


def test_books_without_corner_fixtures_have_no_corner_markets():
    # SportPesa/Betika captures genuinely carry no corner data. Betway's
    # PREMATCH capture also lacks corners (its corner markets live in
    # 2way_handicap_ft.json), so parsing prematch.json must still resolve
    # none — guards against hallucinating corners from a corner-less event.
    for book in ("betway", "sportpesa", "betika"):
        markets = _markets(book)
        corner_ids = {
            m.canonical_id
            for m in markets
            if m.canonical_id in {"1x2_corners_ft", "over_under_corners_ft"}
        }
        assert corner_ids == set(), (
            f"{book} unexpectedly resolved corner markets: {corner_ids}"
        )
