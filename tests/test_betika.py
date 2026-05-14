"""Unit tests for the Betika client.

Betika is country-agnostic at the API layer — all five supported country
codes (ke, ug, tz, mw, gh) resolve to the same ``api.betika.com`` host.
Live in-play data is served from a separate host, ``live.betika.com``.
"""

import pytest

from bookieskit.bookmakers.betika import Betika


@pytest.mark.parametrize("country", ["ke", "ug", "tz", "mw", "gh"])
def test_betika_country_resolves_domain(country):
    client = Betika(country=country)
    assert client.base_url == "https://api.betika.com"


def test_betika_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError
    with pytest.raises(UnsupportedCountryError):
        Betika(country="xx")


def test_betika_default_headers_have_user_agent():
    client = Betika(country="ke")
    headers = client._build_headers()
    assert "user-agent" in headers
    assert "Mozilla" in headers["user-agent"]


def test_betika_live_base_url_constant():
    assert Betika.LIVE_BASE_URL == "https://live.betika.com"


def test_betika_platform_key():
    assert Betika.PLATFORM_KEY == "betika"


# ---- get_sports / get_navigation ------------------------------------------


@pytest.mark.asyncio
async def test_betika_get_sports():
    import respx
    payload = {"data": [{"id": 14, "name": "Soccer"}], "meta": {}}
    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/sports").respond(json=payload)
        async with Betika(country="ke") as client:
            result = await client.get_sports()
    assert result["data"][0]["name"] == "Soccer"


@pytest.mark.asyncio
async def test_betika_get_navigation_aliases_get_sports():
    import respx
    payload = {"data": [{"id": 14, "name": "Soccer"}], "meta": {}}
    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/sports").respond(json=payload)
        async with Betika(country="ke") as client:
            result = await client.get_navigation()
    assert result["data"][0]["id"] == 14
