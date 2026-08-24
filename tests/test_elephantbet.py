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
