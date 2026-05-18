"""Built-in market mappings (6 markets: 1X2, O/U, BTTS, DC, 1X2 1Up, 1X2 2Up)."""

from bookieskit.markets.types import MarketMapping, OutcomeMapping

BUILTIN_MAPPINGS: list[MarketMapping] = [
    MarketMapping(
        canonical_id="1x2_ft",
        name="1X2 - Full Time",
        betpawa_id="3743",
        sportybet_id="1",
        bet9ja_key="S_1X2",
        betway_id="[Win/Draw/Win]",
        msport_id="1",
        sportpesa_id="10",
        betika_id="1",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
                betway="__HOME__",
                msport="Home",
                sportpesa="1",
                betika="1",
            ),
            "draw": OutcomeMapping(
                canonical_name="draw",
                betpawa="X",
                sportybet="Draw",
                bet9ja="X",
                betway="Draw",
                msport="Draw",
                sportpesa="X",
                betika="X",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__AWAY__",
                msport="Away",
                sportpesa="2",
                betika="2",
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
        msport_id="18",
        sportpesa_id="52",
        betika_id="18",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="O",
                betway="Over",
                msport="Over",
                sportpesa="OV",
                betika="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="U",
                betway="Under",
                msport="Under",
                sportpesa="UN",
                betika="Under",
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
        msport_id="29",
        sportpesa_id="43",
        betika_id="29",
        outcomes={
            "yes": OutcomeMapping(
                canonical_name="yes",
                betpawa="Yes",
                sportybet="Yes",
                bet9ja="Y",
                betway="Yes",
                msport="Yes",
                sportpesa="Yes",
                betika="Yes",
            ),
            "no": OutcomeMapping(
                canonical_name="no",
                betpawa="No",
                sportybet="No",
                bet9ja="N",
                betway="No",
                msport="No",
                sportpesa="No",
                betika="No",
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
        msport_id="10",
        sportpesa_id="46",
        betika_id="10",
        outcomes={
            "home_draw": OutcomeMapping(
                canonical_name="home_draw",
                betpawa="1X",
                sportybet="Home or Draw",
                bet9ja="1X",
                betway="__POS_1__",
                msport="1 X",
                sportpesa="1X",
                betika="1/X",
            ),
            "draw_away": OutcomeMapping(
                canonical_name="draw_away",
                betpawa="X2",
                sportybet="Draw or Away",
                bet9ja="X2",
                betway="__POS_3__",
                msport="X 2",
                sportpesa="X2",
                betika="X/2",
            ),
            "home_away": OutcomeMapping(
                canonical_name="home_away",
                betpawa="12",
                sportybet="Home or Away",
                bet9ja="12",
                betway="__POS_2__",
                msport="1 2",
                sportpesa="12",
                betika="1/2",
            ),
        },
        parameterized=False,
    ),
    # 1X2 1Up — pays as 1X2 if your team gets to a 1-goal lead at any point.
    # Available on BetPawa / SportyBet / Bet9ja / Betway. MSport doesn't
    # expose this market.
    MarketMapping(
        canonical_id="1x2_1up_ft",
        name="1X2 1Up - Full Time",
        betpawa_id="28000810",
        sportybet_id="60200",
        bet9ja_key="S_1X21",
        betway_id="1X2 (1Up)",
        msport_id=None,
        sportpesa_id=None,
        betika_id=None,
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="11",
                betway="__HOME__",
                msport="",
                sportpesa="",
                betika="",
            ),
            "draw": OutcomeMapping(
                canonical_name="draw",
                betpawa="X",
                sportybet="Draw",
                bet9ja="X1",
                betway="Draw",
                msport="",
                sportpesa="",
                betika="",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="21",
                betway="__AWAY__",
                msport="",
                sportpesa="",
                betika="",
            ),
        },
        parameterized=False,
    ),
    # 1X2 2Up — pays as 1X2 if your team gets to a 2-goal lead at any point.
    # Same coverage as 1Up.
    MarketMapping(
        canonical_id="1x2_2up_ft",
        name="1X2 2Up - Full Time",
        betpawa_id=None,
        sportybet_id="60100",
        bet9ja_key="S_1X22",
        betway_id="1X2 (2Up)",
        msport_id=None,
        sportpesa_id=None,
        betika_id=None,
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="",
                sportybet="Home",
                bet9ja="12",
                betway="__HOME__",
                msport="",
                sportpesa="",
                betika="",
            ),
            "draw": OutcomeMapping(
                canonical_name="draw",
                betpawa="",
                sportybet="Draw",
                bet9ja="X2",
                betway="Draw",
                msport="",
                sportpesa="",
                betika="",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="",
                sportybet="Away",
                bet9ja="22",
                betway="__AWAY__",
                msport="",
                sportpesa="",
                betika="",
            ),
        },
        parameterized=False,
    ),
    # =================== Basketball =====================================
    # Basketball market ids for 6 of 7 bookmakers, discovered by probing
    # live basketball events in 2026-05. SportPesa is **deferred** here
    # because its market ids are sport-scoped: SportPesa's id=52 maps to
    # football O/U (already in this registry) AND basketball O/U,
    # creating a registry collision. Adding SportPesa basketball needs
    # sport-aware registry lookups; left as future work.
    #
    # Outcome conventions per platform:
    #   - BetPawa, Bet9ja, Betika: numeric "1"/"2" for ML and handicap
    #     (matches their soccer 1X2 convention minus the X)
    #   - SportyBet, MSport: word labels "Home"/"Away"
    #   - Betway: team-name outcomes; the parser maps these via the
    #     __HOME__/__AWAY__ position sentinels (same as soccer 1X2)
    #
    # Betika does NOT currently offer handicap markets for basketball
    # (probed; sub_type_id 223 returned nothing for in-play events),
    # so its handicap mapping is left empty.
    MarketMapping(
        canonical_id="moneyline_basketball_ft",
        name="Moneyline - Full Time (incl. OT)",
        betpawa_id="4791",
        sportybet_id="219",
        bet9ja_key="B_12",
        betway_id="Winner (Incl. Overtime)",
        msport_id="219",
        sportpesa_id=None,  # deferred — sport-scoped id collision
        betika_id="219",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
                betway="__HOME__",
                msport="Home",
                sportpesa="",
                betika="1",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__POS_2__",
                msport="Away",
                sportpesa="",
                betika="2",
            ),
        },
        parameterized=False,
    ),
    MarketMapping(
        canonical_id="over_under_basketball_ft",
        name="Over/Under Total Points - Full Time (incl. OT)",
        betpawa_id="5009",
        sportybet_id="225",
        bet9ja_key="B_OUN",
        betway_id="Total (Incl. Overtime)",
        msport_id="225",
        sportpesa_id=None,  # deferred — sport-scoped id collision (52)
        betika_id="225",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="O",
                betway="Over",
                msport="Over",
                sportpesa="",
                betika="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="U",
                betway="Under",
                msport="Under",
                sportpesa="",
                betika="Under",
            ),
        },
        parameterized=True,
    ),
    # Basketball handicap uses signed lines: home -5.5 means home gives
    # 5.5 points. The bookmakers ship the home-perspective signed line
    # (e.g. -5.5); the parser stores the home outcome at key=-5.5 and
    # the away outcome at key=+5.5 per the spec ("each side ships with
    # its own signed line"). Callers pair entries by abs().
    MarketMapping(
        canonical_id="handicap_basketball_ft",
        name="Handicap - Full Time (incl. OT)",
        betpawa_id="3777",
        sportybet_id="223",
        bet9ja_key="B_H",
        betway_id="Handicap (Incl. Overtime)",
        msport_id="223",
        sportpesa_id=None,  # deferred — sport-scoped id collision
        betika_id=None,  # Betika does not currently expose basketball handicap
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
                betway="__HOME__",
                msport="Home",
                sportpesa="",
                betika="",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__POS_2__",
                msport="Away",
                sportpesa="",
                betika="",
            ),
        },
        parameterized=True,
    ),
]
