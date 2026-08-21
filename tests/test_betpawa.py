import pytest
import respx

from bookieskit.bookmakers.betpawa import BetPawa


def test_betpawa_country_ng_resolves_domain():
    client = BetPawa(country="ng")
    assert client.base_url == "https://www.betpawa.ng"


def test_betpawa_country_gh_resolves_domain():
    client = BetPawa(country="gh")
    assert client.base_url == "https://www.betpawa.com.gh"


def test_betpawa_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        BetPawa(country="xx")


@pytest.mark.parametrize(
    "country,expected_url,expected_brand",
    [
        # Added in 0.8.0
        ("rw", "https://www.betpawa.rw", "betpawa-rwanda"),
        ("cm", "https://www.betpawa.cm", "betpawa-cameroon"),
        # sl moved to the subdomain form in the 2026-08-21 sweep: the
        # ccTLD host 308-redirects, which the client cannot follow.
        ("sl", "https://sl.betpawa.com", "betpawa-sierraleone"),
        # Added in 0.10.0 — completes the full 15-country BetPawa footprint
        # advertised on the landing-page country selector. URLs and brand
        # headers verified against the live sportsbook API.
        ("bj", "https://www.betpawa.bj", "betpawa-benin"),
        ("cg", "https://cg.betpawa.com", "betpawa-congobrazzaville"),
        ("cd", "https://www.betpawa.cd", "betpawa-drc"),
        ("ls", "https://ls.betpawa.com", "betpawa-lesotho"),
        ("mw", "https://www.betpawa.mw", "betpawa-malawi"),
        ("mz", "https://www.betpawa.co.mz", "betpawa-mozambique"),
    ],
)
def test_betpawa_new_countries_resolve_domain_and_brand(
    country, expected_url, expected_brand
):
    """BetPawa countries added in 0.8.0 (rw/cm/sl) and 0.10.0
    (bj/cg/cd/ls/mw/mz) — verified against the live sportsbook API."""
    client = BetPawa(country=country)
    assert client.base_url == expected_url
    headers = client._build_headers()
    assert headers["x-pawa-brand"] == expected_brand


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get("https://www.betpawa.ng/api/sportsbook/v4/categories/list/all").respond(
        json={
            "categories": [
                {"id": "2", "name": "Football"},
                {"id": "3", "name": "Basketball"},
            ]
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_sports()
    assert result["categories"][0]["name"] == "Football"


@pytest.mark.asyncio
@respx.mock
async def test_get_countries():
    respx.get("https://www.betpawa.ng/api/sportsbook/v4/categories/list/2").respond(
        json={
            "id": "2",
            "name": "Football",
            "regions": [
                {"id": "1", "name": "England", "competitions": []},
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_countries(sport_id="2")
    assert result["regions"][0]["name"] == "England"


@pytest.mark.asyncio
@respx.mock
async def test_get_tournaments():
    respx.get("https://www.betpawa.ng/api/sportsbook/v4/categories/list/2").respond(
        json={
            "id": "2",
            "name": "Football",
            "regions": [
                {
                    "id": "1",
                    "name": "England",
                    "competitions": [
                        {"id": "11965", "name": "Premier League"},
                    ],
                },
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_tournaments(sport_id="2")
    assert result["regions"][0]["competitions"][0]["name"] == "Premier League"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get("https://www.betpawa.ng/api/sportsbook/v4/events/lists/by-queries").respond(
        json={
            "responses": [
                {
                    "responses": [
                        {
                            "id": "32299257",
                            "homeTeam": "Manchester City",
                            "awayTeam": "Liverpool",
                        }
                    ]
                }
            ]
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_events(tournament_id="11965")
    assert result["responses"][0]["responses"][0]["homeTeam"] == "Manchester City"


@pytest.mark.asyncio
@respx.mock
async def test_get_events_with_sport_id():
    respx.get("https://www.betpawa.ng/api/sportsbook/v4/events/lists/by-queries").respond(
        json={"responses": [{"responses": []}]}
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_events(tournament_id="11965", sport_id="3")
    assert result["responses"][0]["responses"] == []


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail():
    respx.get("https://www.betpawa.ng/api/sportsbook/v4/events/32299257").respond(
        json={
            "id": "32299257",
            "homeTeam": "Manchester City",
            "awayTeam": "Liverpool",
            "markets": [
                {
                    "marketType": {"id": "3743", "name": "1X2"},
                    "row": [{"prices": [{"name": "1", "price": 1.95}]}],
                }
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_event_detail(event_id="32299257")
    assert result["markets"][0]["marketType"]["id"] == "3743"


@pytest.mark.asyncio
@respx.mock
async def test_betpawa_headers_include_brand():
    route = respx.get("https://www.betpawa.ng/api/sportsbook/v4/categories/list/all").respond(
        json={"categories": []}
    )
    async with BetPawa(country="ng") as client:
        await client.get_sports()
    assert route.calls[0].request.headers["x-pawa-brand"] == "betpawa-nigeria"


@pytest.mark.asyncio
@respx.mock
async def test_betpawa_requests_json_not_protobuf():
    """The v4 API serves application/x-protobuf for `accept: */*` on
    /events/lists/by-queries, which httpx cannot decode. The accept header
    must stay explicit, or every event fetch comes back as binary garbage."""
    route = respx.get(
        "https://www.betpawa.ng/api/sportsbook/v4/events/lists/by-queries"
    ).respond(json={"responses": [{}]})
    async with BetPawa(country="ng") as client:
        await client.get_events(tournament_id="12541")
    assert route.calls[0].request.headers["accept"] == "application/json"


def test_betpawa_supports_all_22_live_jurisdictions():
    """Jurisdiction sweep of 2026-08-21.

    Every candidate domain was probed against
    ``/api/sportsbook/v4/categories/list/all`` and accepted only when the
    response was JSON carrying ``onlyMeta`` — a status-200 check alone is
    not enough, because some ccTLD hosts answer 200 with the marketing
    site's HTML shell (www.betpawa.tg and www.betpawa.tz both did).
    """
    from bookieskit.bookmakers.betpawa import _BRAND_MAP

    expected = {
        "ng", "gh", "ke", "ug", "tz", "zm", "rw", "cm", "sl", "bj", "cg",
        "cd", "ls", "mw", "mz",           # the original 15
        "ao", "bw", "lr", "ml", "ss", "tg", "zw",   # added 2026-08-21
    }
    assert set(BetPawa.DOMAINS) == expected
    # A country is unusable without its brand header, so the two maps must
    # never drift apart.
    assert set(_BRAND_MAP) == set(BetPawa.DOMAINS)
    for cc, url in BetPawa.DOMAINS.items():
        assert url.startswith("https://"), cc
        assert not url.endswith("/"), cc


def test_betpawa_new_jurisdictions_use_the_form_that_served_the_api():
    # lr/ss/tg have no working ccTLD site at all — only the subdomain form.
    assert BetPawa.DOMAINS["lr"] == "https://lr.betpawa.com"
    assert BetPawa.DOMAINS["ss"] == "https://ss.betpawa.com"
    assert BetPawa.DOMAINS["tg"] == "https://tg.betpawa.com"
    assert BetPawa.DOMAINS["bw"] == "https://bw.betpawa.com"
    assert BetPawa.DOMAINS["ml"] == "https://ml.betpawa.com"
    assert BetPawa.DOMAINS["zw"] == "https://zw.betpawa.com"


def test_betpawa_domains_are_redirect_free_forms():
    """The client does not follow redirects, so every domain must answer direct.

    `sl` and `ug` were misconfigured to ccTLD hosts that 308 to another host,
    which made every call to those two jurisdictions raise ResponseError 308.
    Fixed in the 2026-08-21 sweep; pinned here so a redirect-following probe
    cannot reintroduce a redirecting host.
    """
    assert BetPawa.DOMAINS["sl"] == "https://sl.betpawa.com"
    assert BetPawa.DOMAINS["ug"] == "https://www.betpawa.ug"
