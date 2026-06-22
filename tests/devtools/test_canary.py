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


def test_check_book_drift_on_non_dict_data_does_not_raise():
    # Proves Fix 1: structure predicate catches non-dict `data` and
    # short-circuits before _parse_sportybet can call .get() and raise.
    bc = check_book({"data": "error"}, "sportybet", "soccer")
    assert bc.status == "drift"
    assert bc.structure_ok is False


from bookieskit.devtools.canary import run_canary  # noqa: E402

# A SportyBet detail payload resolving all four core canonicals.
SPORTYBET_OK = {"data": {"markets": [
    {"id": "1", "name": "1X2", "outcomes": [
        {"desc": "Home", "odds": "1.5"},
        {"desc": "Draw", "odds": "3.2"},
        {"desc": "Away", "odds": "2.1"},
    ]},
    {"id": "18", "name": "O/U", "specifier": "total=2.5", "outcomes": [
        {"desc": "Over 2.5", "odds": "1.8"},
        {"desc": "Under 2.5", "odds": "2.0"},
    ]},
    {"id": "29", "name": "BTTS", "outcomes": [
        {"desc": "Yes", "odds": "1.7"},
        {"desc": "No", "odds": "2.0"},
    ]},
    {"id": "10", "name": "DC", "outcomes": [
        {"desc": "Home or Draw", "odds": "1.2"},
        {"desc": "Draw or Away", "odds": "1.5"},
        {"desc": "Home or Away", "odds": "1.1"},
    ]},
]}}


class _CanaryClient:
    """Async-context client stub with arbitrary coroutine methods."""

    def __init__(self, **methods):
        self._methods = methods

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def __getattr__(self, name):
        if name in self._methods:
            return self._methods[name]
        raise AttributeError(name)


@pytest.mark.asyncio
async def test_run_canary_mixed_ok_drift_unreachable_skipped():
    # Seed given -> no discovery. betpawa OK, sportybet OK,
    # betway drifts (structure broken), bet9ja unreachable, sportpesa skipped.
    async def _bp_detail(event_id):
        # Resolver's betpawa_seed lookup: SR id + participants.
        return {
            "widgets": [{"id": "777", "type": "SPORTRADAR"}],
            "participants": [{"name": "A"}, {"name": "B"}],
            **BETPAWA_OK,
        }

    async def _sb_detail(event_id, live=False):
        return SPORTYBET_OK

    async def _bw_markets_all(event_id):
        return {"marketz": "broken"}  # structure predicate fails -> drift

    async def _b9_map(sport_id):
        return {}  # SR not in prematch map -> resolver "not found" skip

    clients = {
        "betpawa": _CanaryClient(get_event_detail=_bp_detail),
        "sportybet": _CanaryClient(get_event_detail=_sb_detail),
        "betway": _CanaryClient(get_event_markets_all=_bw_markets_all),
        "bet9ja": _CanaryClient(build_prematch_event_map=_b9_map),
    }
    # books restricted to the injected fakes (+ betpawa is always checked
    # explicitly) so no un-injected book touches the network.
    report = await run_canary(
        "soccer", seed="33289995",
        books=("sportybet", "betway", "bet9ja", "sportpesa"),
        clients=clients,
    )

    by = {c.platform: c for c in report.checks}
    assert by["betpawa"].status == "ok"
    assert by["sportybet"].status == "ok"
    assert by["betway"].status == "drift"
    assert by["betway"].structure_ok is False
    # bet9ja not resolved by the resolver -> skipped with resolver reason.
    assert by["bet9ja"].status == "skipped"
    assert by["bet9ja"].reason == "not found"
    # sportpesa cookie-missing -> skipped.
    assert by["sportpesa"].status == "skipped"
    assert report.drifted is True
    assert report.seed == "33289995"
    assert report.sr_numeric == "777"


@pytest.mark.asyncio
async def test_run_canary_unreachable_does_not_set_drift():
    async def _bp_detail(event_id):
        return {
            "widgets": [{"id": "777", "type": "SPORTRADAR"}],
            "participants": [{"name": "A"}, {"name": "B"}],
            **BETPAWA_OK,
        }

    call_count = {"n": 0}

    async def _bw_markets_all(event_id):
        call_count["n"] += 1
        raise RuntimeError("timeout")

    clients = {
        "betpawa": _CanaryClient(get_event_detail=_bp_detail),
        "betway": _CanaryClient(get_event_markets_all=_bw_markets_all),
    }
    report = await run_canary(
        "soccer", seed="33289995",
        books=("betway",),
        clients=clients,
    )
    by = {c.platform: c for c in report.checks}
    assert by["betway"].status == "unreachable"
    assert "timeout" in by["betway"].reason
    assert call_count["n"] == 3  # 1 try + 2 retries
    assert report.drifted is False  # unreachable never fails the run


@pytest.mark.asyncio
async def test_run_canary_seed_discovery_failure_returns_empty_report():
    # No seed + discovery yields None -> empty report, seed None.
    async def _events(sport_id="2", event_type="UPCOMING", **kw):
        return {"responses": []}

    clients = {"betpawa": _CanaryClient(get_events=_events)}
    report = await run_canary("soccer", clients=clients)
    assert report.seed is None
    assert report.sr_numeric is None
    assert report.checks == []
    assert report.drifted is False


@pytest.mark.asyncio
async def test_run_canary_discovers_seed_when_not_given():
    async def _events(sport_id="2", event_type="UPCOMING", **kw):
        return {"responses": [{"responses": [
            {"id": "555", "marketsCount": 200},
        ]}]}

    async def _bp_detail(event_id):
        assert event_id == "555"
        return {
            "widgets": [{"id": "777", "type": "SPORTRADAR"}],
            "participants": [{"name": "A"}, {"name": "B"}],
            **BETPAWA_OK,
        }

    clients = {
        "betpawa": _CanaryClient(
            get_events=_events, get_event_detail=_bp_detail
        ),
    }
    report = await run_canary(
        "soccer", clients=clients, max_candidates=1, books=(),
    )
    assert report.seed == "555"
    by = {c.platform: c for c in report.checks}
    assert by["betpawa"].status == "ok"


import json  # noqa: E402

from bookieskit.devtools import cli  # noqa: E402


def test_build_parser_has_canary_subcommand():
    parser = cli.build_parser()
    args = parser.parse_args(["canary"])
    assert args.cmd == "canary"
    assert args.sport == "soccer"  # default
    assert args.seed is None
    assert args.max_candidates == 3


def test_build_parser_canary_accepts_seed_and_max_candidates():
    parser = cli.build_parser()
    args = parser.parse_args(
        ["canary", "--seed", "555", "--max-candidates", "5", "--json"]
    )
    assert args.seed == "555"
    assert args.max_candidates == 5
    assert args.as_json is True


async def _runner_ok(sport, *, seed=None, max_candidates=3, clients=None):
    return CanaryReport(
        sport=sport, seed="555", sr_numeric="777",
        checks=[BookCheck(
            platform="betway", status="ok", reason="",
            expected_canonicals=["1x2_ft"], resolved_canonicals=["1x2_ft"],
            missing_canonicals=[], structure_ok=True,
        )],
        drifted=False,
    )


async def _runner_drift(sport, *, seed=None, max_candidates=3, clients=None):
    return CanaryReport(
        sport=sport, seed="555", sr_numeric="777",
        checks=[BookCheck(
            platform="betway", status="drift", reason="structure",
            expected_canonicals=["1x2_ft"], resolved_canonicals=[],
            missing_canonicals=["1x2_ft"], structure_ok=False,
        )],
        drifted=True,
    )


async def _runner_no_seed(sport, *, seed=None, max_candidates=3, clients=None):
    return CanaryReport(
        sport=sport, seed=None, sr_numeric=None, checks=[], drifted=False,
    )


async def _runner_unreachable(
    sport, *, seed=None, max_candidates=3, clients=None
):
    return CanaryReport(
        sport=sport, seed="555", sr_numeric="777",
        checks=[BookCheck(
            platform="betway", status="unreachable", reason="fetch failed",
            expected_canonicals=["1x2_ft"], resolved_canonicals=[],
            missing_canonicals=[], structure_ok=False,
        )],
        drifted=False,
    )


@pytest.mark.asyncio
async def test_canary_json_output_and_exit_zero_when_ok(capsys):
    args = cli.build_parser().parse_args(["canary", "--json"])
    code = await cli.run(args, runner=_runner_ok)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["sport"] == "soccer"
    assert out["seed"] == "555"
    assert out["checks"][0]["platform"] == "betway"
    assert out["drifted"] is False


@pytest.mark.asyncio
async def test_canary_exit_one_on_drift(capsys):
    args = cli.build_parser().parse_args(["canary", "--json"])
    code = await cli.run(args, runner=_runner_drift)
    assert code == 1


@pytest.mark.asyncio
async def test_canary_exit_one_on_seed_discovery_failure(capsys):
    args = cli.build_parser().parse_args(["canary", "--json"])
    code = await cli.run(args, runner=_runner_no_seed)
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["seed"] is None


@pytest.mark.asyncio
async def test_canary_exit_zero_when_unreachable_only(capsys):
    args = cli.build_parser().parse_args(["canary"])
    code = await cli.run(args, runner=_runner_unreachable)
    assert code == 0
