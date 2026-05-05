import pytest
import respx

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.sportybet import SportyBet


@pytest.mark.asyncio
@respx.mock
async def test_betpawa_get_markets():
    respx.get(
        "https://www.betpawa.ng/api/sportsbook/v3/events/123"
    ).respond(
        json={
            "id": "123",
            "markets": [
                {
                    "id": "3743",
                    "name": "1X2",
                    "row": [
                        {
                            "prices": [
                                {"name": "1", "odds": 1.95},
                                {"name": "X", "odds": 3.50},
                                {"name": "2", "odds": 2.10},
                            ]
                        }
                    ],
                }
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        markets = await client.get_markets(event_id="123")
    assert len(markets) == 1
    assert markets[0].canonical_id == "1x2_ft"


@pytest.mark.asyncio
@respx.mock
async def test_betpawa_get_sportradar_id():
    respx.get(
        "https://www.betpawa.ng/api/sportsbook/v3/events/123"
    ).respond(
        json={
            "id": "123",
            "widgets": [
                {"type": "SPORTRADAR", "value": "sr:match:999"}
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        sr_id = await client.get_sportradar_id(event_id="123")
    assert sr_id == "999"


@pytest.mark.asyncio
@respx.mock
async def test_sportybet_get_markets():
    respx.get(
        "https://www.sportybet.com/api/ng/factsCenter/event"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "eventId": "sr:match:100",
                "markets": [
                    {
                        "id": "29",
                        "desc": "BTTS",
                        "specifier": None,
                        "outcomes": [
                            {"id": "1", "desc": "Yes", "odds": "1.75"},
                            {"id": "2", "desc": "No", "odds": "2.05"},
                        ],
                    }
                ],
            },
        }
    )
    async with SportyBet(country="ng") as client:
        markets = await client.get_markets(event_id="sr:match:100")
    assert len(markets) == 1
    assert markets[0].canonical_id == "btts_ft"


@pytest.mark.asyncio
@respx.mock
async def test_bet9ja_get_sportradar_id():
    respx.get(
        "https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetEvent"
    ).respond(
        json={"R": "D", "D": {"EXTID": "61300947", "O": {}}}
    )
    async with Bet9ja(country="ng") as client:
        sr_id = await client.get_sportradar_id(event_id="707096003")
    assert sr_id == "61300947"


@respx.mock
def test_sync_get_markets():
    respx.get(
        "https://www.betpawa.ng/api/sportsbook/v3/events/123"
    ).respond(
        json={
            "id": "123",
            "markets": [
                {
                    "id": "3795",
                    "name": "BTTS",
                    "row": [
                        {
                            "prices": [
                                {"name": "Yes", "odds": 1.75},
                                {"name": "No", "odds": 2.05},
                            ]
                        }
                    ],
                }
            ],
        }
    )
    with BetPawa(country="ng") as client:
        markets = client.get_markets(event_id="123")
    assert len(markets) == 1
    assert markets[0].canonical_id == "btts_ft"
