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


def test_extract_from_msport():
    response = {
        "bizCode": 10000,
        "data": {"eventId": "sr:match:61301231", "markets": []},
    }
    sr_id = extract_sportradar_id(response, platform="msport")
    assert sr_id == "61301231"


def test_extract_from_msport_no_prefix():
    response = {
        "bizCode": 10000,
        "data": {"eventId": "61301231", "markets": []},
    }
    sr_id = extract_sportradar_id(response, platform="msport")
    assert sr_id == "61301231"


def test_extract_from_msport_no_event_id():
    response = {"bizCode": 10000, "data": {"markets": []}}
    sr_id = extract_sportradar_id(response, platform="msport")
    assert sr_id is None


def test_extract_from_msport_no_data():
    sr_id = extract_sportradar_id({"bizCode": 10000}, platform="msport")
    assert sr_id is None


def test_extract_sportradar_id_sportpesa_missing_returns_none():
    # SportPesa returns a list of length 1 from /api/upcoming/games. Missing
    # or empty inputs in either list-shape or dict-wrapped shape resolve to None.
    from bookieskit.matching.extractor import extract_sportradar_id
    assert extract_sportradar_id({}, platform="sportpesa") is None
    assert extract_sportradar_id([], platform="sportpesa") is None
    assert extract_sportradar_id([{}], platform="sportpesa") is None
    # betradarId == 0 is the documented "not supplied" sentinel.
    assert extract_sportradar_id([{"betradarId": 0}], platform="sportpesa") is None


def test_extract_sportradar_id_sportpesa_from_list_shape():
    # Real response shape: list of length 1 with betradarId as an int.
    from bookieskit.matching.extractor import extract_sportradar_id
    response = [{"id": 8868005, "betradarId": 71348330}]
    assert extract_sportradar_id(response, platform="sportpesa") == "71348330"


def test_extract_sportradar_id_sportpesa_from_fixture():
    # Bind against the captured prematch fixture.
    import json
    from pathlib import Path

    from bookieskit.matching.extractor import extract_sportradar_id

    fixture = (
        Path(__file__).parent
        / "fixtures" / "event_info" / "sportpesa" / "prematch.json"
    )
    response = json.loads(fixture.read_text(encoding="utf-8"))
    sr = extract_sportradar_id(response, platform="sportpesa")
    assert sr is not None and sr.isdigit()


def test_extract_sportradar_id_betika_from_dict_shape():
    from bookieskit.matching.extractor import extract_sportradar_id
    response = {"data": [{"match_id": "10846988", "parent_match_id": "70784812"}]}
    assert extract_sportradar_id(response, platform="betika") == "70784812"


def test_extract_sportradar_id_betika_from_bare_list():
    from bookieskit.matching.extractor import extract_sportradar_id
    response = [{"match_id": "10846988", "parent_match_id": "70784812"}]
    assert extract_sportradar_id(response, platform="betika") == "70784812"


def test_extract_sportradar_id_betika_handles_int_parent_match_id():
    # Live responses return parent_match_id as int (not string).
    from bookieskit.matching.extractor import extract_sportradar_id
    response = [{"match_id": "4734371", "parent_match_id": 71463790}]
    assert extract_sportradar_id(response, platform="betika") == "71463790"


def test_extract_sportradar_id_betika_missing_returns_none():
    from bookieskit.matching.extractor import extract_sportradar_id
    assert extract_sportradar_id({}, platform="betika") is None
    assert extract_sportradar_id([], platform="betika") is None
    assert extract_sportradar_id([{}], platform="betika") is None
    assert extract_sportradar_id({"data": []}, platform="betika") is None
    assert extract_sportradar_id(
        [{"parent_match_id": 0}], platform="betika"
    ) is None
    assert extract_sportradar_id(
        [{"parent_match_id": "0"}], platform="betika"
    ) is None


def test_extract_sportradar_id_betika_from_fixture():
    import json
    from pathlib import Path
    from bookieskit.matching.extractor import extract_sportradar_id

    fixture = (
        Path(__file__).parent
        / "fixtures" / "event_info" / "betika" / "prematch.json"
    )
    response = json.loads(fixture.read_text(encoding="utf-8"))
    sr = extract_sportradar_id(response, platform="betika")
    assert sr is not None
    assert sr.isdigit()
