"""Offline market-mapping coverage audit tests.

Three test groups:
1. Golden-snapshot regression — coverage_matrix() must equal the frozen dict.
2. render_markdown() — must include all platform names and a known row.
3. Fixture-driven resolution — verify() resolves the expected canonicals
   from real fixture files, proving parser and registry agree.
"""

import json
from pathlib import Path

import pytest

from bookieskit.devtools.coverage import PLATFORMS, coverage_matrix, render_markdown
from bookieskit.devtools.verify import verify

# ---------------------------------------------------------------------------
# 1.  Golden-snapshot regression
# ---------------------------------------------------------------------------

EXPECTED_MATRIX: dict[str, dict[str, bool]] = {
    "1x2_1up_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": False,
        "sportpesa": False,
        "betika": False,
    },
    "1x2_2up_ft": {
        "betpawa": False,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": False,
        "sportpesa": False,
        "betika": False,
    },
    "1x2_bookings_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": False,
        "betika": False,
    },
    "1x2_corners_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": False,
        "betika": False,
    },
    "1x2_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": True,
        "betika": True,
    },
    "2way_handicap_basketball_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": True,
        "betika": False,
    },
    "2way_handicap_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": False,
        "betika": False,
    },
    "away_over_under_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": False,
        "betika": True,
    },
    "btts_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": True,
        "betika": True,
    },
    "double_chance_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": True,
        "betika": True,
    },
    "handicap_games_tennis_match": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": True,
        "betika": True,
    },
    "home_over_under_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": False,
        "betika": True,
    },
    "moneyline_basketball_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": True,
        "betika": True,
    },
    "moneyline_tennis_match": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": True,
        "betika": True,
    },
    "next_goal_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": False,
        "betika": True,
    },
    "over_under_bookings_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": False,
        "betika": False,
    },
    "over_under_corners_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": False,
        "betika": False,
    },
    "over_under_basketball_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": True,
        "betika": True,
    },
    "over_under_ft": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": True,
        "betika": True,
    },
    "over_under_games_tennis_match": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": True,
        "sportpesa": True,
        "betika": True,
    },
    "over_under_sets_tennis_match": {
        "betpawa": True,
        "sportybet": True,
        "bet9ja": True,
        "betway": True,
        "msport": False,
        "sportpesa": False,
        "betika": False,
    },
}


def test_coverage_matrix_golden_snapshot():
    """coverage_matrix() must equal the frozen expected dict (all 21 markets)."""
    matrix = coverage_matrix()
    assert matrix == EXPECTED_MATRIX, (
        "Registry changed — update EXPECTED_MATRIX if intentional."
    )


def test_coverage_matrix_has_21_markets():
    matrix = coverage_matrix()
    assert len(matrix) == 21


def test_coverage_matrix_has_all_platforms():
    matrix = coverage_matrix()
    for row in matrix.values():
        assert set(row.keys()) == set(PLATFORMS)


# ---------------------------------------------------------------------------
# 2.  render_markdown()
# ---------------------------------------------------------------------------


def test_render_markdown_contains_all_platforms():
    md = render_markdown(coverage_matrix())
    for platform in PLATFORMS:
        assert platform in md, f"Platform {platform!r} missing from markdown"


def test_render_markdown_contains_known_row():
    md = render_markdown(coverage_matrix())
    # 1x2_ft is supported on all 7 platforms → every cell should be ✓
    assert "1x2_ft" in md
    # There should be 7 check marks in the 1x2_ft row
    for line in md.splitlines():
        if "1x2_ft" in line:
            assert line.count("✓") == 7, f"Unexpected row: {line!r}"
            break


def test_render_markdown_has_title():
    md = render_markdown(coverage_matrix())
    assert "# bookieskit" in md


def test_render_markdown_rows_sorted():
    md = render_markdown(coverage_matrix())
    rows = [
        ln.split("|")[1].strip()
        for ln in md.splitlines()
        if ln.startswith("| ") and "canonical" not in ln and "---" not in ln
    ]
    assert rows == sorted(rows)


# ---------------------------------------------------------------------------
# 3.  Fixture-driven resolution (representative sample)
# ---------------------------------------------------------------------------

_FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "event_info"


@pytest.mark.parametrize(
    "platform,sport,fixture_name,expected_subset",
    [
        (
            "betpawa",
            "soccer",
            "betpawa/prematch.json",
            {"1x2_ft", "over_under_ft", "btts_ft", "double_chance_ft"},
        ),
        (
            "betpawa",
            "basketball",
            "betpawa/basketball.json",
            {"moneyline_basketball_ft", "over_under_basketball_ft"},
        ),
        (
            "betpawa",
            "tennis",
            "betpawa/tennis.json",
            {"moneyline_tennis_match", "over_under_games_tennis_match"},
        ),
        (
            "sportybet",
            "soccer",
            "sportybet/prematch.json",
            {"1x2_ft", "over_under_ft", "btts_ft", "double_chance_ft"},
        ),
        (
            "betpawa",
            "soccer",
            "betpawa/prematch.json",
            {"1x2_corners_ft", "over_under_corners_ft"},
        ),
        (
            "msport",
            "soccer",
            "msport/prematch.json",
            {"1x2_corners_ft", "over_under_corners_ft"},
        ),
        (
            "bet9ja",
            "soccer",
            "bet9ja/prematch.json",
            {"over_under_corners_ft", "1x2_corners_ft"},
        ),
        (
            "betway",
            "soccer",
            "betway/2way_handicap_ft.json",
            {
                "1x2_corners_ft",
                "over_under_corners_ft",
                "1x2_bookings_ft",
                "over_under_bookings_ft",
            },
        ),
        (
            "betpawa",
            "soccer",
            "betpawa/wc_nf.json",
            {"1x2_bookings_ft", "over_under_bookings_ft"},
        ),
        (
            "sportybet",
            "soccer",
            "sportybet/wc_nf.json",
            {"1x2_bookings_ft", "over_under_bookings_ft"},
        ),
        (
            "msport",
            "soccer",
            "msport/wc_nf.json",
            {"1x2_bookings_ft", "over_under_bookings_ft"},
        ),
        (
            "bet9ja",
            "soccer",
            "bet9ja/wc_nf.json",
            {"1x2_bookings_ft", "over_under_bookings_ft"},
        ),
    ],
)
def test_fixture_resolution(
    platform: str,
    sport: str,
    fixture_name: str,
    expected_subset: set[str],
) -> None:
    """verify() resolves expected canonicals from real fixture files."""
    fixture_path = _FIXTURE_ROOT / Path(fixture_name)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    result = verify(payload, platform, sport)
    resolved = set(result.resolved.keys())
    missing = expected_subset - resolved
    assert not missing, (
        f"{platform}/{sport}: expected canonicals not resolved: {missing}"
    )
