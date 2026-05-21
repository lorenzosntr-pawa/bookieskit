from bookieskit.markets.parser import parse_markets

BET9JA_EVENT_RESPONSE = {
    "R": "D",
    "D": {
        "EXTID": "sr:match:61300947",
        "O": {
            "S_1X2_1": "1.95",
            "S_1X2_X": "3.50",
            "S_1X2_2": "2.10",
            "S_OU@2.5_O": "1.80",
            "S_OU@2.5_U": "2.00",
            "S_OU@3.5_O": "2.10",
            "S_OU@3.5_U": "1.70",
            "S_GGNG_Y": "1.75",
            "S_GGNG_N": "2.05",
            "S_DC_1X": "1.25",
            "S_DC_X2": "1.50",
            "S_DC_12": "1.10",
            "S_UNKNOWN_A": "2.00",
        },
    },
}


def test_parse_bet9ja_1x2():
    markets = parse_markets(BET9JA_EVENT_RESPONSE, platform="bet9ja")
    m1x2 = next(m for m in markets if m.canonical_id == "1x2_ft")
    assert m1x2.name == "1X2 - Full Time"
    assert len(m1x2.outcomes) == 3
    assert m1x2.lines is None
    home = next(o for o in m1x2.outcomes if o.canonical_name == "home")
    assert home.odds == 1.95
    assert home.platform_name == "1"


def test_parse_bet9ja_over_under():
    markets = parse_markets(BET9JA_EVENT_RESPONSE, platform="bet9ja")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    assert ou.lines is not None
    assert 2.5 in ou.lines
    assert 3.5 in ou.lines
    over_25 = next(
        o for o in ou.lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds == 1.80
    assert over_25.platform_name == "O"


def test_parse_bet9ja_btts():
    markets = parse_markets(BET9JA_EVENT_RESPONSE, platform="bet9ja")
    btts = next(m for m in markets if m.canonical_id == "btts_ft")
    assert len(btts.outcomes) == 2
    yes = next(o for o in btts.outcomes if o.canonical_name == "yes")
    assert yes.odds == 1.75
    assert yes.platform_name == "Y"


def test_parse_bet9ja_double_chance():
    markets = parse_markets(BET9JA_EVENT_RESPONSE, platform="bet9ja")
    dc = next(m for m in markets if m.canonical_id == "double_chance_ft")
    assert len(dc.outcomes) == 3
    hd = next(o for o in dc.outcomes if o.canonical_name == "home_draw")
    assert hd.odds == 1.25
    assert hd.platform_name == "1X"


def test_parse_bet9ja_skips_unknown():
    markets = parse_markets(BET9JA_EVENT_RESPONSE, platform="bet9ja")
    assert len(markets) == 4


def test_parse_bet9ja_empty_odds():
    response = {"R": "D", "D": {"O": {}}}
    markets = parse_markets(response, platform="bet9ja")
    assert len(markets) == 0


def test_parse_bet9ja_live_keys_with_lives_prefix():
    """Bet9ja live event detail uses LIVES_ prefix and {"v": float} odds."""
    response = {
        "R": "OK",
        "D": {
            "A": {"EXTID": "69339436"},
            "O": {
                "LIVES_1X2_1": {"v": 1.27},
                "LIVES_1X2_X": {"v": 4.9},
                "LIVES_1X2_2": {"v": 20.0},
                "LIVES_OU@2.5_O": {"v": 2.7},
                "LIVES_OU@2.5_U": {"v": 1.49},
                "LIVES_GGNG_Y": {"v": 2.38},
                "LIVES_GGNG_N": {"v": 1.61},
                "LIVES_DC_1X": {"v": 1.0},
                "LIVES_DC_X2": {"v": 3.95},
                "LIVES_DC_12": {"v": 1.19},
            },
        },
    }
    markets = parse_markets(response, platform="bet9ja")
    by_canon = {m.canonical_id: m for m in markets}
    assert "1x2_ft" in by_canon
    assert "over_under_ft" in by_canon
    assert "btts_ft" in by_canon
    assert "double_chance_ft" in by_canon
    home = next(o for o in by_canon["1x2_ft"].outcomes if o.canonical_name == "home")
    assert home.odds == 1.27
    over_25 = next(
        o for o in by_canon["over_under_ft"].lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds == 2.7


def test_parse_bet9ja_next_goal_ft_from_probe_fixture():
    import json
    from pathlib import Path

    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/bet9ja/next_goal_and_team_ou.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="bet9ja")
    ng = next(
        (m for m in markets if m.canonical_id == "next_goal_ft"),
        None,
    )
    assert ng is not None, "Bet9ja next_goal_ft (S_1STGOAL) not found in fixture"
    # Bet9ja S_1STGOAL has no @-line specifier — outcomes carry no goal-number
    # so the parser routes this market through the simple path (outcomes
    # populated, lines None) even though the canonical is parameterized=True.
    if ng.lines is not None:
        for line, outs in ng.lines.items():
            names = {o.canonical_name for o in outs}
            if {"home", "away"}.issubset(names):
                return
        raise AssertionError(f"no line had both home and away: {ng.lines}")
    else:
        names = {o.canonical_name for o in ng.outcomes}
        assert {"home", "away"}.issubset(names), (
            f"missing home/away in outcomes: {names}"
        )


def test_parse_bet9ja_s_haou_splits_into_home_and_away_canonicals():
    """Bet9ja ships per-team Over/Under under a single S_HAOU key with
    outcomes distinguished by suffix (_OH/_UH for home, _OA/_UA for
    away). The parser must route each outcome to the correct canonical
    based on which OutcomeMapping.bet9ja claims the suffix.
    """
    from bookieskit.markets.parser import parse_markets

    response = {
        "D": {
            "O": {
                "S_HAOU@0.5_OH": "1.12",
                "S_HAOU@0.5_UH": "5.40",
                "S_HAOU@0.5_OA": "1.42",
                "S_HAOU@0.5_UA": "2.66",
                "S_HAOU@1.5_OH": "1.70",
                "S_HAOU@1.5_UH": "2.03",
                "S_HAOU@1.5_OA": "3.15",
                "S_HAOU@1.5_UA": "1.31",
            }
        }
    }
    markets = parse_markets(response, platform="bet9ja")
    by_canon = {m.canonical_id: m for m in markets}

    assert "home_over_under_ft" in by_canon
    home = by_canon["home_over_under_ft"]
    assert home.lines is not None
    assert 0.5 in home.lines and 1.5 in home.lines
    home_05 = {o.canonical_name: o.odds for o in home.lines[0.5]}
    assert home_05 == {"over": 1.12, "under": 5.40}
    home_15 = {o.canonical_name: o.odds for o in home.lines[1.5]}
    assert home_15 == {"over": 1.70, "under": 2.03}

    assert "away_over_under_ft" in by_canon
    away = by_canon["away_over_under_ft"]
    assert away.lines is not None
    assert 0.5 in away.lines and 1.5 in away.lines
    away_05 = {o.canonical_name: o.odds for o in away.lines[0.5]}
    assert away_05 == {"over": 1.42, "under": 2.66}
    away_15 = {o.canonical_name: o.odds for o in away.lines[1.5]}
    assert away_15 == {"over": 3.15, "under": 1.31}


def test_parse_bet9ja_2way_handicap_ft_synthetic():
    """Bet9ja Asian Handicap (S_AH) — signed line in @-segment of the
    odds key, outcomes _1 (home) / _2 (away). Each (line, outcome)
    pair produces an Outcome under the line key.
    """
    from bookieskit.markets.parser import parse_markets

    response = {
        "D": {
            "O": {
                "S_AH@-1.5_1": "2.40",
                "S_AH@-1.5_2": "1.55",
                "S_AH@-0.5_1": "1.75",
                "S_AH@-0.5_2": "2.05",
                "S_AH@0_1": "1.55",
                "S_AH@0_2": "2.40",
                "S_AH@0.5_1": "1.35",
                "S_AH@0.5_2": "3.10",
            }
        }
    }
    markets = parse_markets(response, platform="bet9ja")
    ah = next(
        (m for m in markets if m.canonical_id == "2way_handicap_ft"),
        None,
    )
    assert ah is not None, "2way_handicap_ft not produced from S_AH"
    assert ah.lines is not None
    assert set(ah.lines.keys()) == {-1.5, -0.5, 0.0, 0.5}
    line_n15 = {o.canonical_name: o.odds for o in ah.lines[-1.5]}
    assert line_n15 == {"home": 2.40, "away": 1.55}
    line_p05 = {o.canonical_name: o.odds for o in ah.lines[0.5]}
    assert line_p05 == {"home": 1.35, "away": 3.10}


def test_parse_bet9ja_2way_handicap_ft_from_fixture():
    """Sanity-check against the captured Bet9ja fixture (carries S_AH
    keys from the 0.14.0 probe run against Qatar v Sudan).
    """
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path(
        "tests/fixtures/event_info/bet9ja/next_goal_and_team_ou.json"
    )
    response = json.loads(fixture.read_text(encoding="utf-8"))
    markets = parse_markets(response, platform="bet9ja")
    ah = next(
        (m for m in markets if m.canonical_id == "2way_handicap_ft"),
        None,
    )
    assert ah is not None, "Bet9ja 2way_handicap_ft (S_AH) not in fixture"
    assert ah.lines is not None
    assert len(ah.lines) >= 1
    assert any(
        {"home", "away"}.issubset({o.canonical_name for o in outs})
        for outs in ah.lines.values()
    )
