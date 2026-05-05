from bookieskit.matching.extractor import extract_sportradar_id


def test_extract_from_betpawa():
    response = {
        "id": "32299257",
        "widgets": [
            {"type": "OTHER", "value": "something"},
            {"type": "SPORTRADAR", "value": "sr:match:61300947"},
        ],
    }
    sr_id = extract_sportradar_id(response, platform="betpawa")
    assert sr_id == "61300947"


def test_extract_from_betpawa_no_widget():
    response = {"id": "32299257", "widgets": []}
    sr_id = extract_sportradar_id(response, platform="betpawa")
    assert sr_id is None


def test_extract_from_betpawa_no_widgets_key():
    response = {"id": "32299257"}
    sr_id = extract_sportradar_id(response, platform="betpawa")
    assert sr_id is None


def test_extract_from_sportybet():
    response = {
        "bizCode": 10000,
        "data": {"eventId": "sr:match:61300947", "markets": []},
    }
    sr_id = extract_sportradar_id(response, platform="sportybet")
    assert sr_id == "61300947"


def test_extract_from_sportybet_no_prefix():
    response = {
        "bizCode": 10000,
        "data": {"eventId": "61300947", "markets": []},
    }
    sr_id = extract_sportradar_id(response, platform="sportybet")
    assert sr_id == "61300947"


def test_extract_from_sportybet_no_event_id():
    response = {"bizCode": 10000, "data": {"markets": []}}
    sr_id = extract_sportradar_id(response, platform="sportybet")
    assert sr_id is None


def test_extract_from_bet9ja():
    response = {
        "R": "D",
        "D": {"EXTID": "sr:match:61300947", "O": {}},
    }
    sr_id = extract_sportradar_id(response, platform="bet9ja")
    assert sr_id == "61300947"


def test_extract_from_bet9ja_numeric_extid():
    response = {"R": "D", "D": {"EXTID": "61300947", "O": {}}}
    sr_id = extract_sportradar_id(response, platform="bet9ja")
    assert sr_id == "61300947"


def test_extract_from_bet9ja_no_extid():
    response = {"R": "D", "D": {"O": {}}}
    sr_id = extract_sportradar_id(response, platform="bet9ja")
    assert sr_id is None


def test_extract_unknown_platform():
    sr_id = extract_sportradar_id({}, platform="unknown")
    assert sr_id is None


def test_extract_from_betway():
    response = {
        "sportEvent": {
            "eventId": 69339436,
            "name": "Arsenal FC vs. Atletico Madrid",
        }
    }
    sr_id = extract_sportradar_id(response, platform="betway")
    assert sr_id == "69339436"


def test_extract_from_betway_no_event():
    response = {"sportEvent": {}}
    sr_id = extract_sportradar_id(response, platform="betway")
    assert sr_id is None
