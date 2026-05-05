import pytest
import respx
from httpx import Response

from bookieskit.bookmakers.betpawa import BetPawa


def test_betpawa_country_ng_resolves_domain():
    client = BetPawa(country="ng")
    assert client.base_url == "https://www.betpawa.ng"


def test_betpawa_country_gh_resolves_domain():
    client = BetPawa(country="gh")
    assert client.base_url == "https://www.betpawa.com.gh"


def test_betpawa_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        BetPawa(country="xx")


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/categories/list/all").respond(
        json={
            "categories": [
                {"id": "2", "name": "Football"},
                {"id": "3", "name": "Basketball"},
            ]
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_sports()
    assert result["categories"][0]["name"] == "Football"


@pytest.mark.asyncio
@respx.mock
async def test_get_countries():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/categories/list/2").respond(
        json={
            "id": "2",
            "name": "Football",
            "regions": [
                {"id": "1", "name": "England", "competitions": []},
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_countries(sport_id="2")
    assert result["regions"][0]["name"] == "England"


@pytest.mark.asyncio
@respx.mock
async def test_get_tournaments():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/categories/list/2").respond(
        json={
            "id": "2",
            "name": "Football",
            "regions": [
                {
                    "id": "1",
                    "name": "England",
                    "competitions": [
                        {"id": "11965", "name": "Premier League"},
                    ],
                },
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_tournaments(sport_id="2", country_id="1")
    assert result["regions"][0]["competitions"][0]["name"] == "Premier League"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/events/lists/by-queries").respond(
        json={
            "results": [
                {
                    "id": "32299257",
                    "homeTeam": "Manchester City",
                    "awayTeam": "Liverpool",
                }
            ],
            "totalCount": 1,
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_events(tournament_id="11965")
    assert result["results"][0]["homeTeam"] == "Manchester City"


@pytest.mark.asyncio
@respx.mock
async def test_get_events_with_sport_id():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/events/lists/by-queries").respond(
        json={"results": [], "totalCount": 0}
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_events(tournament_id="11965", sport_id="3")
    assert result["totalCount"] == 0


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/events/32299257").respond(
        json={
            "id": "32299257",
            "homeTeam": "Manchester City",
            "awayTeam": "Liverpool",
            "markets": [
                {
                    "id": "3743",
                    "name": "1X2 - Full Time",
                    "row": [{"prices": [{"name": "1", "odds": 1.95}]}],
                }
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_event_detail(event_id="32299257")
    assert result["markets"][0]["name"] == "1X2 - Full Time"


@pytest.mark.asyncio
@respx.mock
async def test_betpawa_headers_include_brand():
    route = respx.get("https://www.betpawa.ng/api/sportsbook/v3/categories/list/all").respond(
        json={"categories": []}
    )
    async with BetPawa(country="ng") as client:
        await client.get_sports()
    assert route.calls[0].request.headers["x-pawa-brand"] == "betpawa-nigeria"
