"""`sport` must reach parse_markets from every client's get_markets."""

import json
from pathlib import Path

import pytest

from bookieskit.bookmakers.betika import Betika
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.betway import Betway
from bookieskit.bookmakers.sportpesa import SportPesa
from bookieskit.markets import parser as parser_mod
from bookieskit.markets.parser import parse_markets

FIXTURE = (
    Path(__file__).parent / "fixtures" / "event_info" / "sportpesa" / "tennis.json"
)

# (client class, fetch method that get_markets calls)
CLIENTS = [
    (BetPawa, "get_event_detail"),
    (Betika, "get_event_markets"),
    (Betway, "get_event_markets_all"),
    (SportPesa, "get_event_markets"),
]


def _patch_fetch(monkeypatch, client, method, payload):
    async def fake(**kwargs):
        return payload

    monkeypatch.setattr(client, method, fake)


async def test_get_markets_passes_sport(monkeypatch):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    client = SportPesa("ke")
    _patch_fetch(monkeypatch, client, "get_event_markets", raw)

    markets = await client.get_markets("8899005", sport="tennis")

    ids = [m.canonical_id for m in markets]
    assert ids
    assert not any("basketball" in i for i in ids)
    assert any("tennis" in i for i in ids)


async def test_get_markets_without_sport_unchanged(monkeypatch):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    client = SportPesa("ke")
    _patch_fetch(monkeypatch, client, "get_event_markets", raw)

    assert await client.get_markets("8899005") == parse_markets(raw, "sportpesa")


@pytest.mark.parametrize("cls,method", CLIENTS)
async def test_get_markets_forwards_sport_to_parser(monkeypatch, cls, method):
    client = cls(country="ng") if cls is Betway else cls("ke")
    _patch_fetch(monkeypatch, client, method, {})
    seen = {}

    def spy(response, platform, registry=None, **kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(parser_mod, "parse_markets", spy)

    await client.get_markets("1", sport="basketball")

    assert seen.get("sport") == "basketball"
