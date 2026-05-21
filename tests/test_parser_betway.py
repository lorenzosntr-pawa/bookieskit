from bookieskit.markets.parser import parse_markets

BETWAY_MARKETS_RESPONSE = {
    "marketGroupNames": ["Main", "Totals"],
    "marketsInGroup": [
        {
            "marketId": "693394361",
            "name": "[Win/Draw/Win]",
            "displayName": "1X2",
            "handicap": 0,
        },
        {
            "marketId": "6933943610",
            "name": "[Double Chance]",
            "displayName": "Double Chance",
            "handicap": 0,
        },
        {
            "marketId": "69339436btts",
            "name": "[Both Teams To Score]",
            "displayName": "Both Teams To Score",
            "handicap": 0,
        },
        {
            "marketId": "6933943618total=2.5~",
            "name": "Total",
            "displayName": "Total (2.5)",
            "handicap": 2.5,
        },
        {
            "marketId": "6933943618total=3.5~",
            "name": "Total",
            "displayName": "Total (3.5)",
            "handicap": 3.5,
        },
        {
            "marketId": "999unknown",
            "name": "[Unknown Market]",
            "displayName": "Unknown",
            "handicap": 0,
        },
    ],
    "outcomes": [
        {"outcomeId": "o1", "marketId": "693394361", "name": "Arsenal FC"},
        {"outcomeId": "o2", "marketId": "693394361", "name": "Draw"},
        {"outcomeId": "o3", "marketId": "693394361", "name": "Atletico Madrid"},
        {"outcomeId": "o4", "marketId": "6933943610", "name": "Arsenal FC or Draw"},
        {
            "outcomeId": "o5",
            "marketId": "6933943610",
            "name": "Draw or Atletico Madrid",
        },
        {
            "outcomeId": "o6",
            "marketId": "6933943610",
            "name": "Arsenal FC or Atletico Madrid",
        },
        {"outcomeId": "o7", "marketId": "69339436btts", "name": "Yes"},
        {"outcomeId": "o8", "marketId": "69339436btts", "name": "No"},
        {"outcomeId": "o9", "marketId": "6933943618total=2.5~", "name": "Over"},
        {"outcomeId": "o10", "marketId": "6933943618total=2.5~", "name": "Under"},
        {"outcomeId": "o11", "marketId": "6933943618total=3.5~", "name": "Over"},
        {"outcomeId": "o12", "marketId": "6933943618total=3.5~", "name": "Under"},
        {"outcomeId": "o99", "marketId": "999unknown", "name": "Opt A"},
    ],
    "prices": [
        {"outcomeId": "o1", "priceDecimal": 1.63},
        {"outcomeId": "o2", "priceDecimal": 4.0},
        {"outcomeId": "o3", "priceDecimal": 4.6},
        {"outcomeId": "o4", "priceDecimal": 1.2},
        {"outcomeId": "o5", "priceDecimal": 1.9},
        {"outcomeId": "o6", "priceDecimal": 1.25},
        {"outcomeId": "o7", "priceDecimal": 1.7},
        {"outcomeId": "o8", "priceDecimal": 2.1},
        {"outcomeId": "o9", "priceDecimal": 1.8},
        {"outcomeId": "o10", "priceDecimal": 2.0},
        {"outcomeId": "o11", "priceDecimal": 2.3},
        {"outcomeId": "o12", "priceDecimal": 1.6},
        {"outcomeId": "o99", "priceDecimal": 3.0},
    ],
}


def test_parse_betway_1x2():
    markets = parse_markets(
        BETWAY_MARKETS_RESPONSE, platform="betway"
    )
    m1x2 = next(m for m in markets if m.canonical_id == "1x2_ft")
    assert m1x2.name == "1X2 - Full Time"
    assert len(m1x2.outcomes) == 3
    assert m1x2.lines is None
    home = next(
        o for o in m1x2.outcomes if o.canonical_name == "home"
    )
    assert home.odds == 1.63


def test_parse_betway_double_chance():
    markets = parse_markets(
        BETWAY_MARKETS_RESPONSE, platform="betway"
    )
    dc = next(
        m for m in markets if m.canonical_id == "double_chance_ft"
    )
    assert len(dc.outcomes) == 3
    hd = next(
        o for o in dc.outcomes if o.canonical_name == "home_draw"
    )
    assert hd.odds == 1.2


def test_parse_betway_btts():
    markets = parse_markets(
        BETWAY_MARKETS_RESPONSE, platform="betway"
    )
    btts = next(
        m for m in markets if m.canonical_id == "btts_ft"
    )
    assert len(btts.outcomes) == 2
    yes = next(
        o for o in btts.outcomes if o.canonical_name == "yes"
    )
    assert yes.odds == 1.7


def test_parse_betway_over_under():
    markets = parse_markets(
        BETWAY_MARKETS_RESPONSE, platform="betway"
    )
    ou = next(
        m for m in markets if m.canonical_id == "over_under_ft"
    )
    assert ou.lines is not None
    assert 2.5 in ou.lines
    assert 3.5 in ou.lines
    over_25 = next(
        o for o in ou.lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds == 1.8


def test_parse_betway_skips_unknown():
    markets = parse_markets(
        BETWAY_MARKETS_RESPONSE, platform="betway"
    )
    assert len(markets) == 4


def test_team_scoped_betway_registry_substitutes_placeholders():
    from bookieskit.markets.parser import _TeamScopedBetwayRegistry
    from bookieskit.markets.registry import MarketRegistry
    from bookieskit.markets.types import MarketMapping, OutcomeMapping

    inner = MarketRegistry(load_builtins=False)
    inner.add(
        canonical_id="home_over_under_ft",
        name="Over/Under Home Team - Full Time",
        betway_id="[Home Team] Total Goals",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over", betpawa="", sportybet="",
                bet9ja="", betway="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under", betpawa="", sportybet="",
                bet9ja="", betway="Under",
            ),
        },
        parameterized=True,
    )

    scoped = _TeamScopedBetwayRegistry(
        inner, home_team="Aston Villa", away_team="Brighton",
    )

    # Substituted form resolves
    mapping = scoped.get_by_platform_id(
        "betway", "Aston Villa Total Goals"
    )
    assert mapping is not None
    assert mapping.canonical_id == "home_over_under_ft"

    # Direct (non-placeholder) lookup still works for non-team markets
    inner.add(
        canonical_id="1x2_ft",
        name="1X2", betway_id="[Win/Draw/Win]",
        outcomes={}, parameterized=False,
    )
    scoped = _TeamScopedBetwayRegistry(
        inner, home_team="Aston Villa", away_team="Brighton",
    )
    direct = scoped.get_by_platform_id("betway", "[Win/Draw/Win]")
    assert direct is not None
    assert direct.canonical_id == "1x2_ft"

    # Wrong team name returns None
    miss = scoped.get_by_platform_id("betway", "Nottingham Total Goals")
    assert miss is None

    # Non-betway platform is a no-op fallback
    assert scoped.get_by_platform_id("sportybet", "x") is None


def test_parse_betway_resolves_team_name_placeholder():
    from bookieskit.markets.parser import parse_markets
    from bookieskit.markets.registry import MarketRegistry
    from bookieskit.markets.types import MarketMapping, OutcomeMapping

    registry = MarketRegistry(load_builtins=False)
    registry.add(
        canonical_id="home_over_under_ft",
        name="Over/Under Home Team - Full Time",
        betway_id="[Home Team] Total Goals",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over", betpawa="", sportybet="",
                bet9ja="", betway="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under", betpawa="", sportybet="",
                bet9ja="", betway="Under",
            ),
        },
        parameterized=True,
    )

    response = {
        "sportEvent": {
            "homeTeam": "Aston Villa",
            "awayTeam": "Brighton",
        },
        "marketsInGroup": [
            {
                "marketId": "m1",
                "name": "Aston Villa Total Goals",
                "handicap": 0,
            },
            {
                "marketId": "m2",
                "name": "Aston Villa Total Goals",
                "handicap": 2.5,
            },
        ],
        "outcomes": [
            {"marketId": "m1", "outcomeId": "m2~over", "name": "Over"},
            {"marketId": "m1", "outcomeId": "m2~under", "name": "Under"},
        ],
        "prices": [
            {"outcomeId": "m2~over", "priceDecimal": 1.85},
            {"outcomeId": "m2~under", "priceDecimal": 1.95},
        ],
    }

    markets = parse_markets(response, platform="betway", registry=registry)
    assert len(markets) == 1
    m = markets[0]
    assert m.canonical_id == "home_over_under_ft"
    assert m.lines is not None
    assert 2.5 in m.lines
    odds_by_name = {o.canonical_name: o.odds for o in m.lines[2.5]}
    assert odds_by_name == {"over": 1.85, "under": 1.95}
