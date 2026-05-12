import pytest
import respx

from bookieskit.bookmakers.sportpesa import SportPesa


def test_sportpesa_country_ke_resolves_domain():
    client = SportPesa(country="ke")
    assert client.base_url == "https://www.ke.sportpesa.com"


def test_sportpesa_country_tz_resolves_domain():
    client = SportPesa(country="tz")
    assert client.base_url == "https://www.tz.sportpesa.com"


def test_sportpesa_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError
    with pytest.raises(UnsupportedCountryError):
        SportPesa(country="xx")


def test_sportpesa_ke_timezone_header():
    client = SportPesa(country="ke")
    headers = client._build_headers()
    assert headers["x-app-timezone"] == "Africa/Nairobi"


def test_sportpesa_tz_timezone_header():
    client = SportPesa(country="tz")
    headers = client._build_headers()
    assert headers["x-app-timezone"] == "Africa/Dar_es_Salaam"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail_prematch():
    respx.get(
        "https://www.ke.sportpesa.com/api/upcoming/games"
    ).respond(json={"data": [{"id": 8868005, "home_team": "Arsenal"}]})

    async with SportPesa(country="ke") as client:
        result = await client.get_event_detail(event_id="8868005")
    assert result["data"][0]["home_team"] == "Arsenal"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_markets():
    respx.get(
        "https://www.ke.sportpesa.com/api/games/markets"
    ).respond(json={"data": [{"id": 8868005, "markets": []}]})

    async with SportPesa(country="ke") as client:
        result = await client.get_event_markets(event_id="8868005")
    assert result["data"][0]["id"] == 8868005


@pytest.mark.asyncio
@respx.mock
async def test_get_markets_calls_markets_endpoint():
    # get_markets should route through get_event_markets (not get_event_detail).
    markets_called = respx.get(
        "https://www.ke.sportpesa.com/api/games/markets"
    ).respond(json={"data": [{"id": 8868005, "markets": []}]})
    detail_called = respx.get(
        "https://www.ke.sportpesa.com/api/upcoming/games"
    ).respond(json={"data": [{"id": 8868005}]})

    async with SportPesa(country="ke") as client:
        await client.get_markets(event_id="8868005")

    assert markets_called.called
    assert not detail_called.called


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get("https://www.ke.sportpesa.com/api/sports").respond(
        json={"data": [{"id": 1, "name": "Football"}]}
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_sports()
    assert result["data"][0]["name"] == "Football"


@pytest.mark.asyncio
@respx.mock
async def test_get_countries():
    respx.get("https://www.ke.sportpesa.com/api/upcoming/categories").respond(
        json={"data": [{"id": 100, "name": "England"}]}
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_countries(sport_id="1")
    assert result["data"][0]["name"] == "England"


@pytest.mark.asyncio
@respx.mock
async def test_get_tournaments():
    respx.get("https://www.ke.sportpesa.com/api/upcoming/competitions").respond(
        json={"data": [{"id": 200, "name": "Premier League"}]}
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_tournaments(sport_id="1", category_id="100")
    assert result["data"][0]["name"] == "Premier League"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get("https://www.ke.sportpesa.com/api/upcoming/games").respond(
        json={"data": [{"id": 8868005, "home_team": "Arsenal"}]}
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_events(sport_id="1", competition_id="200")
    assert result["data"][0]["home_team"] == "Arsenal"


def test_sportpesa_exported_from_top_level():
    from bookieskit import SportPesa as SP
    from bookieskit.bookmakers.sportpesa import SportPesa as SP2
    assert SP is SP2


def test_top_level_version_bumped():
    import bookieskit
    assert bookieskit.__version__ == "0.5.0"
