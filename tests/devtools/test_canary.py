from dataclasses import asdict

from bookieskit.devtools.canary import (
    CORE_CANONICALS,
    STRUCTURE_PREDICATES,
    BookCheck,
    CanaryReport,
    expected_core,
)
from bookieskit.markets.registry import MarketRegistry


def test_core_canonicals_are_the_four_soccer_basics():
    assert CORE_CANONICALS == (
        "1x2_ft", "over_under_ft", "btts_ft", "double_chance_ft",
    )


def test_bookcheck_and_canaryreport_round_trip_through_asdict():
    bc = BookCheck(
        platform="betway",
        status="ok",
        reason="",
        expected_canonicals=["1x2_ft"],
        resolved_canonicals=["1x2_ft"],
        missing_canonicals=[],
        structure_ok=True,
    )
    rep = CanaryReport(
        sport="soccer",
        seed="33289995",
        sr_numeric="68995116",
        checks=[bc],
        drifted=False,
    )
    d = asdict(rep)
    assert d["seed"] == "33289995"
    assert d["sr_numeric"] == "68995116"
    assert d["drifted"] is False
    assert d["checks"][0]["status"] == "ok"
    assert d["checks"][0]["missing_canonicals"] == []


def test_structure_predicates_cover_all_seven_books():
    assert set(STRUCTURE_PREDICATES) == {
        "betpawa", "sportybet", "msport", "bet9ja",
        "betway", "betika", "sportpesa",
    }


def test_structure_predicate_betpawa():
    pred = STRUCTURE_PREDICATES["betpawa"]
    assert pred({"markets": [{"id": "3743"}]}) is True
    assert pred({"markets": "nope"}) is False
    assert pred({}) is False


def test_structure_predicate_sportybet_and_msport():
    for book in ("sportybet", "msport"):
        pred = STRUCTURE_PREDICATES[book]
        assert pred({"data": {"markets": [{"id": "1"}]}}) is True
        assert pred({"data": {"markets": "nope"}}) is False
        assert pred({"data": None}) is False
        assert pred({}) is False


def test_structure_predicate_betway_requires_all_three_lists():
    pred = STRUCTURE_PREDICATES["betway"]
    assert pred(
        {"marketsInGroup": [], "outcomes": [], "prices": []}
    ) is True
    assert pred({"marketsInGroup": [], "outcomes": []}) is False  # no prices
    assert pred(
        {"marketsInGroup": {}, "outcomes": [], "prices": []}
    ) is False


def test_structure_predicate_bet9ja_requires_D_O_dict():
    pred = STRUCTURE_PREDICATES["bet9ja"]
    assert pred({"D": {"O": {"S_1X2_1": 1.95}}}) is True
    assert pred({"D": {"O": []}}) is False
    assert pred({"D": None}) is False
    assert pred({}) is False


def test_structure_predicate_betika_nonempty_data_with_odds_list():
    pred = STRUCTURE_PREDICATES["betika"]
    assert pred({"data": [{"odds": [{"sub_type_id": "1"}]}]}) is True
    assert pred({"data": [{"odds": "nope"}]}) is False
    assert pred({"data": []}) is False
    assert pred({}) is False


def test_structure_predicate_sportpesa_first_value_is_list():
    pred = STRUCTURE_PREDICATES["sportpesa"]
    assert pred({"999": [{"id": "10"}]}) is True
    assert pred({"999": {}}) is False  # first value not a list
    assert pred({}) is False  # empty dict


def test_expected_core_full_for_every_soccer_book():
    reg = MarketRegistry()
    for book in (
        "betpawa", "sportybet", "msport", "bet9ja",
        "betway", "betika", "sportpesa",
    ):
        assert set(expected_core(book, "soccer", reg)) == set(CORE_CANONICALS)


def test_expected_core_empty_for_unknown_platform():
    reg = MarketRegistry()
    assert expected_core("nonexistent", "soccer", reg) == []


def test_expected_core_defaults_to_builtin_registry_when_none():
    # registry arg is required by signature; pass a fresh builtin.
    assert expected_core("betway", "soccer", MarketRegistry())


from bookieskit.devtools.canary import check_book  # noqa: E402

# A BetPawa detail payload that resolves all four core canonicals (reuses
# the shape from tests/test_parser_betpawa.py).
BETPAWA_OK = {
    "id": "32299257",
    "homeTeam": "Manchester City",
    "awayTeam": "Liverpool",
    "markets": [
        {
            "id": "3743",
            "name": "1X2 - Full Time",
            "row": [{"prices": [
                {"name": "1", "odds": 1.95},
                {"name": "X", "odds": 3.50},
                {"name": "2", "odds": 2.10},
            ]}],
        },
        {
            "id": "5000",
            "name": "Over/Under",
            "row": [{"line": 2.5, "prices": [
                {"name": "Over", "odds": 1.80},
                {"name": "Under", "odds": 2.00},
            ]}],
        },
        {
            "id": "3795",
            "name": "Both Teams To Score",
            "row": [{"prices": [
                {"name": "Yes", "odds": 1.75},
                {"name": "No", "odds": 2.05},
            ]}],
        },
        {
            "id": "4693",
            "name": "Double Chance",
            "row": [{"prices": [
                {"name": "1X", "odds": 1.25},
                {"name": "X2", "odds": 1.50},
                {"name": "12", "odds": 1.10},
            ]}],
        },
    ],
}


def test_check_book_ok_when_structure_and_all_core_resolve():
    bc = check_book(BETPAWA_OK, "betpawa", "soccer")
    assert bc.status == "ok"
    assert bc.reason == ""
    assert bc.structure_ok is True
    assert set(bc.expected_canonicals) == set(CORE_CANONICALS)
    assert set(bc.resolved_canonicals) == set(CORE_CANONICALS)
    assert bc.missing_canonicals == []


def test_check_book_drift_when_core_missing():
    # Drop BTTS + Double Chance -> two core canonicals fail to resolve.
    partial = {
        "id": "1",
        "markets": [
            BETPAWA_OK["markets"][0],  # 1X2
            BETPAWA_OK["markets"][1],  # O/U
        ],
    }
    bc = check_book(partial, "betpawa", "soccer")
    assert bc.status == "drift"
    assert bc.structure_ok is True
    assert set(bc.missing_canonicals) == {"btts_ft", "double_chance_ft"}
    assert "missing" in bc.reason


def test_check_book_drift_when_structure_broken():
    # markets renamed -> structure predicate False; nothing resolves.
    broken = {"id": "1", "marketz": []}
    bc = check_book(broken, "betpawa", "soccer")
    assert bc.status == "drift"
    assert bc.structure_ok is False
    assert "structure" in bc.reason


def test_check_book_skipped_when_no_core_mapped():
    # Unknown platform -> expected_core empty -> skipped.
    bc = check_book({}, "nonexistent", "soccer")
    assert bc.status == "skipped"
    assert bc.reason == "no core markets mapped"


import pytest  # noqa: E402

from bookieskit.devtools.canary import _discover_seed  # noqa: E402


class _FakeBetPawa:
    """Async client stub exposing get_events + get_event_detail."""

    def __init__(self, events_payload, details):
        self._events_payload = events_payload
        self._details = details  # event_id -> detail dict
        self.detail_calls: list[str] = []

    async def get_events(self, sport_id="2", event_type="UPCOMING", **kw):
        assert event_type == "UPCOMING"
        return self._events_payload

    async def get_event_detail(self, event_id):
        self.detail_calls.append(event_id)
        return self._details[event_id]


def _events(*rows):
    # rows: (id, marketsCount) tuples -> responses[].responses[] structure.
    return {"responses": [{"responses": [
        {"id": rid, "name": f"E{rid}", "marketsCount": mc}
        for rid, mc in rows
    ]}]}


def _detail_with_sr(sr_id):
    return {"widgets": [
        {"id": sr_id, "type": "SPORTRADAR", "retention": "PREMATCH"},
    ]}


def _detail_no_sr():
    return {"widgets": [
        {"id": "x", "type": "GENIUSSPORTS", "retention": "PREMATCH"},
    ]}


@pytest.mark.asyncio
async def test_discover_seed_picks_highest_markets_with_sr_widget():
    payload = _events(("100", 50), ("200", 300), ("300", 120))
    details = {
        "200": _detail_with_sr("999"),  # top by marketsCount, has SR
        "300": _detail_with_sr("888"),
        "100": _detail_with_sr("777"),
    }
    bp = _FakeBetPawa(payload, details)
    seed = await _discover_seed(bp, "2", 3)
    assert seed == "200"  # highest marketsCount, SR present
    assert bp.detail_calls == ["200"]  # stopped at first qualifying


@pytest.mark.asyncio
async def test_discover_seed_skips_candidates_without_sr_widget():
    payload = _events(("200", 300), ("300", 120))
    details = {
        "200": _detail_no_sr(),       # top by markets but no SR -> skip
        "300": _detail_with_sr("888"),
    }
    bp = _FakeBetPawa(payload, details)
    seed = await _discover_seed(bp, "2", 3)
    assert seed == "300"
    assert bp.detail_calls == ["200", "300"]


@pytest.mark.asyncio
async def test_discover_seed_respects_max_candidates():
    payload = _events(("200", 300), ("300", 120), ("400", 10))
    details = {
        "200": _detail_no_sr(),
        "300": _detail_no_sr(),
        "400": _detail_with_sr("888"),  # would qualify but is beyond top 2
    }
    bp = _FakeBetPawa(payload, details)
    seed = await _discover_seed(bp, "2", 2)
    assert seed is None
    assert bp.detail_calls == ["200", "300"]


@pytest.mark.asyncio
async def test_discover_seed_returns_none_on_empty_listing():
    bp = _FakeBetPawa({"responses": []}, {})
    assert await _discover_seed(bp, "2", 3) is None
