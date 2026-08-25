from bookieskit.devtools.search import discover, iter_candidates, unmapped
from bookieskit.markets.registry import MarketRegistry

SPORTYBET_PAYLOAD = {
    "data": {
        "markets": [
            {
                "id": "1",
                "name": "1X2",
                "specifier": "",
                "outcomes": [
                    {"desc": "Home"}, {"desc": "Draw"}, {"desc": "Away"},
                ],
            },
            {
                "id": "18",
                "name": "Over/Under",
                "specifier": "total=2.5",
                "outcomes": [{"desc": "Over 2.5"}, {"desc": "Under 2.5"}],
            },
            {
                "id": "99999",
                "name": "Total Corners",
                "specifier": "total=9.5",
                "outcomes": [{"desc": "Over"}, {"desc": "Under"}],
            },
        ]
    }
}


def test_iter_candidates_sportybet_reads_ids_names_outcomes():
    cands = iter_candidates(SPORTYBET_PAYLOAD, "sportybet")
    by_id = {c.market_id: c for c in cands}
    assert by_id["1"].name == "1X2"
    assert by_id["1"].outcomes == ["Home", "Draw", "Away"]
    assert by_id["18"].specifier == "total=2.5"


def test_discover_filters_by_term_against_name_and_outcomes():
    hits = discover(SPORTYBET_PAYLOAD, "sportybet", r"over/?under|corner")
    ids = {c.market_id for c in hits}
    assert ids == {"18", "99999"}  # O/U by name, Corners by name


def test_discover_matches_outcome_strings():
    hits = discover(SPORTYBET_PAYLOAD, "sportybet", r"draw")
    assert {c.market_id for c in hits} == {"1"}


def test_unmapped_keeps_only_ids_absent_from_registry():
    reg = MarketRegistry()  # 1X2 ("1") and O/U ("18") are mapped for soccer
    cands = unmapped(SPORTYBET_PAYLOAD, "sportybet", "soccer", registry=reg)
    ids = {c.market_id for c in cands}
    # 1 and 18 are registry-mapped soccer markets -> excluded.
    # 99999 (Total Corners) is unmapped -> included.
    assert ids == {"99999"}


def test_unmapped_defaults_to_builtin_registry():
    cands = unmapped(SPORTYBET_PAYLOAD, "sportybet", "soccer")
    assert {c.market_id for c in cands} == {"99999"}


BETIKA_PAYLOAD = {
    "data": [
        {
            "match_id": "5",
            "odds": [
                {
                    "sub_type_id": "1",
                    "name": "3 Way",
                    "odds": [{"display": "1"}, {"display": "X"}, {"display": "2"}],
                },
                {
                    "sub_type_id": "77777",
                    "name": "Weird Market",
                    "odds": [{"display": "A"}, {"display": "B"}],
                },
            ],
        }
    ]
}


def test_unmapped_betika_sub_type_id():
    cands = unmapped(BETIKA_PAYLOAD, "betika", "soccer")
    assert {c.market_id for c in cands} == {"77777"}


def _load_elephantbet_prematch() -> dict:
    import json
    from pathlib import Path

    fixture = (
        Path(__file__).parent.parent
        / "fixtures" / "event_info" / "elephantbet" / "prematch.json"
    )
    return json.loads(fixture.read_text(encoding="utf-8"))


def test_iter_candidates_elephantbet_reads_ids_names_outcomes():
    # Regression: no reader was registered for elephantbet, so
    # `discover --unmapped` could never list its unmapped markets
    # (Task 6 fix round 1).
    payload = _load_elephantbet_prematch()
    cands = iter_candidates(payload, "elephantbet")
    by_id = {c.market_id: c for c in cands}
    assert "3" in by_id  # 1x2_ft, registered elephantbet_id
    assert by_id["3"].name == "1X2"
    assert by_id["3"].outcomes == ["1", "X", "2"]


def test_unmapped_elephantbet_excludes_registered_markets():
    payload = _load_elephantbet_prematch()
    cands = unmapped(payload, "elephantbet", "soccer")
    ids = {c.market_id for c in cands}
    # The four registered core markets (1x2=3, O/U=29, BTTS=7, DC=17) must
    # be excluded; the fixture's many other market ids are unmapped.
    assert "3" not in ids
    assert "29" not in ids
    assert "7" not in ids
    assert "17" not in ids
    assert ids  # the fixture carries plenty of genuinely unmapped markets
