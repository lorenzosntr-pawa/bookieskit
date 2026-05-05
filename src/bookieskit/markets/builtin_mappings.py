"""Built-in market mappings for the 4 main markets."""

from bookieskit.markets.types import MarketMapping, OutcomeMapping

BUILTIN_MAPPINGS: list[MarketMapping] = [
    MarketMapping(
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
            "draw": OutcomeMapping(
                canonical_name="draw",
                betpawa="X",
                sportybet="Draw",
                bet9ja="X",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
            ),
        },
        parameterized=False,
    ),
    MarketMapping(
        canonical_id="over_under_ft",
        name="Over/Under - Full Time",
        betpawa_id="5000",
        sportybet_id="18",
        bet9ja_key="S_OU",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="O",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="U",
            ),
        },
        parameterized=True,
    ),
    MarketMapping(
        canonical_id="btts_ft",
        name="Both Teams To Score - Full Time",
        betpawa_id="3795",
        sportybet_id="29",
        bet9ja_key="S_GGNG",
        outcomes={
            "yes": OutcomeMapping(
                canonical_name="yes",
                betpawa="Yes",
                sportybet="Yes",
                bet9ja="Y",
            ),
            "no": OutcomeMapping(
                canonical_name="no",
                betpawa="No",
                sportybet="No",
                bet9ja="N",
            ),
        },
        parameterized=False,
    ),
    MarketMapping(
        canonical_id="double_chance_ft",
        name="Double Chance - Full Time",
        betpawa_id="4693",
        sportybet_id="10",
        bet9ja_key="S_DC",
        outcomes={
            "home_draw": OutcomeMapping(
                canonical_name="home_draw",
                betpawa="1X",
                sportybet="Home or Draw",
                bet9ja="1X",
            ),
            "draw_away": OutcomeMapping(
                canonical_name="draw_away",
                betpawa="X2",
                sportybet="Draw or Away",
                bet9ja="X2",
            ),
            "home_away": OutcomeMapping(
                canonical_name="home_away",
                betpawa="12",
                sportybet="Home or Away",
                bet9ja="12",
            ),
        },
        parameterized=False,
    ),
]
