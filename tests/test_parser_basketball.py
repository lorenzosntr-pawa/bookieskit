"""Cross-bookmaker basketball parser tests.

All 7 bookmakers ship working basketball coverage at v0.12.0:
BetPawa, SportyBet, MSport, Betway, Bet9ja, Betika (ML+O/U only),
and SportPesa (via the sport-aware registry lookup —
``parse_markets(..., sport="basketball")``).

Each fixture was captured live from a real basketball event in
2026-05. Betika does not currently expose handicap markets for
basketball, so it's only tested for ML + O/U.

SportPesa requires the ``sport="basketball"`` filter because its
market id ``52`` collides between football O/U and basketball O/U.
The other 6 bookmakers' ids are sport-disjoint so the bare lookup
works without sport disambiguation, but they're tested both ways
for completeness.
"""
import json
from pathlib import Path

import pytest

from bookieskit.markets.parser import parse_markets

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "event_info"

# Bookmakers with all three basketball markets working end-to-end via
# the bare ``parse_markets(response, platform=...)`` call (no sport
# filter required — their basketball market ids don't collide with
# soccer ids on the same platform).
WORKING_PLATFORMS = ("betpawa", "sportybet", "msport", "betway", "bet9ja")

# Betika offers ML + O/U but not handicap on basketball — handled
# in dedicated tests below.
ML_OU_PLATFORMS = WORKING_PLATFORMS + ("betika",)
HANDICAP_PLATFORMS = WORKING_PLATFORMS


def _load(platform: str, name: str = "basketball") -> dict:
    return json.loads(
        (FIXTURE_DIR / platform / f"{name}.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("platform", WORKING_PLATFORMS)
def test_basketball_parser_recognises_three_markets(platform):
    """Each of the bookmakers offering full basketball coverage exposes
    all three markets through the default registry."""
    result = parse_markets(_load(platform), platform=platform)
    canonical = {m.canonical_id for m in result}
    assert "moneyline_basketball_ft" in canonical, (
        f"{platform} missing moneyline_basketball_ft"
    )
    assert "over_under_basketball_ft" in canonical, (
        f"{platform} missing over_under_basketball_ft"
    )
    assert "2way_handicap_basketball_ft" in canonical, (
        f"{platform} missing 2way_handicap_basketball_ft"
    )


def test_betika_basketball_ml_and_ou_only_no_handicap():
    """Betika offers ML and O/U for basketball but not handicap
    (sub_type_id 223 returned nothing for the captured event)."""
    result = parse_markets(_load("betika"), platform="betika")
    canonical = {m.canonical_id for m in result}
    assert "moneyline_basketball_ft" in canonical
    assert "over_under_basketball_ft" in canonical
    assert "2way_handicap_basketball_ft" not in canonical


@pytest.mark.parametrize("platform", ML_OU_PLATFORMS)
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


@pytest.mark.parametrize("platform", ML_OU_PLATFORMS)
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


# ---- SportPesa basketball (requires sport-aware registry lookup) ---------


def test_sportpesa_basketball_requires_sport_filter():
    """SportPesa's market id ``52`` is used for both football O/U and
    basketball O/U; without the ``sport="basketball"`` filter the
    registry returns the soccer mapping (first-registered wins). Pin
    both behaviours so the sport-aware design contract is explicit."""
    raw = _load("sportpesa", "basketball_markets")

    # Without sport filter — id=52 resolves to the soccer O/U mapping.
    default = parse_markets(raw, platform="sportpesa")
    canonical_default = {m.canonical_id for m in default}
    assert "over_under_ft" in canonical_default
    assert "over_under_basketball_ft" not in canonical_default

    # With sport=basketball — id=52 resolves to the basketball O/U mapping.
    bb = parse_markets(raw, platform="sportpesa", sport="basketball")
    canonical_bb = {m.canonical_id for m in bb}
    assert "moneyline_basketball_ft" in canonical_bb
    assert "over_under_basketball_ft" in canonical_bb
    assert "2way_handicap_basketball_ft" in canonical_bb
    assert "over_under_ft" not in canonical_bb


def test_sportpesa_basketball_moneyline():
    raw = _load("sportpesa", "basketball_markets")
    result = parse_markets(raw, platform="sportpesa", sport="basketball")
    ml = next(m for m in result if m.canonical_id == "moneyline_basketball_ft")
    names = sorted(o.canonical_name for o in ml.outcomes)
    assert names == ["away", "home"]
    assert ml.lines is None


def test_sportpesa_basketball_handicap():
    raw = _load("sportpesa", "basketball_markets")
    result = parse_markets(raw, platform="sportpesa", sport="basketball")
    hcap = next(
        m for m in result if m.canonical_id == "2way_handicap_basketball_ft"
    )
    assert hcap.outcomes == []
    assert hcap.lines is not None
    assert len(hcap.lines) >= 1


@pytest.mark.parametrize("platform", HANDICAP_PLATFORMS)
def test_basketball_handicap_signed_lines(platform):
    """Handicap uses signed lines keyed by the home team's perspective.
    line=-5.5 means home favored by 5.5; both home and away outcomes
    live under that single key (the away team's effective +5.5 line
    is inferred by negating the key).
    """
    result = parse_markets(_load(platform), platform=platform)
    hcap = next(
        m for m in result if m.canonical_id == "2way_handicap_basketball_ft"
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
