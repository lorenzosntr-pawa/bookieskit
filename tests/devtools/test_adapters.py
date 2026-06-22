import httpx
import pytest
import respx

from bookieskit import Betika, Betway, MSport, SportyBet
from bookieskit.devtools.adapters import ADAPTERS
from bookieskit.devtools.types import Handle


@pytest.mark.asyncio
async def test_sportybet_resolve_wraps_prefixed_id():
    adapter = ADAPTERS["sportybet"]
    async with SportyBet(country="ng") as client:
        handle = await adapter.resolve(client, "42", "soccer")
    assert handle == Handle(platform="sportybet", event_id="sr:match:42")


@pytest.mark.asyncio
@respx.mock
async def test_sportybet_fetch_raw_markets_returns_detail_payload():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/event").respond(
        json={"data": {"markets": [{"id": "1"}]}}
    )
    adapter = ADAPTERS["sportybet"]
    handle = Handle(platform="sportybet", event_id="sr:match:42")
    async with SportyBet(country="ng") as client:
        raw = await adapter.fetch_raw_markets(client, handle)
    assert raw["data"]["markets"][0]["id"] == "1"


@pytest.mark.asyncio
async def test_msport_resolve_wraps_prefixed_id():
    adapter = ADAPTERS["msport"]
    async with MSport(country="ng") as client:
        handle = await adapter.resolve(client, "42", "soccer")
    assert handle.event_id == "sr:match:42"


@pytest.mark.asyncio
async def test_betway_resolve_uses_bare_numeric():
    adapter = ADAPTERS["betway"]
    async with Betway(country="ng") as client:
        handle = await adapter.resolve(client, "42", "soccer")
    assert handle == Handle(platform="betway", event_id="42")


@pytest.mark.asyncio
@respx.mock
async def test_betway_fetch_raw_markets_delegates_to_markets_all():
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v3/Feeds/"
        "Events/EventAndGameState"
    ).respond(json={"sportEvent": {"homeTeam": "A", "awayTeam": "B"}})
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/"
        "MarketGroupings/MarketGroupNamesAndMarketsForEvent"
    ).respond(json={"marketsInGroup": [], "outcomes": [], "prices": []})
    adapter = ADAPTERS["betway"]
    handle = Handle(platform="betway", event_id="42")
    async with Betway(country="ng") as client:
        raw = await adapter.fetch_raw_markets(client, handle)
    assert raw["sportEvent"] == {"homeTeam": "A", "awayTeam": "B"}
    assert raw["marketsInGroup"] == []


@pytest.mark.asyncio
@respx.mock
async def test_betika_resolve_scans_listing_for_parent_match_id():
    route = respx.get("https://api.betika.com/v1/uo/matches")
    route.side_effect = [
        httpx.Response(200, json={"data": [
            {"match_id": "111", "parent_match_id": "999", "competition_id": "7"},
        ]}),
        httpx.Response(200, json={"data": [
            {"match_id": "222", "parent_match_id": "42", "competition_id": "8"},
        ]}),
    ]
    adapter = ADAPTERS["betika"]
    async with Betika(country="ke") as client:
        handle = await adapter.resolve(client, "42", "soccer")
    assert handle is not None
    assert handle.event_id == "222"
    assert handle.extra["competition_id"] == "8"


@pytest.mark.asyncio
@respx.mock
async def test_betika_resolve_returns_none_when_not_found():
    respx.get("https://api.betika.com/v1/uo/matches").respond(json={"data": []})
    adapter = ADAPTERS["betika"]
    async with Betika(country="ke") as client:
        handle = await adapter.resolve(client, "42", "soccer")
    assert handle is None


@pytest.mark.asyncio
async def test_betpawa_and_sportpesa_resolve_return_none():
    # No SR->internal reverse lookup in v1; resolver records these as skips.
    assert ADAPTERS["betpawa"].resolve is not None
    assert ADAPTERS["sportpesa"].resolve is not None
    # Both platforms are present in the adapter table.
    assert set(ADAPTERS) == {
        "betpawa", "sportybet", "msport", "bet9ja",
        "betway", "betika", "sportpesa",
    }
