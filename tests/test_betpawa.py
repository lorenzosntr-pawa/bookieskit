import pytest
import respx

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


@pytest.mark.parametrize(
    "country,expected_url,expected_brand",
    [
        # Added in 0.8.0
        ("rw", "https://www.betpawa.rw", "betpawa-rwanda"),
        ("cm", "https://www.betpawa.cm", "betpawa-cameroon"),
        ("sl", "https://www.betpawa.sl", "betpawa-sierraleone"),
        # Added in 0.10.0 — completes the full 15-country BetPawa footprint
        # advertised on the landing-page country selector. URLs and brand
        # headers verified against the live sportsbook API.
        ("bj", "https://www.betpawa.bj", "betpawa-benin"),
        ("cg", "https://cg.betpawa.com", "betpawa-congobrazzaville"),
        ("cd", "https://www.betpawa.cd", "betpawa-drc"),
        ("ls", "https://ls.betpawa.com", "betpawa-lesotho"),
        ("mw", "https://www.betpawa.mw", "betpawa-malawi"),
        ("mz", "https://www.betpawa.co.mz", "betpawa-mozambique"),
    ],
)
def test_betpawa_new_countries_resolve_domain_and_brand(
    country, expected_url, expected_brand
):
    """BetPawa countries added in 0.8.0 (rw/cm/sl) and 0.10.0
    (bj/cg/cd/ls/mw/mz) — verified against the live sportsbook API."""
    client = BetPawa(country=country)
    assert client.base_url == expected_url
    headers = client._build_headers()
    assert headers["x-pawa-brand"] == expected_brand


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
        result = await client.get_tournaments(sport_id="2")
    assert result["regions"][0]["competitions"][0]["name"] == "Premier League"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/events/lists/by-queries").respond(
        json={
            "responses": [
                {
                    "responses": [
                        {
                            "id": "32299257",
                            "homeTeam": "Manchester City",
                            "awayTeam": "Liverpool",
                        }
                    ]
                }
            ]
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_events(tournament_id="11965")
    assert result["responses"][0]["responses"][0]["homeTeam"] == "Manchester City"


@pytest.mark.asyncio
@respx.mock
async def test_get_events_with_sport_id():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/events/lists/by-queries").respond(
        json={"responses": [{"responses": []}]}
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_events(tournament_id="11965", sport_id="3")
    assert result["responses"][0]["responses"] == []


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
                    "marketType": {"id": "3743", "name": "1X2"},
                    "row": [{"prices": [{"name": "1", "price": 1.95}]}],
                }
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_event_detail(event_id="32299257")
    assert result["markets"][0]["marketType"]["id"] == "3743"


@pytest.mark.asyncio
@respx.mock
async def test_betpawa_headers_include_brand():
    route = respx.get("https://www.betpawa.ng/api/sportsbook/v3/categories/list/all").respond(
        json={"categories": []}
    )
    async with BetPawa(country="ng") as client:
        await client.get_sports()
    assert route.calls[0].request.headers["x-pawa-brand"] == "betpawa-nigeria"
