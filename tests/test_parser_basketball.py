"""Cross-bookmaker basketball parser tests.

Four bookmakers ship working basketball coverage at v0.11.0: BetPawa,
SportyBet, MSport, Betway. Each fixture was captured live from a real
basketball event (BetPawa: Baskets Bonn vs Wurzburg Baskets live;
SportyBet: an Argentina LNB game; MSport: a similar live event;
Betway: Baskets Bonn vs Wurzburg Baskets).

Bet9ja basketball uses a different market-key prefix (``B_*`` rather
than soccer's ``S_*``) which the current parser doesn't handle; left as
a follow-up. Betika ML + O/U work in principle (same SR-standard
sub_type_ids 219/225 the parser already accepts) but the captured
fixture is the default 1X2-only view rather than the multi-market
aggregator output, so it shows 0 basketball markets parsed. Capturing
a multi-market Betika fixture is a small follow-up.

SportPesa basketball is deferred: its market ids are sport-scoped
(id=52 maps to both football O/U and basketball O/U), so a sport-aware
registry lookup is needed before sportpesa basketball mappings can be
added to the default registry.
"""
import json
from pathlib import Path

import pytest

from bookieskit.markets.parser import parse_markets

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "event_info"

WORKING_PLATFORMS = ("betpawa", "sportybet", "msport", "betway")


def _load(platform: str) -> dict:
    return json.loads(
        (FIXTURE_DIR / platform / "basketball.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("platform", WORKING_PLATFORMS)
def test_basketball_parser_recognises_three_markets(platform):
    """Each of the four working bookmakers' fixtures must expose all
    three basketball markets through the default registry."""
    result = parse_markets(_load(platform), platform=platform)
    canonical = {m.canonical_id for m in result}
    assert "moneyline_basketball_ft" in canonical, (
        f"{platform} missing moneyline_basketball_ft"
    )
    assert "over_under_basketball_ft" in canonical, (
        f"{platform} missing over_under_basketball_ft"
    )
    assert "handicap_basketball_ft" in canonical, (
        f"{platform} missing handicap_basketball_ft"
    )


@pytest.mark.parametrize("platform", WORKING_PLATFORMS)
def test_basketball_moneyline_has_two_outcomes(platform):
    """Basketball ML is 2-way (home/away) — no draw, unlike soccer 1X2."""
    result = parse_markets(_load(platform), platform=platform)
    ml = next(m for m in result if m.canonical_id == "moneyline_basketball_ft")
    names = sorted(o.canonical_name for o in ml.outcomes)
    assert names == ["away", "home"], (
        f"{platform} ML outcomes: expected ['away', 'home'], got {names}"
    )
    for o in ml.outcomes:
        assert isinstance(o.odds, float)
        assert o.odds > 1.0
    assert ml.lines is None


@pytest.mark.parametrize("platform", WORKING_PLATFORMS)
def test_basketball_over_under_has_lines(platform):
    """O/U is parameterized — lines populated, outcomes empty."""
    result = parse_markets(_load(platform), platform=platform)
    ou = next(
        m for m in result if m.canonical_id == "over_under_basketball_ft"
    )
    assert ou.outcomes == []
    assert ou.lines is not None
    assert len(ou.lines) >= 1
    # Basketball totals are 150-200+ (not goals!)
    for line in ou.lines:
        assert isinstance(line, float)
        assert line > 100.0, (
            f"{platform} O/U line {line} is too low for basketball"
        )
    for line, outcomes in ou.lines.items():
        names = sorted(o.canonical_name for o in outcomes)
        assert names == ["over", "under"], (
            f"{platform} O/U line {line} outcomes: {names}"
        )


@pytest.mark.parametrize("platform", WORKING_PLATFORMS)
def test_basketball_handicap_signed_lines(platform):
    """Handicap uses signed lines keyed by the home team's perspective.
    line=-5.5 means home favored by 5.5; both home and away outcomes
    live under that single key (the away team's effective +5.5 line
    is inferred by negating the key).
    """
    result = parse_markets(_load(platform), platform=platform)
    hcap = next(
        m for m in result if m.canonical_id == "handicap_basketball_ft"
    )
    assert hcap.outcomes == []
    assert hcap.lines is not None
    assert len(hcap.lines) >= 1
    for line, outcomes in hcap.lines.items():
        assert isinstance(line, float)
        # Each line must have at least one outcome; both home and away
        # in the common case, but some bookmakers ship asymmetric data
        # (e.g. only one side priced for a particular line).
        assert len(outcomes) >= 1
        for o in outcomes:
            assert o.canonical_name in ("home", "away")
            assert isinstance(o.odds, float)
            assert o.odds > 1.0
