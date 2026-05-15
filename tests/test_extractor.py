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


# ---- extract_event_ids — SportyBet (eventSource + sourceId prefix) -------
#
# Real SportyBet payloads (observed via live probe, 2026-05) ship:
#   data.eventId   = "sr:match:<sr_id>"      (ALWAYS the SR id, regardless
#                                             of provider — including for
#                                             BetGenius events)
#   data.eventSource.{preMatchSource,liveSource}.sourceType = "BET_RADAR"
#                                                          or "BET_GENIUS"
#   data.eventSource.*.sourceId = "1111111<id>" (7-ones prefix) on some
#                                                rows, bare id on others
# The 7-ones prefix is a SportyBet namespacing marker; strip it before
# returning the provider id so SportyBet's Genius id matches BetPawa's
# GENIUSSPORTS widget id (which is the bare 8-digit form like "13599033").


def test_extract_event_ids_sportybet_event_source_radar():
    """Pure SportRadar event — sourceType=BET_RADAR on both phases.
    preMatchSource.sourceId carries the 7-ones prefix in this real-world
    capture; liveSource.sourceId is bare. The extractor strips when
    present and produces the same bare SR id regardless."""
    from bookieskit.matching.extractor import extract_event_ids
    response = {
        "data": {
            "eventId": "sr:match:71127902",
            "bgEvent": False,
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_RADAR", "sourceId": "111111171127902",
                },
                "liveSource": {
                    "sourceType": "BET_RADAR", "sourceId": "71127902",
                },
            },
        },
    }
    ids = extract_event_ids(response, platform="sportybet")
    assert ids.sportradar == "71127902"
    assert ids.genius is None


def test_extract_event_ids_sportybet_event_source_genius():
    """Real BetGenius event — sourceType=BET_GENIUS on both phases,
    sourceId carries the 7-ones prefix. The eventId is STILL the
    SportRadar id (SportyBet's eventId is always sr:match:<sr_id>
    regardless of provider — BetGenius events have BOTH a Genius id
    and an SR id for the same physical match)."""
    from bookieskit.matching.extractor import extract_event_ids
    response = {
        "data": {
            # SR id of the same match — SportyBet always carries this.
            "eventId": "sr:match:71453928",
            "bgEvent": False,  # observed: bgEvent is NOT reliably set
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_GENIUS",
                    "sourceId": "111111113899686",  # 7 ones + Genius id
                },
                "liveSource": {
                    "sourceType": "BET_GENIUS",
                    "sourceId": "111111113899686",
                },
            },
        },
    }
    ids = extract_event_ids(response, platform="sportybet")
    # BOTH provider ids are populated for a real Genius event.
    assert ids.sportradar == "71453928"
    assert ids.genius == "13899686"


def test_extract_event_ids_sportybet_mixed_phase_providers():
    """SportyBet sometimes routes prematch via SportRadar and live via
    BetGenius (or vice versa) for the same event. Both ids must be
    extracted — the SR id from the BET_RADAR phase, the Genius id from
    the BET_GENIUS phase."""
    from bookieskit.matching.extractor import extract_event_ids
    response = {
        "data": {
            "eventId": "sr:match:71494650",
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_RADAR", "sourceId": "71494650",
                },
                "liveSource": {
                    "sourceType": "BET_GENIUS",
                    "sourceId": "111111113902741",
                },
            },
        },
    }
    ids = extract_event_ids(response, platform="sportybet")
    assert ids.sportradar == "71494650"
    assert ids.genius == "13902741"


def test_extract_event_ids_sportybet_event_id_only_fallback():
    """When eventSource is absent (e.g. minimal list-view payloads),
    data.eventId is the only signal — and it always carries the SR id."""
    from bookieskit.matching.extractor import extract_event_ids
    response = {"data": {"eventId": "sr:match:70784812"}}
    ids = extract_event_ids(response, platform="sportybet")
    assert ids.sportradar == "70784812"
    assert ids.genius is None


def test_extract_event_ids_sportybet_eventid_disagreement_warns(caplog):
    """If the SR id derived from eventSource (BET_RADAR sourceId stripped
    of prefix) disagrees with the SR id on data.eventId, log a warning
    and prefer the eventSource value. This is the only realistic
    cross-check disagreement scenario; the prior synthetic-encoding
    disagreement test was based on a payload shape that never exists
    in production."""
    import logging

    from bookieskit.matching.extractor import extract_event_ids
    response = {
        "data": {
            # eventId says SR id is "99999999"
            "eventId": "sr:match:99999999",
            "eventSource": {
                "preMatchSource": {
                    # eventSource says SR id is "70784812" (after strip)
                    "sourceType": "BET_RADAR",
                    "sourceId": "111111170784812",
                },
            },
        },
    }
    with caplog.at_level(logging.WARNING, logger="bookieskit.matching.extractor"):
        ids = extract_event_ids(response, platform="sportybet")
    assert ids.sportradar == "70784812"  # eventSource wins
    assert any(
        "70784812" in r.getMessage() and "99999999" in r.getMessage()
        for r in caplog.records
    )


# ---- SportyBet sourceId prefix-stripping unit tests -----------------------


def test_sportybet_prefix_strips_genius_sourceid():
    """The 7-ones prefix is what makes SportyBet's Genius sourceId match
    BetPawa's bare 8-digit Genius widget id."""
    from bookieskit.matching.extractor import _strip_sportybet_source_prefix
    assert _strip_sportybet_source_prefix("111111113899686") == "13899686"


def test_sportybet_prefix_strips_radar_sourceid():
    """The same prefix appears on BET_RADAR preMatchSource rows."""
    from bookieskit.matching.extractor import _strip_sportybet_source_prefix
    assert _strip_sportybet_source_prefix("111111171127902") == "71127902"


def test_sportybet_prefix_passes_bare_sourceid_through():
    """liveSource for BET_RADAR rows ships the bare id (no prefix).
    The strip helper must be a no-op."""
    from bookieskit.matching.extractor import _strip_sportybet_source_prefix
    assert _strip_sportybet_source_prefix("71127902") == "71127902"


def test_sportybet_prefix_requires_more_than_prefix():
    """Don't strip if the result would be empty."""
    from bookieskit.matching.extractor import _strip_sportybet_source_prefix
    assert _strip_sportybet_source_prefix("1111111") == "1111111"


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
