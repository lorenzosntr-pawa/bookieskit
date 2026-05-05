from bookieskit.markets.parser import parse_markets

SPORTYBET_EVENT_RESPONSE = {
    "bizCode": 10000,
    "data": {
        "eventId": "sr:match:61300947",
        "markets": [
            {
                "id": "1",
                "desc": "1X2 - Full Time",
                "specifier": None,
                "outcomes": [
                    {"id": "1", "desc": "Home", "odds": "1.95"},
                    {"id": "2", "desc": "Draw", "odds": "3.50"},
                    {"id": "3", "desc": "Away", "odds": "2.10"},
                ],
            },
            {
                "id": "18",
                "desc": "Over/Under",
                "specifier": "total=2.5",
                "outcomes": [
                    {"id": "1", "desc": "Over", "odds": "1.80"},
                    {"id": "2", "desc": "Under", "odds": "2.00"},
                ],
            },
            {
                "id": "18",
                "desc": "Over/Under",
                "specifier": "total=3.5",
                "outcomes": [
                    {"id": "1", "desc": "Over", "odds": "2.10"},
                    {"id": "2", "desc": "Under", "odds": "1.70"},
                ],
            },
            {
                "id": "29",
                "desc": "Both Teams To Score",
                "specifier": None,
                "outcomes": [
                    {"id": "1", "desc": "Yes", "odds": "1.75"},
                    {"id": "2", "desc": "No", "odds": "2.05"},
                ],
            },
            {
                "id": "10",
                "desc": "Double Chance",
                "specifier": None,
                "outcomes": [
                    {"id": "1", "desc": "Home or Draw", "odds": "1.25"},
                    {"id": "2", "desc": "Draw or Away", "odds": "1.50"},
                    {"id": "3", "desc": "Home or Away", "odds": "1.10"},
                ],
            },
            {
                "id": "999",
                "desc": "Unknown Market",
                "specifier": None,
                "outcomes": [
                    {"id": "1", "desc": "Option A", "odds": "2.00"},
                ],
            },
        ],
    },
}


def test_parse_sportybet_1x2():
    markets = parse_markets(SPORTYBET_EVENT_RESPONSE, platform="sportybet")
    m1x2 = next(m for m in markets if m.canonical_id == "1x2_ft")
    assert m1x2.name == "1X2 - Full Time"
    assert len(m1x2.outcomes) == 3
    assert m1x2.lines is None
    home = next(o for o in m1x2.outcomes if o.canonical_name == "home")
    assert home.odds == 1.95
    assert home.platform_name == "Home"


def test_parse_sportybet_over_under():
    markets = parse_markets(SPORTYBET_EVENT_RESPONSE, platform="sportybet")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    assert ou.lines is not None
    assert 2.5 in ou.lines
    assert 3.5 in ou.lines
    over_25 = next(
        o for o in ou.lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds == 1.80
    assert over_25.platform_name == "Over"


def test_parse_sportybet_btts():
    markets = parse_markets(SPORTYBET_EVENT_RESPONSE, platform="sportybet")
    btts = next(m for m in markets if m.canonical_id == "btts_ft")
    assert len(btts.outcomes) == 2
    yes = next(o for o in btts.outcomes if o.canonical_name == "yes")
    assert yes.odds == 1.75


def test_parse_sportybet_double_chance():
    markets = parse_markets(SPORTYBET_EVENT_RESPONSE, platform="sportybet")
    dc = next(m for m in markets if m.canonical_id == "double_chance_ft")
    assert len(dc.outcomes) == 3
    hd = next(o for o in dc.outcomes if o.canonical_name == "home_draw")
    assert hd.odds == 1.25
    assert hd.platform_name == "Home or Draw"


def test_parse_sportybet_skips_unknown():
    markets = parse_markets(SPORTYBET_EVENT_RESPONSE, platform="sportybet")
    assert len(markets) == 4
