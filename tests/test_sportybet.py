import pytest
import respx

from bookieskit.bookmakers.sportybet import SportyBet


def test_sportybet_country_ng_resolves_domain():
    client = SportyBet(country="ng")
    assert client.base_url == "https://www.sportybet.com"


@pytest.mark.parametrize("country", ["tz", "za", "cm", "zm"])
def test_sportybet_new_countries_resolve_domain(country):
    """4 SportyBet countries added in 0.10.0 — verified live via
    /factsCenter/popularAndSportList. All share the same base; country
    is differentiated by the URL path segment."""
    client = SportyBet(country=country)
    assert client.base_url == "https://www.sportybet.com"


def test_sportybet_canada_not_supported():
    """SportyBet operates sportybet.ca but on a different platform with
    a different API shape — intentionally NOT in DOMAINS. Pin the
    behaviour so future maintainers don't add it speculatively."""
    from bookieskit.exceptions import UnsupportedCountryError
    with pytest.raises(UnsupportedCountryError):
        SportyBet(country="ca")


def test_sportybet_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        SportyBet(country="xx")


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/popularAndSportList").respond(
        json={
            "bizCode": 10000,
            "data": {
                "sportList": [
                    {"id": "sr:sport:1", "name": "Football"},
                    {"id": "sr:sport:2", "name": "Basketball"},
                ]
            },
        }
    )
    async with SportyBet(country="ng") as client:
        result = await client.get_sports()
    assert result["data"]["sportList"][0]["name"] == "Football"


@pytest.mark.asyncio
@respx.mock
async def test_get_countries():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/popularAndSportList").respond(
        json={
            "bizCode": 10000,
            "data": {
                "sportList": [
                    {
                        "id": "sr:sport:1",
                        "name": "Football",
                        "categories": [
                            {"id": "sr:category:1", "name": "England"},
                        ],
                    }
                ]
            },
        }
    )
    async with SportyBet(country="ng") as client:
        result = await client.get_countries(sport_id="sr:sport:1")
    assert result["data"]["sportList"][0]["categories"][0]["name"] == "England"


@pytest.mark.asyncio
@respx.mock
async def test_get_tournaments():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/popularAndSportList").respond(
        json={
            "bizCode": 10000,
            "data": {
                "sportList": [
                    {
                        "id": "sr:sport:1",
                        "categories": [
                            {
                                "id": "sr:category:1",
                                "name": "England",
                                "tournaments": [
                                    {
                                        "id": "sr:tournament:17",
                                        "name": "Premier League",
                                    },
                                ],
                            }
                        ],
                    }
                ]
            },
        }
    )
    async with SportyBet(country="ng") as client:
        result = await client.get_tournaments(sport_id="sr:sport:1")
    tournaments = result["data"]["sportList"][0]["categories"][0]["tournaments"]
    assert tournaments[0]["name"] == "Premier League"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.post("https://www.sportybet.com/api/ng/factsCenter/pcEvents").respond(
        json={
            "bizCode": 10000,
            "data": [
                {
                    "events": [
                        {
                            "eventId": "sr:match:61300947",
                            "homeTeamName": "Manchester City",
                            "awayTeamName": "Liverpool",
                        }
                    ]
                }
            ],
        }
    )
    async with SportyBet(country="ng") as client:
        result = await client.get_events(tournament_id="sr:tournament:17")
    assert result["data"][0]["events"][0]["homeTeamName"] == "Manchester City"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/event").respond(
        json={
            "bizCode": 10000,
            "data": {
                "eventId": "sr:match:61300947",
                "markets": [
                    {
                        "id": "1",
                        "desc": "1X2 - Full Time",
                        "outcomes": [
                            {"id": "1", "desc": "Home", "odds": "1.95"},
                        ],
                    }
                ],
            },
        }
    )
    async with SportyBet(country="ng") as client:
        result = await client.get_event_detail(event_id="sr:match:61300947")
    assert result["data"]["markets"][0]["desc"] == "1X2 - Full Time"


@pytest.mark.asyncio
@respx.mock
async def test_sportybet_headers():
    route = respx.get("https://www.sportybet.com/api/ng/factsCenter/popularAndSportList").respond(
        json={"bizCode": 10000, "data": {"sportList": []}}
    )
    async with SportyBet(country="ng") as client:
        await client.get_sports()
    assert route.calls[0].request.headers["clientid"] == "web"
    assert route.calls[0].request.headers["operid"] == "2"


@pytest.mark.asyncio
@respx.mock
async def test_sportybet_gh_uses_gh_path():
    respx.get("https://www.sportybet.com/api/gh/factsCenter/popularAndSportList").respond(
        json={"bizCode": 10000, "data": {"sportList": []}}
    )
    async with SportyBet(country="gh") as client:
        result = await client.get_sports()
    assert result["bizCode"] == 10000


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail_live_uses_product_1():
    route = respx.get("https://www.sportybet.com/api/ng/factsCenter/event").respond(
        json={"bizCode": 10000, "data": {"markets": []}}
    )
    async with SportyBet(country="ng") as client:
        await client.get_event_detail(event_id="sr:match:69339436", live=True)
    assert route.calls[0].request.url.params["productId"] == "1"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail_default_uses_product_3():
    route = respx.get("https://www.sportybet.com/api/ng/factsCenter/event").respond(
        json={"bizCode": 10000, "data": {"markets": []}}
    )
    async with SportyBet(country="ng") as client:
        await client.get_event_detail(event_id="sr:match:61300947")
    assert route.calls[0].request.url.params["productId"] == "3"
