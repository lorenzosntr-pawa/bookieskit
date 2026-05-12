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
