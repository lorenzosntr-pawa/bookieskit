import pytest
import respx
from httpx import Response

from bookieskit import ElephantBet


def test_elephantbet_country_mz_resolves_domain():
    client = ElephantBet(country="mz")
    assert client.base_url == "https://sports-core.elephantbet.com"


def test_elephantbet_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        ElephantBet(country="ao")


@pytest.mark.asyncio
@respx.mock
async def test_get_sports_sends_culture():
    route = respx.get(
        "https://sports-core.elephantbet.com/rest/FEWFixture/Sports"
    ).mock(return_value=Response(200, json=[{"id": 1, "n": "Futebol", "c": "soccer"}]))
    async with ElephantBet(country="mz") as client:
        data = await client.get_sports()
    assert data[0]["c"] == "soccer"
    # Culture is mandatory upstream: omitting it returns HTTP 400.
    assert route.calls.last.request.url.params["Culture"] == "pt"


@pytest.mark.asyncio
@respx.mock
async def test_get_events_uses_grouped_matches():
    route = respx.get(
        "https://sports-core.elephantbet.com/rest/FEMobile/GetGroupedMatches"
    ).mock(return_value=Response(200, json=[{"id": 1, "t": []}]))
    async with ElephantBet(country="mz") as client:
        await client.get_events(tournament_id="1428062", limit=5)
    params = route.calls.last.request.url.params
    assert params["TournamentData[]"] == "1428062"
    assert params["Culture"] == "pt"
    assert params["Limit"] == "5"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail_uses_fewmatches():
    route = respx.get(
        "https://sports-core.elephantbet.com/rest/FEWMatches/MatchOdds"
    ).mock(return_value=Response(200, json={"s": None, "t": []}))
    async with ElephantBet(country="mz") as client:
        await client.get_event_detail("5998731")
    assert route.calls.last.request.url.params["MatchID"] == "5998731"


@pytest.mark.asyncio
@respx.mock
async def test_get_live_events_uses_live_metadata_endpoint():
    route = respx.get(
        "https://sports-core.elephantbet.com/rest/FEMobile/GetLiveMatchesMetaData"
    ).mock(return_value=Response(200, json=[{"sid": 1, "mid": 1, "ht": "A", "at": "B"}]))
    async with ElephantBet(country="mz") as client:
        data = await client.get_live_events()
    assert data[0]["ht"] == "A"
    assert route.calls.last.request.url.params["Culture"] == "pt"


@pytest.mark.asyncio
@respx.mock
async def test_get_live_events_filters_by_sport_id_client_side():
    """The endpoint returns every sport at once; sport_id filters locally."""
    payload = [
        {"sid": 1, "mid": 1, "ht": "Soccer H", "at": "Soccer A"},
        {"sid": 2, "mid": 2, "ht": "Basket H", "at": "Basket A"},
    ]
    respx.get(
        "https://sports-core.elephantbet.com/rest/FEMobile/GetLiveMatchesMetaData"
    ).mock(return_value=Response(200, json=payload))
    async with ElephantBet(country="mz") as client:
        soccer = await client.get_live_events(sport_id="1")
        every = await client.get_live_events()
    assert [m["mid"] for m in soccer] == [1]
    assert [m["mid"] for m in every] == [1, 2]
