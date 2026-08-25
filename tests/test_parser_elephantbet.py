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


# --- Soccer breadth increment: corners, bookings, per-team totals ----------
# Ids and labels lifted from the same captured fixture. All five reuse
# outcome vocabulary already in the registry ("Acima"/"Abaixo", "1"/"X"/"2"),
# so only the market ids are new.


def test_elephantbet_over_under_corners_ft():
    # id=107 "Total de cantos DO JOGO", parameterized by sbv.
    m = next(m for m in _markets() if m.canonical_id == "over_under_corners_ft")
    assert m.lines is not None
    assert 10.5 in m.lines
    by = {o.canonical_name: o.odds for o in m.lines[10.5]}
    assert by == {"over": 1.95, "under": 1.65}


def test_elephantbet_over_under_bookings_ft():
    # id=73 "Total Cartões Partida".
    m = next(
        m for m in _markets() if m.canonical_id == "over_under_bookings_ft"
    )
    assert m.lines is not None
    by = {o.canonical_name: o.odds for o in m.lines[4.5]}
    assert by == {"over": 1.90, "under": 1.75}


def test_elephantbet_home_and_away_over_under_ft_are_distinct():
    # id=353 "Totais Equipa da casa" / id=352 "Totais Equipa de fora".
    # Both use Acima/Abaixo, so a mapping that crossed the two market ids
    # would silently swap home and away totals.
    ms = _markets()
    home = next(m for m in ms if m.canonical_id == "home_over_under_ft")
    away = next(m for m in ms if m.canonical_id == "away_over_under_ft")
    assert home.lines is not None and away.lines is not None
    assert {o.canonical_name for o in home.lines[0.5]} == {"over", "under"}
    # From the fixture: home Acima 0.5 = 1.40, away Acima 1.5 = 1.80.
    assert {o.canonical_name: o.odds for o in home.lines[0.5]}["over"] == 1.40
    assert {o.canonical_name: o.odds for o in away.lines[1.5]}["over"] == 1.80


def test_elephantbet_1x2_corners_ft():
    # id=111 "QUAL DAS EQUIPAS TERÁ MAIS CANTOS?" — most-corners 1X2,
    # unparameterized (no sbv on its outcomes).
    m = next(m for m in _markets() if m.canonical_id == "1x2_corners_ft")
    assert m.lines is None
    by = {o.canonical_name: o.odds for o in m.outcomes}
    assert by == {"home": 2.20, "draw": 8.50, "away": 1.85}


def test_elephantbet_does_not_map_three_way_handicap():
    """id=27 "Handicap" is the 3-way European variant (has an X outcome).

    Only the 2-way Asian handicap is in the canonical set, and ElephantBet's
    id=23 needs per-outcome sign normalisation (home sbv=+1.5 pairs with away
    sbv=-1.5), which the parser does not do — deferred to its own increment.
    Neither must resolve as 2way_handicap_ft in the meantime.
    """
    assert not [
        m for m in _markets() if m.canonical_id == "2way_handicap_ft"
    ]


# --- Live feed --------------------------------------------------------------


def test_elephantbet_live_fixture_id_fields_match_documented_shape():
    """Guards the brid/obrid trap against a real committed live capture.

    On the live feed `brid` is an 18-digit BtoBet snowflake and the
    SportRadar id is in `obrid`. Half the entries have no `obrid` at all,
    so `extract_event_ids` must yield None for those rather than emitting
    the BtoBet id as a provider id.
    """
    from bookieskit.matching import extract_event_ids

    live = json.loads(
        (_FIXTURES / "elephantbet" / "live.json").read_text(encoding="utf-8")
    )
    assert live, "live fixture is empty"
    # Length is NOT a usable discriminator: virtual events carry 7-digit
    # brids that look like SportRadar ids. In-play state is.
    assert all(
        any(k in e for k in ("ms", "mt", "sc", "ss")) for e in live
    ), "every live entry must carry in-play state"
    for entry in live:
        sr = extract_event_ids(entry, platform="elephantbet").sportradar
        if entry.get("obrid"):
            assert sr == str(entry["obrid"])
        else:
            assert sr is None, "must not emit the BtoBet brid as an SR id"


# --- Basketball and tennis --------------------------------------------------
# ElephantBet REUSES market ids across sports, so these must be resolved
# through the sport-scoped registry index. Verified in the captures:
#   id 4   = basketball "VENCEDOR (INCL. PROLONGAMENTO)" AND tennis
#            "Probabilidades 2-way"  -> two different canonicals
#   id 23  = soccer / basketball / tennis handicap  -> all three deferred
#   id 352 = soccer "Totais Equipa de fora" AND basketball
#            "Totais Equipa de fora (incl. prol.)"


def test_elephantbet_basketball_markets():
    m = _markets("basketball.json")  # no sport= -> flat index
    del m
    ms = parse_markets(
        json.loads(
            (_FIXTURES / "elephantbet" / "basketball.json").read_text(
                encoding="utf-8"
            )
        ),
        platform="elephantbet",
        sport="basketball",
    )
    by = {x.canonical_id: x for x in ms}
    assert "moneyline_basketball_ft" in by
    ml = by["moneyline_basketball_ft"]
    assert {o.canonical_name for o in ml.outcomes} == {"home", "away"}
    ou = by["over_under_basketball_ft"]
    assert ou.lines is not None and 221.5 in ou.lines
    assert {o.canonical_name for o in ou.lines[221.5]} == {"over", "under"}


def test_elephantbet_tennis_markets():
    ms = parse_markets(
        json.loads(
            (_FIXTURES / "elephantbet" / "tennis.json").read_text(
                encoding="utf-8"
            )
        ),
        platform="elephantbet",
        sport="tennis",
    )
    by = {x.canonical_id: x for x in ms}
    assert {o.canonical_name for o in by["moneyline_tennis_match"].outcomes} == {
        "home", "away",
    }
    games = by["over_under_games_tennis_match"]
    assert games.lines is not None and 22.5 in games.lines


def test_elephantbet_market_id_4_resolves_by_sport_not_first_wins():
    """id 4 is basketball moneyline AND tennis moneyline.

    Without the sport-scoped index one of the two would silently resolve to
    the other sport's canonical.
    """
    from bookieskit.markets.registry import MarketRegistry

    r = MarketRegistry()
    assert (
        r.get_by_platform_id("elephantbet", "4", sport="basketball").canonical_id
        == "moneyline_basketball_ft"
    )
    assert (
        r.get_by_platform_id("elephantbet", "4", sport="tennis").canonical_id
        == "moneyline_tennis_match"
    )


def test_elephantbet_basketball_does_not_leak_soccer_per_team_totals():
    """ids 352/353 exist on BOTH soccer and basketball events.

    Parsed with sport="basketball" they must not surface as the soccer
    canonicals `home_over_under_ft` / `away_over_under_ft`, which describe
    goals, not points.
    """
    ms = parse_markets(
        json.loads(
            (_FIXTURES / "elephantbet" / "basketball.json").read_text(
                encoding="utf-8"
            )
        ),
        platform="elephantbet",
        sport="basketball",
    )
    ids = {x.canonical_id for x in ms}
    assert "home_over_under_ft" not in ids
    assert "away_over_under_ft" not in ids
