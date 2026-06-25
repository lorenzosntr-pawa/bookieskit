"""Parser tests for the football booking (cards) markets (1X2 + Over/Under).

Increment 2 of #19 (#22). All assertions run against real captured
fixtures — market ids and outcome labels were lifted from those payloads,
never guessed. The only bookmaker whose captured fixture exposes booking
markets is Betway (in its ``2way_handicap_ft.json`` capture): markets
"Booking 1X2" and "Total Bookings". Every other book's booking market is
genuinely absent from the current captures and is deferred to an in-region
live capture (increment 2b) rather than guessed:

  - Bet9ja: keys S_1X2BOOK / S_OUBOOK exist only in the global D.TRANS
    translation table; the captured event carries no booking odds.
  - SportyBet: no card/booking market in the captured prematch.json.
  - SportPesa: owner-confirmed it does not offer corner/booking markets.
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


# --- Betway booking 1X2 (home/draw/away) -----------------------------------


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


# --- Betway booking Over/Under (parameterized) -----------------------------


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


# --- Books without captured booking data resolve nothing (2b gap) ----------


def test_bet9ja_has_no_booking_markets():
    # S_1X2BOOK / S_OUBOOK are in the TRANS table but carry no odds in the
    # captured event — deferred to a live capture, not guessed.
    markets = _markets("bet9ja")
    booking_ids = {
        m.canonical_id
        for m in markets
        if m.canonical_id in {"1x2_bookings_ft", "over_under_bookings_ft"}
    }
    assert booking_ids == set()


def test_sportybet_has_no_booking_markets():
    markets = _markets("sportybet")
    booking_ids = {
        m.canonical_id
        for m in markets
        if m.canonical_id in {"1x2_bookings_ft", "over_under_bookings_ft"}
    }
    assert booking_ids == set()
