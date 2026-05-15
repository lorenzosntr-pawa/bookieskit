from bookieskit.matching.matcher import MatchedEvent, match_events


def test_match_events_two_platforms():
    bp_events = [
        {
            "id": "111",
            "widgets": [
                {"type": "SPORTRADAR", "value": "sr:match:100"}
            ],
        },
        {
            "id": "222",
            "widgets": [
                {"type": "SPORTRADAR", "value": "sr:match:200"}
            ],
        },
    ]
    sb_events = [
        {"bizCode": 10000, "data": {"eventId": "sr:match:100"}},
        {"bizCode": 10000, "data": {"eventId": "sr:match:300"}},
    ]

    matched = match_events(("betpawa", bp_events), ("sportybet", sb_events))

    assert len(matched) == 3
    # Find the one that matches both
    both = next(m for m in matched if m.betpawa and m.sportybet)
    assert both.sportradar_id == "100"


def test_match_events_three_platforms():
    bp = [
        {
            "id": "1",
            "widgets": [
                {"type": "SPORTRADAR", "value": "sr:match:999"}
            ],
        }
    ]
    sb = [{"bizCode": 10000, "data": {"eventId": "sr:match:999"}}]
    b9 = [{"R": "D", "D": {"EXTID": "999", "O": {}}}]

    matched = match_events(
        ("betpawa", bp), ("sportybet", sb), ("bet9ja", b9)
    )

    assert len(matched) == 1
    assert matched[0].sportradar_id == "999"
    assert matched[0].betpawa is not None
    assert matched[0].sportybet is not None
    assert matched[0].bet9ja is not None


def test_match_events_no_overlap():
    bp = [
        {
            "id": "1",
            "widgets": [
                {"type": "SPORTRADAR", "value": "sr:match:100"}
            ],
        }
    ]
    sb = [{"bizCode": 10000, "data": {"eventId": "sr:match:200"}}]

    matched = match_events(("betpawa", bp), ("sportybet", sb))

    assert len(matched) == 2
    bp_only = next(m for m in matched if m.sportradar_id == "100")
    assert bp_only.betpawa is not None
    assert bp_only.sportybet is None


def test_match_events_empty_input():
    matched = match_events(("betpawa", []), ("sportybet", []))
    assert len(matched) == 0


def test_match_events_skips_events_without_sr_id():
    bp = [{"id": "1", "widgets": []}]  # No SR ID
    sb = [{"bizCode": 10000, "data": {"eventId": "sr:match:100"}}]

    matched = match_events(("betpawa", bp), ("sportybet", sb))

    assert len(matched) == 1
    assert matched[0].sportradar_id == "100"
    assert matched[0].betpawa is None
    assert matched[0].sportybet is not None


def test_matched_event_dataclass():
    me = MatchedEvent(sportradar_id="123")
    assert me.betpawa is None
    assert me.sportybet is None
    assert me.bet9ja is None


def test_match_events_handles_betway_and_msport():
    from bookieskit.matching import match_events
    bw_event = {"sportEvent": {"eventId": 12345}}
    ms_event = {"data": {"eventId": "sr:match:12345"}}
    matched = match_events(("betway", [bw_event]), ("msport", [ms_event]))
    assert len(matched) == 1
    assert matched[0].sportradar_id == "12345"
    assert matched[0].betway is bw_event
    assert matched[0].msport is ms_event


def test_match_events_populates_sportpesa_field():
    # SportPesa's natural event-detail shape is a list of length 1 with
    # `betradarId` carrying the SR id. The matcher treats each `event` in
    # the list-of-events as-is and passes it to extract_sportradar_id.
    from bookieskit.matching.matcher import match_events

    bw_event = {"sportEvent": {"eventId": "12345"}}
    sp_event = [{"id": 8868005, "betradarId": 12345}]

    results = match_events(
        ("betway", [bw_event]),
        ("sportpesa", [sp_event]),
    )

    assert len(results) == 1
    me = results[0]
    assert me.sportradar_id == "12345"
    assert me.betway is bw_event
    assert me.sportpesa is sp_event


def test_match_events_populates_betika_field():
    # Betika's parent_match_id is the SR id. Once the extractor branch
    # for "betika" lands (Task 9), this test passes end-to-end.
    from bookieskit.matching.matcher import match_events

    bw_event = {"sportEvent": {"eventId": "70784812"}}
    bk_event = [{"match_id": "10846988", "parent_match_id": "70784812"}]

    results = match_events(
        ("betway", [bw_event]),
        ("betika", [bk_event]),
    )

    assert len(results) == 1
    me = results[0]
    assert me.sportradar_id == "70784812"
    assert me.betway is bw_event
    assert me.betika is bk_event


# ---- BetGenius support (v0.9.0) -------------------------------------------


def test_matched_event_supports_genius_id_field():
    """MatchedEvent gains an optional ``genius_id`` field in 0.9.0.
    sportradar_id becomes optional too — a Genius-only match has no SR id."""
    me = MatchedEvent(genius_id="13599033")
    assert me.sportradar_id is None
    assert me.genius_id == "13599033"


def test_match_events_pairs_betpawa_sportybet_via_genius():
    """BetPawa exposes both SR and Genius widgets; SportyBet exposes
    Genius via eventSource.preMatchSource.sourceType=BET_GENIUS (with
    the sourceId prefixed by seven '1's). The matcher must pair them
    on the Genius id even though BetPawa's SR widget id (68995116)
    differs from SportyBet's SR id (71453928 — different sources may
    pick different SportRadar ids for the same physical match)."""
    from bookieskit.matching.matcher import match_events

    bp_event = {
        "widgets": [
            {"id": "68995116", "type": "SPORTRADAR"},
            {"id": "13599033", "type": "GENIUSSPORTS"},
        ],
    }
    sb_event = {
        "data": {
            "eventId": "sr:match:71453928",  # SportyBet's own SR id
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_GENIUS",
                    "sourceId": "111111113599033",  # 7-ones + Genius id
                },
            },
        },
    }

    results = match_events(("betpawa", [bp_event]), ("sportybet", [sb_event]))
    assert len(results) == 1
    me = results[0]
    # Both bookmakers' SR ids end up in the same group (only one of them
    # appears on `sportradar_id`; first-seen wins). The Genius id is
    # what actually bridges them.
    assert me.genius_id == "13599033"
    assert me.sportradar_id in ("68995116", "71453928")
    assert me.betpawa is bp_event
    assert me.sportybet is sb_event


def test_match_events_union_find_three_platforms_bridge_via_betpawa():
    """The union-find algorithm must group three events transitively:
    Betway provides SR id, SportyBet provides a different SR id plus
    a Genius id, BetPawa provides both BetPawa's SR id and the same
    Genius id. The Genius id bridges BetPawa <-> SportyBet, and the
    BetPawa SR id bridges BetPawa <-> Betway — all three end up in
    one MatchedEvent."""
    from bookieskit.matching.matcher import match_events

    bp_event = {
        "widgets": [
            {"id": "70784812", "type": "SPORTRADAR"},
            {"id": "13599033", "type": "GENIUSSPORTS"},
        ],
    }
    bw_event = {"sportEvent": {"eventId": "70784812"}}  # BetPawa-bridged SR
    sb_event = {  # Genius-bridged
        "data": {
            "eventId": "sr:match:71453928",
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_GENIUS",
                    "sourceId": "111111113599033",
                },
            },
        },
    }

    results = match_events(
        ("betpawa", [bp_event]),
        ("betway", [bw_event]),
        ("sportybet", [sb_event]),
    )
    assert len(results) == 1
    me = results[0]
    assert me.genius_id == "13599033"
    # sportradar_id is one of the two SR ids in the group (first-seen wins).
    assert me.sportradar_id in ("70784812", "71453928")
    assert me.betpawa is bp_event
    assert me.betway is bw_event
    assert me.sportybet is sb_event


def test_match_events_genius_only_match_has_no_sportradar_id():
    """When the only known signal is a Genius id (BetPawa carries
    just the GENIUSSPORTS widget, no SPORTRADAR widget), the match
    produces a MatchedEvent with sportradar_id=None.

    NB: in practice this is a single-bookmaker case — real SportyBet
    payloads always carry an SR id on data.eventId even for Genius
    events. The contract being pinned is the matcher's behaviour when
    the SR id is genuinely absent."""
    from bookieskit.matching.matcher import match_events

    bp_event = {"widgets": [{"id": "13599033", "type": "GENIUSSPORTS"}]}

    results = match_events(("betpawa", [bp_event]))
    assert len(results) == 1
    me = results[0]
    assert me.sportradar_id is None
    assert me.genius_id == "13599033"
    assert me.betpawa is bp_event


def test_match_events_pairs_betpawa_sportybet_via_shared_sr():
    """When BetPawa and SportyBet both expose the SAME SR id for the
    same match (the common case for non-Genius events), they pair on
    the SR key. This was true before 0.9.0 too — pinning it here for
    regression coverage."""
    from bookieskit.matching.matcher import match_events

    bp_event = {
        "widgets": [{"id": "71127902", "type": "SPORTRADAR"}],
    }
    sb_event = {
        "data": {
            "eventId": "sr:match:71127902",
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_RADAR",
                    "sourceId": "111111171127902",  # prefixed
                },
                "liveSource": {
                    "sourceType": "BET_RADAR",
                    "sourceId": "71127902",  # bare
                },
            },
        },
    }

    results = match_events(("betpawa", [bp_event]), ("sportybet", [sb_event]))
    assert len(results) == 1
    me = results[0]
    assert me.sportradar_id == "71127902"
    assert me.genius_id is None
    assert me.betpawa is bp_event
    assert me.sportybet is sb_event


def test_match_events_no_ids_event_is_skipped():
    """An event with neither SR nor Genius id contributes nothing to
    the result (today's contract: skip-with-no-id)."""
    from bookieskit.matching.matcher import match_events

    bp_blank = {"widgets": []}  # no ids
    sb_event = {"data": {"eventId": "sr:match:1"}}

    results = match_events(("betpawa", [bp_blank]), ("sportybet", [sb_event]))
    assert len(results) == 1
    assert results[0].betpawa is None
    assert results[0].sportybet is sb_event
    assert results[0].sportradar_id == "1"
