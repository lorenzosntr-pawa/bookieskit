import pytest
import respx

from bookieskit.bookmakers.msport import MSport


def test_msport_country_ng_resolves_domain():
    client = MSport(country="ng")
    assert client.base_url == "https://www.msport.com"


def test_msport_country_gh_resolves_domain():
    client = MSport(country="gh")
    assert client.base_url == "https://www.msport.com"


def test_msport_country_ke_resolves_domain():
    client = MSport(country="ke")
    assert client.base_url == "https://www.msport.com"


def test_msport_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        MSport(country="xx")


@pytest.mark.asyncio
@respx.mock
async def test_msport_headers():
    route = respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/sports"
    ).respond(json={"bizCode": 10000, "data": {"sports": []}})
    async with MSport(country="ng") as client:
        await client.get_sports()
    headers = route.calls[0].request.headers
    assert headers["clientid"] == "web"
    assert headers["operid"] == "2"
    assert headers["platform"] == "web"


@pytest.mark.parametrize(
    "country,expected_operid",
    [
        ("ng", "2"),
        ("gh", "3"),
        ("ke", "1"),
        ("ug", "4"),
        ("zm", "5"),
    ],
)
def test_msport_operid_is_per_country(country, expected_operid):
    """MSport's API rejects requests with the wrong operId for a country.
    The lib previously hardcoded operid=2, which only worked for NG —
    GH/KE/UG/ZM silently returned bizCode 19000 'invalid operId'.
    Each country MUST send its own operid."""
    client = MSport(country=country)
    headers = client._build_headers()
    assert headers["operid"] == expected_operid


@pytest.mark.parametrize("country", ["ug", "zm"])
def test_msport_new_countries_resolve_domain(country):
    """UG and ZM added in 0.8.0 — same base URL as the original three;
    the operid map differentiates them at the API layer."""
    client = MSport(country=country)
    assert client.base_url == "https://www.msport.com"


@pytest.mark.asyncio
@respx.mock
async def test_msport_ke_sends_operid_1_not_2():
    """Regression: before 0.8.0 the lib sent operid=2 for every country,
    breaking MSport KE on the live API. Pin the fix."""
    route = respx.get(
        "https://www.msport.com/api/ke/facts-center/query/frontend/sports"
    ).respond(json={"bizCode": 10000, "data": {"sports": []}})
    async with MSport(country="ke") as client:
        await client.get_sports()
    headers = route.calls[0].request.headers
    assert headers["operid"] == "1"


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/sports"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "sports": [
                    {"sportId": "sr:sport:1", "sportName": "Soccer", "count": 0},
                    {"sportId": "sr:sport:2", "sportName": "Basketball", "count": 0},
                ]
            },
        }
    )
    async with MSport(country="ng") as client:
        result = await client.get_sports()
    assert result["data"]["sports"][0]["sportName"] == "Soccer"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/sports-matches-list"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "tournaments": [
                    {
                        "category": "England",
                        "tournament": "Premier League",
                        "tournamentId": "sr:tournament:17",
                        "events": [
                            {
                                "eventId": "sr:match:61301233",
                                "homeTeam": "Liverpool",
                                "awayTeam": "Chelsea",
                            }
                        ],
                    }
                ]
            },
        }
    )
    async with MSport(country="ng") as client:
        result = await client.get_events(sport_id="sr:sport:1")
    tournaments = result["data"]["tournaments"]
    assert tournaments[0]["events"][0]["homeTeam"] == "Liverpool"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail():
    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/match/detail"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "eventId": "sr:match:61301231",
                "homeTeam": "Fulham",
                "awayTeam": "Bournemouth",
                "markets": [
                    {
                        "id": 1,
                        "description": "1x2",
                        "name": "1x2",
                        "specifiers": None,
                        "outcomes": [
                            {"description": "Home", "id": "1", "odds": "2.76"},
                        ],
                    }
                ],
            },
        }
    )
    async with MSport(country="ng") as client:
        result = await client.get_event_detail(event_id="sr:match:61301231")
    assert result["data"]["markets"][0]["description"] == "1x2"


@pytest.mark.asyncio
@respx.mock
async def test_get_live_sports():
    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/live-matches/sports"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "sports": [
                    {"sportId": "sr:sport:1", "sportName": "Soccer", "count": 30},
                ]
            },
        }
    )
    async with MSport(country="ng") as client:
        result = await client.get_live_sports()
    assert result["data"]["sports"][0]["count"] == 30


@pytest.mark.asyncio
@respx.mock
async def test_get_live_events():
    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/live-matches/list"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "tournaments": [],
                "events": [{"eventId": "sr:match:61301233"}],
                "comingSoons": [],
            },
        }
    )
    async with MSport(country="ng") as client:
        result = await client.get_live_events(sport_id="sr:sport:1")
    assert result["data"]["events"][0]["eventId"] == "sr:match:61301233"


@pytest.mark.asyncio
@respx.mock
async def test_msport_gh_uses_gh_path():
    respx.get(
        "https://www.msport.com/api/gh/facts-center/query/frontend/sports"
    ).respond(json={"bizCode": 10000, "data": {"sports": []}})
    async with MSport(country="gh") as client:
        result = await client.get_sports()
    assert result["bizCode"] == 10000


@pytest.mark.asyncio
@respx.mock
async def test_msport_ke_uses_ke_path():
    respx.get(
        "https://www.msport.com/api/ke/facts-center/query/frontend/sports"
    ).respond(json={"bizCode": 10000, "data": {"sports": []}})
    async with MSport(country="ke") as client:
        result = await client.get_sports()
    assert result["bizCode"] == 10000


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail_live_uses_product_1():
    route = respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/match/detail"
    ).respond(json={"bizCode": 10000, "data": {"markets": []}})
    async with MSport(country="ng") as client:
        await client.get_event_detail(event_id="sr:match:69339436", live=True)
    assert route.calls[0].request.url.params["productId"] == "1"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail_default_uses_product_3():
    route = respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/match/detail"
    ).respond(json={"bizCode": 10000, "data": {"markets": []}})
    async with MSport(country="ng") as client:
        await client.get_event_detail(event_id="sr:match:61301231")
    assert route.calls[0].request.url.params["productId"] == "3"
