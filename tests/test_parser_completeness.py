"""Completeness filter: suspended / missing prices drop the line or market.

Owner rule (option A): odds <= 1.0 or a missing price on ANY expected
outcome drops the whole line (parameterized) or the whole market
(simple); a parameterized market left with no lines is dropped.
"""

import json
from pathlib import Path

from bookieskit.markets.parser import _keep_complete, parse_markets
from bookieskit.markets.registry import MarketRegistry
from bookieskit.markets.types import NormalizedMarket, Outcome, OutcomeMapping

_FIXTURES = Path(__file__).parent / "fixtures" / "event_info"


def _load(book: str, name: str) -> dict:
    return json.loads((_FIXTURES / book / name).read_text(encoding="utf-8"))


def _o(name: str, odds: float) -> Outcome:
    return Outcome(canonical_name=name, odds=odds, platform_name=name)


def _1x2(home: float, draw: float, away: float) -> NormalizedMarket:
    return NormalizedMarket(
        canonical_id="1x2_ft",
        name="1X2",
        outcomes=[_o("home", home), _o("draw", draw), _o("away", away)],
    )


def test_simple_market_with_zero_odds_dropped():
    out = _keep_complete([_1x2(2.1, 0.0, 3.4)], MarketRegistry(), "betpawa")
    assert out == []


def test_simple_market_with_one_point_zero_dropped_one_point_zero_one_kept():
    reg = MarketRegistry()
    assert _keep_complete([_1x2(2.1, 1.0, 3.4)], reg, "bet9ja") == []
    kept = _keep_complete([_1x2(2.1, 1.01, 3.4)], reg, "bet9ja")
    assert kept == [_1x2(2.1, 1.01, 3.4)]


def test_simple_market_with_missing_outcome_dropped():
    m = NormalizedMarket(
        canonical_id="1x2_ft",
        name="1X2",
        outcomes=[_o("home", 2.1), _o("away", 3.4)],
    )
    assert _keep_complete([m], MarketRegistry(), "betway") == []


def test_line_with_missing_side_dropped_others_kept():
    m = NormalizedMarket(
        canonical_id="over_under_ft",
        name="Over/Under",
        lines={
            2.5: [_o("over", 1.9), _o("under", 1.9)],
            8.5: [_o("over", 15.0)],
        },
    )
    out = _keep_complete([m], MarketRegistry(), "bet9ja")
    assert len(out) == 1
    assert list(out[0].lines) == [2.5]
    assert out[0].lines[2.5] == m.lines[2.5]


def test_parameterized_market_with_no_lines_dropped():
    m = NormalizedMarket(
        canonical_id="over_under_ft",
        name="Over/Under",
        lines={
            0.5: [_o("over", 1.0), _o("under", 16.0)],
            8.5: [_o("over", 15.0)],
        },
    )
    assert _keep_complete([m], MarketRegistry(), "bet9ja") == []


def test_unmapped_market_passes_through():
    m = NormalizedMarket(
        canonical_id="not_registered", name="X", outcomes=[_o("a", 0.0)]
    )
    assert _keep_complete([m], MarketRegistry(), "betpawa") == [m]


def test_custom_mapping_counts_only_nonempty_labels():
    reg = MarketRegistry(load_builtins=False)
    reg.add(
        canonical_id="custom_3way",
        name="Custom",
        betpawa_id="900",
        bet9ja_key="S_CUSTOM",
        outcomes={
            "a": OutcomeMapping(canonical_name="a", betpawa="A", sportybet="A", bet9ja="A"),
            "b": OutcomeMapping(canonical_name="b", betpawa="B", sportybet="B", bet9ja="B"),
            "c": OutcomeMapping(canonical_name="c", betpawa="C", sportybet="C", bet9ja=""),
        },
    )
    m = NormalizedMarket(
        canonical_id="custom_3way",
        name="Custom",
        outcomes=[_o("a", 2.0), _o("b", 2.0)],
    )
    assert _keep_complete([m], reg, "bet9ja") == [m]
    # BetPawa does label "c", so the same market is incomplete there.
    assert _keep_complete([m], reg, "betpawa") == []


def _all_outcomes(markets: list[NormalizedMarket]) -> list[Outcome]:
    out: list[Outcome] = []
    for m in markets:
        if m.lines is None:
            out.extend(m.outcomes)
        else:
            for outcomes in m.lines.values():
                out.extend(outcomes)
    return out


def test_betpawa_live_fixture_has_no_suspended_prices():
    markets = parse_markets(_load("betpawa", "live.json"), "betpawa")
    assert markets
    assert [o for o in _all_outcomes(markets) if o.odds <= 1.0] == []


def test_bet9ja_wc_nf_over_under_drops_placeholder_and_one_sided_lines():
    markets = parse_markets(_load("bet9ja", "wc_nf.json"), "bet9ja")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    assert 0.5 not in ou.lines  # O = literal "1"
    assert 8.5 not in ou.lines  # over only
    assert ou.lines  # other lines survive
    for outcomes in ou.lines.values():
        assert sorted(o.canonical_name for o in outcomes) == ["over", "under"]
