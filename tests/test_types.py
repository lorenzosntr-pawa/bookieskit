from bookieskit.markets.types import (
    MarketMapping,
    NormalizedMarket,
    Outcome,
    OutcomeMapping,
)


def test_outcome_is_frozen():
    o = Outcome(canonical_name="home", odds=1.95, platform_name="1")
    assert o.canonical_name == "home"
    assert o.odds == 1.95
    assert o.platform_name == "1"


def test_normalized_market_simple():
    market = NormalizedMarket(
        canonical_id="1x2_ft",
        name="1X2 - Full Time",
        outcomes=[
            Outcome(canonical_name="home", odds=1.95, platform_name="1"),
            Outcome(canonical_name="draw", odds=3.50, platform_name="X"),
            Outcome(canonical_name="away", odds=2.10, platform_name="2"),
        ],
    )
    assert market.canonical_id == "1x2_ft"
    assert len(market.outcomes) == 3
    assert market.lines is None


def test_normalized_market_parameterized():
    market = NormalizedMarket(
        canonical_id="over_under_ft",
        name="Over/Under - Full Time",
        outcomes=[],
        lines={
            2.5: [
                Outcome(
                    canonical_name="over", odds=1.80, platform_name="Over"
                ),
                Outcome(
                    canonical_name="under", odds=2.00, platform_name="Under"
                ),
            ],
        },
    )
    assert market.lines is not None
    assert 2.5 in market.lines
    assert len(market.lines[2.5]) == 2


def test_outcome_mapping():
    om = OutcomeMapping(
        canonical_name="home",
        betpawa="1",
        sportybet="Home",
        bet9ja="1",
    )
    assert om.canonical_name == "home"
    assert om.betpawa == "1"
    assert om.sportybet == "Home"
    assert om.bet9ja == "1"


def test_market_mapping():
    mm = MarketMapping(
        canonical_id="1x2_ft",
        name="1X2 - Full Time",
        betpawa_id="3743",
        sportybet_id="1",
        bet9ja_key="S_1X2",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
            ),
        },
        parameterized=False,
    )
    assert mm.canonical_id == "1x2_ft"
    assert mm.betpawa_id == "3743"
    assert mm.parameterized is False
    assert "home" in mm.outcomes


def test_market_mapping_with_none_platform():
    mm = MarketMapping(
        canonical_id="test_market",
        name="Test",
        betpawa_id="123",
        sportybet_id=None,
        bet9ja_key=None,
        outcomes={},
        parameterized=False,
    )
    assert mm.sportybet_id is None
    assert mm.bet9ja_key is None


def test_outcome_mapping_with_msport():
    om = OutcomeMapping(
        canonical_name="home",
        betpawa="1",
        sportybet="Home",
        bet9ja="1",
        betway="__HOME__",
        msport="Home",
    )
    assert om.msport == "Home"


def test_outcome_mapping_msport_defaults_empty():
    om = OutcomeMapping(
        canonical_name="home",
        betpawa="1",
        sportybet="Home",
        bet9ja="1",
    )
    assert om.msport == ""


def test_market_mapping_with_msport_id():
    mm = MarketMapping(
        canonical_id="1x2_ft",
        name="1X2 - Full Time",
        betpawa_id="3743",
        sportybet_id="1",
        bet9ja_key="S_1X2",
        betway_id="[Win/Draw/Win]",
        msport_id="1",
        outcomes={},
        parameterized=False,
    )
    assert mm.msport_id == "1"


def test_market_mapping_msport_id_defaults_none():
    mm = MarketMapping(
        canonical_id="x",
        name="X",
        betpawa_id=None,
        sportybet_id=None,
        bet9ja_key=None,
        outcomes={},
    )
    assert mm.msport_id is None


def test_outcome_mapping_sportpesa_field_defaults_to_empty():
    from bookieskit.markets.types import OutcomeMapping
    om = OutcomeMapping(
        canonical_name="home", betpawa="1", sportybet="Home", bet9ja="1"
    )
    assert om.sportpesa == ""


def test_outcome_mapping_sportpesa_field_round_trips():
    from bookieskit.markets.types import OutcomeMapping
    om = OutcomeMapping(
        canonical_name="home", betpawa="1", sportybet="Home", bet9ja="1",
        betway="__HOME__", msport="Home", sportpesa="1",
    )
    assert om.sportpesa == "1"


def test_market_mapping_sportpesa_id_defaults_to_none():
    from bookieskit.markets.types import MarketMapping
    mm = MarketMapping(
        canonical_id="1x2_ft", name="1X2 - Full Time",
        betpawa_id="3743", sportybet_id="1", bet9ja_key="S_1X2",
    )
    assert mm.sportpesa_id is None


def test_market_mapping_sportpesa_id_round_trips():
    from bookieskit.markets.types import MarketMapping
    mm = MarketMapping(
        canonical_id="1x2_ft", name="1X2 - Full Time",
        betpawa_id="3743", sportybet_id="1", bet9ja_key="S_1X2",
        betway_id="[Win/Draw/Win]", msport_id="1", sportpesa_id="1",
    )
    assert mm.sportpesa_id == "1"


def test_outcome_mapping_betika_field_defaults_to_empty():
    from bookieskit.markets.types import OutcomeMapping
    om = OutcomeMapping(
        canonical_name="home", betpawa="1", sportybet="Home", bet9ja="1"
    )
    assert om.betika == ""


def test_outcome_mapping_betika_field_round_trips():
    from bookieskit.markets.types import OutcomeMapping
    om = OutcomeMapping(
        canonical_name="home", betpawa="1", sportybet="Home", bet9ja="1",
        betway="__HOME__", msport="Home", sportpesa="1", betika="1",
    )
    assert om.betika == "1"
