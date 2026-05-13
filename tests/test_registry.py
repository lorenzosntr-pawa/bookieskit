
from bookieskit.markets.registry import MarketRegistry
from bookieskit.markets.types import OutcomeMapping


def test_registry_loads_builtins_by_default():
    registry = MarketRegistry()
    markets = registry.list_markets()
    # 1X2, O/U, BTTS, DC + 1X2 1Up, 1X2 2Up
    assert len(markets) == 6


def test_registry_no_builtins():
    registry = MarketRegistry(load_builtins=False)
    markets = registry.list_markets()
    assert len(markets) == 0


def test_registry_get_by_canonical():
    registry = MarketRegistry()
    mapping = registry.get_by_canonical("1x2_ft")
    assert mapping is not None
    assert mapping.name == "1X2 - Full Time"


def test_registry_get_by_canonical_not_found():
    registry = MarketRegistry()
    assert registry.get_by_canonical("nonexistent") is None


def test_registry_get_by_platform_id_betpawa():
    registry = MarketRegistry()
    mapping = registry.get_by_platform_id("betpawa", "3743")
    assert mapping is not None
    assert mapping.canonical_id == "1x2_ft"


def test_registry_get_by_platform_id_sportybet():
    registry = MarketRegistry()
    mapping = registry.get_by_platform_id("sportybet", "18")
    assert mapping is not None
    assert mapping.canonical_id == "over_under_ft"


def test_registry_get_by_platform_id_bet9ja():
    registry = MarketRegistry()
    mapping = registry.get_by_platform_id("bet9ja", "S_GGNG")
    assert mapping is not None
    assert mapping.canonical_id == "btts_ft"


def test_registry_get_by_platform_id_not_found():
    registry = MarketRegistry()
    assert registry.get_by_platform_id("betpawa", "99999") is None


def test_registry_add_custom_mapping():
    registry = MarketRegistry()
    registry.add(
        canonical_id="draw_no_bet_ft",
        name="Draw No Bet - Full Time",
        betpawa_id="4703",
        sportybet_id="11",
        bet9ja_key="S_DNB",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
            ),
        },
    )
    # 6 builtins + the new draw_no_bet custom mapping
    assert len(registry.list_markets()) == 7
    mapping = registry.get_by_canonical("draw_no_bet_ft")
    assert mapping is not None
    assert mapping.betpawa_id == "4703"


def test_registry_add_parameterized():
    registry = MarketRegistry(load_builtins=False)
    registry.add(
        canonical_id="asian_handicap_ft",
        name="Asian Handicap - Full Time",
        betpawa_id="3774",
        sportybet_id="16",
        bet9ja_key="S_AH",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
            ),
        },
        parameterized=True,
    )
    mapping = registry.get_by_canonical("asian_handicap_ft")
    assert mapping.parameterized is True


def test_registry_get_by_platform_id_msport():
    registry = MarketRegistry()
    mapping = registry.get_by_platform_id("msport", "1")
    assert mapping is not None
    assert mapping.canonical_id == "1x2_ft"


def test_registry_add_with_msport_id():
    registry = MarketRegistry(load_builtins=False)
    registry.add(
        canonical_id="custom",
        name="Custom",
        msport_id="42",
        outcomes={},
    )
    mapping = registry.get_by_platform_id("msport", "42")
    assert mapping is not None
    assert mapping.canonical_id == "custom"


def test_registry_resolves_by_sportpesa_id():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry(load_builtins=False)
    registry.add(
        canonical_id="test_market",
        name="Test",
        sportpesa_id="42",
    )
    m = registry.get_by_platform_id("sportpesa", "42")
    assert m is not None
    assert m.canonical_id == "test_market"


def test_registry_sportpesa_lookup_returns_none_for_unknown_id():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry(load_builtins=False)
    assert registry.get_by_platform_id("sportpesa", "999") is None


def test_builtin_1x2_ft_has_sportpesa_mapping():
    # SportPesa market id 10 = "3 Way" = canonical 1X2 (per RESOLVED.md).
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    m = registry.get_by_platform_id("sportpesa", "10")
    assert m is not None
    assert m.canonical_id == "1x2_ft"
    assert m.outcomes["home"].sportpesa  # any non-empty string


def test_builtin_over_under_ft_has_sportpesa_mapping():
    # SportPesa market id 52 = "Total Goals Over/Under - Full Time".
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    m = registry.get_by_platform_id("sportpesa", "52")
    assert m is not None
    assert m.canonical_id == "over_under_ft"
    assert m.parameterized is True


def test_builtin_btts_ft_has_sportpesa_mapping():
    # SportPesa market id 43 = "Both Teams To Score".
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    m = registry.get_by_platform_id("sportpesa", "43")
    assert m is not None
    assert m.canonical_id == "btts_ft"


def test_builtin_dc_ft_has_sportpesa_mapping():
    # SportPesa market id 46 = "Double Chance".
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    m = registry.get_by_platform_id("sportpesa", "46")
    assert m is not None
    assert m.canonical_id == "double_chance_ft"


def test_builtin_1up_2up_have_no_sportpesa_mapping():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    one_up = registry.get_by_canonical("1x2_1up_ft")
    two_up = registry.get_by_canonical("1x2_2up_ft")
    assert one_up.sportpesa_id is None
    assert two_up.sportpesa_id is None
    for om in one_up.outcomes.values():
        assert om.sportpesa == ""


def test_registry_resolves_by_betika_id():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry(load_builtins=False)
    registry.add(
        canonical_id="test_market", name="Test", betika_id="42",
    )
    m = registry.get_by_platform_id("betika", "42")
    assert m is not None
    assert m.canonical_id == "test_market"


def test_registry_betika_lookup_returns_none_for_unknown_id():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry(load_builtins=False)
    assert registry.get_by_platform_id("betika", "999") is None


def test_builtin_1x2_ft_has_betika_mapping():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    m = registry.get_by_platform_id("betika", "1")
    assert m is not None
    assert m.canonical_id == "1x2_ft"
    assert m.outcomes["home"].betika == "1"
    assert m.outcomes["draw"].betika == "X"
    assert m.outcomes["away"].betika == "2"


def test_builtin_over_under_ft_has_betika_mapping():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    m = registry.get_by_platform_id("betika", "18")
    assert m is not None
    assert m.canonical_id == "over_under_ft"
    assert m.parameterized is True
    assert m.outcomes["over"].betika == "Over"
    assert m.outcomes["under"].betika == "Under"


def test_builtin_btts_ft_has_betika_mapping():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    m = registry.get_by_platform_id("betika", "29")
    assert m is not None
    assert m.canonical_id == "btts_ft"
    assert m.outcomes["yes"].betika == "Yes"
    assert m.outcomes["no"].betika == "No"


def test_builtin_dc_ft_has_betika_mapping():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    m = registry.get_by_platform_id("betika", "10")
    assert m is not None
    assert m.canonical_id == "double_chance_ft"
    assert m.outcomes["home_draw"].betika == "1/X"
    assert m.outcomes["draw_away"].betika == "X/2"
    assert m.outcomes["home_away"].betika == "1/2"


def test_builtin_1up_2up_have_no_betika_mapping():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    one_up = registry.get_by_canonical("1x2_1up_ft")
    two_up = registry.get_by_canonical("1x2_2up_ft")
    assert one_up.betika_id is None
    assert two_up.betika_id is None
    for om in one_up.outcomes.values():
        assert om.betika == ""
    for om in two_up.outcomes.values():
        assert om.betika == ""
