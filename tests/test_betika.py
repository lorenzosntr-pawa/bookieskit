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


# ---- get_matches / get_live_matches ---------------------------------------


@pytest.mark.asyncio
async def test_betika_get_matches_default_params():
    import respx
    payload = {"data": [{"match_id": "X"}], "meta": {"total": 1}}
    with respx.mock(base_url="https://api.betika.com") as mock:
        route = mock.get("/v1/uo/matches").respond(json=payload)
        async with Betika(country="ke") as client:
            result = await client.get_matches()
    assert result["meta"]["total"] == 1
    # Defaults: sport_id=14 (football), page=1, limit=100.
    req = route.calls[0].request
    assert "sport_id=14" in req.url.query.decode()
    assert "page=1" in req.url.query.decode()
    assert "limit=100" in req.url.query.decode()


@pytest.mark.asyncio
async def test_betika_get_matches_with_filters():
    import respx
    payload = {"data": [], "meta": {"total": 0}}
    with respx.mock(base_url="https://api.betika.com") as mock:
        route = mock.get("/v1/uo/matches").respond(json=payload)
        async with Betika(country="ke") as client:
            await client.get_matches(
                sport_id=14, page=2, limit=50,
                sub_type_id="18", competition_id="123", match_id="456",
            )
    q = route.calls[0].request.url.query.decode()
    assert "page=2" in q
    assert "limit=50" in q
    assert "sub_type_id=18" in q
    assert "competition_id=123" in q
    assert "match_id=456" in q


@pytest.mark.asyncio
async def test_betika_get_live_matches_uses_live_host():
    import respx
    payload = {"data": [], "meta": {"total": 0}}
    with respx.mock() as mock:
        route = mock.get("https://live.betika.com/v1/uo/matches").respond(
            json=payload
        )
        async with Betika(country="ke") as client:
            await client.get_live_matches()
    assert route.calls.call_count == 1
    q = route.calls[0].request.url.query.decode()
    assert "sport_id=14" in q


@pytest.mark.asyncio
async def test_betika_get_live_matches_with_match_id():
    import respx
    payload = {"data": [{"match_id": "X"}], "meta": {"total": 1}}
    with respx.mock() as mock:
        route = mock.get("https://live.betika.com/v1/uo/matches").respond(
            json=payload
        )
        async with Betika(country="ke") as client:
            result = await client.get_live_matches(match_id="X")
    assert result["data"][0]["match_id"] == "X"
    q = route.calls[0].request.url.query.decode()
    assert "match_id=X" in q
