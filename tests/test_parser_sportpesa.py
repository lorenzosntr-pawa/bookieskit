"""Parser tests for SportPesa markets payload.

Most cases exercise the parser against the captured `markets.json` fixture
under `tests/fixtures/event_info/sportpesa/`. A few synthetic cases cover
edge shapes (empty payload, unknown markets, malformed odds) so we don't
need to keep regenerating the fixture for those.
"""
import json
from pathlib import Path

from bookieskit.markets.parser import parse_markets

FIXTURE = (
    Path(__file__).parent
    / "fixtures" / "event_info" / "sportpesa" / "markets.json"
)


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------- fixture-bound tests --------------------------------------------


def test_parse_sportpesa_returns_list():
    result = parse_markets(_load(), platform="sportpesa")
    assert isinstance(result, list)


def test_parse_sportpesa_recognizes_all_four_universal_markets():
    result = parse_markets(_load(), platform="sportpesa")
    canonical_ids = {m.canonical_id for m in result}
    # Every one of the four universal markets in the spec should be present.
    assert "1x2_ft" in canonical_ids
    assert "over_under_ft" in canonical_ids
    assert "btts_ft" in canonical_ids
    assert "double_chance_ft" in canonical_ids


def test_parse_sportpesa_1x2_has_three_outcomes():
    result = parse_markets(_load(), platform="sportpesa")
    one_x_two = next(m for m in result if m.canonical_id == "1x2_ft")
    names = sorted(o.canonical_name for o in one_x_two.outcomes)
    assert names == ["away", "draw", "home"]
    # All odds should be positive floats greater than 1.0
    for o in one_x_two.outcomes:
        assert isinstance(o.odds, float)
        assert o.odds > 1.0
        assert o.platform_name in ("1", "X", "2")


def test_parse_sportpesa_btts_has_yes_no():
    result = parse_markets(_load(), platform="sportpesa")
    btts = next(m for m in result if m.canonical_id == "btts_ft")
    names = sorted(o.canonical_name for o in btts.outcomes)
    assert names == ["no", "yes"]
    for o in btts.outcomes:
        assert o.odds > 1.0


def test_parse_sportpesa_double_chance_has_three_outcomes():
    result = parse_markets(_load(), platform="sportpesa")
    dc = next(m for m in result if m.canonical_id == "double_chance_ft")
    names = sorted(o.canonical_name for o in dc.outcomes)
    assert names == ["draw_away", "home_away", "home_draw"]


def test_parse_sportpesa_over_under_is_parameterized():
    result = parse_markets(_load(), platform="sportpesa")
    ou = next(m for m in result if m.canonical_id == "over_under_ft")
    # Parameterized markets have lines, not flat outcomes.
    assert ou.outcomes == []
    assert ou.lines is not None
    # The fixture's O/U entry spans many specValue lines (0.5, 1.5, 1.75,
    # 2, 2.25, 2.5, ..., 6.25 — 21 lines as captured). Assert we got at
    # least a handful of distinct lines.
    assert len(ou.lines) >= 3
    # All line keys should be floats.
    for line in ou.lines:
        assert isinstance(line, float)
    # Each line should have exactly two outcomes: over and under.
    for line, outcomes in ou.lines.items():
        names = sorted(o.canonical_name for o in outcomes)
        assert names == ["over", "under"], f"line={line} outcomes={names}"
        for o in outcomes:
            assert o.platform_name in ("OV", "UN")


def test_parse_sportpesa_over_under_includes_25_line():
    # The 2.5 line is almost always present in any captured soccer
    # O/U payload — sanity-check the most common one explicitly.
    result = parse_markets(_load(), platform="sportpesa")
    ou = next(m for m in result if m.canonical_id == "over_under_ft")
    assert 2.5 in ou.lines


# ---------- synthetic edge cases -------------------------------------------


def test_parse_sportpesa_empty_payload_returns_empty():
    assert parse_markets({}, platform="sportpesa") == []
    assert parse_markets({"8868005": []}, platform="sportpesa") == []


def test_parse_sportpesa_non_dict_payload_returns_empty():
    # The caller passing a list (which is the shape of /api/upcoming/games)
    # instead of the games/markets dict shape should not crash.
    assert parse_markets([{"foo": "bar"}], platform="sportpesa") == []


def test_parse_sportpesa_unknown_market_id_skipped():
    payload = {
        "8868005": [
            {
                "id": 99999,  # unknown to the registry
                "name": "Some Exotic Market",
                "specValue": 0,
                "selections": [
                    {"shortName": "A", "odds": "2.0"},
                    {"shortName": "B", "odds": "1.5"},
                ],
            }
        ]
    }
    assert parse_markets(payload, platform="sportpesa") == []


def test_parse_sportpesa_malformed_odds_skipped():
    payload = {
        "8868005": [
            {
                "id": 10,
                "name": "3 Way",
                "specValue": 0,
                "selections": [
                    {"shortName": "1", "odds": "not-a-number"},
                    {"shortName": "X", "odds": "3.40"},
                    {"shortName": "2", "odds": "4.20"},
                ],
            }
        ]
    }
    result = parse_markets(payload, platform="sportpesa")
    one_x_two = next(m for m in result if m.canonical_id == "1x2_ft")
    # The malformed "1" outcome is silently dropped; the others survive.
    names = sorted(o.canonical_name for o in one_x_two.outcomes)
    assert names == ["away", "draw"]


def test_parse_sportpesa_outcome_with_unknown_shortname_skipped():
    # If SportPesa adds a new outcome type (e.g. some weird "1.5" handicap
    # split), the resolver returns None and the outcome is silently dropped.
    payload = {
        "8868005": [
            {
                "id": 10,
                "name": "3 Way",
                "specValue": 0,
                "selections": [
                    {"shortName": "1", "odds": "2.0"},
                    {"shortName": "MaybeDraw", "odds": "3.0"},  # unknown
                    {"shortName": "2", "odds": "4.0"},
                ],
            }
        ]
    }
    result = parse_markets(payload, platform="sportpesa")
    one_x_two = next(m for m in result if m.canonical_id == "1x2_ft")
    names = sorted(o.canonical_name for o in one_x_two.outcomes)
    assert names == ["away", "home"]


def test_parse_sportpesa_probability_mode_passes_through():
    # SportPesa selections carry no `probability` / `void_probability`
    # fields — both Outcome fields should stay None regardless of mode.
    payload = {
        "8868005": [
            {
                "id": 10,
                "name": "3 Way",
                "specValue": 0,
                "selections": [
                    {"shortName": "1", "odds": "2.0"},
                    {"shortName": "X", "odds": "3.0"},
                    {"shortName": "2", "odds": "4.0"},
                ],
            }
        ]
    }
    for mode in ("off", "true", "with_void"):
        result = parse_markets(payload, platform="sportpesa", probability=mode)
        outcomes = result[0].outcomes
        for o in outcomes:
            assert o.true_probability is None
            assert o.void_probability is None
