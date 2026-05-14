from bookieskit.matching.extractor import EventIds, extract_sportradar_id

# ---- EventIds dataclass ---------------------------------------------------


def test_event_ids_defaults_both_none():
    e = EventIds()
    assert e.sportradar is None
    assert e.genius is None


def test_event_ids_is_frozen():
    import dataclasses

    import pytest
    e = EventIds(sportradar="70784812")
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.sportradar = "1"  # type: ignore[misc]


def test_event_ids_keys_empty_when_no_ids():
    assert EventIds().keys() == ()


def test_event_ids_keys_only_sportradar():
    assert EventIds(sportradar="70784812").keys() == ("sr:70784812",)


def test_event_ids_keys_only_genius():
    assert EventIds(genius="13599033").keys() == ("genius:13599033",)


def test_event_ids_keys_both_ordered():
    """sr key comes first when both are present so consumers can rely
    on a stable ordering for logging / dedup."""
    e = EventIds(sportradar="70784812", genius="13599033")
    assert e.keys() == ("sr:70784812", "genius:13599033")


# ---- extract_event_ids — BetPawa (both providers) -------------------------


def test_extract_event_ids_betpawa_both_widgets():
    """BetPawa carries SPORTRADAR and GENIUSSPORTS widgets in
    parallel — both should be extracted."""
    from bookieskit.matching.extractor import extract_event_ids
    response = {
        "widgets": [
            {"id": "70784812", "type": "SPORTRADAR", "retention": "PREMATCH"},
            {"id": "13599033", "type": "GENIUSSPORTS", "retention": None},
        ],
    }
    ids = extract_event_ids(response, platform="betpawa")
    assert ids.sportradar == "70784812"
    assert ids.genius == "13599033"


def test_extract_event_ids_betpawa_sr_only():
    from bookieskit.matching.extractor import extract_event_ids
    response = {"widgets": [{"id": "70784812", "type": "SPORTRADAR"}]}
    ids = extract_event_ids(response, platform="betpawa")
    assert ids.sportradar == "70784812"
    assert ids.genius is None


def test_extract_event_ids_betpawa_genius_only():
    from bookieskit.matching.extractor import extract_event_ids
    response = {"widgets": [{"id": "13599033", "type": "GENIUSSPORTS"}]}
    ids = extract_event_ids(response, platform="betpawa")
    assert ids.sportradar is None
    assert ids.genius == "13599033"


def test_extract_event_ids_betpawa_from_prematch_fixture():
    import json
    from pathlib import Path

    from bookieskit.matching.extractor import extract_event_ids
    fixture = (
        Path(__file__).parent / "fixtures" / "event_info"
        / "betpawa" / "prematch.json"
    )
    response = json.loads(fixture.read_text(encoding="utf-8"))
    ids = extract_event_ids(response, platform="betpawa")
    assert ids.sportradar == "68995116"
    assert ids.genius == "13599033"


def test_extract_event_ids_betpawa_from_live_fixture():
    import json
    from pathlib import Path

    from bookieskit.matching.extractor import extract_event_ids
    fixture = (
        Path(__file__).parent / "fixtures" / "event_info"
        / "betpawa" / "live.json"
    )
    response = json.loads(fixture.read_text(encoding="utf-8"))
    ids = extract_event_ids(response, platform="betpawa")
    assert ids.sportradar == "67645534"
    assert ids.genius == "13571147"


# ---- extract_event_ids — SportyBet (eventSource + 11111111 fallback) -----


def test_extract_event_ids_sportybet_event_source_radar():
    from bookieskit.matching.extractor import extract_event_ids
    response = {
        "data": {
            "eventId": "sr:match:70784812",
            "bgEvent": False,
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_RADAR", "sourceId": "70784812",
                },
                "liveSource": {
                    "sourceType": "BET_RADAR", "sourceId": "70784812",
                },
            },
        },
    }
    ids = extract_event_ids(response, platform="sportybet")
    assert ids.sportradar == "70784812"
    assert ids.genius is None


def test_extract_event_ids_sportybet_event_source_genius():
    """When sourceType=BET_GENIUS the sourceId is the Genius event id."""
    from bookieskit.matching.extractor import extract_event_ids
    response = {
        "data": {
            "eventId": "sr:match:1111111113599033",
            "bgEvent": True,
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_GENIUS", "sourceId": "13599033",
                },
                "liveSource": {
                    "sourceType": "BET_GENIUS", "sourceId": "13599033",
                },
            },
        },
    }
    ids = extract_event_ids(response, platform="sportybet")
    assert ids.genius == "13599033"
    # Plain SR id is NOT recovered (the eventId is a synthetic
    # Genius encoding, not a real SR id).
    assert ids.sportradar is None


def test_extract_event_ids_sportybet_event_id_genius_fallback():
    """No eventSource → recover Genius id from the
    sr:match:11111111<gid> synthetic encoding on data.eventId."""
    from bookieskit.matching.extractor import extract_event_ids
    response = {"data": {"eventId": "sr:match:1111111113599033"}}
    ids = extract_event_ids(response, platform="sportybet")
    assert ids.genius == "13599033"
    assert ids.sportradar is None


def test_extract_event_ids_sportybet_event_id_sr_fallback():
    """No eventSource, plain eventId → SR id only."""
    from bookieskit.matching.extractor import extract_event_ids
    response = {"data": {"eventId": "sr:match:70784812"}}
    ids = extract_event_ids(response, platform="sportybet")
    assert ids.sportradar == "70784812"
    assert ids.genius is None


def test_extract_event_ids_sportybet_cross_check_disagreement_warns(caplog):
    """When eventSource and the 11111111-decoded id disagree, log a
    warning and prefer eventSource."""
    import logging

    from bookieskit.matching.extractor import extract_event_ids
    response = {
        "data": {
            "eventId": "sr:match:1111111199999999",  # decodes to 99999999
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_GENIUS", "sourceId": "13599033",
                },
            },
        },
    }
    with caplog.at_level(logging.WARNING, logger="bookieskit.matching.extractor"):
        ids = extract_event_ids(response, platform="sportybet")
    assert ids.genius == "13599033"  # eventSource wins
    assert any("13599033" in r.getMessage() for r in caplog.records)


# ---- extract_event_ids — SR-only platforms ---------------------------------


def test_extract_event_ids_betway_sr_only():
    from bookieskit.matching.extractor import extract_event_ids
    response = {"sportEvent": {"eventId": 69339436}}
    ids = extract_event_ids(response, platform="betway")
    assert ids.sportradar == "69339436"
    assert ids.genius is None


def test_extract_event_ids_msport_sr_only():
    from bookieskit.matching.extractor import extract_event_ids
    response = {"data": {"eventId": "sr:match:61301231"}}
    ids = extract_event_ids(response, platform="msport")
    assert ids.sportradar == "61301231"
    assert ids.genius is None


def test_extract_event_ids_bet9ja_prematch_sr_only():
    """Bet9ja prematch is SR-only (Genius is only on live; deferred)."""
    from bookieskit.matching.extractor import extract_event_ids
    response = {"R": "D", "D": {"EXTID": "sr:match:61300947"}}
    ids = extract_event_ids(response, platform="bet9ja")
    assert ids.sportradar == "61300947"
    assert ids.genius is None


def test_extract_event_ids_sportpesa_sr_only():
    from bookieskit.matching.extractor import extract_event_ids
    response = [{"id": 8868005, "betradarId": 71348330}]
    ids = extract_event_ids(response, platform="sportpesa")
    assert ids.sportradar == "71348330"
    assert ids.genius is None


def test_extract_event_ids_betika_sr_only():
    from bookieskit.matching.extractor import extract_event_ids
    response = {"data": [{"parent_match_id": "70784812"}]}
    ids = extract_event_ids(response, platform="betika")
    assert ids.sportradar == "70784812"
    assert ids.genius is None


def test_extract_event_ids_unknown_platform_empty():
    from bookieskit.matching.extractor import extract_event_ids
    ids = extract_event_ids({}, platform="unknown")
    assert ids == EventIds()


# ---- extract_sportradar_id is unchanged (back-compat wrapper) -------------


def test_extract_sportradar_id_back_compat_for_genius_only_event():
    """An event with only a Genius id (no SR widget) should yield None
    from the back-compat function. Callers wanting the Genius id must
    migrate to extract_event_ids."""
    response = {"widgets": [{"id": "13599033", "type": "GENIUSSPORTS"}]}
    assert extract_sportradar_id(response, "betpawa") is None


# ---- existing SR-id-only extractor tests -----------------------------------


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
