"""Built-in market mappings.

Soccer: 1X2, O/U, BTTS, DC, 1X2 1Up, 1X2 2Up, next-goal, home/away O/U,
2-way handicap, and corner 1X2 + corner O/U. Plus basketball and tennis
market groups.
"""

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
    # =================== Corner markets (football) =====================
    # 1X2 + Over/Under on full-time corner count. Market ids and outcome
    # labels were lifted from the real captured prematch.json fixtures,
    # never guessed. Outcome conventions mirror the soccer 1X2 / O/U
    # markets:
    #   - BetPawa: numeric "1"/"X"/"2" and "Over"/"Under"
    #   - SportyBet, MSport: word labels "Home"/"Draw"/"Away", "Over"/"Under"
    #   - Bet9ja: key suffixes "O"/"U" (O/U only)
    # Coverage notes (— in the coverage matrix means a dedicated in-region
    # live probe is still needed):
    #   - Betway, SportPesa, Betika fixtures contain NO corner data at all.
    #   - Bet9ja DOES expose corner markets: it has an unambiguous FT O/U
    #     corners key (S_OUCORNERS, mapped below) but NO unambiguous FT
    #     corner-1X2 key — the 1/X/2-shaped corner keys (S_TEAMCORNER,
    #     S_HALFCORNER, S_CORNERHTFT) can't be confidently disambiguated to
    #     "full-time most-corners 1X2" from the fixture alone, so 1X2 stays
    #     None pending a labelled live probe rather than guessing the id.
    MarketMapping(
        canonical_id="1x2_corners_ft",
        name="1X2 Corners - Full Time",
        betpawa_id="1096787",  # "Corner Count 1X2 - FT"
        sportybet_id="162",  # "Corners 1X2"
        bet9ja_key=None,  # corner data exists but no unambiguous FT 1X2 key
        betway_id=None,  # no corner data in captured fixture — needs probe
        msport_id="162",  # "Corner 1x2"
        sportpesa_id=None,  # no corner data in captured fixture — needs probe
        betika_id=None,  # no corner data in captured fixture — needs probe
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="",
                betway="",
                msport="Home",
                sportpesa="",
                betika="",
            ),
            "draw": OutcomeMapping(
                canonical_name="draw",
                betpawa="X",
                sportybet="Draw",
                bet9ja="",
                betway="",
                msport="Draw",
                sportpesa="",
                betika="",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="",
                betway="",
                msport="Away",
                sportpesa="",
                betika="",
            ),
        },
        parameterized=False,
    ),
    MarketMapping(
        canonical_id="over_under_corners_ft",
        name="Over/Under Corners - Full Time",
        betpawa_id="1096783",  # "Total Corners Over/Under - FT"
        sportybet_id="166",  # "Corners - Over/Under"
        bet9ja_key="S_OUCORNERS",  # "S_OUCORNERS@<line>_O/_U"
        betway_id=None,  # no corner data in captured fixture — needs probe
        msport_id="166",  # "Corners O/U"
        sportpesa_id=None,  # no corner data in captured fixture — needs probe
        betika_id=None,  # no corner data in captured fixture — needs probe
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="O",
                betway="",
                msport="Over",
                sportpesa="",
                betika="",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="U",
                betway="",
                msport="Under",
                sportpesa="",
                betika="",
            ),
        },
        parameterized=True,
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
        sportpesa_id="382",  # "2 Way - OT incl." (basketball)
        betika_id="219",
        sport="basketball",
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
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__POS_2__",
                msport="Away",
                sportpesa="2",
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
        sportpesa_id="52",  # collides with soccer O/U; disambiguated by sport field
        betika_id="225",
        sport="basketball",
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
    # Basketball handicap (2-way, home/away) uses signed lines: home
    # -5.5 means home gives 5.5 points. The bookmakers ship the
    # home-perspective signed line (e.g. -5.5); the parser stores the
    # home outcome at key=-5.5 and the away outcome at key=+5.5 per
    # the spec ("each side ships with its own signed line"). Callers
    # pair entries by abs(). The "2way_" prefix on the canonical_id
    # disambiguates from a hypothetical future 3way (European 1X2)
    # handicap variant; see 2way_handicap_ft for the soccer companion.
    MarketMapping(
        canonical_id="2way_handicap_basketball_ft",
        name="2-Way Handicap - Full Time (incl. OT)",
        betpawa_id="3777",
        sportybet_id="223",
        bet9ja_key="B_H",
        betway_id="Handicap (Incl. Overtime)",
        msport_id="223",
        sportpesa_id="51",  # "Handicap - OT incl." (basketball)
        betika_id=None,  # Betika does not currently expose basketball handicap
        sport="basketball",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
                betway="__HOME__",
                msport="Home",
                sportpesa="1",
                betika="",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__POS_2__",
                msport="Away",
                sportpesa="2",
                betika="",
            ),
        },
        parameterized=True,
    ),
    # =================== Tennis =========================================
    # Tennis market ids discovered by live probe against a real match
    # (Rinderknech vs Tirante, SR 71529092). Four canonical markets:
    # moneyline, total games, total sets, game handicap. Each carries
    # ``sport="tennis"`` so the registry's sport-aware index resolves
    # cross-sport id collisions correctly (e.g. SportPesa id "51" is
    # basketball Handicap AND tennis Game Handicap).
    #
    # Per-bookmaker conventions:
    #   - BetPawa: bespoke numeric ids; outcomes "1" / "2".
    #   - SportyBet/MSport/Betway/Betika: SR-standard codes 186 (ML),
    #     189 (Total Games), 314 (Total Sets), 187 (Game Handicap).
    #   - Bet9ja: T_-prefixed keys T_12, T_OUG, T_TS, T_GH.
    #   - SportPesa: 382 (ML), 226 (Total Games), 51 (Game Handicap).
    #     Total Sets is unavailable on the captured event — None mapping.
    #
    # MSport doesn't expose Total Sets directly on the captured event
    # (only set-related markets are 196 Exact Sets / 194 Any Set To Nil
    # — neither is a clean O/U). Marked None; document gap.
    # Betika doesn't offer Set or Game Handicap or Total Sets on the
    # captured event (sub_type_ids 187/188/314 returned nothing).
    MarketMapping(
        canonical_id="moneyline_tennis_match",
        name="Moneyline - Match",
        betpawa_id="2043818",
        sportybet_id="186",
        bet9ja_key="T_12",
        betway_id="[Match Winner]",
        msport_id="186",
        sportpesa_id="382",
        betika_id="186",
        sport="tennis",
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
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__POS_2__",
                msport="Away",
                sportpesa="2",
                betika="2",
            ),
        },
        parameterized=False,
    ),
    MarketMapping(
        canonical_id="over_under_games_tennis_match",
        name="Over/Under Total Games - Match",
        betpawa_id="4895",
        sportybet_id="189",
        bet9ja_key="T_OUG",
        betway_id="Total Games",
        msport_id="189",
        sportpesa_id="226",
        betika_id="189",
        sport="tennis",
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
        canonical_id="over_under_sets_tennis_match",
        name="Over/Under Total Sets - Match",
        betpawa_id="3597899",
        sportybet_id="314",
        bet9ja_key="T_TS",
        betway_id="Total Sets",
        msport_id=None,  # MSport doesn't expose a clean Total Sets O/U
        sportpesa_id=None,  # not available on the captured event
        betika_id=None,  # captured event didn't expose 314
        sport="tennis",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="O",
                betway="Over",
                msport="",
                sportpesa="",
                betika="",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="U",
                betway="Under",
                msport="",
                sportpesa="",
                betika="",
            ),
        },
        parameterized=True,
    ),
    # Tennis handicap uses signed lines on game count (e.g. home -3.5
    # games means home has to win by 4+ more games than away). Both
    # outcomes (home, away) live under one signed key just like the
    # basketball handicap convention.
    MarketMapping(
        canonical_id="handicap_games_tennis_match",
        name="Game Handicap - Match",
        betpawa_id="3532590",
        sportybet_id="187",
        bet9ja_key="T_GH",
        betway_id="Game Handicap",
        msport_id="187",
        sportpesa_id="51",
        betika_id="187",
        sport="tennis",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
                betway="__HOME__",
                msport="Home",
                sportpesa="1",
                # Betika display is "1 (-3.5)" / "1 (-4.5)" / etc.;
                # _resolve_outcome_betika matches on the first token.
                betika="1",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__POS_2__",
                msport="Away",
                sportpesa="2",
                betika="2",
            ),
        },
        parameterized=True,
    ),
    # =================== Soccer — Next Goal ============================
    # 1st Goal / Nth Goal: which team scores the next goal. Prematch
    # always carries goal-number 1 (line=1.0); during live play multiple
    # goal numbers can be exposed (line=2.0 after the first goal is
    # scored, etc.). The line value is the GOAL NUMBER, not a goal-count
    # threshold — distinct semantic from over_under_ft despite reusing
    # the parameterized lines dict.
    #
    # Per-bookmaker line-extraction shapes:
    #   - SportyBet/MSport: specifier="goalnr=N" — extended
    #     _extract_line_from_specifier recognises goalnr= alongside
    #     total= and hcp=.
    #   - BetPawa: formattedHandicap="N" — already read first by
    #     _parse_betpawa_parameterized.
    #   - Bet9ja: line in @-segment of the odds key (S_NG@N_outcome).
    #   - Betway: per-line entries with handicap=N.
    #   - SportPesa: specValue=N on the market entry.
    #   - Betika: special_bet_value="N" or extracted from display.
    #
    # IDs for bet9ja/betway/sportpesa/betika are locked-in via the
    # probe script run as Phase 0 of this implementation.
    MarketMapping(
        canonical_id="next_goal_ft",
        name="Next Goal - Full Time",
        betpawa_id="28000224",
        sportybet_id="8",
        bet9ja_key="S_1STGOAL",  # locked-in via probe (none-suffix "X")
        betway_id="1st Goal",    # locked-in via probe (literal market name)
        msport_id="8",          # tentative SR-code mirror; probe confirms
        sportpesa_id=None,       # NOT PROBED — Akamai cookie unavailable
        # locked-in via probe (sub_type_id; market labelled "1ST GOAL")
        betika_id="8",
        sport="soccer",
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
            # The none-outcome strings for bet9ja / sportpesa / betika
            # are tentative best-guesses (SR convention "X" / "None");
            # probe confirms or replaces.
            "none": OutcomeMapping(
                canonical_name="none",
                betpawa="None",
                sportybet="None",
                bet9ja="X",
                betway="__POS_2__",
                msport="None",
                sportpesa="X",
                betika="None",
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
        parameterized=True,
    ),
    # =================== Soccer — Home Team Over/Under =================
    # Per-team Over/Under: line = total goals scored by the home team
    # specifically (e.g. line=1.5 means home scores 2+). Every bookmaker
    # we support ships this as a distinct market id from the away
    # variant — so we model it as two separate canonicals
    # (home_over_under_ft + away_over_under_ft) rather than a single
    # canonical with team encoded in outcome names.
    #
    # Betway is the special case: its market name carries the literal
    # team name (e.g. "Aston Villa Total"). We register the canonical
    # with the [Home Team] placeholder; the _TeamScopedBetwayRegistry
    # wrapper substitutes the placeholder against sportEvent.homeTeam
    # at parse-time. (The "Goals" suffix in the spec was an early
    # assumption; the probe found Betway actually uses just "<Team> Total".)
    #
    # Bet9ja: SHARED KEY — S_HAOU is a combined Home+Away O/U single
    # market. The 4 outcomes per line distinguish team and side via
    # suffix: _OH=Over Home, _UH=Under Home, _OA=Over Away, _UA=Under
    # Away. _parse_bet9ja routes each (S_HAOU, outcome_suffix) tuple to
    # the right per-team canonical based on whose OutcomeMapping.bet9ja
    # claims the suffix. (Both home_over_under_ft and away_over_under_ft
    # register bet9ja_key="S_HAOU".)
    MarketMapping(
        canonical_id="home_over_under_ft",
        name="Over/Under Home Team - Full Time",
        betpawa_id="5006",
        sportybet_id="19",
        bet9ja_key="S_HAOU",  # shared with away_over_under_ft (see comment)
        betway_id="[Home Team] Total",         # placeholder substituted at parse-time
        msport_id="19",                        # locked-in via probe
        sportpesa_id=None,                     # NOT PROBED
        betika_id="19",                        # locked-in via probe
        sport="soccer",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="OH",
                betway="Over",
                msport="Over",
                sportpesa="OV",
                betika="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="UH",
                betway="Under",
                msport="Under",
                sportpesa="UN",
                betika="Under",
            ),
        },
        parameterized=True,
    ),
    # =================== Soccer — Away Team Over/Under =================
    # Mirror of home_over_under_ft for the away team. Same probe coverage
    # — Bet9ja shares the S_HAOU key (see comment on home_over_under_ft;
    # this canonical's OutcomeMapping.bet9ja claims the _OA / _UA
    # outcome suffixes), SportPesa NOT PROBED.
    MarketMapping(
        canonical_id="away_over_under_ft",
        name="Over/Under Away Team - Full Time",
        betpawa_id="5003",
        sportybet_id="20",
        bet9ja_key="S_HAOU",  # shared with home_over_under_ft (see comment)
        betway_id="[Away Team] Total",         # placeholder substituted at parse-time
        msport_id="20",                        # locked-in via probe
        sportpesa_id=None,                     # NOT PROBED
        betika_id="20",                        # locked-in via probe
        sport="soccer",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="OA",
                betway="Over",
                msport="Over",
                sportpesa="OV",
                betika="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="UA",
                betway="Under",
                msport="Under",
                sportpesa="UN",
                betika="Under",
            ),
        },
        parameterized=True,
    ),
    # =================== Soccer — 2-way Asian Handicap ==================
    # Asian Handicap (2-way, home/away). Signed line from home's
    # perspective — line=-1.5 means home gives 1.5 goals. Both outcomes
    # live under a single signed key (same convention as
    # 2way_handicap_basketball_ft and handicap_games_tennis_match).
    #
    # The "2way_" prefix distinguishes this from a hypothetical future
    # 3way_handicap_ft (the European 1X2 handicap with draw). BetPawa
    # ships both as separate markets (id=3774 vs id=4724); Bet9ja
    # similarly ships S_AH (Asian) vs S_1X2HND (European). The 3-way
    # variant is explicitly out of scope for this release.
    #
    # Quarter lines (0.25 / 0.75 steps) work natively — the lines dict
    # accepts any float key.
    #
    # Per-bookmaker coverage notes:
    #   - Betika does NOT expose 2-way Asian Handicap (only the 3-way
    #     HANDICAP (1X2) at sub_type_id=14); confirmed via Task 2 probe
    #     sweep of sub_type_ids 1-200. Stays None.
    #   - SportPesa: NOT PROBED — Akamai cookie unavailable at probe
    #     time; same precedent as the 0.14.0 soccer markets.
    #   - Betway ships the market with a HANDICAP=0 anchor row plus
    #     children carrying real signed handicap values; existing
    #     _build_betway_parameterized Case 1 (parent + per-line
    #     distribution) handles this correctly.
    MarketMapping(
        canonical_id="2way_handicap_ft",
        name="2-Way Asian Handicap - Full Time",
        betpawa_id="3774",
        sportybet_id="16",        # probe-confirmed (SR-code mirror)
        bet9ja_key="S_AH",
        betway_id="[Handicap] [2-Way]",  # probe-confirmed literal name
        msport_id="16",           # probe-confirmed (SR-code mirror)
        sportpesa_id=None,        # NOT PROBED — Akamai cookie unavailable
        betika_id=None,           # NOT EXPOSED — Betika only ships 3-way handicap
        sport="soccer",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
                betway="__HOME__",
                msport="Home",
                sportpesa="1",
                betika="",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__POS_2__",
                msport="Away",
                sportpesa="2",
                betika="",
            ),
        },
        parameterized=True,
    ),
]
