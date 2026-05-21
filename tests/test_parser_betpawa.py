from bookieskit.markets.parser import parse_markets
from bookieskit.markets.registry import MarketRegistry

BETPAWA_EVENT_RESPONSE = {
    "id": "32299257",
    "homeTeam": "Manchester City",
    "awayTeam": "Liverpool",
    "markets": [
        {
            "id": "3743",
            "name": "1X2 - Full Time",
            "row": [
                {
                    "prices": [
                        {"name": "1", "odds": 1.95},
                        {"name": "X", "odds": 3.50},
                        {"name": "2", "odds": 2.10},
                    ]
                }
            ],
        },
        {
            "id": "5000",
            "name": "Over/Under",
            "row": [
                {
                    "line": 2.5,
                    "prices": [
                        {"name": "Over", "odds": 1.80},
                        {"name": "Under", "odds": 2.00},
                    ],
                },
                {
                    "line": 3.5,
                    "prices": [
                        {"name": "Over", "odds": 2.10},
                        {"name": "Under", "odds": 1.70},
                    ],
                },
            ],
        },
        {
            "id": "3795",
            "name": "Both Teams To Score",
            "row": [
                {
                    "prices": [
                        {"name": "Yes", "odds": 1.75},
                        {"name": "No", "odds": 2.05},
                    ]
                }
            ],
        },
        {
            "id": "4693",
            "name": "Double Chance",
            "row": [
                {
                    "prices": [
                        {"name": "1X", "odds": 1.25},
                        {"name": "X2", "odds": 1.50},
                        {"name": "12", "odds": 1.10},
                    ]
                }
            ],
        },
        {
            "id": "9999",
            "name": "Unknown Market",
            "row": [{"prices": [{"name": "A", "odds": 2.00}]}],
        },
    ],
}


def test_parse_betpawa_1x2():
    markets = parse_markets(BETPAWA_EVENT_RESPONSE, platform="betpawa")
    m1x2 = next(m for m in markets if m.canonical_id == "1x2_ft")
    assert m1x2.name == "1X2 - Full Time"
    assert len(m1x2.outcomes) == 3
    assert m1x2.lines is None
    home = next(o for o in m1x2.outcomes if o.canonical_name == "home")
    assert home.odds == 1.95
    assert home.platform_name == "1"


def test_parse_betpawa_over_under():
    markets = parse_markets(BETPAWA_EVENT_RESPONSE, platform="betpawa")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    assert ou.lines is not None
    assert 2.5 in ou.lines
    assert 3.5 in ou.lines
    assert len(ou.outcomes) == 0
    over_25 = next(
        o for o in ou.lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds == 1.80
    assert over_25.platform_name == "Over"


def test_parse_betpawa_btts():
    markets = parse_markets(BETPAWA_EVENT_RESPONSE, platform="betpawa")
    btts = next(m for m in markets if m.canonical_id == "btts_ft")
    assert len(btts.outcomes) == 2
    yes = next(o for o in btts.outcomes if o.canonical_name == "yes")
    assert yes.odds == 1.75


def test_parse_betpawa_double_chance():
    markets = parse_markets(BETPAWA_EVENT_RESPONSE, platform="betpawa")
    dc = next(m for m in markets if m.canonical_id == "double_chance_ft")
    assert len(dc.outcomes) == 3
    hd = next(o for o in dc.outcomes if o.canonical_name == "home_draw")
    assert hd.odds == 1.25


def test_parse_betpawa_skips_unknown_markets():
    markets = parse_markets(BETPAWA_EVENT_RESPONSE, platform="betpawa")
    ids = [m.canonical_id for m in markets]
    assert len(markets) == 4
    assert "1x2_ft" in ids
    assert "over_under_ft" in ids
    assert "btts_ft" in ids
    assert "double_chance_ft" in ids


def test_parse_betpawa_with_custom_registry():
    registry = MarketRegistry(load_builtins=False)
    markets = parse_markets(
        BETPAWA_EVENT_RESPONSE, platform="betpawa", registry=registry
    )
    assert len(markets) == 0


def test_parse_betpawa_next_goal_ft_from_real_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betpawa/prematch.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="betpawa")
    ng = next(
        (m for m in markets if m.canonical_id == "next_goal_ft"),
        None,
    )
    assert ng is not None
    assert ng.name == "Next Goal - Full Time"
    assert ng.lines is not None
    # Prematch always has goal-number 1 (the next-goal-to-be-scored)
    assert 1.0 in ng.lines
    line1 = {o.canonical_name: o for o in ng.lines[1.0]}
    assert set(line1.keys()) == {"home", "none", "away"}
    # From the fixture: 1=1.94, None=11.04, 2=2.20
    assert line1["home"].odds == 1.94
    assert line1["none"].odds == 11.04
    assert line1["away"].odds == 2.20


def test_parse_betpawa_home_over_under_ft_from_real_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betpawa/prematch.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="betpawa")
    home_ou = next(
        (m for m in markets if m.canonical_id == "home_over_under_ft"),
        None,
    )
    assert home_ou is not None
    assert home_ou.lines is not None
    # Fixture has lines 0.5 / 1.5 / 2.5 from rows id=374100486/485/493
    assert 0.5 in home_ou.lines
    line05 = {o.canonical_name: o.odds for o in home_ou.lines[0.5]}
    assert line05 == {"over": 1.23, "under": 3.47}


def test_parse_betpawa_away_over_under_ft_from_real_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betpawa/prematch.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="betpawa")
    away_ou = next(
        (m for m in markets if m.canonical_id == "away_over_under_ft"),
        None,
    )
    assert away_ou is not None
    assert away_ou.lines is not None
    assert len(away_ou.lines) >= 1
    # At least one line must have both over and under outcomes
    for line, outs in away_ou.lines.items():
        names = {o.canonical_name for o in outs}
        if {"over", "under"}.issubset(names):
            return
    raise AssertionError("no away O/U line had both over and under")
