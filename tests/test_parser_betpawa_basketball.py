"""Parser tests for BetPawa basketball markets (v0.11.0).

Three canonical markets are wired today: moneyline (4791), over/under
total points (5009), and handicap (3777). Each is fixture-bound to the
captured Baskets Bonn vs Wurzburg Baskets live event.
"""
import json
from pathlib import Path

from bookieskit.markets.parser import parse_markets

FIXTURE = (
    Path(__file__).parent
    / "fixtures" / "event_info" / "betpawa" / "basketball.json"
)


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_betpawa_basketball_recognises_three_markets():
    result = parse_markets(_load(), platform="betpawa")
    canonical_ids = {m.canonical_id for m in result}
    assert "moneyline_basketball_ft" in canonical_ids
    assert "over_under_basketball_ft" in canonical_ids
    assert "2way_handicap_basketball_ft" in canonical_ids


def test_parse_betpawa_basketball_moneyline():
    result = parse_markets(_load(), platform="betpawa")
    ml = next(m for m in result if m.canonical_id == "moneyline_basketball_ft")
    names = sorted(o.canonical_name for o in ml.outcomes)
    assert names == ["away", "home"]
    for o in ml.outcomes:
        assert isinstance(o.odds, float) and o.odds > 1.0
        assert o.platform_name in ("1", "2")
    # Basketball ML has NO draw outcome (unlike soccer's 1X2)
    assert ml.lines is None


def test_parse_betpawa_basketball_over_under():
    result = parse_markets(_load(), platform="betpawa")
    ou = next(m for m in result if m.canonical_id == "over_under_basketball_ft")
    # Parameterized — outcomes is empty, lines is populated
    assert ou.outcomes == []
    assert ou.lines is not None
    assert len(ou.lines) >= 1
    # Basketball totals are 150-200+ (not goals!)
    for line in ou.lines:
        assert isinstance(line, float)
        assert line > 100.0
    for line, outcomes in ou.lines.items():
        names = sorted(o.canonical_name for o in outcomes)
        assert names == ["over", "under"], f"line={line} outcomes={names}"


def test_parse_betpawa_basketball_handicap_uses_home_signed_line():
    """Handicap stores BOTH outcomes (home and away) under a single
    key — the home team's signed line. line=-5.5 means home is
    favored by 5.5 points; the away team's effective line is +5.5
    (inferred by negating the key).

    The 0.11.0 design discussion considered an alternative
    ``{-5.5: [home], +5.5: [away]}`` shape, but bookmakers natively
    ship both prices at one line value, so the wire-faithful shape
    is one key per row with both outcomes together.
    """
    result = parse_markets(_load(), platform="betpawa")
    hcap = next(
        m for m in result if m.canonical_id == "2way_handicap_basketball_ft"
    )
    assert hcap.outcomes == []
    assert hcap.lines is not None
    assert len(hcap.lines) >= 1
    # At least one negative line (home favored) on the captured event.
    assert any(line < 0 for line in hcap.lines)
    for line, outcomes in hcap.lines.items():
        names = sorted(o.canonical_name for o in outcomes)
        assert names == ["away", "home"], f"line={line} outcomes={names}"
        for o in outcomes:
            assert o.platform_name in ("1", "2")
            assert o.odds > 1.0
