"""Parser tests for Betika markets payload.

Betika's event-detail endpoint returns one market group per call by default
(typically 1X2). The captured fixture at
``tests/fixtures/event_info/betika/prematch.json`` therefore covers only
1X2 — other markets are tested with synthetic payloads modelled on the
documented response shape (see ``betika/RESOLVED.md``).
"""
import json
from pathlib import Path

from bookieskit.markets.parser import parse_markets

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "event_info" / "betika"


def _load(phase: str = "prematch") -> dict:
    return json.loads((FIXTURE_DIR / f"{phase}.json").read_text(encoding="utf-8"))


def _load_markets() -> dict:
    return json.loads(
        (FIXTURE_DIR / "markets.json").read_text(encoding="utf-8")
    )


def _wrap(market_groups: list[dict]) -> dict:
    """Build a Betika-shaped response containing the given market groups."""
    return {"data": [{"odds": market_groups}], "meta": {}}


# ---------- fixture-bound tests --------------------------------------------


def test_parse_betika_returns_list():
    result = parse_markets(_load(), platform="betika")
    assert isinstance(result, list)


def test_parse_betika_1x2_from_fixture():
    result = parse_markets(_load(), platform="betika")
    one_x_two = next(m for m in result if m.canonical_id == "1x2_ft")
    names = sorted(o.canonical_name for o in one_x_two.outcomes)
    assert names == ["away", "draw", "home"]
    for o in one_x_two.outcomes:
        assert isinstance(o.odds, float)
        assert o.odds > 1.0
        assert o.platform_name in ("1", "X", "2")


# ---- multi-market fixture (captured via Betika.get_event_markets) --------


def test_parse_betika_markets_fixture_yields_all_four_canonicals():
    """Real captured payload (Valencia vs Rayo Vallecano, all 4 universal
    sub_type_ids merged). Verifies the parser recognises every market
    against a real Betika response, not just synthetic shapes."""
    result = parse_markets(_load_markets(), platform="betika")
    canonical_ids = {m.canonical_id for m in result}
    assert canonical_ids == {
        "1x2_ft", "double_chance_ft", "over_under_ft", "btts_ft",
    }


def test_parse_betika_over_under_from_fixture_has_25_line():
    """OU line 2.5 is universally present on football OU payloads;
    pin it explicitly. The captured fixture's ``special_bet_value`` uses
    the ``"total=2.5"`` format rather than a bare ``"2.5"`` — the parser
    must recover the line from either format."""
    result = parse_markets(_load_markets(), platform="betika")
    ou = next(m for m in result if m.canonical_id == "over_under_ft")
    assert ou.outcomes == []
    assert ou.lines is not None
    assert 2.5 in ou.lines
    over_25 = next(
        o for o in ou.lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds > 1.0


def test_parse_betika_btts_from_fixture_case_insensitive():
    """The captured fixture has BTTS outcomes as uppercase ``"YES"`` /
    ``"NO"``. The parser must resolve these against the registry's
    case-mixed ``betika="Yes"`` / ``"No"`` keys."""
    result = parse_markets(_load_markets(), platform="betika")
    btts = next(m for m in result if m.canonical_id == "btts_ft")
    names = sorted(o.canonical_name for o in btts.outcomes)
    assert names == ["no", "yes"]


def test_parse_betika_double_chance_from_fixture_three_outcomes():
    """The captured fixture's DC selections come back as ``"1/X"``,
    ``"1/2"``, ``"X/2"`` — the registry maps these to canonical
    ``home_draw`` / ``home_away`` / ``draw_away``."""
    result = parse_markets(_load_markets(), platform="betika")
    dc = next(m for m in result if m.canonical_id == "double_chance_ft")
    names = sorted(o.canonical_name for o in dc.outcomes)
    assert names == ["draw_away", "home_away", "home_draw"]


def test_parse_betika_line_extracts_total_equals_format():
    """``special_bet_value`` was observed in captured payloads as
    ``"total=2.5"`` — not a bare numeric string. The line extractor
    must recover the number from either format."""
    from bookieskit.markets.parser import _parse_betika_line
    assert _parse_betika_line({"special_bet_value": "total=2.5"}) == 2.5
    assert _parse_betika_line({"special_bet_value": "2.5"}) == 2.5
    assert _parse_betika_line(
        {"special_bet_value": "", "display": "OVER 1.5"}
    ) == 1.5
    assert _parse_betika_line(
        {"special_bet_value": "garbage", "display": "no number here"}
    ) is None


# ---------- synthetic edge cases -------------------------------------------


def test_parse_betika_over_under_is_parameterized():
    payload = _wrap([
        {
            "sub_type_id": "18",
            "name": "Total",
            "odds": [
                {"display": "OVER 2.5", "odd_value": "1.85",
                 "special_bet_value": "2.5"},
                {"display": "UNDER 2.5", "odd_value": "1.95",
                 "special_bet_value": "2.5"},
                {"display": "OVER 1.5", "odd_value": "1.30",
                 "special_bet_value": "1.5"},
                {"display": "UNDER 1.5", "odd_value": "3.40",
                 "special_bet_value": "1.5"},
            ],
        }
    ])
    result = parse_markets(payload, platform="betika")
    ou = next(m for m in result if m.canonical_id == "over_under_ft")
    assert ou.outcomes == []
    assert ou.lines is not None
    assert 2.5 in ou.lines and 1.5 in ou.lines
    for line, outcomes in ou.lines.items():
        names = sorted(o.canonical_name for o in outcomes)
        assert names == ["over", "under"], f"line={line} outcomes={names}"


def test_parse_betika_over_under_line_from_display_fallback():
    # If `special_bet_value` is missing, the line must be recovered from
    # the display label (e.g. "OVER 2.5").
    payload = _wrap([
        {
            "sub_type_id": "18",
            "name": "Total",
            "odds": [
                {"display": "OVER 2.5", "odd_value": "1.85"},
                {"display": "UNDER 2.5", "odd_value": "1.95"},
            ],
        }
    ])
    result = parse_markets(payload, platform="betika")
    ou = next(m for m in result if m.canonical_id == "over_under_ft")
    assert 2.5 in ou.lines


def test_parse_betika_btts_is_case_insensitive():
    payload = _wrap([
        {
            "sub_type_id": "29",
            "name": "GG/NG",
            "odds": [
                {"display": "YES", "odd_value": "1.60"},
                {"display": "no", "odd_value": "2.20"},
            ],
        }
    ])
    result = parse_markets(payload, platform="betika")
    btts = next(m for m in result if m.canonical_id == "btts_ft")
    names = sorted(o.canonical_name for o in btts.outcomes)
    assert names == ["no", "yes"]


def test_parse_betika_double_chance_three_outcomes():
    payload = _wrap([
        {
            "sub_type_id": "10",
            "name": "Double Chance",
            "odds": [
                {"display": "1/X", "odd_value": "1.10"},
                {"display": "X/2", "odd_value": "3.50"},
                {"display": "1/2", "odd_value": "1.20"},
            ],
        }
    ])
    result = parse_markets(payload, platform="betika")
    dc = next(m for m in result if m.canonical_id == "double_chance_ft")
    names = sorted(o.canonical_name for o in dc.outcomes)
    assert names == ["draw_away", "home_away", "home_draw"]


def test_parse_betika_empty_payload_returns_empty():
    assert parse_markets({}, platform="betika") == []
    assert parse_markets({"data": []}, platform="betika") == []
    assert parse_markets(_wrap([]), platform="betika") == []


def test_parse_betika_non_dict_payload_returns_empty():
    # The matcher passes raw event lists in some flows — make sure a
    # bare list doesn't crash.
    assert parse_markets([{"foo": "bar"}], platform="betika") == []


def test_parse_betika_unknown_market_id_skipped():
    payload = _wrap([
        {
            "sub_type_id": "99999",  # not in the registry
            "name": "Exotic",
            "odds": [{"display": "A", "odd_value": "2.0"}],
        }
    ])
    assert parse_markets(payload, platform="betika") == []


def test_parse_betika_malformed_odd_value_skipped():
    payload = _wrap([
        {
            "sub_type_id": "1",
            "name": "1X2",
            "odds": [
                {"display": "1", "odd_value": "not-a-number"},
                {"display": "X", "odd_value": "3.40"},
                {"display": "2", "odd_value": "4.20"},
            ],
        }
    ])
    result = parse_markets(payload, platform="betika")
    one_x_two = next(m for m in result if m.canonical_id == "1x2_ft")
    names = sorted(o.canonical_name for o in one_x_two.outcomes)
    assert names == ["away", "draw"]


def test_parse_betika_unknown_outcome_skipped():
    payload = _wrap([
        {
            "sub_type_id": "1",
            "name": "1X2",
            "odds": [
                {"display": "1", "odd_value": "2.0"},
                {"display": "WeirdNewOutcome", "odd_value": "3.0"},
                {"display": "2", "odd_value": "4.0"},
            ],
        }
    ])
    result = parse_markets(payload, platform="betika")
    one_x_two = next(m for m in result if m.canonical_id == "1x2_ft")
    names = sorted(o.canonical_name for o in one_x_two.outcomes)
    assert names == ["away", "home"]


def test_parse_betika_probability_mode_passes_through():
    # Betika selections carry no probability fields — both stay None
    # regardless of mode.
    payload = _wrap([
        {
            "sub_type_id": "1",
            "name": "1X2",
            "odds": [
                {"display": "1", "odd_value": "2.0"},
                {"display": "X", "odd_value": "3.0"},
                {"display": "2", "odd_value": "4.0"},
            ],
        }
    ])
    for mode in ("off", "true", "with_void"):
        result = parse_markets(payload, platform="betika", probability=mode)
        one_x_two = next(m for m in result if m.canonical_id == "1x2_ft")
        for o in one_x_two.outcomes:
            assert o.true_probability is None
            assert o.void_probability is None


def test_parse_betika_next_goal_ft_from_probe_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betika/next_goal_and_team_ou.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="betika")
    ng = next(
        (m for m in markets if m.canonical_id == "next_goal_ft"),
        None,
    )
    assert ng is not None, "Betika next_goal_ft (sub_type_id=8) not found in fixture"
    if ng.lines is not None:
        assert any(
            {"home", "away"}.issubset({o.canonical_name for o in outs})
            for outs in ng.lines.values()
        ), f"no line had both home and away: {ng.lines}"
    else:
        names = {o.canonical_name for o in ng.outcomes}
        assert {"home", "away"}.issubset(names), f"missing home/away: {names}"
