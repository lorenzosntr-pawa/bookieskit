"""Completeness filter: suspended / missing prices drop the line or market.

Owner rule (option A): odds <= 1.0 or a missing price on ANY expected
outcome drops the whole line (parameterized) or the whole market
(simple); a parameterized market left with no lines is dropped.
"""

import json
import logging
from pathlib import Path

import pytest

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


def _betpawa_suspended_rows(payload: dict) -> set[tuple[str, float | None, str]]:
    """(betpawa market id, line, price name) of every raw suspended price."""
    keys: set[tuple[str, float | None, str]] = set()
    for market in payload.get("markets", []):
        market_id = str(market.get("marketType", {}).get("id", market.get("id", "")))
        for row in market.get("row") or []:
            if row.get("formattedHandicap") is not None:
                line = float(row["formattedHandicap"])
            elif row.get("handicap") is not None:
                line = float(row["handicap"]) / 4
            else:
                line = None
            for price in row.get("prices", []):
                if price.get("suspended"):
                    keys.add((market_id, line, str(price.get("name"))))
    return keys


@pytest.mark.parametrize("fixture", ["live.json", "prematch.json", "wc_nf.json"])
def test_betpawa_no_outcome_survives_from_a_suspended_row(fixture):
    payload = _load("betpawa", fixture)
    suspended = _betpawa_suspended_rows(payload)
    assert suspended  # every fixture carries at least one suspended row
    reg = MarketRegistry()
    survivors: set[tuple[str, float | None, str]] = set()
    for m in parse_markets(payload, "betpawa"):
        market_id = reg.get_by_canonical(m.canonical_id).betpawa_id
        if m.lines is None:
            for o in m.outcomes:
                survivors.add((market_id, None, o.platform_name))
        else:
            for line, outcomes in m.lines.items():
                for o in outcomes:
                    survivors.add((market_id, line, o.platform_name))
        assert all(o.odds > 1.0 for o in _all_outcomes([m]))
    # Simple-market rows carry handicap 0 in the raw payload; compare both
    # the line-less and line-0 spellings.
    leaked = {k for k in survivors if k in suspended or (k[0], 0.0, k[2]) in suspended}
    assert leaked == set()


def test_betpawa_live_fixture_is_fully_suspended():
    # Every price in live.json is flagged suspended, so nothing survives.
    assert parse_markets(_load("betpawa", "live.json"), "betpawa") == []


def test_drop_is_logged_at_debug(caplog):
    caplog.set_level(logging.DEBUG, logger="bookieskit.markets.parser")
    ou = NormalizedMarket(
        canonical_id="over_under_ft",
        name="Over/Under",
        lines={
            2.5: [_o("over", 1.9), _o("under", 1.9)],
            8.5: [_o("over", 15.0)],
        },
    )
    _keep_complete([ou, _1x2(2.1, 1.0, 3.4)], MarketRegistry(), "bet9ja")
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
    assert any(
        "bet9ja" in m and "over_under_ft" in m and "8.5" in m and "missing" in m and "under" in m
        for m in messages
    )
    assert any(
        "bet9ja" in m and "1x2_ft" in m and "draw" in m and "1.0" in m
        for m in messages
    )
    assert not any("2.5" in m for m in messages)


def test_bet9ja_wc_nf_over_under_drops_placeholder_and_one_sided_lines():
    markets = parse_markets(_load("bet9ja", "wc_nf.json"), "bet9ja")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    assert 0.5 not in ou.lines  # O = literal "1"
    assert 8.5 not in ou.lines  # over only
    assert ou.lines  # other lines survive
    for outcomes in ou.lines.values():
        assert sorted(o.canonical_name for o in outcomes) == ["over", "under"]


# keep_incomplete=True: health checks need the markets the default drops.


def _bp_1x2(prices: list[tuple[str, float]]) -> dict:
    return {"markets": [{"marketType": {"id": "3743"}, "row": [{"prices": [
        {"name": n, "price": p} for n, p in prices]}]}]}


def test_keep_incomplete_keeps_zero_odds_betpawa_market():
    resp = _bp_1x2([("1", 2.9), ("X", 3.3), ("2", 0.0)])
    assert parse_markets(resp, "betpawa") == []
    kept = parse_markets(resp, "betpawa", keep_incomplete=True)
    assert [m.canonical_id for m in kept] == ["1x2_ft"]
    assert sorted(o.odds for o in kept[0].outcomes) == [0.0, 2.9, 3.3]


def test_keep_incomplete_returns_markets_of_fully_suspended_fixture():
    payload = _load("betpawa", "live.json")
    assert parse_markets(payload, "betpawa") == []
    assert parse_markets(payload, "betpawa", keep_incomplete=True) != []
