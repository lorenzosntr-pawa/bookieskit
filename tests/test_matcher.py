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
    Genius via eventSource.preMatchSource.sourceType=BET_GENIUS. The
    matcher must pair them — these two are the platforms where most
    Genius-only matching happens."""
    from bookieskit.matching.matcher import match_events

    bp_event = {
        "widgets": [
            {"id": "68995116", "type": "SPORTRADAR"},
            {"id": "13599033", "type": "GENIUSSPORTS"},
        ],
    }
    sb_event = {
        "data": {
            "eventId": "sr:match:1111111113599033",
            "bgEvent": True,
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_GENIUS", "sourceId": "13599033",
                },
            },
        },
    }

    results = match_events(("betpawa", [bp_event]), ("sportybet", [sb_event]))
    assert len(results) == 1
    me = results[0]
    assert me.sportradar_id == "68995116"  # from BetPawa
    assert me.genius_id == "13599033"
    assert me.betpawa is bp_event
    assert me.sportybet is sb_event


def test_match_events_union_find_three_platforms_bridge_via_betpawa():
    """The union-find algorithm must group three events transitively:
    Betway provides SR id, SportyBet provides Genius id, BetPawa provides
    both — all three end up in one MatchedEvent because BetPawa bridges
    them."""
    from bookieskit.matching.matcher import match_events

    bp_event = {
        "widgets": [
            {"id": "70784812", "type": "SPORTRADAR"},
            {"id": "13599033", "type": "GENIUSSPORTS"},
        ],
    }
    bw_event = {"sportEvent": {"eventId": "70784812"}}  # SR only
    sb_event = {  # Genius only
        "data": {
            "eventId": "sr:match:1111111113599033",
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_GENIUS", "sourceId": "13599033",
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
    assert me.sportradar_id == "70784812"
    assert me.genius_id == "13599033"
    assert me.betpawa is bp_event
    assert me.betway is bw_event
    assert me.sportybet is sb_event


def test_match_events_genius_only_match_has_no_sportradar_id():
    """When neither side carries an SR id (BetPawa Genius widget alone,
    SportyBet Genius event alone), the match still happens via the
    Genius id; sportradar_id stays None."""
    from bookieskit.matching.matcher import match_events

    bp_event = {"widgets": [{"id": "13599033", "type": "GENIUSSPORTS"}]}
    sb_event = {
        "data": {
            "eventId": "sr:match:1111111113599033",
            "eventSource": {
                "preMatchSource": {
                    "sourceType": "BET_GENIUS", "sourceId": "13599033",
                },
            },
        },
    }

    results = match_events(("betpawa", [bp_event]), ("sportybet", [sb_event]))
    assert len(results) == 1
    me = results[0]
    assert me.sportradar_id is None
    assert me.genius_id == "13599033"
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
