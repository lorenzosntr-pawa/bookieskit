"""Built-in market mappings for the 4 main markets."""

from bookieskit.markets.types import MarketMapping, OutcomeMapping

BUILTIN_MAPPINGS: list[MarketMapping] = [
    MarketMapping(
        canonical_id="1x2_ft",
        name="1X2 - Full Time",
        betpawa_id="3743",
        sportybet_id="1",
        bet9ja_key="S_1X2",
        betway_id="[Win/Draw/Win]",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
                betway="__HOME__",
            ),
            "draw": OutcomeMapping(
                canonical_name="draw",
                betpawa="X",
                sportybet="Draw",
                bet9ja="X",
                betway="Draw",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__AWAY__",
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
        betway_id="[Total Goals]",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="O",
                betway="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="U",
                betway="Under",
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
        betway_id="[Both Teams To Score]",
        outcomes={
            "yes": OutcomeMapping(
                canonical_name="yes",
                betpawa="Yes",
                sportybet="Yes",
                bet9ja="Y",
                betway="Yes",
            ),
            "no": OutcomeMapping(
                canonical_name="no",
                betpawa="No",
                sportybet="No",
                bet9ja="N",
                betway="No",
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
        betway_id="[Double Chance]",
        outcomes={
            "home_draw": OutcomeMapping(
                canonical_name="home_draw",
                betpawa="1X",
                sportybet="Home or Draw",
                bet9ja="1X",
                betway="__POS_1__",
            ),
            "draw_away": OutcomeMapping(
                canonical_name="draw_away",
                betpawa="X2",
                sportybet="Draw or Away",
                bet9ja="X2",
                betway="__POS_2__",
            ),
            "home_away": OutcomeMapping(
                canonical_name="home_away",
                betpawa="12",
                sportybet="Home or Away",
                bet9ja="12",
                betway="__POS_3__",
            ),
        },
        parameterized=False,
    ),
]
