"""Cross-bookmaker tennis parser tests.

Tennis canonical markets (4): moneyline, over_under_games, over_under_sets,
handicap_games. All carry ``sport="tennis"`` so the sport-aware registry
resolves cross-sport id collisions (notably SportPesa id ``51`` is
basketball handicap AND tennis Game Handicap).

Coverage by bookmaker, per the live probe in 2026-05:
  - BetPawa, SportyBet:     all 4
  - Bet9ja:                 all 4 (T_* prefix now supported)
  - MSport, SportPesa:      3 of 4 (no Total Sets on the captured event)
  - Betway:                 3 of 4 (the captured event lacks Total Sets)
  - Betika:                 2 of 4 (only ML + O/U Games; sets/handicap
                                    not offered for the captured event)
"""
import json
from pathlib import Path

import pytest

from bookieskit.markets.parser import parse_markets

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "event_info"

# All bookmakers with at least ML + O/U Games + Handicap Games.
HCAP_OU_PLATFORMS = (
    "betpawa", "sportybet", "msport", "betway", "bet9ja", "sportpesa",
)
# Plus betika which only has ML + O/U Games.
ML_OU_PLATFORMS = HCAP_OU_PLATFORMS + ("betika",)
# Total Sets is sparser — only confirmed on BetPawa, SportyBet, Bet9ja
# in the captured fixtures.
SETS_PLATFORMS = ("betpawa", "sportybet", "bet9ja")


def _load(platform: str) -> dict:
    return json.loads(
        (FIXTURE_DIR / platform / "tennis.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("platform", ML_OU_PLATFORMS)
def test_tennis_moneyline_two_outcomes(platform):
    """Tennis ML is 2-way (player1 / player2 — no draws)."""
    result = parse_markets(_load(platform), platform=platform, sport="tennis")
    ml = next(m for m in result if m.canonical_id == "moneyline_tennis_match")
    names = sorted(o.canonical_name for o in ml.outcomes)
    assert names == ["away", "home"], f"{platform} ML: {names}"
    for o in ml.outcomes:
        assert isinstance(o.odds, float) and o.odds > 1.0
    assert ml.lines is None


@pytest.mark.parametrize("platform", ML_OU_PLATFORMS)
def test_tennis_over_under_games(platform):
    """Total Games is parameterized — lines are total games values
    (typically 17.5–27.5 for a best-of-3 match)."""
    result = parse_markets(_load(platform), platform=platform, sport="tennis")
    ou = next(
        m for m in result if m.canonical_id == "over_under_games_tennis_match"
    )
    assert ou.outcomes == []
    assert ou.lines is not None
    assert len(ou.lines) >= 1
    for line, outcomes in ou.lines.items():
        assert isinstance(line, float)
        # Tennis O/U Games lines are usually in 15-40 range
        assert 10 <= line <= 50, f"{platform} unusual line: {line}"
        names = sorted(o.canonical_name for o in outcomes)
        assert names == ["over", "under"], f"{platform} line {line}: {names}"


@pytest.mark.parametrize("platform", SETS_PLATFORMS)
def test_tennis_over_under_sets(platform):
    """Total Sets is parameterized — lines are total sets (typically 2.5
    for best-of-3, 3.5 for best-of-5)."""
    result = parse_markets(_load(platform), platform=platform, sport="tennis")
    ou = next(
        m for m in result if m.canonical_id == "over_under_sets_tennis_match"
    )
    assert ou.outcomes == []
    assert ou.lines is not None
    for line, outcomes in ou.lines.items():
        # Sets lines are small
        assert 1.0 <= line <= 5.0, f"{platform} unusual sets line: {line}"
        names = sorted(o.canonical_name for o in outcomes)
        assert names == ["over", "under"]


@pytest.mark.parametrize("platform", HCAP_OU_PLATFORMS)
def test_tennis_game_handicap_signed_lines(platform):
    """Game Handicap uses signed lines keyed by the home player's
    perspective (line=-3.5 means home gives 3.5 games)."""
    result = parse_markets(_load(platform), platform=platform, sport="tennis")
    hcap = next(
        m for m in result if m.canonical_id == "handicap_games_tennis_match"
    )
    assert hcap.outcomes == []
    assert hcap.lines is not None
    assert len(hcap.lines) >= 1
    for line, outcomes in hcap.lines.items():
        assert isinstance(line, float)
        for o in outcomes:
            assert o.canonical_name in ("home", "away")
            assert isinstance(o.odds, float) and o.odds > 1.0


def test_tennis_betika_fixture_carries_ml_and_ou_games_only():
    """The captured Betika tennis fixture only includes sub_type_ids 186
    (WINNER) and 189 (TOTAL GAMES) because the capture script did not
    include 187 (GAME HANDICAP) or 188 (SET HANDICAP).

    Live, Betika DOES expose 187 for tennis; see
    ``test_tennis_betika_parses_game_handicap_when_present`` for the
    parser-side proof that sub_type_id=187 maps to
    ``handicap_games_tennis_match``.
    """
    result = parse_markets(_load("betika"), platform="betika", sport="tennis")
    tennis_canonicals = {
        m.canonical_id for m in result if "tennis" in m.canonical_id
    }
    assert tennis_canonicals == {
        "moneyline_tennis_match",
        "over_under_games_tennis_match",
    }


def test_tennis_betika_parses_game_handicap_when_present():
    """Synthetic Betika response carrying sub_type_id=187 (GAME HANDICAP).

    Confirms the parser maps it to ``handicap_games_tennis_match`` and
    groups the six selections under three signed lines.
    """
    raw = {
        "data": [{
            "match_id": "10945420",
            "parent_match_id": "71557920",
            "sport_id": "28",
            "odds": [{
                "sub_type_id": "187",
                "sub_type_name": "GAME HANDICAP",
                "odds": [
                    {"display": "1 (-3.5)", "odd_value": "1.62", "special_bet_value": "hcp=-3.5"},
                    {"display": "1 (-4.5)", "odd_value": "1.92", "special_bet_value": "hcp=-4.5"},
                    {"display": "1 (-5.5)", "odd_value": "2.42", "special_bet_value": "hcp=-5.5"},
                    {"display": "2 (+3.5)", "odd_value": "2.21", "special_bet_value": "hcp=-3.5"},
                    {"display": "2 (+4.5)", "odd_value": "1.82", "special_bet_value": "hcp=-4.5"},
                    {"display": "2 (+5.5)", "odd_value": "1.52", "special_bet_value": "hcp=-5.5"},
                ],
            }],
        }],
        "meta": {},
    }
    markets = parse_markets(raw, platform="betika", sport="tennis")
    hcap = next(
        m for m in markets if m.canonical_id == "handicap_games_tennis_match"
    )
    assert set(hcap.lines.keys()) == {-3.5, -4.5, -5.5}
    for line, outcomes in hcap.lines.items():
        names = {o.canonical_name for o in outcomes}
        assert names == {"home", "away"}
    home_at_neg45 = next(
        o for o in hcap.lines[-4.5] if o.canonical_name == "home"
    )
    away_at_neg45 = next(
        o for o in hcap.lines[-4.5] if o.canonical_name == "away"
    )
    assert home_at_neg45.odds == 1.92
    assert away_at_neg45.odds == 1.82


def test_tennis_sportpesa_requires_sport_filter():
    """SportPesa id ``51`` collides between basketball handicap and
    tennis Game Handicap. The sport-aware lookup is what picks the
    right canonical."""
    raw = _load("sportpesa")
    # With sport='tennis' the id=51 resolves to game handicap
    tennis = parse_markets(raw, platform="sportpesa", sport="tennis")
    canonical = {m.canonical_id for m in tennis}
    assert "handicap_games_tennis_match" in canonical
    assert "handicap_basketball_ft" not in canonical
