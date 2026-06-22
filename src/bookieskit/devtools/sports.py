"""Canonical sport -> per-bookmaker sport id.

Values verified live and encoded in
``examples/compare_betpawa_competition_full.py`` SPORT_CONFIG and the
per-client ``get_*`` defaults. BetPawa uses numeric category ids
(soccer=2, basketball=3, tennis=452); SportyBet/MSport use SportRadar
ids (``sr:sport:N``); Bet9ja prematch uses single-digit sport ids;
Betika and SportPesa use their own numeric sport ids; Betway's API
``sportId`` is a lowercase slug.
"""

SPORT_IDS: dict[str, dict[str, str | None]] = {
    "soccer": {
        "betpawa": "2",
        "sportybet": "sr:sport:1",
        "msport": "sr:sport:1",
        "bet9ja": "1",
        "betway": "soccer",
        "betika": "14",
        "sportpesa": "1",
    },
    "basketball": {
        "betpawa": "3",
        "sportybet": "sr:sport:2",
        "msport": "sr:sport:2",
        "bet9ja": "2",
        "betway": "basketball",
        "betika": "30",
        "sportpesa": "2",
    },
    "tennis": {
        "betpawa": "452",
        "sportybet": "sr:sport:5",
        "msport": "sr:sport:5",
        "bet9ja": "5",
        "betway": "tennis",
        "betika": "28",
        "sportpesa": "5",
    },
}


def sport_id(platform: str, sport: str) -> str | None:
    """Return the per-bookmaker sport id for a canonical sport.

    Returns None when the sport or platform is unknown.
    """
    return SPORT_IDS.get(sport, {}).get(platform)
