"""Parser tests for the football booking (cards) markets (1X2 + Over/Under).

Increment 2 of #19: #22 mapped Betway; #28 extends to BetPawa, SportyBet,
MSport and Bet9ja. Every assertion runs against real captured fixtures —
market ids and outcome labels were lifted from those payloads, never guessed.

Live-evidence capture (#28): a single in-region prematch capture of the
BetPawa tournament-258194 World Cup fixture *Norway–France* (BetPawa event
35429065 / SR 66457014), saved per book as ``wc_nf.json``:

  - BetPawa: "Team With Most Bookings 3 Way - FT" (id 1096774) and "Total
    Bookings Over/Under - FT" (id 1096764). The 1H variants (1096775/1096765)
    and the team-specific Home/Away totals are distinct ids, left unmapped.
  - SportyBet: "Bookings 1X2" (id 136) and "Bookings - Over/Under" (id 139,
    the card-count O/U — NOT id 138 "Total Booking Points").
  - MSport: "Booking 1x2" (id 136) and "Bookings O/U" (id 139).
  - Bet9ja: S_1X2BOOK ("Cards - 1X2", most bookings FT) and S_OUBOOK
    ("Cards - Over/Under", total bookings FT). The 1st-half (S_*1T) and
    team-specific (S_OUBOOKHOME/AWAY) keys are distinct, left unmapped.

Still unmapped, deferred rather than guessed:
  - SportPesa: booking odds need a session cookie the harness can't supply
    offline; owner previously flagged it as not offering corner/booking → —.
  - Betika: the no-cookie market-list fetch is truncated (tracked by #31);
    its booking column lands once #31 restores the full fetch.
"""

import json
from pathlib import Path

from bookieskit.markets.parser import parse_markets

_FIXTURES = Path(__file__).parent / "fixtures" / "event_info"
_WC = "wc_nf.json"


def _markets(book: str, fixture: str = "prematch.json"):
    payload = json.loads(
        (_FIXTURES / book / fixture).read_text(encoding="utf-8")
    )
    return parse_markets(payload, platform=book)


# --- Betway booking 1X2 + Over/Under (#22, unchanged) ----------------------


def test_betway_1x2_bookings_ft():
    # Market name "Booking 1X2"; team-name outcomes resolved via
    # __HOME__/Draw/__AWAY__ sentinels.
    markets = _markets("betway", "2way_handicap_ft.json")
    m = next(m for m in markets if m.canonical_id == "1x2_bookings_ft")
    assert m.lines is None
    names = {o.canonical_name: o for o in m.outcomes}
    assert set(names) == {"home", "draw", "away"}
    # From the fixture: home(CF Cruz Azul)=3.2, Draw=5.0, away(Pumas)=1.65.
    assert names["home"].odds == 3.2
    assert names["draw"].odds == 5.0
    assert names["away"].odds == 1.65


def test_betway_over_under_bookings_ft():
    # Market name "Total Bookings" (card count, NOT "Total Booking Points").
    markets = _markets("betway", "2way_handicap_ft.json")
    m = next(m for m in markets if m.canonical_id == "over_under_bookings_ft")
    assert m.outcomes == []
    assert m.lines is not None
    # From the fixture: line 5.5 has Over=1.58, Under=2.05.
    assert 5.5 in m.lines
    line = {o.canonical_name: o for o in m.lines[5.5]}
    assert set(line) == {"over", "under"}
    assert line["over"].odds == 1.58
    assert line["under"].odds == 2.05


def test_betway_does_not_map_total_booking_points():
    # "Total Booking Points" (points-scoring variant) must NOT be resolved
    # as over_under_bookings_ft — only the card-count "Total Bookings" is.
    markets = _markets("betway", "2way_handicap_ft.json")
    booking_ou = [
        m for m in markets if m.canonical_id == "over_under_bookings_ft"
    ]
    # Exactly one O/U bookings market (from "Total Bookings"), not two.
    assert len(booking_ou) == 1
    # Card-count lines (3.5–7.5) only — the points-scoring "Total Booking
    # Points" lines (35.5/45.5/55.5/65.5/75.5) must not leak in. (Both would
    # merge into this one market since it's keyed by betway_id, so a count
    # check alone is insufficient — assert a points line is absent.)
    lines = booking_ou[0].lines or {}
    assert 45.5 not in lines
    assert max(lines) <= 7.5


# --- BetPawa booking 1X2 + Over/Under (#28) --------------------------------


def test_betpawa_1x2_bookings_ft():
    # Market id 1096774 "Team With Most Bookings 3 Way - FT"; outcomes 1/X/2.
    markets = _markets("betpawa", _WC)
    m = next(m for m in markets if m.canonical_id == "1x2_bookings_ft")
    assert m.lines is None
    names = {o.canonical_name: o for o in m.outcomes}
    assert set(names) == {"home", "draw", "away"}
    # From the fixture: 1=2.53, X=2.89, 2=2.78.
    assert names["home"].odds == 2.53
    assert names["draw"].odds == 2.89
    assert names["away"].odds == 2.78


def test_betpawa_over_under_bookings_ft():
    # Market id 1096764 "Total Bookings Over/Under - FT"; raw handicap ÷4
    # gives the line (handicap 10 → 2.5).
    markets = _markets("betpawa", _WC)
    m = next(m for m in markets if m.canonical_id == "over_under_bookings_ft")
    assert m.outcomes == []
    assert m.lines is not None
    assert 2.5 in m.lines
    line = {o.canonical_name: o for o in m.lines[2.5]}
    assert set(line) == {"over", "under"}
    assert line["over"].odds == 2.29
    assert line["under"].odds == 1.51


# --- SportyBet booking 1X2 + Over/Under (#28) ------------------------------


def test_sportybet_1x2_bookings_ft():
    # Market id 136 "Bookings 1X2"; Home/Draw/Away descs.
    markets = _markets("sportybet", _WC)
    m = next(m for m in markets if m.canonical_id == "1x2_bookings_ft")
    assert m.lines is None
    names = {o.canonical_name: o for o in m.outcomes}
    assert set(names) == {"home", "draw", "away"}
    # From the fixture: Home=2.50, Draw=2.85, Away=2.75.
    assert names["home"].odds == 2.50
    assert names["draw"].odds == 2.85
    assert names["away"].odds == 2.75


def test_sportybet_over_under_bookings_ft():
    # Market id 139 "Bookings - Over/Under" (card count, NOT id 138 "Total
    # Booking Points"). Over/Under descs carry the line ("Over 2.5").
    markets = _markets("sportybet", _WC)
    m = next(m for m in markets if m.canonical_id == "over_under_bookings_ft")
    assert m.outcomes == []
    assert m.lines is not None
    assert 2.5 in m.lines
    line = {o.canonical_name: o for o in m.lines[2.5]}
    assert set(line) == {"over", "under"}
    assert line["over"].odds == 2.35
    assert line["under"].odds == 1.53


def test_sportybet_does_not_map_total_booking_points():
    # id 138 "Total Booking Points" (points variant) must NOT resolve as
    # over_under_bookings_ft — only the id-139 card-count O/U is mapped.
    markets = _markets("sportybet", _WC)
    booking_ou = [
        m for m in markets if m.canonical_id == "over_under_bookings_ft"
    ]
    assert len(booking_ou) == 1
    lines = booking_ou[0].lines or {}
    # Points lines (5.5/15.5/25.5/35.5/45.5) must not leak in.
    assert 25.5 not in lines
    assert max(lines) <= 4.5


# --- MSport booking 1X2 + Over/Under (#28) ---------------------------------


def test_msport_1x2_bookings_ft():
    # Market id 136 "Booking 1x2"; Home/Draw/Away descriptions.
    markets = _markets("msport", _WC)
    m = next(m for m in markets if m.canonical_id == "1x2_bookings_ft")
    assert m.lines is None
    names = {o.canonical_name: o for o in m.outcomes}
    assert set(names) == {"home", "draw", "away"}
    # From the fixture: Home=2.55, Draw=2.90, Away=2.80.
    assert names["home"].odds == 2.55
    assert names["draw"].odds == 2.90
    assert names["away"].odds == 2.80


def test_msport_over_under_bookings_ft():
    # Market id 139 "Bookings O/U"; Over/Under descs carry the line.
    markets = _markets("msport", _WC)
    m = next(m for m in markets if m.canonical_id == "over_under_bookings_ft")
    assert m.outcomes == []
    assert m.lines is not None
    assert 2.5 in m.lines
    line = {o.canonical_name: o for o in m.lines[2.5]}
    assert set(line) == {"over", "under"}
    assert line["over"].odds == 2.30
    assert line["under"].odds == 1.51


# --- Bet9ja booking 1X2 + Over/Under (#28) ---------------------------------


def test_bet9ja_1x2_bookings_ft():
    # S_1X2BOOK "Cards - 1X2" (most bookings, FT). Suffixes 1/X/2. The
    # 1st-half variant S_1X2BOOK1T is a distinct key and must not merge.
    markets = _markets("bet9ja", _WC)
    m = next(m for m in markets if m.canonical_id == "1x2_bookings_ft")
    assert m.lines is None
    names = {o.canonical_name: o for o in m.outcomes}
    assert set(names) == {"home", "draw", "away"}
    # From the fixture: S_1X2BOOK_1=2.47, _X=3.01, _2=2.76.
    assert names["home"].odds == 2.47
    assert names["draw"].odds == 3.01
    assert names["away"].odds == 2.76


def test_bet9ja_over_under_bookings_ft():
    # S_OUBOOK "Cards - Over/Under" (total bookings, FT). Suffixes O/U.
    # S_OUBOOK1T (1st half) / S_OUBOOKHOME / S_OUBOOKAWAY are distinct keys.
    markets = _markets("bet9ja", _WC)
    m = next(m for m in markets if m.canonical_id == "over_under_bookings_ft")
    assert m.outcomes == []
    assert m.lines is not None
    assert 2.5 in m.lines
    line = {o.canonical_name: o for o in m.lines[2.5]}
    assert set(line) == {"over", "under"}
    # From the fixture: S_OUBOOK@2.5_O=2.84, @2.5_U=1.36.
    assert line["over"].odds == 2.84
    assert line["under"].odds == 1.36


def test_bet9ja_bookings_ou_excludes_team_and_half_variants():
    # Only the full-match S_OUBOOK is the over_under_bookings_ft market.
    # The team-specific (S_OUBOOKHOME/AWAY) and 1st-half (S_OUBOOK1T) keys
    # are unmapped and must not produce a second O/U bookings market.
    markets = _markets("bet9ja", _WC)
    booking_ou = [
        m for m in markets if m.canonical_id == "over_under_bookings_ft"
    ]
    assert len(booking_ou) == 1


# --- No-hallucination guard: fixtures without booking data resolve none ----


def test_old_prematch_fixtures_have_no_booking_markets():
    # The pre-#28 prematch.json captures (different matches) carry no booking
    # odds at all. Even with the registry now mapping booking ids, parsing
    # them must yield zero booking markets — proves resolution is driven by
    # the payload, never hallucinated from the mapping table.
    for book in ("betpawa", "sportybet", "bet9ja", "msport"):
        markets = _markets(book)
        booking = {
            m.canonical_id
            for m in markets
            if m.canonical_id in {"1x2_bookings_ft", "over_under_bookings_ft"}
        }
        assert booking == set(), f"{book} hallucinated booking markets"
