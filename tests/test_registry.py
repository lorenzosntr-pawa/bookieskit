
from bookieskit.markets.registry import MarketRegistry
from bookieskit.markets.types import OutcomeMapping


def test_registry_loads_builtins_by_default():
    registry = MarketRegistry()
    markets = registry.list_markets()
    assert len(markets) == 4


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
    assert len(registry.list_markets()) == 5
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
