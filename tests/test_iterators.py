"""Unit tests for the iter_all_prematch_events catalogue iterators.

Each iterator on the three "complex fan-out" bookmakers (Betway, MSport,
SportPesa) wraps a multi-call enumeration of the bookmaker's full prematch
catalogue. These tests mock the underlying endpoints with `respx` and
assert each iterator yields the expected `PrematchEventStub` shapes.
"""
import pytest
import respx

from bookieskit import Betway, MSport, PrematchEventStub, SportPesa

# ---------- Betway: walks regions/leagues -> per-league events --------------


@pytest.mark.asyncio
@respx.mock
async def test_betway_iter_all_prematch_events():
    # Sport list — Betway uses a separate config domain for /cron/sports.
    respx.get(
        "https://config.betwayafrica.com/cron/sports/NG/en-US"
    ).respond(
        json={
            "sports": [
                {
                    "sportId": "soccer",
                    "name": "Soccer",
                    "sportType": "Sport",
                    "hasUpcomingEvents": True,
                    "liveInPlayCount": 0,
                },
                {
                    "sportId": "skip-me",
                    "name": "Skipped",
                    "sportType": "Sport",
                    "hasUpcomingEvents": False,  # skipped by iterator
                    "liveInPlayCount": 0,
                },
            ]
        }
    )
    # Regions / leagues for soccer
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/Feeds/RegionsAndLeagues/soccer"
    ).respond(
        json={
            "regions": [
                {
                    "regionId": "england",
                    "leagues": [
                        {"leagueId": "premier-league"},
                        {"leagueId": "fa-cup"},
                    ],
                }
            ]
        }
    )
    # Per-league events
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/BetBook/Filtered/"
    ).respond(
        json={"events": [{"eventId": 100}, {"eventId": 101}]}
    )

    stubs = []
    async with Betway(country="ng") as bw:
        async for stub in bw.iter_all_prematch_events():
            stubs.append(stub)

    # 2 leagues × 2 events each, but mock returns same payload for both
    # leagues so the dedupe by event_id keeps just 2 unique events.
    assert len(stubs) == 2
    assert {s.event_id for s in stubs} == {"100", "101"}
    assert all(s.sport_id == "soccer" for s in stubs)
    assert {s.league_id for s in stubs} <= {"premier-league", "fa-cup"}


# ---------- MSport: cursor pagination --------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_msport_iter_all_prematch_events_cursor_pagination():
    # Sports list
    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/sports"
    ).respond(
        json={
            "data": {
                "sports": [
                    {"sportId": "sr:sport:1", "sportName": "Soccer"},
                ]
            }
        }
    )
    # /sports-matches-list pages — the route handler returns different
    # data depending on whether `lastEventId` is set.
    def _handler(request):
        params = dict(request.url.params)
        last = params.get("lastEventId")
        if last is None:
            # First page: 2 tournaments, 2 events, cursor advances to ev2.
            return respx.MockResponse(
                json={
                    "data": {
                        "tournaments": [
                            {
                                "tournamentId": "TA",
                                "events": [
                                    {"eventId": "sr:match:1"},
                                    {"eventId": "sr:match:2"},
                                ],
                            },
                        ],
                        "lastEventId": "sr:match:2",
                    }
                }
            )
        if last == "sr:match:2":
            # Second page: 1 new event, cursor advances.
            return respx.MockResponse(
                json={
                    "data": {
                        "tournaments": [
                            {
                                "tournamentId": "TB",
                                "events": [{"eventId": "sr:match:3"}],
                            },
                        ],
                        "lastEventId": "sr:match:3",
                    }
                }
            )
        # Subsequent pages: empty → terminates.
        return respx.MockResponse(
            json={"data": {"tournaments": [], "lastEventId": last}}
        )

    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/sports-matches-list"
    ).mock(side_effect=_handler)

    stubs = []
    async with MSport(country="ng") as ms:
        async for stub in ms.iter_all_prematch_events():
            stubs.append(stub)

    assert {s.event_id for s in stubs} == {
        "sr:match:1", "sr:match:2", "sr:match:3"
    }
    assert {s.sport_id for s in stubs} == {"sr:sport:1"}
    assert {s.league_id for s in stubs} == {"TA", "TB"}


# ---------- SportPesa: navigation tree -> per-league events ----------------


@pytest.mark.asyncio
@respx.mock
async def test_sportpesa_iter_all_prematch_events():
    # Navigation tree
    respx.get("https://www.ke.sportpesa.com/api/navigation").respond(
        json=[
            {
                "id": 1,
                "name": "Football",
                "has_matches": True,
                "countries": [
                    {
                        "id": 61,
                        "leagues": [
                            {"id": 67600, "name": "Premier League"},
                            {"id": 67601, "name": "FA Cup"},
                        ],
                    }
                ],
            },
            {
                "id": 99,
                "name": "Inactive",
                "has_matches": False,  # skipped
                "countries": [],
            },
        ]
    )
    # Per-league events (the mock returns the same payload for any
    # leagueId; the iterator dedupes by event_id so we still see only
    # the unique ones).
    respx.get(
        "https://www.ke.sportpesa.com/api/upcoming/games"
    ).respond(json=[{"id": 8868005}, {"id": 8868006}])

    stubs = []
    async with SportPesa(country="ke", cookie="bm_sv=test") as sp:
        async for stub in sp.iter_all_prematch_events():
            stubs.append(stub)

    assert {s.event_id for s in stubs} == {"8868005", "8868006"}
    assert all(s.sport_id == "1" for s in stubs)
    # 2 unique events surfaced from 2 leagues; deduped by event_id.
    assert len(stubs) == 2


# ---------- PrematchEventStub itself ---------------------------------------


def test_prematch_event_stub_is_frozen():
    stub = PrematchEventStub(event_id="1", league_id="L", sport_id="S")
    with pytest.raises(Exception):
        stub.event_id = "2"  # type: ignore[misc]


def test_prematch_event_stub_exported_from_top_level():
    from bookieskit import PrematchEventStub as Public
    from bookieskit.bookmakers.types import PrematchEventStub as Internal
    assert Public is Internal
