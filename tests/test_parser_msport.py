from bookieskit.markets.parser import parse_markets

MSPORT_EVENT_RESPONSE = {
    "bizCode": 10000,
    "data": {
        "eventId": "sr:match:61301231",
        "markets": [
            {
                "id": "1",
                "description": "1x2",
                "name": "1x2",
                "specifiers": None,
                "outcomes": [
                    {"id": "1", "description": "Home", "odds": "2.76"},
                    {"id": "2", "description": "Draw", "odds": "3.77"},
                    {"id": "3", "description": "Away", "odds": "2.39"},
                ],
            },
            {
                "id": "18",
                "description": "Over/Under",
                "name": "Over/Under",
                "specifiers": "total=2.5",
                "outcomes": [
                    {"id": "12", "description": "Over", "odds": "1.80"},
                    {"id": "13", "description": "Under", "odds": "2.00"},
                ],
            },
            {
                "id": "18",
                "description": "Over/Under",
                "name": "Over/Under",
                "specifiers": "total=3.5",
                "outcomes": [
                    {"id": "12", "description": "Over", "odds": "2.10"},
                    {"id": "13", "description": "Under", "odds": "1.70"},
                ],
            },
            {
                "id": "29",
                "description": "Both Teams To Score",
                "name": "Both Teams To Score",
                "specifiers": None,
                "outcomes": [
                    {"id": "74", "description": "Yes", "odds": "1.75"},
                    {"id": "76", "description": "No", "odds": "2.05"},
                ],
            },
            {
                "id": "10",
                "description": "Double Chance",
                "name": "Double Chance",
                "specifiers": None,
                "outcomes": [
                    {"id": "9", "description": "1 X", "odds": "1.25"},
                    {"id": "11", "description": "X 2", "odds": "1.50"},
                    {"id": "10", "description": "1 2", "odds": "1.10"},
                ],
            },
            {
                "id": "999",
                "description": "Unknown Market",
                "name": "Unknown",
                "specifiers": None,
                "outcomes": [
                    {"id": "1", "description": "Option A", "odds": "2.00"},
                ],
            },
        ],
    },
}


def test_parse_msport_1x2():
    markets = parse_markets(MSPORT_EVENT_RESPONSE, platform="msport")
    m = next(m for m in markets if m.canonical_id == "1x2_ft")
    assert len(m.outcomes) == 3
    assert m.lines is None
    home = next(o for o in m.outcomes if o.canonical_name == "home")
    assert home.odds == 2.76
    assert home.platform_name == "Home"


def test_parse_msport_over_under():
    markets = parse_markets(MSPORT_EVENT_RESPONSE, platform="msport")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    assert ou.lines is not None
    assert 2.5 in ou.lines
    assert 3.5 in ou.lines
    over_25 = next(
        o for o in ou.lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds == 1.80


def test_parse_msport_btts():
    markets = parse_markets(MSPORT_EVENT_RESPONSE, platform="msport")
    btts = next(m for m in markets if m.canonical_id == "btts_ft")
    assert len(btts.outcomes) == 2
    yes = next(o for o in btts.outcomes if o.canonical_name == "yes")
    assert yes.odds == 1.75


def test_parse_msport_double_chance():
    markets = parse_markets(MSPORT_EVENT_RESPONSE, platform="msport")
    dc = next(m for m in markets if m.canonical_id == "double_chance_ft")
    assert len(dc.outcomes) == 3
    home_draw = next(
        o for o in dc.outcomes if o.canonical_name == "home_draw"
    )
    assert home_draw.platform_name == "1 X"


def test_parse_msport_skips_unknown_market():
    markets = parse_markets(MSPORT_EVENT_RESPONSE, platform="msport")
    canonical_ids = {m.canonical_id for m in markets}
    assert "999" not in canonical_ids
    assert len(markets) == 4


def test_parse_msport_outcome_prefix_fallback():
    """Parameterized markets sometimes embed the line in the description
    (e.g. 'Over 2.5'). The resolver should match by prefix."""
    response = {
        "bizCode": 10000,
        "data": {
            "markets": [
                {
                    "id": "18",
                    "description": "Over/Under",
                    "specifiers": "total=2.5",
                    "outcomes": [
                        {"id": "12", "description": "Over 2.5", "odds": "1.80"},
                        {"id": "13", "description": "Under 2.5", "odds": "2.00"},
                    ],
                }
            ]
        },
    }
    markets = parse_markets(response, platform="msport")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    over = next(o for o in ou.lines[2.5] if o.canonical_name == "over")
    assert over.platform_name == "Over 2.5"


def test_parse_msport_next_goal_ft_from_probe_fixture():
    """Skipped: MSport only exposes Next Goal (id=8) on live events; the
    captured probe fixture is the prematch Qatar v Sudan which doesn't
    contain id=8. The shape is verified by the registry smoke test
    and by the live-probe RESOLVED record entry.
    """
    import pytest
    pytest.skip("MSport next_goal_ft not captured in prematch probe fixture")


def test_parse_msport_home_over_under_ft_from_probe_fixture():
    import json
    from pathlib import Path

    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/msport/next_goal_and_team_ou.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))
    markets = parse_markets(response, platform="msport")
    home_ou = next(
        (m for m in markets if m.canonical_id == "home_over_under_ft"),
        None,
    )
    assert home_ou is not None, "MSport home_over_under_ft (id=19) not found"
    assert home_ou.lines is not None
    assert len(home_ou.lines) >= 1
    # At least one line must have both over+under
    assert any(
        {"over", "under"}.issubset({o.canonical_name for o in outs})
        for outs in home_ou.lines.values()
    )


def test_parse_msport_away_over_under_ft_from_probe_fixture():
    import json
    from pathlib import Path

    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/msport/next_goal_and_team_ou.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))
    markets = parse_markets(response, platform="msport")
    away_ou = next(
        (m for m in markets if m.canonical_id == "away_over_under_ft"),
        None,
    )
    assert away_ou is not None, "MSport away_over_under_ft (id=20) not found"
    assert away_ou.lines is not None
    assert any(
        {"over", "under"}.issubset({o.canonical_name for o in outs})
        for outs in away_ou.lines.values()
    )


def test_parse_msport_2way_handicap_ft_from_probe_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/msport/2way_handicap_ft.json")
    if not fixture.exists():
        import pytest
        pytest.skip("MSport probe fixture not captured")
    response = json.loads(fixture.read_text(encoding="utf-8"))
    markets = parse_markets(response, platform="msport")
    ah = next(
        (m for m in markets if m.canonical_id == "2way_handicap_ft"),
        None,
    )
    assert ah is not None, "MSport 2way_handicap_ft (id=16) not in fixture"
    assert ah.lines is not None
    assert any(
        {"home", "away"}.issubset({o.canonical_name for o in outs})
        for outs in ah.lines.values()
    )
