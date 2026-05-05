import respx

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.sportybet import SportyBet


@respx.mock
def test_betpawa_sync_get_sports():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/categories/list/all").respond(
        json={"categories": [{"id": "2", "name": "Football"}]}
    )
    with BetPawa(country="ng") as client:
        result = client.get_sports()
    assert result["categories"][0]["name"] == "Football"


@respx.mock
def test_betpawa_sync_get_event_detail():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/events/32299257").respond(
        json={"id": "32299257", "markets": []}
    )
    with BetPawa(country="ng") as client:
        result = client.get_event_detail(event_id="32299257")
    assert result["id"] == "32299257"


@respx.mock
def test_sportybet_sync_get_sports():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/popularAndSportList").respond(
        json={"bizCode": 10000, "data": {"sportList": []}}
    )
    with SportyBet(country="ng") as client:
        result = client.get_sports()
    assert result["bizCode"] == 10000


@respx.mock
def test_bet9ja_sync_get_event_detail():
    respx.get("https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetEvent").respond(
        json={"R": "D", "D": {"O": {"S_1X2_1": "2.00"}}}
    )
    with Bet9ja(country="ng") as client:
        result = client.get_event_detail(event_id="123")
    assert result["D"]["O"]["S_1X2_1"] == "2.00"
