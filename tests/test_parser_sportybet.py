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


def test_extract_line_from_specifier_recognises_goalnr():
    from bookieskit.markets.parser import _extract_line_from_specifier
    assert _extract_line_from_specifier("goalnr=1") == 1.0
    assert _extract_line_from_specifier("goalnr=2") == 2.0
    assert _extract_line_from_specifier("total=2.5|goalnr=3") == 2.5  # total wins (first match)
    # Non-recognised key still returns None
    assert _extract_line_from_specifier("foo=1") is None


def test_parse_sportybet_next_goal_ft_from_real_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/sportybet/prematch.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="sportybet")
    ng = next(
        (m for m in markets if m.canonical_id == "next_goal_ft"),
        None,
    )
    assert ng is not None
    assert ng.lines is not None
    assert 1.0 in ng.lines  # 1st Goal — goalnr=1 → line=1.0
    line1 = {o.canonical_name: o for o in ng.lines[1.0]}
    assert set(line1.keys()) == {"home", "none", "away"}
    # From the fixture: Home=1.93, None=11.00, Away=2.20
    assert line1["home"].odds == 1.93
    assert line1["none"].odds == 11.00
    assert line1["away"].odds == 2.20
