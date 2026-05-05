from bookieskit.markets.parser import parse_markets
from bookieskit.markets.registry import MarketRegistry


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
