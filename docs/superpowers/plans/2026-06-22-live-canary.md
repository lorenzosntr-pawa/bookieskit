# Live Canary (`bookieskit.devtools.canary`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scheduled, offline-testable, agent-runnable drift detector for `bookieskit`. On a schedule it fetches **real** bookmaker payloads and detects drift — a payload whose parser-critical structure changed, or a core market that stopped resolving via `parse_markets`. It distinguishes **drift** (reachable but broken → actionable, fails the run) from **transient unreachability** (network blip → soft warning, run still passes), and survives daily event churn via dynamic BetPawa seed discovery. All checker logic is offline-unit-tested; the only networked path is the scheduled workflow.

**Architecture:** One new focused module `src/bookieskit/devtools/canary.py` (dataclasses `BookCheck` / `CanaryReport`, `CORE_CANONICALS`, `STRUCTURE_PREDICATES`, `expected_core`, `check_book`, `_discover_seed`, `run_canary`) that **reuses the existing harness core** — `resolve_event` + `ALL_BOOKS` (resolver.py), `ADAPTERS` (adapters.py), `verify` (verify.py) — with no duplicated fan-out. A `canary` subcommand is added to the existing `src/bookieskit/devtools/cli.py`, wired exactly like `resolve`/`discover`/`capture`/`verify` (argparse subparser, `--json`, injection seams). A new `.github/workflows/canary.yml` runs it daily on a schedule (never on push/PR). The canary is sub-project 3 of 5 in the project-workflow track; its `CanaryReport` JSON is the stable contract the future orchestrator (sub-project 5) turns into GitHub Issues / Slack alerts.

**Tech Stack:** Python 3.11+ stdlib only for new logic (`dataclasses`, `asyncio`, `json`, `argparse`); `httpx` is the only runtime dep (used transitively via the clients). Tests: `pytest` + `pytest-asyncio` (auto mode) + `respx`, with injected `clients=`/fakes — no live network. GitHub Actions for the scheduled workflow.

## Global Constraints

- Python floor **3.11** (`requires-python>=3.11`); `dataclasses` / `argparse` / `asyncio` are stdlib — OK to use. Runtime dep is **`httpx` only**; do NOT add dependencies (no new runtime or dev deps).
- New logic lives in `src/bookieskit/devtools/canary.py`; invoked as `python -m bookieskit.devtools canary` — ADD a `canary` subcommand to the existing `cli.py`, mirroring how `resolve`/`discover`/`capture`/`verify` are wired (including the `--json` flag and the injection seams: an injected `runner` callable and a `clients=` map).
- Ruff config: `select = ["E","F","I"]`, `line-length = 88`, `target-version = "py311"`. **`src/` must stay 100% ruff-clean.** `tests/**` ignores `E501`.
- ALL new tests are **offline** (respx + injected `clients=`/fakes), under `tests/devtools/test_canary.py`. No live network in any test. The scheduled workflow is the only networked path and is not run in PR CI.
- Local commands use `.venv/Scripts/python.exe -m pytest ...` / `-m ruff ...` (Windows); CI uses bare `pytest` / `ruff`.
- Agent-runnable: `canary --json` emits the serialized `CanaryReport`; exit code **1** on drift OR total seed-discovery failure, else **0** (unreachable-only runs exit 0 with warnings printed).
- Karpathy principle: smallest surgical change; one focused single-responsibility module. No speculative extension points.
- Each task ends green and is independently testable. Sequence: dataclasses+constants+`expected_core` → `check_book` → `_discover_seed` → `run_canary` → CLI subcommand → workflow + YAML validate.

---

### Task 1: `canary.py` core — dataclasses, `CORE_CANONICALS`, `STRUCTURE_PREDICATES`, `expected_core`

**Files:**
- Create: `src/bookieskit/devtools/canary.py`
- Create: `tests/devtools/test_canary.py`

**Interfaces:**
- Consumes: `MarketRegistry` (`bookieskit.markets.registry`); the per-platform candidate readers' payload shapes (encoded as `STRUCTURE_PREDICATES`).
- Produces: dataclasses `BookCheck` / `CanaryReport`; constant `CORE_CANONICALS`; `STRUCTURE_PREDICATES: dict[str, Callable[[dict], bool]]`; `expected_core(platform, sport, registry) -> list[str]`. All consumed by `check_book` (Task 2), `run_canary` (Task 4), and the CLI (Task 5).

Design notes (encoded from the approved design + verified against source):
- The four CORE canonicals (`1x2_ft`, `over_under_ft`, `btts_ft`, `double_chance_ft`) each map **all seven platforms** for soccer in `builtin_mappings.py`, so `expected_core(book, "soccer", registry)` returns the full 4-list for every book in practice. The function is still written as an intersection so a future registry edit (or a non-soccer sport) narrows it automatically.
- `expected_core` checks, for each CORE canonical, that `registry.get_by_canonical(c)` exists AND its per-platform id attribute (`betpawa_id` / `sportybet_id` / `bet9ja_key` / `betway_id` / `msport_id` / `sportpesa_id` / `betika_id`) is non-None. Attribute names verified in `src/bookieskit/markets/types.py` (`MarketMapping`).
- `STRUCTURE_PREDICATES` key checks are derived from the `_candidates_*` readers in `search.py` so they match reality: betpawa reads `payload["markets"]` (list); sportybet/msport read `payload["data"]["markets"]` (list); betway reads `payload["marketsInGroup"]` / `["outcomes"]` / `["prices"]` (all lists); bet9ja reads `payload["D"]["O"]` (dict); betika reads `payload["data"][0]["odds"]` (list); sportpesa reads `{<game_id>: [<market>]}` (non-empty dict whose first value is a list).

- [ ] **Step 1: Write the failing test**

Create `tests/devtools/test_canary.py`:

```python
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
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_canary.py -q`
Expected: collection/import error — `ModuleNotFoundError: No module named 'bookieskit.devtools.canary'`.

- [ ] **Step 3: Implement the core of `canary.py`**

Create `src/bookieskit/devtools/canary.py`:

```python
"""Live canary: probe real bookmaker payloads on a schedule and detect drift.

Drift = a reachable payload whose parser-critical structure changed, or a
core market that stopped resolving via parse_markets. Distinguished from
transient unreachability (network blip -> soft warning). Reuses the harness
core: resolve_event (fan-out), ADAPTERS (fetch), verify (resolution check).

All checker logic is offline-unit-testable; the only networked path is the
scheduled workflow (.github/workflows/canary.yml). The CanaryReport JSON is
the stable contract the orchestrator (sub-project 5) turns into alerts.
"""

from dataclasses import dataclass
from typing import Any, Callable

from bookieskit.markets.registry import MarketRegistry

CORE_CANONICALS: tuple[str, ...] = (
    "1x2_ft",
    "over_under_ft",
    "btts_ft",
    "double_chance_ft",
)

# Per-platform id attribute on MarketMapping (verified in markets/types.py).
_ID_ATTR: dict[str, str] = {
    "betpawa": "betpawa_id",
    "sportybet": "sportybet_id",
    "msport": "msport_id",
    "bet9ja": "bet9ja_key",
    "betway": "betway_id",
    "betika": "betika_id",
    "sportpesa": "sportpesa_id",
}


@dataclass
class BookCheck:
    """The drift verdict for one bookmaker on one canary run."""

    platform: str
    status: str  # "ok" | "drift" | "unreachable" | "skipped"
    reason: str  # human explanation (empty when ok)
    expected_canonicals: list[str]  # the core subset this book should resolve
    resolved_canonicals: list[str]  # what actually resolved
    missing_canonicals: list[str]  # expected - resolved (drift driver)
    structure_ok: bool


@dataclass
class CanaryReport:
    """The full canary run: per-book checks + the run-level drift flag."""

    sport: str
    seed: str | None  # the BetPawa event id used (None if discovery failed)
    sr_numeric: str | None
    checks: list[BookCheck]
    drifted: bool  # any check.status == "drift"


# ---- Structure predicates -------------------------------------------------
# One per book; each asserts the parser-critical shape, derived from the
# matching _candidates_* reader in search.py so it matches the real parser.


def _struct_betpawa(payload: dict) -> bool:
    return isinstance(payload.get("markets"), list)


def _struct_data_markets(payload: dict) -> bool:
    # sportybet / msport: data.markets is a list.
    return isinstance((payload.get("data") or {}).get("markets"), list)


def _struct_betway(payload: dict) -> bool:
    return all(
        isinstance(payload.get(k), list)
        for k in ("marketsInGroup", "outcomes", "prices")
    )


def _struct_bet9ja(payload: dict) -> bool:
    return isinstance((payload.get("D") or {}).get("O"), dict)


def _struct_betika(payload: dict) -> bool:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return False
    first = data[0]
    return isinstance(first, dict) and isinstance(first.get("odds"), list)


def _struct_sportpesa(payload: dict) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    first = next(iter(payload.values()), None)
    return isinstance(first, list)


STRUCTURE_PREDICATES: dict[str, Callable[[dict], bool]] = {
    "betpawa": _struct_betpawa,
    "sportybet": _struct_data_markets,
    "msport": _struct_data_markets,
    "betway": _struct_betway,
    "bet9ja": _struct_bet9ja,
    "betika": _struct_betika,
    "sportpesa": _struct_sportpesa,
}


def expected_core(
    platform: str, sport: str, registry: MarketRegistry
) -> list[str]:
    """CORE_CANONICALS intersected with what the registry maps for this book.

    A canonical counts as mapped for ``platform`` iff its MarketMapping has a
    non-None platform id attribute. For soccer every CORE canonical maps all
    seven books, so this returns the full list; for a narrower sport or a
    future registry edit it narrows automatically.
    """
    attr = _ID_ATTR.get(platform)
    if attr is None:
        return []
    out: list[str] = []
    for canonical in CORE_CANONICALS:
        mapping = registry.get_by_canonical(canonical)
        if mapping is None:
            continue
        if getattr(mapping, attr, None) is not None:
            out.append(canonical)
    return out
```

(Note: `sport` is accepted for forward-compatibility — the soccer registry does not key core mappings by sport, but the parameter keeps the signature stable for basketball/tennis later. `Any` is imported now because Task 2 adds `check_book(payload: dict[str, Any], ...)` in the same module.)

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_canary.py -q`
Expected: `12 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

(If `Any` is flagged `F401` unused at this point, remove the `Any` import now and re-add it in Task 2's import edit. Prefer keeping it and landing Task 2 immediately after.)

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/canary.py tests/devtools/test_canary.py
git commit -m "feat(canary): dataclasses, CORE_CANONICALS, structure predicates, expected_core

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `check_book` — structure predicate AND core resolution

**Files:**
- Modify: `src/bookieskit/devtools/canary.py` (add `check_book`)
- Modify: `tests/devtools/test_canary.py` (add `check_book` tests)

**Interfaces:**
- Consumes: `STRUCTURE_PREDICATES` + `expected_core` (Task 1); `verify` from `bookieskit.devtools.verify`; `MarketRegistry`.
- Produces: `check_book(payload, platform, sport, registry=None) -> BookCheck`. Consumed by `run_canary` (Task 4).

Design notes:
- `check_book` runs the structure predicate AND `verify(payload, platform, sport, canonical_ids=expected_core(...))`.
- `resolved_canonicals` = the expected canonicals that `verify` resolved (i.e. `expected - verify_result.missing`). `missing_canonicals` = `verify_result.missing`.
- Reachable-but-broken (structure False OR any missing core) → `status="drift"` with a human `reason`. All good → `status="ok"`, `reason=""`.
- An empty `expected_core` (registry maps none of the core for this book) → `status="skipped"`, `reason="no core markets mapped"` — this is decided here so both the CLI and `run_canary` get consistent behavior. (`run_canary` also short-circuits empty-expected to skipped before fetching; `check_book` handles it defensively too.)
- Unknown platform (no structure predicate) → treat structure as False → drift reason "no structure predicate" (defensive; never hit for the seven real books).

- [ ] **Step 1: Add the failing tests**

Append to `tests/devtools/test_canary.py`:

```python
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
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_canary.py -q`
Expected: FAIL — `ImportError: cannot import name 'check_book'`.

- [ ] **Step 3: Implement `check_book`**

In `src/bookieskit/devtools/canary.py`, add the import near the top (after the existing imports):

```python
from bookieskit.devtools.verify import verify
```

Then add, after `expected_core`:

```python
def check_book(
    payload: dict[str, Any],
    platform: str,
    sport: str,
    registry: MarketRegistry | None = None,
) -> BookCheck:
    """Structure predicate + core resolution -> a per-book drift verdict.

    Reachable-but-broken (structure False OR any expected core canonical did
    not resolve) -> status "drift". All good -> "ok". When the registry maps
    none of the core for this book -> "skipped".
    """
    if registry is None:
        registry = MarketRegistry()
    expected = expected_core(platform, sport, registry)
    if not expected:
        return BookCheck(
            platform=platform,
            status="skipped",
            reason="no core markets mapped",
            expected_canonicals=[],
            resolved_canonicals=[],
            missing_canonicals=[],
            structure_ok=False,
        )

    predicate = STRUCTURE_PREDICATES.get(platform)
    if predicate is None:
        structure_ok = False
    else:
        structure_ok = bool(predicate(payload))

    result = verify(payload, platform, sport, canonical_ids=expected)
    missing = list(result.missing)
    resolved = [c for c in expected if c not in missing]

    if not structure_ok:
        return BookCheck(
            platform=platform,
            status="drift",
            reason="structure predicate failed",
            expected_canonicals=expected,
            resolved_canonicals=resolved,
            missing_canonicals=missing,
            structure_ok=False,
        )
    if missing:
        return BookCheck(
            platform=platform,
            status="drift",
            reason=f"missing core canonicals: {', '.join(missing)}",
            expected_canonicals=expected,
            resolved_canonicals=resolved,
            missing_canonicals=missing,
            structure_ok=True,
        )
    return BookCheck(
        platform=platform,
        status="ok",
        reason="",
        expected_canonicals=expected,
        resolved_canonicals=resolved,
        missing_canonicals=[],
        structure_ok=True,
    )
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_canary.py -q`
Expected: `16 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/canary.py tests/devtools/test_canary.py
git commit -m "feat(canary): check_book (structure predicate + core resolution)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `_discover_seed` — dynamic BetPawa seed discovery

**Files:**
- Modify: `src/bookieskit/devtools/canary.py` (add `_discover_seed`)
- Modify: `tests/devtools/test_canary.py` (add `_discover_seed` tests)

**Interfaces:**
- Consumes: a BetPawa client's `get_events(sport_id=..., event_type="UPCOMING")` and `get_event_detail(event_id=...)`; `extract_sportradar_id` from `bookieskit.matching`.
- Produces: `async _discover_seed(bp_client, sport_id, max_candidates) -> str | None`. Consumed by `run_canary` (Task 4).

Design notes (verified against source):
- `get_events` returns `{"responses": [{"responses": [<event>, ...]}, ...]}`; each event carries `id`, `name`, `marketsCount` (BetPawa). Navigate `responses[].responses[]` and flatten.
- Rank candidates by `marketsCount` descending (events with most markets are likeliest to carry the SportRadar widget + the full core set). Missing/None `marketsCount` sorts last (treated as 0).
- For each of the top `max_candidates`, fetch `get_event_detail(event_id=id)` and return the first id whose `extract_sportradar_id(detail, "betpawa")` is not None (the extractor walks `widgets[]` for the `SPORTRADAR` entry — same code path the resolver's `_betpawa_seed_lookup` relies on).
- If none of the top candidates yields an SR id (or the listing is empty) → return `None` (signals BetPawa listing drift to the caller).
- `sport_id` is the BetPawa numeric category id (soccer = `"2"`), passed by `run_canary` via `sports.sport_id("betpawa", sport)`.

- [ ] **Step 1: Add the failing tests**

Append to `tests/devtools/test_canary.py`:

```python
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
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_canary.py -q`
Expected: FAIL — `ImportError: cannot import name '_discover_seed'`.

- [ ] **Step 3: Implement `_discover_seed`**

In `src/bookieskit/devtools/canary.py`, add to the imports:

```python
from bookieskit.matching import extract_sportradar_id
```

Then add, after `check_book`:

```python
def _list_betpawa_events(payload: dict) -> list[dict]:
    """Flatten BetPawa get_events responses[].responses[] into one list."""
    out: list[dict] = []
    for group in payload.get("responses") or []:
        if not isinstance(group, dict):
            continue
        for event in group.get("responses") or []:
            if isinstance(event, dict):
                out.append(event)
    return out


async def _discover_seed(
    bp_client: Any, sport_id: str, max_candidates: int
) -> str | None:
    """Return a current top BetPawa event id that carries a SportRadar id.

    Lists UPCOMING events for the sport, ranks by marketsCount desc, then
    fetches detail for up to ``max_candidates`` and returns the first whose
    detail yields a SportRadar id. None if none qualify (a signal that the
    BetPawa listing itself may have drifted).
    """
    payload = await bp_client.get_events(
        sport_id=sport_id, event_type="UPCOMING"
    )
    events = _list_betpawa_events(payload)
    events.sort(key=lambda e: e.get("marketsCount") or 0, reverse=True)
    for event in events[:max_candidates]:
        event_id = event.get("id")
        if event_id is None:
            continue
        event_id = str(event_id)
        detail = await bp_client.get_event_detail(event_id=event_id)
        if extract_sportradar_id(detail, platform="betpawa") is not None:
            return event_id
    return None
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_canary.py -q`
Expected: `20 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/canary.py tests/devtools/test_canary.py
git commit -m "feat(canary): _discover_seed (dynamic BetPawa top-event discovery)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `run_canary` — discover → resolve → fetch+check → report

**Files:**
- Modify: `src/bookieskit/devtools/canary.py` (add `run_canary` + fetch-with-retry helper)
- Modify: `tests/devtools/test_canary.py` (add `run_canary` tests)

**Interfaces:**
- Consumes: `_discover_seed` (Task 3); `resolve_event` + `ALL_BOOKS` (resolver.py); `ADAPTERS` (adapters.py); `check_book` (Task 2); `Handle` (types.py); `BetPawa` client (constructed when `clients` lacks one); `sport_id` (sports.py).
- Produces: `async run_canary(sport="soccer", *, seed=None, max_candidates=3, clients=None) -> CanaryReport`. Consumed by the CLI (Task 5) and the workflow.

Design notes (the run flow, from the approved design):
1. Discover the seed (BetPawa internal id) via `_discover_seed` unless `seed` is given. If discovery returns None → return a `CanaryReport` with `seed=None`, `sr_numeric=None`, `checks=[]`, `drifted=False` (the CLI maps seed-None to exit 1). Discovery uses the injected `clients["betpawa"]` if present, else constructs `BetPawa(country="ng")`.
2. `resolve_event(seed, sport, books=ALL_BOOKS, betpawa_seed=True, clients=clients)` → `sr_numeric` + per-book handles + resolver skips. The resolver skips `betpawa` (seed anchor) and `sportpesa` (no cookie) in its fan-out.
3. Build the **check set** = the resolver's `handles` PLUS an explicit `Handle("betpawa", event_id=seed)` (BetPawa checked via its own adapter using the seed id — same fetch+check path as every other book).
4. For each book in the check set: if `expected_core(book, sport, registry)` is empty → `BookCheck(status="skipped", reason="no core markets mapped")` (no fetch). Else fetch raw markets via `ADAPTERS[book].fetch_raw_markets(client, handle, live=False)` with **up to 2 retries** on transient error; persistent fetch error → `BookCheck(status="unreachable", reason="fetch failed: <repr>")`. On success → `check_book(raw, book, sport, registry)`.
5. Books in the resolver's `skipped` map → `BookCheck(status="skipped", reason=<resolver reason>)`. (BetPawa's resolver-skip reason is replaced by the real check, since BetPawa is in the check set via the explicit handle.)
6. `drifted = any(c.status == "drift")`. Assemble `CanaryReport`.

- Fetch helper `_fetch_with_retries(adapter, client, handle, *, retries=2)`: try up to `1 + retries` times; on the last failure re-raise. Per-book client resolution mirrors the resolver/CLI: injected `clients[book]` if present, else construct `_CLIENT_CLASSES[book](country=_COUNTRY[book])` via async context (imported lazily from `resolver`). A single `MarketRegistry()` is built once and passed to `expected_core`/`check_book` for the whole run.

- [ ] **Step 1: Add the failing tests**

Append to `tests/devtools/test_canary.py`:

```python
from bookieskit.devtools.canary import run_canary  # noqa: E402
from bookieskit.devtools.types import Handle  # noqa: E402

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
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_canary.py -q`
Expected: FAIL — `ImportError: cannot import name 'run_canary'`.

- [ ] **Step 3: Implement `run_canary`**

In `src/bookieskit/devtools/canary.py`, add to the imports:

```python
from bookieskit.devtools.adapters import ADAPTERS
from bookieskit.devtools.resolver import ALL_BOOKS, resolve_event
from bookieskit.devtools.sports import sport_id as _sport_id
from bookieskit.devtools.types import Handle
```

Then add, after `_discover_seed`:

```python
_FETCH_RETRIES = 2  # 1 try + 2 retries before a book is "unreachable"


async def _fetch_with_retries(
    adapter: Any, client: Any, handle: Handle, *, retries: int = _FETCH_RETRIES
) -> dict:
    """Fetch raw markets, retrying transient errors; re-raise on the last."""
    last: Exception | None = None
    for _ in range(1 + retries):
        try:
            return await adapter.fetch_raw_markets(client, handle, live=False)
        except Exception as exc:  # transient until proven persistent
            last = exc
    assert last is not None
    raise last


async def _fetch_for_book(
    book: str, handle: Handle, clients: dict[str, Any] | None
) -> dict:
    """Resolve the client for ``book`` (injected or constructed) and fetch."""
    adapter = ADAPTERS[book]
    injected = (clients or {}).get(book)
    if injected is not None:
        return await _fetch_with_retries(adapter, injected, handle)
    from bookieskit.devtools.resolver import _CLIENT_CLASSES, _COUNTRY

    async with _CLIENT_CLASSES[book](country=_COUNTRY[book]) as client:
        return await _fetch_with_retries(adapter, client, handle)


async def run_canary(
    sport: str = "soccer",
    *,
    seed: str | None = None,
    max_candidates: int = 3,
    books: tuple[str, ...] = ALL_BOOKS,
    clients: dict[str, Any] | None = None,
) -> CanaryReport:
    """Discover a seed, resolve across books, check each reachable book.

    Args:
        sport: Canonical sport (v1 = "soccer").
        seed: BetPawa internal event id; discovered dynamically when None.
        max_candidates: Top-N BetPawa events to try during discovery.
        books: Subset of ALL_BOOKS to fan out to (defaults to all). Narrowed
            by tests so only books with injected clients are fetched — keeps
            the suite offline. BetPawa is always checked (added explicitly).
        clients: Optional pre-entered client instances keyed by platform
            (test injection). When None, clients are constructed per book.

    Returns:
        CanaryReport. ``drifted`` is True iff any check is "drift".
        ``seed`` is None when discovery failed (no checks).
    """
    registry = MarketRegistry()

    # 1. Seed discovery.
    if seed is None:
        bp_sport_id = _sport_id("betpawa", sport) or "2"
        bp = (clients or {}).get("betpawa")
        if bp is not None:
            seed = await _discover_seed(bp, bp_sport_id, max_candidates)
        else:
            from bookieskit import BetPawa

            async with BetPawa(country="ng") as bp_client:
                seed = await _discover_seed(
                    bp_client, bp_sport_id, max_candidates
                )
    if seed is None:
        return CanaryReport(
            sport=sport, seed=None, sr_numeric=None, checks=[], drifted=False
        )

    # 2. Resolve across books from the BetPawa seed.
    resolved = await resolve_event(
        seed, sport, books=books, betpawa_seed=True, clients=clients
    )

    # 3. Check set = resolved handles + explicit BetPawa handle.
    handles: dict[str, Handle] = dict(resolved.handles)
    handles["betpawa"] = Handle(platform="betpawa", event_id=seed)

    checks: list[BookCheck] = []

    # 4. Reachable books: fetch (with retries) + check_book.
    for book, handle in handles.items():
        if not expected_core(book, sport, registry):
            checks.append(BookCheck(
                platform=book, status="skipped",
                reason="no core markets mapped",
                expected_canonicals=[], resolved_canonicals=[],
                missing_canonicals=[], structure_ok=False,
            ))
            continue
        try:
            raw = await _fetch_for_book(book, handle, clients)
        except Exception as exc:
            checks.append(BookCheck(
                platform=book, status="unreachable",
                reason=f"fetch failed: {exc!r}",
                expected_canonicals=expected_core(book, sport, registry),
                resolved_canonicals=[], missing_canonicals=[],
                structure_ok=False,
            ))
            continue
        checks.append(check_book(raw, book, sport, registry))

    # 5. Resolver-skipped books (not in the check set) -> skipped.
    for book, reason in resolved.skipped.items():
        if book in handles:
            continue  # checked via the explicit/resolved handle
        checks.append(BookCheck(
            platform=book, status="skipped", reason=reason,
            expected_canonicals=[], resolved_canonicals=[],
            missing_canonicals=[], structure_ok=False,
        ))

    drifted = any(c.status == "drift" for c in checks)
    return CanaryReport(
        sport=sport, seed=seed, sr_numeric=resolved.sr_numeric,
        checks=checks, drifted=drifted,
    )
```

(Note: BetPawa is always in `handles` via the explicit handle, so the resolver's `"betpawa"` skip entry is filtered out in step 5 — BetPawa is checked for real. The resolver also skips `sportpesa` ("cookie missing") which is NOT in `handles`, so it surfaces as a `skipped` BookCheck.)

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_canary.py -q`
Expected: `24 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/canary.py tests/devtools/test_canary.py
git commit -m "feat(canary): run_canary (discover -> resolve -> fetch+check -> report)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `canary` CLI subcommand on the existing `cli.py`

**Files:**
- Modify: `src/bookieskit/devtools/cli.py` (add the `canary` subparser + `run` branch)
- Modify: `tests/devtools/test_canary.py` (add CLI tests)

**Interfaces:**
- Consumes: `run_canary` + `CanaryReport` (Task 4); the existing `build_parser`/`run`/`_emit` scaffolding.
- Produces: `python -m bookieskit.devtools canary [--sport soccer] [--json] [--seed <id>] [--max-candidates 3]`. Exit code **1** if `report.drifted` OR seed discovery failed entirely (`seed is None`); else **0** (unreachable-only → 0).

Design notes — mirror the existing subcommand wiring:
- `canary` does NOT take the positional `seed` that the other four subcommands share (its seed is optional and discovered). So it is added as its own subparser with its own args, NOT via `_common`.
- The existing `run(args, *, resolver=..., clients=...)` handles the other four commands via `resolver`. For testability, add a parallel injected `runner: Callable[..., Awaitable[CanaryReport]] = run_canary` parameter to `run`, used only by the `canary` branch (so tests pass a fake `runner`). The `canary` branch must be handled BEFORE the existing `resolver(...)` fan-out call (which assumes a `seed` positional + per-book handles) — early-return from `run` for `args.cmd == "canary"`.
- `--json` emits `asdict(report)`. Human mode prints a per-book status line + a summary line.

- [ ] **Step 1: Add the failing tests**

Append to `tests/devtools/test_canary.py`:

```python
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
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_canary.py -q`
Expected: FAIL — the `canary` subparser does not exist (`SystemExit: invalid choice: 'canary'`) and `run(..., runner=...)` is an unexpected keyword argument.

- [ ] **Step 3: Wire the `canary` subcommand into `cli.py`**

In `src/bookieskit/devtools/cli.py`, add to the imports:

```python
from bookieskit.devtools.canary import CanaryReport, run_canary
```

and update the `Resolver` typing line region to also declare the runner type:

```python
Resolver = Callable[..., Awaitable[ResolvedEvent]]
CanaryRunner = Callable[..., Awaitable[CanaryReport]]
```

In `build_parser`, after the `p_verify` block (before `return parser`), add the `canary` subparser (note: NOT via `_common`, since it has no positional seed):

```python
    p_canary = sub.add_parser("canary")
    p_canary.add_argument("--sport", default="soccer")
    p_canary.add_argument("--json", action="store_true", dest="as_json")
    p_canary.add_argument("--seed", default=None)
    p_canary.add_argument("--max-candidates", type=int, default=3,
                          dest="max_candidates")
```

In `run`, add the `runner` parameter to the signature:

```python
async def run(
    args: argparse.Namespace,
    *,
    resolver: Resolver = resolve_event,
    runner: CanaryRunner = run_canary,
    clients: dict[str, Any] | None = None,
) -> int:
```

and, as the FIRST thing inside `run` (before `books = _books_arg(args)`), handle the canary branch and early-return:

```python
    if args.cmd == "canary":
        report = await runner(
            args.sport,
            seed=args.seed,
            max_candidates=args.max_candidates,
            clients=clients,
        )
        _emit(
            asdict(report),
            args.as_json,
            [f"canary sport={report.sport} seed={report.seed} "
             f"sr={report.sr_numeric} drifted={report.drifted}"]
            + [f"  {c.platform}: {c.status} {c.reason}".rstrip()
               for c in report.checks],
        )
        if report.drifted or report.seed is None:
            return 1
        return 0
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_canary.py -q`
Expected: `31 passed`.

- [ ] **Step 5: Confirm the existing CLI tests still pass (no regression to the four other subcommands)**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_cli.py -q`
Expected: all pass, 0 failed.

- [ ] **Step 6: Smoke-test the entrypoint `--help` (non-interactive, offline)**

Run: `.venv/Scripts/python.exe -m bookieskit.devtools --help`
Expected: usage text whose subcommand list now includes `canary` (i.e. `{resolve,discover,capture,verify,canary}`); exit 0.

Run: `.venv/Scripts/python.exe -m bookieskit.devtools canary --help`
Expected: usage text showing `--sport`, `--json`, `--seed`, `--max-candidates`; exit 0. (Do NOT run `canary` without `--help` here — that would hit the live network.)

- [ ] **Step 7: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add src/bookieskit/devtools/cli.py tests/devtools/test_canary.py
git commit -m "feat(canary): canary CLI subcommand (--json + exit codes)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `.github/workflows/canary.yml` + YAML validation

**Files:**
- Create: `.github/workflows/canary.yml`

**Interfaces:**
- Consumes: the working `python -m bookieskit.devtools canary --json` (Tasks 1-5).
- Produces: the scheduled drift-detection gate. A `drift` (or seed-failure) exit fails the job → GitHub notifies via the Actions UI/email. `unreachable`-only runs pass (no false alarm). Verified on GitHub once the owner triggers a `workflow_dispatch` run.

Design notes (from the approved design; uses `ci.yml` as the structural template):
- Triggers: `schedule` (cron `"0 6 * * *"`, daily ~06:00 UTC) + `workflow_dispatch`. **NOT** `push` / `pull_request`.
- `concurrency`: group `"canary"`, `cancel-in-progress: false` (a long live run must not be cancelled by the next schedule tick).
- One `canary` job: `ubuntu-latest`, `timeout-minutes: 10`, Python `"3.13"`, pip cache keyed on `pyproject.toml`, `pip install -e ".[dev]"`, then `python -m bookieskit.devtools canary --json`.

- [ ] **Step 1: Create `.github/workflows/canary.yml`**

```yaml
name: Canary

on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch:

concurrency:
  group: canary
  cancel-in-progress: false

jobs:
  canary:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: pyproject.toml
      - run: pip install -e ".[dev]"
      - run: python -m bookieskit.devtools canary --json
```

- [ ] **Step 2: Validate the YAML parses (ephemeral PyYAML — NOT added to project deps)**

IMPORTANT: PyYAML parses the YAML `on:` key as the boolean `True` (the "Norway problem"), so the triggers live under `d[True]`, not `d["on"]`. Run exactly this:

```bash
.venv/Scripts/python.exe -m pip install -q pyyaml && \
.venv/Scripts/python.exe -c "import yaml; d=yaml.safe_load(open('.github/workflows/canary.yml')); on=d[True]; assert 'schedule' in on and 'workflow_dispatch' in on; assert 'push' not in on and 'pull_request' not in on; assert d['jobs']['canary']['timeout-minutes']==10; assert d['concurrency']['cancel-in-progress'] is False; print('YAML OK')"
```
Expected: `YAML OK`

- [ ] **Step 3: Run the full devtools suite + lint the whole tree (final green gate)**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools -q`
Expected: all pass, 0 failed (includes the full `tests/devtools/test_canary.py`).

Run: `.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/canary.yml
git commit -m "ci: add scheduled canary workflow (daily cron + workflow_dispatch)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 5: (Deferred — owner-triggered) Verify the live path on GitHub**

Once the branch is on a remote with Actions enabled, the owner triggers one `workflow_dispatch` run and confirms it completes within the 10-minute timeout and reports per-book `ok`/`skipped` against live endpoints (proving the live path works end-to-end). Do not block plan completion on this step; record it as the post-remote follow-up.

---

## Notes for the executor

- Run commands with the project venv: `.venv/Scripts/python.exe -m <tool>` (Windows). On CI (Ubuntu) the canary workflow uses plain `python -m bookieskit.devtools canary --json` after `pip install -e ".[dev]"`.
- All `canary` logic reaches the network only in production; every test injects `clients=`/fakes or a fake `runner`, so the suite stays fully offline. Never run `python -m bookieskit.devtools canary` (without `--help`) locally during the plan — it hits live bookmaker endpoints.
- The canary REUSES the harness core verbatim: `resolve_event` + `ALL_BOOKS`, `ADAPTERS`, `verify`. No fan-out is duplicated. The only new fetch logic is the retry wrapper (`_fetch_with_retries`).
- `expected_core` returns the full four-canonical list for every soccer book (all four CORE canonicals map all seven platforms in `builtin_mappings.py`); the intersection logic exists for future sports/registry edits, not because soccer narrows it today.
- Karpathy: one focused module, smallest surgical CLI edit (one subparser + one early-return branch + one injected `runner` seam), no speculative extension points beyond what the design calls out.

## Controller self-review notes (verified against source; address during execution)

These were checked against the live source while writing the plan; the interface assumptions hold:
- `resolve_event(seed, sport, books=ALL_BOOKS, *, live, betpawa_seed, sportpesa_cookie, betika_cookie, clients)` and `ALL_BOOKS` exist in `resolver.py`; `_CLIENT_CLASSES`/`_COUNTRY` are module-level and importable (the CLI already imports them lazily). The resolver skips `betpawa` and (without cookie) `sportpesa` — both handled in `run_canary` step 5.
- `ADAPTERS[book].fetch_raw_markets(client, handle, *, live)` matches the retry wrapper's call. BetPawa's adapter `fetch_raw_markets` calls `get_event_detail(event_id=handle.event_id)` — so the explicit `Handle("betpawa", seed)` fetches the seed's own detail (which carries `markets`), and `check_book` runs the betpawa structure predicate + `verify` on it.
- `verify(payload, platform, sport, canonical_ids=expected)` returns `VerifyResult(platform, resolved, missing)`; `resolved` is keyed by canonical_id, `missing` lists requested-but-unresolved — exactly what `check_book` consumes.
- `extract_sportradar_id(detail, platform="betpawa")` walks `widgets[]` for the first `SPORTRADAR` id (see `extractor._extract_event_ids_betpawa`); the `_discover_seed` test details use that exact widget shape, and `run_canary`'s betpawa-seed tests reuse `tests/devtools/test_resolver.py`'s detail shape (SPORTRADAR widget + participants) so the resolver's `_betpawa_seed_lookup` resolves `sr_numeric` for the right reason.
- BetPawa `get_events(sport_id="2", event_type="UPCOMING")` returns `responses[].responses[]`; events carry `id` and `marketsCount` — `_discover_seed` navigates and ranks accordingly.
- All four CORE canonicals (`1x2_ft`, `over_under_ft`, `btts_ft`, `double_chance_ft`) have non-None ids for all seven platforms in `builtin_mappings.py`; `MarketMapping` id attributes are `betpawa_id`/`sportybet_id`/`bet9ja_key`/`betway_id`/`msport_id`/`sportpesa_id`/`betika_id` (`markets/types.py`).
- **Residual Minor risk:** the hand-rolled `SPORTYBET_OK` payload in Task 4 must actually `parse_markets`-resolve all four core canonicals. If the SportyBet parser expects a different odds field/outcome shape, the RED→GREEN cycle for `test_run_canary_mixed_ok_drift_unreachable_skipped` will surface it — prefer copying the exact outcome shape from `tests/test_parser_sportybet.py` over tweaking the invented one. The `BETPAWA_OK` payload is copied verbatim from `tests/test_parser_betpawa.py` and is known-good.
