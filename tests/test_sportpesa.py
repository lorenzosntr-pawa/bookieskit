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
    # SportPesa returns a list of length 1 (not a dict with a "data" key).
    respx.get(
        "https://www.ke.sportpesa.com/api/upcoming/games"
    ).respond(json=[{"id": 8868005, "competitors": [{"name": "Arsenal"}, {"name": "Atletico"}]}])  # noqa: E501

    async with SportPesa(country="ke") as client:
        result = await client.get_event_detail(event_id="8868005")
    assert result[0]["competitors"][0]["name"] == "Arsenal"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_markets():
    # Markets payload is a dict keyed by game id; value is a list of markets.
    respx.get(
        "https://www.ke.sportpesa.com/api/games/markets"
    ).respond(json={"8868005": []})

    async with SportPesa(country="ke") as client:
        result = await client.get_event_markets(event_id="8868005")
    assert "8868005" in result


@pytest.mark.asyncio
@respx.mock
async def test_get_markets_calls_markets_endpoint():
    # get_markets should route through get_event_markets (not get_event_detail).
    markets_called = respx.get(
        "https://www.ke.sportpesa.com/api/games/markets"
    ).respond(json={"8868005": []})
    detail_called = respx.get(
        "https://www.ke.sportpesa.com/api/upcoming/games"
    ).respond(json=[{"id": 8868005}])

    async with SportPesa(country="ke") as client:
        await client.get_markets(event_id="8868005")

    assert markets_called.called
    assert not detail_called.called


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get("https://www.ke.sportpesa.com/api/live/sports").respond(
        json={"sports": [{"id": 1, "name": "Football", "eventNumber": 5}]}
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_sports()
    assert result["sports"][0]["name"] == "Football"
    assert result["sports"][0]["eventNumber"] == 5


@pytest.mark.asyncio
@respx.mock
async def test_get_events_prematch():
    respx.get("https://www.ke.sportpesa.com/api/upcoming/games").respond(
        json=[{"id": 8868005, "competition": {"id": 100, "name": "EPL"}}]
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_events(sport_id="1", league_id="100")
    assert result[0]["competition"]["name"] == "EPL"


@pytest.mark.asyncio
@respx.mock
async def test_get_events_live_uses_highlights():
    respx.get("https://www.ke.sportpesa.com/api/highlights/1").respond(
        json=[{"id": 8868005, "marketsCount": 22}]
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_events(sport_id="1", live=True)
    assert result[0]["marketsCount"] == 22


@pytest.mark.asyncio
@respx.mock
async def test_get_navigation():
    respx.get("https://www.ke.sportpesa.com/api/navigation").respond(
        json=[
            {
                "id": 1,
                "name": "Football",
                "order": 0,
                "has_matches": True,
                "countries": [
                    {
                        "id": 61,
                        "name": "England",
                        "iso_name": "eng",
                        "leagues": [
                            {"id": 67600, "name": "Premier League",
                             "top_league_pos": 2},
                        ],
                    },
                ],
            },
        ]
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_navigation()
    assert result[0]["name"] == "Football"
    assert result[0]["countries"][0]["leagues"][0]["id"] == 67600


@pytest.mark.asyncio
@respx.mock
async def test_get_live_events_started():
    respx.get(
        "https://www.ke.sportpesa.com/api/live/sports/1/events/started"
    ).respond(
        json={
            "events": [
                {
                    "id": 8868005,
                    "tournament": {"id": 67600, "name": "Premier League"},
                    "sport": {"id": 1, "name": "Football"},
                    "country": {"id": 61, "name": "England"},
                },
            ]
        }
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_live_events_started(sport_id="1")
    assert result["events"][0]["tournament"]["id"] == 67600


@pytest.mark.asyncio
@respx.mock
async def test_get_live_sport_events():
    respx.get(
        "https://www.ke.sportpesa.com/api/live/sports/1/events"
    ).respond(json={"events": [{"id": 8868005}, {"id": 8868006}]})
    async with SportPesa(country="ke") as client:
        result = await client.get_live_sport_events(sport_id="1")
    assert len(result["events"]) == 2


@pytest.mark.asyncio
@respx.mock
async def test_get_events_uses_league_id_not_competition_id():
    # `leagueId` is the only filter that actually walks past the rolling
    # window; `competitionId` is silently ignored by the API.
    route = respx.get(
        "https://www.ke.sportpesa.com/api/upcoming/games"
    ).respond(json=[{"id": 8868005, "competition": {"id": 67600}}])
    async with SportPesa(country="ke") as client:
        await client.get_events(sport_id="1", league_id="67600", pag_count=100)
    # Verify the captured request used leagueId (NOT competitionId)
    last_call = route.calls.last
    assert "leagueId=67600" in str(last_call.request.url)
    assert "competitionId" not in str(last_call.request.url)


def test_sportpesa_exported_from_top_level():
    from bookieskit import SportPesa as SP
    from bookieskit.bookmakers.sportpesa import SportPesa as SP2
    assert SP is SP2


def test_top_level_version_bumped():
    import bookieskit
    assert bookieskit.__version__ == "0.8.0"
