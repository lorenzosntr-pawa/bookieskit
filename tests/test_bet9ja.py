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
    respx.get("https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetEventsInGroup").respond(
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


@pytest.mark.asyncio
@respx.mock
async def test_find_event_id_by_sr_id_found():
    respx.get(
        "https://sports.bet9ja.com/desktop/feapi/PalimpsestLiveAjax/GetLiveEventsV3"
    ).respond(
        json={
            "D": {
                "E": {
                    "9138769": {"EXTID": "69339436", "DS": "Arsenal vs Atletico"},
                    "9138770": {"EXTID": "13858490", "DS": "Other"},
                }
            }
        }
    )
    async with Bet9ja(country="ng") as client:
        internal = await client.find_event_id_by_sr_id("sr:match:69339436")
    assert internal == "9138769"


@pytest.mark.asyncio
@respx.mock
async def test_find_event_id_by_sr_id_numeric_input():
    respx.get(
        "https://sports.bet9ja.com/desktop/feapi/PalimpsestLiveAjax/GetLiveEventsV3"
    ).respond(
        json={"D": {"E": {"9138769": {"EXTID": "69339436"}}}}
    )
    async with Bet9ja(country="ng") as client:
        internal = await client.find_event_id_by_sr_id("69339436")
    assert internal == "9138769"


@pytest.mark.asyncio
@respx.mock
async def test_find_event_id_by_sr_id_not_found():
    respx.get(
        "https://sports.bet9ja.com/desktop/feapi/PalimpsestLiveAjax/GetLiveEventsV3"
    ).respond(json={"D": {"E": {"9138770": {"EXTID": "99999"}}}})
    async with Bet9ja(country="ng") as client:
        internal = await client.find_event_id_by_sr_id("69339436")
    assert internal is None


@pytest.mark.asyncio
@respx.mock
async def test_get_live_event_detail_uses_eventid_param():
    route = respx.get(
        "https://sports.bet9ja.com/desktop/feapi/PalimpsestLiveAjax/GetLiveEvent"
    ).respond(json={"R": "OK", "D": {"O": {}}})
    async with Bet9ja(country="ng") as client:
        await client.get_live_event_detail(event_id="9138769")
    # The live endpoint expects parameter name EVENTID (uppercase).
    assert route.calls[0].request.url.params["EVENTID"] == "9138769"


@pytest.mark.asyncio
@respx.mock
async def test_build_prematch_event_map_walks_tournaments():
    # GetSports response: one sport ("1" = Soccer), one country, two
    # tournaments. The map should cover events from BOTH.
    respx.get(
        "https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetSports"
    ).respond(
        json={
            "D": {
                "PAL": {
                    "1": {
                        "S_DESC": "Soccer",
                        "SG": {
                            "ENG": {
                                "G": {
                                    "170880": {"G_DESC": "Premier League"},
                                    "170881": {"G_DESC": "Championship"},
                                }
                            }
                        },
                    }
                }
            }
        }
    )
    # GetEventsInGroup — respond differently per tournament via side_effect.
    def by_tournament(request):
        import httpx
        tid = request.url.params.get("GROUPID", "")
        if tid == "170880":
            return httpx.Response(
                200,
                json={"D": {"E": [
                    {"ID": 9000001, "EXTID": "11111"},
                    {"ID": 9000002, "EXTID": "22222"},
                ]}},
            )
        if tid == "170881":
            return httpx.Response(
                200,
                json={"D": {"E": [{"ID": 9000003, "EXTID": "33333"}]}},
            )
        return httpx.Response(200, json={"D": {"E": []}})

    respx.get(
        "https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetEventsInGroup"
    ).mock(side_effect=by_tournament)

    async with Bet9ja(country="ng") as client:
        sr_map = await client.build_prematch_event_map(sport_id="1")

    assert sr_map == {"11111": "9000001", "22222": "9000002", "33333": "9000003"}
