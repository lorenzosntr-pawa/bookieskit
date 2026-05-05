import pytest
import respx

from bookieskit.bookmakers.bet9ja import Bet9ja


def test_bet9ja_country_ng_resolves_domain():
    client = Bet9ja(country="ng")
    assert client.base_url == "https://sports.bet9ja.com"


def test_bet9ja_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        Bet9ja(country="gh")


def test_bet9ja_default_rate_limits():
    client = Bet9ja(country="ng")
    assert client._max_concurrent == 15
    assert client._request_delay == 0.025


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get("https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetSports").respond(
        json={
            "R": "OK",
            "D": {
                "PAL": {"sports": [{"id": "1", "name": "Football"}]}
            },
        }
    )
    async with Bet9ja(country="ng") as client:
        result = await client.get_sports()
    assert result["R"] == "OK"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get("https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetEventsInGroupV2").respond(
        json={
            "R": "OK",
            "D": {
                "E": [
                    {"id": "707096003", "name": "Man City vs Liverpool"}
                ]
            },
        }
    )
    async with Bet9ja(country="ng") as client:
        result = await client.get_events(tournament_id="170880")
    assert result["D"]["E"][0]["name"] == "Man City vs Liverpool"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail():
    respx.get("https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetEvent").respond(
        json={
            "R": "D",
            "D": {
                "EXTID": "sr:match:61300947",
                "O": {
                    "S_1X2_1": "1.50",
                    "S_1X2_X": "3.20",
                    "S_1X2_2": "2.10",
                },
            },
        }
    )
    async with Bet9ja(country="ng") as client:
        result = await client.get_event_detail(event_id="707096003")
    assert result["D"]["O"]["S_1X2_1"] == "1.50"
    assert result["D"]["EXTID"] == "sr:match:61300947"


@pytest.mark.asyncio
@respx.mock
async def test_bet9ja_headers():
    route = respx.get("https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetSports").respond(
        json={"R": "OK", "D": {}}
    )
    async with Bet9ja(country="ng") as client:
        await client.get_sports()
    headers = route.calls[0].request.headers
    assert "Mozilla" in headers["user-agent"]
