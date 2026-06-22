import httpx
import pytest
import respx

from bookieskit.bookmakers.betway import Betway

_MARKETS_URL = (
    "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/"
    "MarketGroupings/MarketGroupNamesAndMarketsForEvent"
)
_DETAIL_URL = (
    "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v3/Feeds/"
    "Events/EventAndGameState"
)


def _page(mig, outs, prices):
    return {"marketsInGroup": mig, "outcomes": outs, "prices": prices}


@pytest.mark.asyncio
@respx.mock
async def test_get_event_markets_all_merges_pages_and_stops_on_short_page():
    respx.get(_DETAIL_URL).respond(
        json={"sportEvent": {"homeTeam": "A", "awayTeam": "B"}}
    )
    # Page 0: full page of 100 -> loop must request page 1.
    page0_mig = [{"marketId": f"m{i}", "name": "X"} for i in range(100)]
    page0_outs = [{"outcomeId": "o0", "marketId": "m0", "name": "Over"}]
    page0_prices = [{"outcomeId": "o0", "priceDecimal": 1.5}]
    # Page 1: short page (2 markets) -> loop must stop after this page.
    page1_mig = [{"marketId": "m100", "name": "Y"}, {"marketId": "m101", "name": "Z"}]
    page1_outs = [{"outcomeId": "o1", "marketId": "m100", "name": "Under"}]
    page1_prices = [{"outcomeId": "o1", "priceDecimal": 2.0}]

    route = respx.get(_MARKETS_URL)
    route.side_effect = [
        httpx.Response(200, json=_page(page0_mig, page0_outs, page0_prices)),
        httpx.Response(200, json=_page(page1_mig, page1_outs, page1_prices)),
    ]

    async with Betway(country="ng") as client:
        merged = await client.get_event_markets_all(event_id="42")

    assert route.call_count == 2  # stopped after the short second page
    assert len(merged["marketsInGroup"]) == 102
    assert merged["outcomes"] == page0_outs + page1_outs
    assert merged["prices"] == page0_prices + page1_prices
    assert merged["sportEvent"] == {"homeTeam": "A", "awayTeam": "B"}


@pytest.mark.asyncio
@respx.mock
async def test_get_event_markets_all_empty_first_page():
    respx.get(_DETAIL_URL).respond(json={"sportEvent": {}})
    respx.get(_MARKETS_URL).respond(
        json={"marketsInGroup": [], "outcomes": [], "prices": []}
    )
    async with Betway(country="ng") as client:
        merged = await client.get_event_markets_all(event_id="42")
    assert merged["marketsInGroup"] == []
    assert merged["sportEvent"] == {}
