from bookieskit.devtools.sports import SPORT_IDS, sport_id


def test_soccer_ids_for_every_platform():
    assert sport_id("betpawa", "soccer") == "2"
    assert sport_id("sportybet", "soccer") == "sr:sport:1"
    assert sport_id("msport", "soccer") == "sr:sport:1"
    assert sport_id("bet9ja", "soccer") == "1"
    assert sport_id("betway", "soccer") == "soccer"
    assert sport_id("betika", "soccer") == "14"
    assert sport_id("sportpesa", "soccer") == "1"


def test_basketball_ids():
    assert sport_id("betpawa", "basketball") == "3"
    assert sport_id("sportybet", "basketball") == "sr:sport:2"
    assert sport_id("bet9ja", "basketball") == "2"
    assert sport_id("betika", "basketball") == "30"
    assert sport_id("betway", "basketball") == "basketball"


def test_unknown_sport_or_platform_returns_none():
    assert sport_id("betpawa", "curling") is None
    assert sport_id("nonexistent", "soccer") is None


def test_table_covers_all_eight_platforms_for_soccer():
    assert set(SPORT_IDS["soccer"].keys()) == {
        "betpawa", "sportybet", "msport", "bet9ja",
        "betway", "betika", "sportpesa", "elephantbet",
    }


def test_elephantbet_covers_all_three_sports():
    # Verified live: soccer=1, basketball=2 ("Basquetebol"),
    # tennis=5 ("Tenis"), read from GET /rest/FEWFixture/Sports.
    assert sport_id("elephantbet", "soccer") == "1"
    assert sport_id("elephantbet", "basketball") == "2"
    assert sport_id("elephantbet", "tennis") == "5"
