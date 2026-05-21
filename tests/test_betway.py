import httpx
import pytest
import respx

from bookieskit.bookmakers.betway import Betway


def test_betway_country_ng_resolves_domain():
    client = Betway(country="ng")
    assert client.base_url == "https://feeds-roa2.betwayafrica.com"


def test_betway_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        Betway(country="xx")


def test_betway_country_code_mapping():
    client = Betway(country="ng")
    assert client._country_code == "NG"
    client_gh = Betway(country="gh")
    assert client_gh._country_code == "GH"


def test_betway_za_resolves_country_code():
    """South Africa added in 0.8.0 — verified against the live config
    endpoint (config.betwayafrica.com/cron/sports/ZA/en-US)."""
    client = Betway(country="za")
    assert client.base_url == "https://feeds-roa2.betwayafrica.com"
    assert client._country_code == "ZA"


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get(
        "https://config.betwayafrica.com/cron/sports/NG/en-US"
    ).respond(
        json={
            "sports": [
                {
                    "sportId": "soccer",
                    "name": "Soccer",
                    "liveInPlayCount": 5,
                    "hasUpcomingEvents": True,
                }
            ]
        }
    )
    async with Betway(country="ng") as client:
        result = await client.get_sports()
    assert result["sports"][0]["name"] == "Soccer"


@pytest.mark.asyncio
@respx.mock
async def test_get_countries():
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/Feeds/RegionsAndLeagues/soccer"
    ).respond(
        json={
            "regions": [
                {
                    "regionId": "england",
                    "name": "England",
                    "leagues": [
                        {
                            "leagueId": "premier-league",
                            "name": "Premier League",
                        }
                    ],
                }
            ]
        }
    )
    async with Betway(country="ng") as client:
        result = await client.get_countries(sport_id="soccer")
    assert result["regions"][0]["name"] == "England"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/BetBook/Highlights/"
    ).respond(
        json={
            "events": [
                {
                    "eventId": 69339436,
                    "name": "Arsenal FC vs. Atletico Madrid",
                    "homeTeam": "Arsenal FC",
                    "awayTeam": "Atletico Madrid",
                }
            ],
            "markets": [],
            "outcomes": [],
            "prices": [],
        }
    )
    async with Betway(country="ng") as client:
        result = await client.get_events(
            league_id="international-clubs_uefa-champions-league"
        )
    assert result["events"][0]["homeTeam"] == "Arsenal FC"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail():
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v3/Feeds/Events/EventAndGameState"
    ).respond(
        json={
            "sportEvent": {
                "eventId": 69339436,
                "name": "Arsenal FC vs. Atletico Madrid",
                "homeTeam": "Arsenal FC",
                "awayTeam": "Atletico Madrid",
            }
        }
    )
    async with Betway(country="ng") as client:
        result = await client.get_event_detail(event_id="69339436")
    assert result["sportEvent"]["eventId"] == 69339436


@pytest.mark.asyncio
@respx.mock
async def test_get_event_markets():
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/MarketGroupings/MarketGroupNamesAndMarketsForEvent"
    ).respond(
        json={
            "marketGroupNames": ["Main"],
            "marketsInGroup": [
                {
                    "marketId": "693394361",
                    "name": "[Win/Draw/Win]",
                    "handicap": 0,
                }
            ],
            "outcomes": [
                {
                    "outcomeId": "6933943611",
                    "marketId": "693394361",
                    "name": "Arsenal FC",
                }
            ],
            "prices": [
                {
                    "outcomeId": "6933943611",
                    "priceDecimal": 1.63,
                }
            ],
        }
    )
    async with Betway(country="ng") as client:
        result = await client.get_event_markets(event_id="69339436")
    assert len(result["marketsInGroup"]) == 1


@pytest.mark.asyncio
@respx.mock
async def test_get_markets_convenience():
    # get_markets now also calls get_event_detail to splice sportEvent
    # into the merged payload — mock both endpoints.
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v3/Feeds/Events/EventAndGameState"
    ).respond(
        json={
            "sportEvent": {
                "homeTeam": "Home",
                "awayTeam": "Away",
            }
        }
    )
    # Single page with 1 market — pagination loop should exit after the
    # first page because len(mig)=1 < take=100.
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/MarketGroupings/MarketGroupNamesAndMarketsForEvent"
    ).respond(
        json={
            "marketsInGroup": [
                {
                    "marketId": "1",
                    "name": "[Both Teams To Score]",
                    "handicap": 0,
                }
            ],
            "outcomes": [
                {"outcomeId": "a", "marketId": "1", "name": "Yes"},
                {"outcomeId": "b", "marketId": "1", "name": "No"},
            ],
            "prices": [
                {"outcomeId": "a", "priceDecimal": 1.7},
                {"outcomeId": "b", "priceDecimal": 2.1},
            ],
        }
    )
    async with Betway(country="ng") as client:
        markets = await client.get_markets(event_id="123")
    assert len(markets) == 1
    assert markets[0].canonical_id == "btts_ft"


@pytest.mark.asyncio
@respx.mock
async def test_get_markets_paginates_until_empty_page():
    """get_markets must fetch all pages of marketsInGroup before
    parsing, so markets past index 100 aren't silently dropped.
    """
    # Mock get_event_detail (scoreboard call for sportEvent)
    respx.get(
        url__regex=r"^https://feeds-roa2.betwayafrica.com/br/_apis/sport/v3/Feeds/Events/EventAndGameState.*"  # noqa: E501
    ).mock(return_value=httpx.Response(
        200, json={
            "sportEvent": {
                "homeTeam": "Test Home",
                "awayTeam": "Test Away",
            },
        }
    ))

    # Mock 2 pages of markets — first page returns 100 markets and
    # forces a second call; second page returns 5 and signals the end.
    page1_markets = [
        {
            "marketId": f"m1_{i}",
            "name": "[Total Goals]",
            "handicap": float(i),
        } for i in range(100)
    ]
    page2_markets = [
        {
            "marketId": f"m2_{i}",
            "name": "[Win/Draw/Win]",
            "handicap": 0,
        } for i in range(5)
    ]

    pages = [
        {"marketsInGroup": page1_markets, "outcomes": [], "prices": []},
        {"marketsInGroup": page2_markets, "outcomes": [], "prices": []},
    ]

    call_count = {"n": 0}

    def _markets_side_effect(request):
        i = call_count["n"]
        call_count["n"] += 1
        if i >= len(pages):
            return httpx.Response(200, json={"marketsInGroup": [], "outcomes": [], "prices": []})
        return httpx.Response(200, json=pages[i])

    respx.get(
        url__regex=r"^https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/MarketGroupings.*"  # noqa: E501
    ).mock(side_effect=_markets_side_effect)

    async with Betway(country="ng") as bw:
        await bw.get_markets(event_id="71443804")

    # Must have made AT LEAST 2 calls to the markets endpoint (page 1 + page 2)
    assert call_count["n"] >= 2, (
        f"Expected pagination (>=2 calls) but got {call_count['n']}"
    )


@pytest.mark.asyncio
async def test_get_sportradar_id_no_api_call():
    """Betway event IDs ARE SR IDs — no API call needed."""
    client = Betway(country="ng")
    sr_id = await client.get_sportradar_id(event_id="69339436")
    assert sr_id == "69339436"
