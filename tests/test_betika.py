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


# ---- event_detail / event_markets / get_markets ---------------------------
#
# /v1/uo/matches ignores match_id (live probe 2026-11-18: every lookup
# returned the same unrelated match), so per-event calls go to
# /v1/uo/match?id=<match_id>, which returns {"data": [<group>...],
# "meta": {<match fields>}}. The client reshapes it to the listing shape
# {"data": [{**meta, "odds": groups}], "meta": {}} the parser expects.


def _detail(mid="M", groups=None, **meta):
    return {
        "data": groups if groups is not None else [
            {"sub_type_id": "1", "name": "1X2", "odds": [
                {"display": "1", "odd_value": "2.0"},
                {"display": "X", "odd_value": "3.0"},
                {"display": "2", "odd_value": "4.0"},
            ]},
        ],
        "meta": {"match_id": mid, "parent_match_id": "70784812", **meta},
    }


@pytest.mark.asyncio
async def test_betika_get_event_detail_uses_match_endpoint_and_reshapes():
    import respx
    with respx.mock(
        base_url="https://api.betika.com", assert_all_called=False
    ) as mock:
        listing = mock.get("/v1/uo/matches")
        route = mock.get("/v1/uo/match").respond(json=_detail())
        async with Betika(country="ke") as client:
            result = await client.get_event_detail(event_id="M")
    assert route.calls.call_count == 1
    assert route.calls[0].request.url.params.get("id") == "M"
    assert listing.calls.call_count == 0
    row = result["data"][0]
    assert row["match_id"] == "M"
    assert row["parent_match_id"] == "70784812"
    assert [g["sub_type_id"] for g in row["odds"]] == ["1"]


@pytest.mark.asyncio
async def test_betika_get_event_detail_live_uses_live_host():
    import respx
    with respx.mock() as mock:
        route = mock.get("https://live.betika.com/v1/uo/match").respond(
            json=_detail()
        )
        async with Betika(country="ke") as client:
            await client.get_event_detail(event_id="M", live=True)
    assert route.calls.call_count == 1


@pytest.mark.asyncio
async def test_betika_get_event_markets_is_one_full_call():
    import respx
    groups = [{"sub_type_id": s, "name": s, "odds": []}
              for s in ("1", "10", "18", "29", "136", "166")]
    with respx.mock(base_url="https://api.betika.com") as mock:
        route = mock.get("/v1/uo/match").respond(json=_detail(groups=groups))
        async with Betika(country="ke") as client:
            result = await client.get_event_markets(event_id="M")
    assert route.calls.call_count == 1
    assert dict(route.calls[0].request.url.params) == {"id": "M"}
    assert [g["sub_type_id"] for g in result["data"][0]["odds"]] == [
        "1", "10", "18", "29", "136", "166"]


@pytest.mark.asyncio
async def test_betika_competition_id_is_accepted_and_not_needed():
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        route = mock.get("/v1/uo/match").respond(json=_detail())
        async with Betika(country="ke") as client:
            await client.get_event_detail(event_id="M", competition_id="26639")
            await client.get_event_markets(event_id="M", competition_id="26639")
    for call in route.calls:
        assert dict(call.request.url.params) == {"id": "M"}


@pytest.mark.asyncio
async def test_betika_get_markets_returns_normalized():
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/uo/match").respond(json=_detail())
        async with Betika(country="ke") as client:
            markets = await client.get_markets(event_id="M")
    assert {m.canonical_id for m in markets} == {"1x2_ft"}


# ---- iter_all_prematch_events ---------------------------------------------


@pytest.mark.asyncio
async def test_betika_iter_all_prematch_events_walks_meta_total():
    """``iter_all_prematch_events`` should derive the total page count
    from ``meta.total`` on the first call and fan the remaining pages
    out concurrently."""
    import httpx
    import respx

    def _page(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params.get("page", "1"))
        # 250 total events with limit=100 → 3 pages.
        events = [
            {"match_id": f"M{(page - 1) * 100 + i}",
             "competition_id": "C", "sport_id": "14"}
            for i in range(
                100 if page < 3 else 50
            )
        ]
        return httpx.Response(
            200,
            json={"data": events, "meta": {"total": 250, "page": page}},
        )

    base = "https://api.betika.com"
    with respx.mock(base_url=base) as mock:
        route = mock.get("/v1/uo/matches").mock(side_effect=_page)
        async with Betika(country="ke") as client:
            stubs = []
            async for stub in client.iter_all_prematch_events():
                stubs.append(stub)

    assert len(stubs) == 250
    assert all(s.event_id.startswith("M") for s in stubs)
    assert all(s.league_id == "C" for s in stubs)
    assert all(s.sport_id == "14" for s in stubs)
    # Exactly 3 page requests (page=1, 2, 3) — no off-by-one.
    pages_seen = sorted(int(c.request.url.params.get("page", "0"))
                        for c in route.calls)
    assert pages_seen == [1, 2, 3]


@pytest.mark.asyncio
async def test_betika_iter_all_prematch_events_empty():
    import respx
    base = "https://api.betika.com"
    with respx.mock(base_url=base) as mock:
        mock.get("/v1/uo/matches").respond(
            json={"data": [], "meta": {"total": 0}}
        )
        async with Betika(country="ke") as client:
            stubs = [s async for s in client.iter_all_prematch_events()]
    assert stubs == []


# ---- convenience checks ---------------------------------------------------


def test_betika_exported_from_top_level():
    from bookieskit import Betika as BK
    from bookieskit.bookmakers.betika import Betika as BK2
    assert BK is BK2


def test_betika_listed_in_supported_count():
    """Sanity check: the package description should advertise 8 bookmakers.

    Reads ``pyproject.toml`` directly (not ``importlib.metadata.metadata``)
    so the test doesn't depend on a fresh ``pip install -e .`` after the
    description changes — that was a CI hazard flagged in code review.
    """
    import tomllib
    from pathlib import Path
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject.open("rb") as f:
        meta = tomllib.load(f)
    desc = (meta.get("project", {}).get("description") or "").lower()
    assert "betika" in desc
    assert "8 african" in desc


# ---- regression: meta.total comes back as a string ------------------------


@pytest.mark.asyncio
async def test_betika_iter_all_handles_string_total():
    """Real Betika responses serialize ``meta.total`` as a string
    (``"176"``). The iterator must coerce it before computing page count,
    otherwise pagination stops after page 1 — undercounting by every page
    past the first."""
    import httpx
    import respx

    def _page(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params.get("page", "1"))
        # 250 events across 3 pages, but meta.total is a STRING.
        events = [
            {"match_id": f"M{(page - 1) * 100 + i}",
             "competition_id": "C", "sport_id": "14"}
            for i in range(100 if page < 3 else 50)
        ]
        return httpx.Response(
            200,
            json={"data": events, "meta": {"total": "250", "current_page": page}},
        )

    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/uo/matches").mock(side_effect=_page)
        async with Betika(country="ke") as client:
            stubs = [s async for s in client.iter_all_prematch_events()]

    assert len(stubs) == 250


@pytest.mark.asyncio
async def test_betika_iter_all_defaults_to_period_id_9_full_catalogue():
    """The iterator should default to ``period_id=9`` so it returns the
    full multi-month catalogue rather than the API's rolling-48hr view."""
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        route = mock.get("/v1/uo/matches").respond(
            json={"data": [], "meta": {"total": "0"}}
        )
        async with Betika(country="ke") as client:
            _ = [s async for s in client.iter_all_prematch_events()]
    assert route.calls.call_count == 1
    q = route.calls[0].request.url.query.decode()
    assert "period_id=9" in q


@pytest.mark.asyncio
async def test_betika_get_matches_passes_period_id_when_set():
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        route = mock.get("/v1/uo/matches").respond(
            json={"data": [], "meta": {"total": "0"}}
        )
        async with Betika(country="ke") as client:
            await client.get_matches(period_id=9)
    q = route.calls[0].request.url.query.decode()
    assert "period_id=9" in q


@pytest.mark.asyncio
async def test_betika_get_matches_omits_period_id_when_none():
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        route = mock.get("/v1/uo/matches").respond(
            json={"data": [], "meta": {"total": "0"}}
        )
        async with Betika(country="ke") as client:
            await client.get_matches()
    q = route.calls[0].request.url.query.decode()
    assert "period_id" not in q


# ---- fail closed: never return another match's prices ----------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get_event_detail", "get_event_markets"])
async def test_rejects_other_match(method):
    import respx

    from bookieskit.exceptions import ResponseError
    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/uo/match").respond(json=_detail(mid="OTHER"))
        async with Betika(country="ke") as client:
            with pytest.raises(ResponseError) as ei:
                await getattr(client, method)(event_id="M")
    assert "M" in str(ei.value) and "OTHER" in str(ei.value)


@pytest.mark.asyncio
async def test_int_match_id_in_meta_matches_string_event_id():
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/uo/match").respond(json=_detail(mid=123))
        async with Betika(country="ke") as client:
            result = await client.get_event_detail(event_id="123")
    assert result["data"][0]["match_id"] == 123


@pytest.mark.asyncio
async def test_unknown_event_returns_empty_payload():
    """Live shape for an unknown id: data null, meta without match_id."""
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/uo/match").respond(
            json={"data": None, "meta": {"is_esport": False}}
        )
        async with Betika(country="ke") as client:
            assert await client.get_event_detail(event_id="M") == {
                "data": [], "meta": {}}
            assert await client.get_event_markets(event_id="M") == {
                "data": [], "meta": {}}
            assert await client.get_markets(event_id="M") == []


@pytest.mark.asyncio
async def test_known_event_without_markets_keeps_match_fields():
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/uo/match").respond(
            json={"data": None, "meta": _detail()["meta"]}
        )
        async with Betika(country="ke") as client:
            result = await client.get_event_detail(event_id="M")
    assert result["data"][0]["odds"] == []
    assert result["data"][0]["parent_match_id"] == "70784812"


@pytest.mark.asyncio
async def test_get_sportradar_id_from_match_endpoint():
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/uo/match").respond(json=_detail())
        async with Betika(country="ke") as client:
            assert await client.get_sportradar_id("M") == "70784812"


@pytest.mark.asyncio
async def test_get_sportradar_id_none_for_unknown_event():
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/uo/match").respond(
            json={"data": None, "meta": {"is_esport": False}}
        )
        async with Betika(country="ke") as client:
            assert await client.get_sportradar_id("M") is None


@pytest.mark.asyncio
async def test_live_host_fails_closed_and_handles_unknown():
    import respx

    from bookieskit.exceptions import ResponseError
    with respx.mock() as mock:
        route = mock.get("https://live.betika.com/v1/uo/match")
        route.side_effect = [
            __import__("httpx").Response(200, json=_detail(mid="OTHER")),
            __import__("httpx").Response(
                200, json={"data": None, "meta": {"is_esport": False}}),
        ]
        async with Betika(country="ke") as client:
            with pytest.raises(ResponseError):
                await client.get_event_detail(event_id="M", live=True)
            assert await client.get_event_markets(event_id="M", live=True) == {
                "data": [], "meta": {}}


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [[], "x", {"data": {"a": 1}, "meta": "m"}])
async def test_malformed_response_is_empty_payload(body):
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/uo/match").respond(json=body)
        async with Betika(country="ke") as client:
            assert await client.get_event_detail(event_id="M") == {
                "data": [], "meta": {}}


@pytest.mark.asyncio
async def test_non_list_data_and_non_dict_groups_are_dropped():
    import respx
    with respx.mock(base_url="https://api.betika.com") as mock:
        mock.get("/v1/uo/match").mock(side_effect=[
            __import__("httpx").Response(200, json=_detail(groups={"x": 1})),
            __import__("httpx").Response(
                200, json=_detail(groups=["junk", {"sub_type_id": "1"}])),
        ])
        async with Betika(country="ke") as client:
            a = await client.get_event_detail(event_id="M")
            b = await client.get_event_detail(event_id="M")
    assert a["data"][0]["odds"] == []
    assert b["data"][0]["odds"] == [{"sub_type_id": "1"}]
