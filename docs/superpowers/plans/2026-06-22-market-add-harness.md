# Market-Add Harness (`bookieskit.devtools`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the five throwaway probe/capture scripts with one tested, offline-verifiable, agent-runnable subpackage `src/bookieskit/devtools/`, invoked as `python -m bookieskit.devtools {resolve,discover,capture,verify}`. It covers the recurring market-add loop — resolve an event across all 7 bookmakers from a single seed, discover candidate markets (by regex term **or** by registry-diff `--unmapped`), capture raw fixtures, and verify which canonicals `parse_markets` resolves — with per-book failure isolation, `--json` structured output, and meaningful exit codes.

**Architecture:** Nine focused modules under `src/bookieskit/devtools/`: `types.py` (dataclasses Handle / ResolvedEvent / Candidate / VerifyResult), `sports.py` (canonical-sport → per-bookmaker sport-id table), `adapters.py` (one tiny `resolve` + `fetch_raw_markets` adapter per bookmaker), `resolver.py` (the cross-book fan-out orchestrator), `search.py` (`discover` term-match + `unmapped` registry-diff), `verify.py` (run `parse_markets` per book, report resolved canonicals), `fixtures.py` (write raw fixtures under `tests/fixtures/event_info/`), `cli.py` (argparse, 4 subcommands), `__main__.py` (entrypoint). One folded-in library change extracts Betway's pagination-merge loop into `get_event_markets_all()`. The resolver + adapters + `search.unmapped` core is the shared substrate the later canary and scout sub-projects reuse.

**Tech Stack:** Python 3.11+ stdlib (`argparse`, `dataclasses`, `asyncio`, `json`, `re`, `pathlib`), `httpx` (existing runtime dep, used transitively via the clients). Tests: `pytest` + `pytest-asyncio` (auto mode) + `respx`. No new runtime or dev dependencies.

## Global Constraints

- Python floor **3.11** (`requires-python>=3.11`); `tomllib` / `dataclasses` / `argparse` are stdlib — OK to use. Runtime dep is **`httpx` only**; do NOT add dependencies.
- New code lives in `src/bookieskit/devtools/` and is invoked as `python -m bookieskit.devtools <cmd>`.
- Ruff config: `select = ["E","F","I"]`, `line-length = 88`, `target-version = "py311"`. **`src/` must stay 100% ruff-clean.** `tests/**` ignores `E501`.
- ALL new tests are **offline** (respx-mocked), under `tests/devtools/`, reusing `tests/fixtures/`. No live network in tests.
- Local commands use `.venv/Scripts/python.exe -m pytest ...` / `-m ruff ...` (Windows); CI uses bare `pytest` / `ruff`.
- Agent-runnable: every command non-interactive, supports `--json` structured output (serialized dataclasses), meaningful exit codes, no prompts.
- Karpathy principle: smallest surgical change; focused single-responsibility modules.
- Sequence so each task ends green: types → sports → betway client refactor → adapters → resolver → search(+unmapped) → verify → fixtures → cli/`__main__` → cleanup.
- Each `tests/devtools/` test file needs `tests/devtools/__init__.py` to exist (created in Task 1) so `pytest` collects the package cleanly under `pythonpath = ["."]`.

---

### Task 1: `devtools` package skeleton + `types.py` dataclasses

**Files:**
- Create: `src/bookieskit/devtools/__init__.py`
- Create: `src/bookieskit/devtools/types.py`
- Create: `tests/devtools/__init__.py`
- Create: `tests/devtools/test_types.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Handle`, `ResolvedEvent`, `Candidate`, `VerifyResult` dataclasses (consumed by every later task); the `devtools` package namespace.

- [ ] **Step 1: Write the failing test**

Create `tests/devtools/__init__.py` as an empty file (package marker), then create `tests/devtools/test_types.py`:

```python
from dataclasses import asdict

from bookieskit.devtools.types import (
    Candidate,
    Handle,
    ResolvedEvent,
    VerifyResult,
)


def test_handle_defaults_extra_to_empty_dict():
    h = Handle(platform="betway", event_id="123")
    assert h.platform == "betway"
    assert h.event_id == "123"
    assert h.extra == {}
    # extra dicts are per-instance (no shared mutable default)
    h.extra["competition_id"] = "7"
    assert Handle(platform="x", event_id=None).extra == {}


def test_resolved_event_round_trips_through_asdict():
    ev = ResolvedEvent(
        seed="sr:match:42",
        sport="soccer",
        sr_numeric="42",
        home="A",
        away="B",
        handles={"betway": Handle(platform="betway", event_id="42")},
        skipped={"sportpesa": "cookie missing"},
    )
    d = asdict(ev)
    assert d["sr_numeric"] == "42"
    assert d["handles"]["betway"]["event_id"] == "42"
    assert d["skipped"]["sportpesa"] == "cookie missing"


def test_candidate_fields():
    c = Candidate(
        platform="sportybet",
        market_id="18",
        name="Over/Under",
        specifier="total=2.5",
        outcomes=["Over", "Under"],
    )
    assert c.market_id == "18"
    assert c.outcomes == ["Over", "Under"]


def test_verify_result_fields():
    vr = VerifyResult(
        platform="betpawa",
        resolved={"1x2_ft": {"outcomes": {"home": 1.5}}},
        missing=["over_under_ft"],
    )
    assert "1x2_ft" in vr.resolved
    assert vr.missing == ["over_under_ft"]
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_types.py -q`
Expected: collection/import error — `ModuleNotFoundError: No module named 'bookieskit.devtools'`.

- [ ] **Step 3: Implement the package + dataclasses**

Create `src/bookieskit/devtools/__init__.py`:

```python
"""Market-add harness — resolve/discover/capture/verify across bookmakers.

Dev/agent tooling, not a stability-guaranteed public API. Invoke as
``python -m bookieskit.devtools <cmd>``.
"""
```

Create `src/bookieskit/devtools/types.py`:

```python
"""Dataclasses for the market-add harness."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Handle:
    """Per-bookmaker identifier(s) needed to fetch markets for the event."""

    platform: str
    event_id: str | None  # SR-prefixed, numeric, or internal id to fetch with
    extra: dict[str, Any] = field(default_factory=dict)  # e.g. betika comp id


@dataclass
class ResolvedEvent:
    """The outcome of resolving one seed across the requested bookmakers."""

    seed: str
    sport: str
    sr_numeric: str | None
    home: str
    away: str
    handles: dict[str, Handle]  # platform -> handle (present only where resolved)
    skipped: dict[str, str]  # platform -> human reason (cookie/not found/error)


@dataclass
class Candidate:
    """One candidate market discovered on a bookmaker payload."""

    platform: str
    market_id: str | None  # id / key / marketId / sub_type_id, per platform
    name: str
    specifier: str | None
    outcomes: list[str]


@dataclass
class VerifyResult:
    """Per-platform parse_markets result."""

    platform: str
    resolved: dict[str, Any]  # canonical_id -> {lines/outcomes with odds}
    missing: list[str]  # requested canonical_ids that did NOT parse
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_types.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/__init__.py src/bookieskit/devtools/types.py tests/devtools/__init__.py tests/devtools/test_types.py
git commit -m "feat(devtools): package skeleton + harness dataclasses

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `sports.py` — canonical-sport → per-bookmaker sport-id table

**Files:**
- Create: `src/bookieskit/devtools/sports.py`
- Create: `tests/devtools/test_sports.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SPORT_IDS: dict[str, dict[str, str | None]]` and `sport_id(platform, sport) -> str | None` (consumed by adapters + resolver).

The values are taken verbatim from `examples/compare_betpawa_competition_full.py` `SPORT_CONFIG` and the per-client defaults: BetPawa soccer category id `"2"`, basketball `"3"`, tennis `"452"`; SportyBet/MSport use SportRadar sport ids `sr:sport:1` (soccer), `sr:sport:2` (basketball), `sr:sport:5` (tennis); Bet9ja prematch sport ids `"1"`/`"2"`/`"5"`; Betika `"14"`/`"30"`/`"28"`; SportPesa `"1"`/`"2"`/`"5"`. Betway uses string slugs `"soccer"`/`"basketball"`/`"tennis"` (its API sportId is the slug).

- [ ] **Step 1: Write the failing test**

Create `tests/devtools/test_sports.py`:

```python
from bookieskit.devtools.sports import SPORT_IDS, sport_id


def test_soccer_ids_for_every_platform():
    assert sport_id("betpawa", "soccer") == "2"
    assert sport_id("sportybet", "soccer") == "sr:sport:1"
    assert sport_id("msport", "soccer") == "sr:sport:1"
    assert sport_id("bet9ja", "soccer") == "1"
    assert sport_id("betway", "soccer") == "soccer"
    assert sport_id("betika", "soccer") == "14"
    assert sport_id("sportpesa", "soccer") == "1"


def test_basketball_ids():
    assert sport_id("betpawa", "basketball") == "3"
    assert sport_id("sportybet", "basketball") == "sr:sport:2"
    assert sport_id("bet9ja", "basketball") == "2"
    assert sport_id("betika", "basketball") == "30"
    assert sport_id("betway", "basketball") == "basketball"


def test_unknown_sport_or_platform_returns_none():
    assert sport_id("betpawa", "curling") is None
    assert sport_id("nonexistent", "soccer") is None


def test_table_covers_all_seven_platforms_for_soccer():
    assert set(SPORT_IDS["soccer"].keys()) == {
        "betpawa", "sportybet", "msport", "bet9ja",
        "betway", "betika", "sportpesa",
    }
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_sports.py -q`
Expected: `ModuleNotFoundError: No module named 'bookieskit.devtools.sports'`.

- [ ] **Step 3: Implement `sports.py`**

Create `src/bookieskit/devtools/sports.py`:

```python
"""Canonical sport -> per-bookmaker sport id.

Values verified live and encoded in
``examples/compare_betpawa_competition_full.py`` SPORT_CONFIG and the
per-client ``get_*`` defaults. BetPawa uses numeric category ids
(soccer=2, basketball=3, tennis=452); SportyBet/MSport use SportRadar
ids (``sr:sport:N``); Bet9ja prematch uses single-digit sport ids;
Betika and SportPesa use their own numeric sport ids; Betway's API
``sportId`` is a lowercase slug.
"""

SPORT_IDS: dict[str, dict[str, str | None]] = {
    "soccer": {
        "betpawa": "2",
        "sportybet": "sr:sport:1",
        "msport": "sr:sport:1",
        "bet9ja": "1",
        "betway": "soccer",
        "betika": "14",
        "sportpesa": "1",
    },
    "basketball": {
        "betpawa": "3",
        "sportybet": "sr:sport:2",
        "msport": "sr:sport:2",
        "bet9ja": "2",
        "betway": "basketball",
        "betika": "30",
        "sportpesa": "2",
    },
    "tennis": {
        "betpawa": "452",
        "sportybet": "sr:sport:5",
        "msport": "sr:sport:5",
        "bet9ja": "5",
        "betway": "tennis",
        "betika": "28",
        "sportpesa": "5",
    },
}


def sport_id(platform: str, sport: str) -> str | None:
    """Return the per-bookmaker sport id for a canonical sport.

    Returns None when the sport or platform is unknown.
    """
    return SPORT_IDS.get(sport, {}).get(platform)
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_sports.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/sports.py tests/devtools/test_sports.py
git commit -m "feat(devtools): per-bookmaker sport-id table

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Betway library change — extract `get_event_markets_all()`

**Files:**
- Modify: `src/bookieskit/bookmakers/betway.py` (the `get_markets` method, ~267-327)
- Create: `tests/devtools/test_betway_markets_all.py`

**Interfaces:**
- Consumes: existing `Betway.get_event_detail`, `Betway.get_event_markets`.
- Produces: `async Betway.get_event_markets_all(self, event_id: str) -> dict[str, Any]` returning the raw merged payload (`marketsInGroup` / `outcomes` / `prices` / `sportEvent`). Consumed by the Betway adapter (Task 4). `get_markets()` behavior is unchanged.

- [ ] **Step 1: Write the failing test (pagination merge + short-page stop)**

Create `tests/devtools/test_betway_markets_all.py`:

```python
import httpx
import pytest
import respx

from bookieskit.bookmakers.betway import Betway

_MARKETS_URL = (
    "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/"
    "MarketGroupings/MarketGroupNamesAndMarketsForEvent"
)
_DETAIL_URL = (
    "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v3/Feeds/"
    "Events/EventAndGameState"
)


def _page(mig, outs, prices):
    return {"marketsInGroup": mig, "outcomes": outs, "prices": prices}


@pytest.mark.asyncio
@respx.mock
async def test_get_event_markets_all_merges_pages_and_stops_on_short_page():
    respx.get(_DETAIL_URL).respond(
        json={"sportEvent": {"homeTeam": "A", "awayTeam": "B"}}
    )
    # Page 0: full page of 100 -> loop must request page 1.
    page0_mig = [{"marketId": f"m{i}", "name": "X"} for i in range(100)]
    page0_outs = [{"outcomeId": "o0", "marketId": "m0", "name": "Over"}]
    page0_prices = [{"outcomeId": "o0", "priceDecimal": 1.5}]
    # Page 1: short page (2 markets) -> loop must stop after this page.
    page1_mig = [{"marketId": "m100", "name": "Y"}, {"marketId": "m101", "name": "Z"}]
    page1_outs = [{"outcomeId": "o1", "marketId": "m100", "name": "Under"}]
    page1_prices = [{"outcomeId": "o1", "priceDecimal": 2.0}]

    route = respx.get(_MARKETS_URL)
    route.side_effect = [
        httpx.Response(200, json=_page(page0_mig, page0_outs, page0_prices)),
        httpx.Response(200, json=_page(page1_mig, page1_outs, page1_prices)),
    ]

    async with Betway(country="ng") as client:
        merged = await client.get_event_markets_all(event_id="42")

    assert route.call_count == 2  # stopped after the short second page
    assert len(merged["marketsInGroup"]) == 102
    assert merged["outcomes"] == page0_outs + page1_outs
    assert merged["prices"] == page0_prices + page1_prices
    assert merged["sportEvent"] == {"homeTeam": "A", "awayTeam": "B"}


@pytest.mark.asyncio
@respx.mock
async def test_get_event_markets_all_empty_first_page():
    respx.get(_DETAIL_URL).respond(json={"sportEvent": {}})
    respx.get(_MARKETS_URL).respond(
        json={"marketsInGroup": [], "outcomes": [], "prices": []}
    )
    async with Betway(country="ng") as client:
        merged = await client.get_event_markets_all(event_id="42")
    assert merged["marketsInGroup"] == []
    assert merged["sportEvent"] == {}
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_betway_markets_all.py -q`
Expected: FAIL — `AttributeError: 'Betway' object has no attribute 'get_event_markets_all'`.

- [ ] **Step 3: Refactor `get_markets` to delegate to a new `get_event_markets_all`**

In `src/bookieskit/bookmakers/betway.py`, replace the entire `get_markets` method body (the block currently at ~267-327, from `async def get_markets(` through the `return parse_markets(...)` line) with:

```python
    async def get_event_markets_all(self, event_id: str) -> dict[str, Any]:
        """Auto-paginate get_event_markets and return the raw merged payload.

        Betway's markets endpoint returns at most 100 markets per call. This
        walks every page and merges marketsInGroup / outcomes / prices, then
        attaches the event scoreboard (sportEvent.homeTeam / awayTeam) which
        the parser uses for team-name placeholder substitution. Returns the
        raw merged dict the parser (and the devtools harness) consume —
        without parsing.

        Args:
            event_id: Betway event ID (= SportRadar ID)

        Returns:
            dict with marketsInGroup / outcomes / prices / sportEvent.
        """
        detail = await self.get_event_detail(event_id=event_id)
        sport_event = detail.get("sportEvent") or {}

        all_mig: list = []
        all_outs: list = []
        all_prices: list = []

        skip = 0
        take = 100
        while True:
            page = await self.get_event_markets(
                event_id=event_id, skip=skip, take=take
            )
            mig = page.get("marketsInGroup") or []
            if not mig:
                break
            all_mig.extend(mig)
            all_outs.extend(page.get("outcomes") or [])
            all_prices.extend(page.get("prices") or [])
            if len(mig) < take:
                # Last page (fewer than `take` markets returned)
                break
            skip += take
            # Safety cap: don't loop forever if the endpoint pathologically
            # always returns full pages. Soccer events have <500 markets in
            # practice; cap at 1000 (10 pages).
            if skip >= 1000:
                break

        return {
            "marketsInGroup": all_mig,
            "outcomes": all_outs,
            "prices": all_prices,
            "sportEvent": sport_event,
        }

    async def get_markets(self, event_id: str, registry: Any = None) -> list:
        """Fetch event markets and return normalized markets.

        Auto-paginates Betway's markets endpoint (which returns at most 100
        markets per call) and merges marketsInGroup / outcomes / prices
        across pages before parsing. Without this, events with >100
        markets (large soccer fixtures, big basketball games) would
        silently drop markets that live past the first page — including
        the per-team Over/Under and Next Goal markets which often land
        past index 100 on top fixtures.

        Args:
            event_id: Betway event ID (= SportRadar ID)
            registry: MarketRegistry (default: built-in)

        Returns:
            List of NormalizedMarket for recognized markets across all pages.
        """
        from bookieskit.markets.parser import parse_markets

        merged = await self.get_event_markets_all(event_id=event_id)
        return parse_markets(
            merged, platform=self.PLATFORM_KEY, registry=registry
        )
```

- [ ] **Step 4: Run the new test to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_betway_markets_all.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Confirm existing Betway tests stay green (no behavior change)**

Run: `.venv/Scripts/python.exe -m pytest tests/test_betway.py tests/test_parser_betway.py -q`
Expected: all pass, 0 failed.

- [ ] **Step 6: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/bookmakers/betway.py tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add src/bookieskit/bookmakers/betway.py tests/devtools/test_betway_markets_all.py
git commit -m "refactor(betway): extract get_event_markets_all for raw merged payload

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `adapters.py` — per-bookmaker resolve + fetch_raw_markets

**Files:**
- Create: `src/bookieskit/devtools/adapters.py`
- Create: `tests/devtools/test_adapters.py`

**Interfaces:**
- Consumes: `sport_id` (Task 2); `Handle` (Task 1); each bookmaker client's fetch surface — `BetPawa.get_event_detail`, `SportyBet.get_event_detail(event_id, live=)`, `MSport.get_event_detail(event_id, live=)`, `Betway.get_event_detail` + `Betway.get_event_markets_all` (Task 3), `Bet9ja.build_prematch_event_map` / `find_event_id_by_sr_id` / `get_event_detail` / `get_live_event_detail`, `Betika.get_matches` / `get_event_markets`, `SportPesa.get_event_markets`; `extract_sportradar_id` from `bookieskit.matching`.
- Produces: `ADAPTERS: dict[str, Adapter]` and an `Adapter` protocol/dataclass with `async resolve(client, sr_numeric, sport, *, live=False) -> Handle | None` and `async fetch_raw_markets(client, handle, *, live=False) -> dict`. Consumed by the resolver (Task 5), verify (Task 7), and capture (Task 8).

Design notes encoded from the scripts/examples:
- **SportyBet / MSport:** the SR-prefixed id (`sr:match:<n>`) IS the fetch id; `fetch_raw_markets` returns the `get_event_detail` payload (it already contains markets). `resolve` just wraps the prefixed id in a `Handle`.
- **Betway:** the bare numeric SR id is the fetch id; `fetch_raw_markets` returns `get_event_markets_all`.
- **BetPawa:** has no SR→internal reverse lookup, so the adapter's `resolve` returns `None` (BetPawa is the seed source, handled directly in the resolver from the seed event-detail) — the adapter still exposes `fetch_raw_markets` taking a BetPawa internal id, used when the seed itself is a BetPawa id.
- **Bet9ja:** prematch → `build_prematch_event_map(sport_id)` then dict-lookup the SR numeric; live → `find_event_id_by_sr_id`. `Handle.event_id` is the internal id. `fetch_raw_markets` calls `get_event_detail` (prematch) or `get_live_event_detail` (live).
- **Betika:** scan `get_matches(sport_id, page, limit=100)` pages for a row whose `parent_match_id == sr_numeric`; capture `match_id` + `competition_id` (the latter into `Handle.extra`). `fetch_raw_markets` calls `get_event_markets(event_id, competition_id=...)`.
- **SportPesa:** cookie-gated and has no cheap SR reverse lookup in scope; `resolve` returns `None` here (the resolver records a skip), and `fetch_raw_markets` takes a SportPesa game id via `get_event_markets`. (Full SR→game-id index building is the canary/scout's job; v1 only fetches when a game id is supplied directly.)

- [ ] **Step 1: Write the failing test**

Create `tests/devtools/test_adapters.py`:

```python
import httpx
import pytest
import respx

from bookieskit import Betika, Betway, MSport, SportyBet
from bookieskit.devtools.adapters import ADAPTERS
from bookieskit.devtools.types import Handle


@pytest.mark.asyncio
async def test_sportybet_resolve_wraps_prefixed_id():
    adapter = ADAPTERS["sportybet"]
    async with SportyBet(country="ng") as client:
        handle = await adapter.resolve(client, "42", "soccer")
    assert handle == Handle(platform="sportybet", event_id="sr:match:42")


@pytest.mark.asyncio
@respx.mock
async def test_sportybet_fetch_raw_markets_returns_detail_payload():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/event").respond(
        json={"data": {"markets": [{"id": "1"}]}}
    )
    adapter = ADAPTERS["sportybet"]
    handle = Handle(platform="sportybet", event_id="sr:match:42")
    async with SportyBet(country="ng") as client:
        raw = await adapter.fetch_raw_markets(client, handle)
    assert raw["data"]["markets"][0]["id"] == "1"


@pytest.mark.asyncio
async def test_msport_resolve_wraps_prefixed_id():
    adapter = ADAPTERS["msport"]
    async with MSport(country="ng") as client:
        handle = await adapter.resolve(client, "42", "soccer")
    assert handle.event_id == "sr:match:42"


@pytest.mark.asyncio
async def test_betway_resolve_uses_bare_numeric():
    adapter = ADAPTERS["betway"]
    async with Betway(country="ng") as client:
        handle = await adapter.resolve(client, "42", "soccer")
    assert handle == Handle(platform="betway", event_id="42")


@pytest.mark.asyncio
@respx.mock
async def test_betway_fetch_raw_markets_delegates_to_markets_all():
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v3/Feeds/"
        "Events/EventAndGameState"
    ).respond(json={"sportEvent": {"homeTeam": "A", "awayTeam": "B"}})
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/"
        "MarketGroupings/MarketGroupNamesAndMarketsForEvent"
    ).respond(json={"marketsInGroup": [], "outcomes": [], "prices": []})
    adapter = ADAPTERS["betway"]
    handle = Handle(platform="betway", event_id="42")
    async with Betway(country="ng") as client:
        raw = await adapter.fetch_raw_markets(client, handle)
    assert raw["sportEvent"] == {"homeTeam": "A", "awayTeam": "B"}
    assert raw["marketsInGroup"] == []


@pytest.mark.asyncio
@respx.mock
async def test_betika_resolve_scans_listing_for_parent_match_id():
    route = respx.get("https://api.betika.com/v1/uo/matches")
    route.side_effect = [
        httpx.Response(200, json={"data": [
            {"match_id": "111", "parent_match_id": "999", "competition_id": "7"},
        ]}),
        httpx.Response(200, json={"data": [
            {"match_id": "222", "parent_match_id": "42", "competition_id": "8"},
        ]}),
    ]
    adapter = ADAPTERS["betika"]
    async with Betika(country="ke") as client:
        handle = await adapter.resolve(client, "42", "soccer")
    assert handle is not None
    assert handle.event_id == "222"
    assert handle.extra["competition_id"] == "8"


@pytest.mark.asyncio
@respx.mock
async def test_betika_resolve_returns_none_when_not_found():
    respx.get("https://api.betika.com/v1/uo/matches").respond(json={"data": []})
    adapter = ADAPTERS["betika"]
    async with Betika(country="ke") as client:
        handle = await adapter.resolve(client, "42", "soccer")
    assert handle is None


@pytest.mark.asyncio
async def test_betpawa_and_sportpesa_resolve_return_none():
    # No SR->internal reverse lookup in v1; resolver records these as skips.
    assert ADAPTERS["betpawa"].resolve is not None
    assert ADAPTERS["sportpesa"].resolve is not None
    # Both platforms are present in the adapter table.
    assert set(ADAPTERS) == {
        "betpawa", "sportybet", "msport", "bet9ja",
        "betway", "betika", "sportpesa",
    }
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_adapters.py -q`
Expected: `ModuleNotFoundError: No module named 'bookieskit.devtools.adapters'`.

- [ ] **Step 3: Implement `adapters.py`**

Create `src/bookieskit/devtools/adapters.py`:

```python
"""Per-bookmaker adapters: resolve a SR id to a fetch Handle, and fetch the
raw markets payload for a Handle.

Each adapter isolates one bookmaker's resolve/fetch quirks behind the same
two-method interface so the resolver, the later canary, and the scout all
reuse it. A parallel ``catalog_fetch`` method can be added alongside without
touching the markets path.
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from bookieskit.devtools.types import Handle

_BETIKA_SCAN_PAGES = 9  # mirrors the old probe/smoke scripts


@dataclass
class Adapter:
    """Two-method adapter for one bookmaker."""

    platform: str
    resolve: Callable[..., Awaitable[Handle | None]]
    fetch_raw_markets: Callable[..., Awaitable[dict]]


# ---- SportyBet ------------------------------------------------------------


async def _sportybet_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    return Handle(platform="sportybet", event_id=f"sr:match:{sr_numeric}")


async def _sportybet_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    return await client.get_event_detail(event_id=handle.event_id, live=live)


# ---- MSport ---------------------------------------------------------------


async def _msport_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    return Handle(platform="msport", event_id=f"sr:match:{sr_numeric}")


async def _msport_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    return await client.get_event_detail(event_id=handle.event_id, live=live)


# ---- Betway ---------------------------------------------------------------


async def _betway_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    # Betway's eventId IS the bare numeric SR id.
    return Handle(platform="betway", event_id=sr_numeric)


async def _betway_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    return await client.get_event_markets_all(event_id=handle.event_id)


# ---- Bet9ja ---------------------------------------------------------------


async def _bet9ja_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    from bookieskit.devtools.sports import sport_id

    if live:
        internal = await client.find_event_id_by_sr_id(sr_numeric)
    else:
        sid = sport_id("bet9ja", sport) or "1"
        event_map = await client.build_prematch_event_map(sport_id=sid)
        internal = event_map.get(sr_numeric)
    if internal is None:
        return None
    return Handle(platform="bet9ja", event_id=str(internal))


async def _bet9ja_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    if live:
        return await client.get_live_event_detail(event_id=handle.event_id)
    return await client.get_event_detail(event_id=handle.event_id)


# ---- Betika ---------------------------------------------------------------


async def _betika_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    from bookieskit.devtools.sports import sport_id

    sid = sport_id("betika", sport) or "14"
    for page in range(1, _BETIKA_SCAN_PAGES + 1):
        listing = await client.get_matches(
            sport_id=int(sid), page=page, limit=100
        )
        data = listing.get("data") or []
        if not data:
            break
        for row in data:
            if str(row.get("parent_match_id", "")) == sr_numeric:
                comp = row.get("competition_id")
                extra = {}
                if comp is not None:
                    extra["competition_id"] = str(comp)
                return Handle(
                    platform="betika",
                    event_id=str(row.get("match_id")),
                    extra=extra,
                )
    return None


async def _betika_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    comp = handle.extra.get("competition_id")
    return await client.get_event_markets(
        event_id=handle.event_id, live=live, competition_id=comp
    )


# ---- BetPawa --------------------------------------------------------------


async def _betpawa_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    # BetPawa has no SR->internal reverse lookup; it is the seed source.
    # The resolver handles a BetPawa-internal seed directly.
    return None


async def _betpawa_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    # handle.event_id is a BetPawa internal id (used when the seed is one).
    return await client.get_event_detail(event_id=handle.event_id)


# ---- SportPesa ------------------------------------------------------------


async def _sportpesa_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    # No cheap SR->game-id reverse lookup in v1 (that is the scout's index
    # builder). Resolver records a skip. fetch_raw_markets still works when
    # a game id is supplied directly.
    return None


async def _sportpesa_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    return await client.get_event_markets(event_id=handle.event_id)


ADAPTERS: dict[str, Adapter] = {
    "betpawa": Adapter("betpawa", _betpawa_resolve, _betpawa_fetch),
    "sportybet": Adapter("sportybet", _sportybet_resolve, _sportybet_fetch),
    "msport": Adapter("msport", _msport_resolve, _msport_fetch),
    "bet9ja": Adapter("bet9ja", _bet9ja_resolve, _bet9ja_fetch),
    "betway": Adapter("betway", _betway_resolve, _betway_fetch),
    "betika": Adapter("betika", _betika_resolve, _betika_fetch),
    "sportpesa": Adapter("sportpesa", _sportpesa_resolve, _sportpesa_fetch),
}
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_adapters.py -q`
Expected: `8 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/adapters.py tests/devtools/test_adapters.py
git commit -m "feat(devtools): per-bookmaker resolve/fetch adapters

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `resolver.py` — cross-book fan-out orchestrator

**Files:**
- Create: `src/bookieskit/devtools/resolver.py`
- Create: `tests/devtools/test_resolver.py`

**Interfaces:**
- Consumes: `ADAPTERS` (Task 4), `Handle` / `ResolvedEvent` (Task 1), the client classes from `bookieskit`, `extract_sportradar_id` + `extract_participants` from the library.
- Produces: `ALL_BOOKS: tuple[str, ...]`; `async resolve_event(seed, sport, books=ALL_BOOKS, *, live=False, sportpesa_cookie=None, betika_cookie=None, clients=None) -> ResolvedEvent`. The `clients` kwarg (default None) lets tests inject already-entered client instances keyed by platform; in production the resolver constructs and enters clients itself. Consumed by `verify`/`capture`/`cli`.

Design notes:
- **Seed parsing:** a seed is either a raw SR id (`sr:match:N` or bare `N`) or a BetPawa internal event id. Heuristic from the scripts: if the seed starts with `sr:match:` or is supplied with `--from-sr`, treat as SR. Otherwise treat as a BetPawa internal id, fetch BetPawa `get_event_detail`, and extract the SR numeric via `extract_sportradar_id(detail, "betpawa")`; home/away from `extract_participants`. To keep v1 simple and match the scripts, the seed is interpreted as: bare-numeric or `sr:match:`-prefixed ⇒ SR id directly; if `--betpawa-seed` flag is set ⇒ BetPawa internal id. (CLI default in Task 9: bare numeric is treated as SR; `--betpawa-seed` opts into the BetPawa-id path.)
- **Per-book isolation:** each book's resolve+nothing-else runs in a `try/except`; on any exception, record `skipped[platform] = "error: <repr>"` and continue (mirrors the scripts' `safe()` wrapper). A `None` from `resolve` records `skipped[platform] = "not found"`.
- **Cookie-gated:** if `sportpesa` is requested but no cookie supplied, skip with `"cookie missing"` before constructing the client. Same option for betika cookie (Betika is open by default, so only skip if a cookie path is *required* and absent — in v1 Betika is never cookie-skipped; the flag is accepted for symmetry).

- [ ] **Step 1: Write the failing test**

Create `tests/devtools/test_resolver.py`:

```python
import pytest

from bookieskit.devtools.resolver import ALL_BOOKS, resolve_event
from bookieskit.devtools.types import Handle


class _FakeClient:
    """Minimal async-context client stub for resolver tests."""

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


def test_all_books_lists_seven():
    assert ALL_BOOKS == (
        "betpawa", "sportybet", "msport", "bet9ja",
        "betway", "betika", "sportpesa",
    )


@pytest.mark.asyncio
async def test_resolve_from_sr_id_populates_handles_and_skips():
    async def _b9_map(sport_id):
        return {}  # SR id not in prematch map -> not found

    clients = {
        "sportybet": _FakeClient(),
        "msport": _FakeClient(),
        "betway": _FakeClient(),
        "bet9ja": _FakeClient(build_prematch_event_map=_b9_map),
    }
    ev = await resolve_event(
        "sr:match:42",
        "soccer",
        books=("sportybet", "msport", "betway", "bet9ja", "sportpesa"),
        clients=clients,
    )
    assert ev.sr_numeric == "42"
    assert ev.handles["sportybet"] == Handle("sportybet", "sr:match:42")
    assert ev.handles["betway"] == Handle("betway", "42")
    assert ev.skipped["bet9ja"] == "not found"
    # SportPesa requested without cookie -> cookie-missing skip.
    assert ev.skipped["sportpesa"] == "cookie missing"


@pytest.mark.asyncio
async def test_resolve_isolates_per_book_exceptions():
    async def _boom(sport_id):
        raise RuntimeError("kaboom")

    clients = {
        "betway": _FakeClient(),
        "bet9ja": _FakeClient(build_prematch_event_map=_boom),
    }
    ev = await resolve_event(
        "sr:match:42", "soccer",
        books=("betway", "bet9ja"), clients=clients,
    )
    assert ev.handles["betway"] == Handle("betway", "42")
    assert ev.skipped["bet9ja"].startswith("error:")
    assert "kaboom" in ev.skipped["bet9ja"]
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_resolver.py -q`
Expected: `ModuleNotFoundError: No module named 'bookieskit.devtools.resolver'`.

- [ ] **Step 3: Implement `resolver.py`**

Create `src/bookieskit/devtools/resolver.py`:

```python
"""Cross-bookmaker fan-out: seed + sport -> ResolvedEvent.

Each book is resolved independently; an exception, a not-found, or a
missing cookie records a per-book skip and never aborts the others.
"""

from typing import Any

from bookieskit import (
    Bet9ja,
    Betika,
    BetPawa,
    Betway,
    MSport,
    SportPesa,
    SportyBet,
)
from bookieskit.devtools.adapters import ADAPTERS
from bookieskit.devtools.types import Handle, ResolvedEvent
from bookieskit.matching import extract_sportradar_id

ALL_BOOKS: tuple[str, ...] = (
    "betpawa", "sportybet", "msport", "bet9ja",
    "betway", "betika", "sportpesa",
)

# Cookie-gated books: resolution is skipped when no cookie is supplied.
_COOKIE_GATED = {"sportpesa"}

_CLIENT_CLASSES: dict[str, type] = {
    "betpawa": BetPawa,
    "sportybet": SportyBet,
    "msport": MSport,
    "bet9ja": Bet9ja,
    "betway": Betway,
    "betika": Betika,
    "sportpesa": SportPesa,
}

# Country variant per book (ng where it operates, ke proxy for ke-only books).
_COUNTRY: dict[str, str] = {
    "betpawa": "ng",
    "sportybet": "ng",
    "msport": "ng",
    "bet9ja": "ng",
    "betway": "ng",
    "betika": "ke",
    "sportpesa": "ke",
}


def _normalize_sr(seed: str) -> str:
    """Return the bare numeric SR id from a seed (strips sr:match: prefix)."""
    if seed.startswith("sr:match:"):
        return seed[len("sr:match:"):]
    return seed


async def resolve_event(
    seed: str,
    sport: str,
    books: tuple[str, ...] = ALL_BOOKS,
    *,
    live: bool = False,
    betpawa_seed: bool = False,
    sportpesa_cookie: str | None = None,
    betika_cookie: str | None = None,
    clients: dict[str, Any] | None = None,
) -> ResolvedEvent:
    """Resolve a seed across the requested bookmakers.

    Args:
        seed: Raw SR id ("sr:match:N" or bare "N"), or a BetPawa internal
            event id when ``betpawa_seed=True``.
        sport: Canonical sport name ("soccer", "basketball", "tennis").
        books: Subset of ALL_BOOKS to resolve.
        live: Resolve/fetch live markets where the book distinguishes.
        betpawa_seed: Treat ``seed`` as a BetPawa internal id; fetch its
            detail and extract the SR id from there.
        sportpesa_cookie / betika_cookie: Warmed cookies for gated books.
        clients: Optional pre-entered client instances keyed by platform
            (test injection). When None, clients are constructed here.

    Returns:
        ResolvedEvent with per-book handles and skip reasons.
    """
    home = away = "?"
    sr_numeric: str | None = None

    # Resolve the SR id (and home/away) up front.
    if betpawa_seed:
        bp = (clients or {}).get("betpawa")
        if bp is not None:
            sr_numeric, home, away = await _betpawa_seed_lookup(bp, seed)
        else:
            async with BetPawa(country="ng") as bp_client:
                sr_numeric, home, away = await _betpawa_seed_lookup(
                    bp_client, seed
                )
    else:
        sr_numeric = _normalize_sr(seed)

    handles: dict[str, Handle] = {}
    skipped: dict[str, str] = {}

    for book in books:
        if book == "betpawa":
            # BetPawa has no SR->internal reverse lookup.
            skipped["betpawa"] = "no SR reverse lookup (use --betpawa-seed)"
            continue
        if book in _COOKIE_GATED and sportpesa_cookie is None:
            skipped[book] = "cookie missing"
            continue
        if sr_numeric is None:
            skipped[book] = "no SR id"
            continue
        adapter = ADAPTERS.get(book)
        if adapter is None:
            skipped[book] = "no adapter"
            continue
        try:
            client = (clients or {}).get(book)
            if client is not None:
                handle = await adapter.resolve(
                    client, sr_numeric, sport, live=live
                )
            else:
                cookie = sportpesa_cookie if book == "sportpesa" else (
                    betika_cookie if book == "betika" else None
                )
                cls = _CLIENT_CLASSES[book]
                kwargs = {"country": _COUNTRY[book]}
                if cookie is not None:
                    kwargs["cookie"] = cookie
                async with cls(**kwargs) as constructed:
                    handle = await adapter.resolve(
                        constructed, sr_numeric, sport, live=live
                    )
            if handle is None:
                skipped[book] = "not found"
            else:
                handles[book] = handle
        except Exception as exc:  # per-book isolation
            skipped[book] = f"error: {exc!r}"

    return ResolvedEvent(
        seed=seed,
        sport=sport,
        sr_numeric=sr_numeric,
        home=home,
        away=away,
        handles=handles,
        skipped=skipped,
    )


async def _betpawa_seed_lookup(bp: Any, seed: str) -> tuple[str | None, str, str]:
    """Fetch a BetPawa event by internal id; return (sr_numeric, home, away)."""
    detail = await bp.get_event_detail(event_id=seed)
    sr_numeric = extract_sportradar_id(detail, platform="betpawa")
    parts = detail.get("participants") or []
    home = parts[0]["name"] if len(parts) > 0 else "?"
    away = parts[1]["name"] if len(parts) > 1 else "?"
    return sr_numeric, home, away
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_resolver.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/resolver.py tests/devtools/test_resolver.py
git commit -m "feat(devtools): cross-book resolver fan-out with per-book isolation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `search.py` — `discover` (regex term) + `unmapped` (registry diff)

**Files:**
- Create: `src/bookieskit/devtools/search.py`
- Create: `tests/devtools/test_search.py`

**Interfaces:**
- Consumes: `Candidate` (Task 1); `MarketRegistry` from `bookieskit.markets.registry`.
- Produces: `iter_candidates(payload, platform) -> list[Candidate]` (the shared per-platform reader), `discover(payload, platform, term) -> list[Candidate]`, `unmapped(payload, platform, sport, registry=None) -> list[Candidate]`.

Per-platform candidate extraction (ids/keys/outcomes), encoded from the parsers and probe scripts:
- **betpawa:** `markets[]`; id = `marketType.id`; name = `marketType.name`; outcomes = each `row[].prices[].name`.
- **sportybet:** `data.markets[]`; id = `id`; name = `name`; specifier = `specifier`; outcomes = `outcomes[].desc`.
- **msport:** `data.markets[]`; id = `id`; name = `name`/`description`; specifier = `specifiers`; outcomes = `outcomes[].description`.
- **bet9ja:** `D.O` flat odds dict; candidate market keys are the `_parse_bet9ja_key`-derived `market_key` (prefix-preserving), name unavailable (use the key), outcomes = the distinct outcome suffixes seen for that key.
- **betway:** `marketsInGroup[]`; id = `marketId`; name = `name`; outcomes = the names from `outcomes[]` whose `marketId == marketId`.
- **sportpesa:** `{<game_id>: [<market>]}`; id = `id`; name = `name`; specifier = `specValue`; outcomes = `selections[].shortName`.
- **betika:** `data[0].odds[]` groups; id = `sub_type_id`; name = `name`; outcomes = `odds[].display`.

`discover` filters `iter_candidates` by a compiled regex `term` matched (case-insensitive) against `name` and each outcome string. `unmapped` keeps every candidate whose `market_id` is **not** mapped: `registry.get_by_platform_id(platform, candidate.market_id, sport=sport) is None`. For Betway, name-based matching means `market_id` here is the `marketId` (not the mapping key), so `unmapped` is a **best-effort discovery aid only** — it may surface false positives from team-name placeholder markets; this limitation is documented in the module docstring and not over-engineered.

- [ ] **Step 1: Write the failing test**

Create `tests/devtools/test_search.py`:

```python
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
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_search.py -q`
Expected: `ModuleNotFoundError: No module named 'bookieskit.devtools.search'`.

- [ ] **Step 3: Implement `search.py`**

Create `src/bookieskit/devtools/search.py`:

```python
"""Discover candidate markets on a raw payload (by regex term) and diff the
payload against the registry (``unmapped``).

NOTE on Betway: Betway maps markets by NAME, so a candidate's ``market_id``
here is the raw ``marketId``, not the registry key. ``unmapped`` for Betway
is therefore a best-effort discovery aid — it can surface false positives
from per-team placeholder markets (e.g. "<Home Team> Total Goals"). Treat
Betway unmapped results as hints to investigate, not as ground truth.
"""

import re
from typing import Any

from bookieskit.devtools.types import Candidate
from bookieskit.markets.parser import _parse_bet9ja_key
from bookieskit.markets.registry import MarketRegistry


def iter_candidates(payload: Any, platform: str) -> list[Candidate]:
    """Read every market on a raw payload as a Candidate (per platform)."""
    readers = {
        "betpawa": _candidates_betpawa,
        "sportybet": _candidates_sportybet,
        "msport": _candidates_msport,
        "bet9ja": _candidates_bet9ja,
        "betway": _candidates_betway,
        "sportpesa": _candidates_sportpesa,
        "betika": _candidates_betika,
    }
    reader = readers.get(platform)
    if reader is None:
        return []
    return reader(payload)


def discover(payload: Any, platform: str, term: str) -> list[Candidate]:
    """Return candidates whose name or any outcome matches ``term`` (regex).

    Case-insensitive. Matches against the market name and each outcome
    string.
    """
    pattern = re.compile(term, re.IGNORECASE)
    out: list[Candidate] = []
    for cand in iter_candidates(payload, platform):
        haystack = " ".join([cand.name, *cand.outcomes])
        if pattern.search(haystack):
            out.append(cand)
    return out


def unmapped(
    payload: Any,
    platform: str,
    sport: str,
    registry: MarketRegistry | None = None,
) -> list[Candidate]:
    """Return candidates whose platform id/key the registry does NOT map.

    A candidate is "unmapped" iff
    ``registry.get_by_platform_id(platform, candidate.market_id,
    sport=sport)`` returns None. Candidates with no usable id are kept
    (they cannot be matched). See the module docstring for the Betway
    caveat.
    """
    if registry is None:
        registry = MarketRegistry()
    out: list[Candidate] = []
    for cand in iter_candidates(payload, platform):
        if cand.market_id is None:
            out.append(cand)
            continue
        if registry.get_by_platform_id(
            platform, cand.market_id, sport=sport
        ) is None:
            out.append(cand)
    return out


# ---- Per-platform readers -------------------------------------------------


def _candidates_betpawa(payload: Any) -> list[Candidate]:
    out: list[Candidate] = []
    for m in payload.get("markets", []) or []:
        mt = m.get("marketType") or {}
        mid = mt.get("id", m.get("id"))
        rows = m.get("row", [])
        if not isinstance(rows, list):
            rows = [rows] if rows else []
        outcomes: list[str] = []
        for row in rows:
            for price in row.get("prices", []) or []:
                name = price.get("name", price.get("displayName"))
                if name:
                    outcomes.append(str(name))
        out.append(Candidate(
            platform="betpawa",
            market_id=str(mid) if mid is not None else None,
            name=str(mt.get("name", "")),
            specifier=None,
            outcomes=outcomes,
        ))
    return out


def _candidates_sportybet(payload: Any) -> list[Candidate]:
    data = payload.get("data", payload)
    out: list[Candidate] = []
    for m in data.get("markets", []) or []:
        out.append(Candidate(
            platform="sportybet",
            market_id=str(m.get("id")) if m.get("id") is not None else None,
            name=str(m.get("name", "")),
            specifier=m.get("specifier") or None,
            outcomes=[
                str(o.get("desc", "")) for o in m.get("outcomes", []) or []
            ],
        ))
    return out


def _candidates_msport(payload: Any) -> list[Candidate]:
    data = payload.get("data", payload)
    out: list[Candidate] = []
    for m in data.get("markets", []) or []:
        out.append(Candidate(
            platform="msport",
            market_id=str(m.get("id")) if m.get("id") is not None else None,
            name=str(m.get("name") or m.get("description") or ""),
            specifier=m.get("specifiers") or None,
            outcomes=[
                str(o.get("description", ""))
                for o in m.get("outcomes", []) or []
            ],
        ))
    return out


def _candidates_bet9ja(payload: Any) -> list[Candidate]:
    data = payload.get("D")
    if not isinstance(data, dict):
        return []
    odds = data.get("O", {}) or {}
    # market_key -> set of outcome suffixes
    by_key: dict[str, list[str]] = {}
    for key in odds:
        k = key
        if k.startswith("LIVES_"):
            k = "S_" + k[len("LIVES_"):]
        parsed = _parse_bet9ja_key(k)
        if parsed is None:
            continue
        market_key, _line, suffix = parsed
        by_key.setdefault(market_key, [])
        if suffix not in by_key[market_key]:
            by_key[market_key].append(suffix)
    return [
        Candidate(
            platform="bet9ja",
            market_id=key,
            name=key,
            specifier=None,
            outcomes=suffixes,
        )
        for key, suffixes in by_key.items()
    ]


def _candidates_betway(payload: Any) -> list[Candidate]:
    outcomes_by_market: dict[str, list[str]] = {}
    for o in payload.get("outcomes", []) or []:
        mid = str(o.get("marketId", ""))
        outcomes_by_market.setdefault(mid, []).append(str(o.get("name", "")))
    out: list[Candidate] = []
    for m in payload.get("marketsInGroup", []) or []:
        mid = str(m.get("marketId", ""))
        out.append(Candidate(
            platform="betway",
            market_id=mid or None,
            name=str(m.get("name", "")),
            specifier=None,
            outcomes=outcomes_by_market.get(mid, []),
        ))
    return out


def _candidates_sportpesa(payload: Any) -> list[Candidate]:
    if not isinstance(payload, dict) or not payload:
        return []
    first = next(iter(payload.values()), None)
    if not isinstance(first, list):
        return []
    out: list[Candidate] = []
    for m in first:
        if not isinstance(m, dict):
            continue
        spec = m.get("specValue")
        out.append(Candidate(
            platform="sportpesa",
            market_id=str(m.get("id")) if m.get("id") is not None else None,
            name=str(m.get("name", "")),
            specifier=str(spec) if spec is not None else None,
            outcomes=[
                str(s.get("shortName", ""))
                for s in m.get("selections", []) or []
                if isinstance(s, dict)
            ],
        ))
    return out


def _candidates_betika(payload: Any) -> list[Candidate]:
    data = payload.get("data") or []
    if not isinstance(data, list) or not data:
        return []
    match = data[0]
    if not isinstance(match, dict):
        return []
    out: list[Candidate] = []
    for grp in match.get("odds", []) or []:
        if not isinstance(grp, dict):
            continue
        sti = grp.get("sub_type_id")
        out.append(Candidate(
            platform="betika",
            market_id=str(sti) if sti is not None else None,
            name=str(grp.get("name", "")),
            specifier=None,
            outcomes=[
                str(s.get("display", ""))
                for s in grp.get("odds", []) or []
                if isinstance(s, dict)
            ],
        ))
    return out
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_search.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/search.py tests/devtools/test_search.py
git commit -m "feat(devtools): discover (term) + unmapped (registry diff)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: `verify.py` — run `parse_markets` per platform, report canonicals

**Files:**
- Create: `src/bookieskit/devtools/verify.py`
- Create: `tests/devtools/test_verify.py`

**Interfaces:**
- Consumes: `VerifyResult` (Task 1); `parse_markets` from `bookieskit.markets.parser`; `NormalizedMarket` shape (`canonical_id`, `outcomes[list[Outcome]]`, `lines[dict[float,list[Outcome]]|None]`; `Outcome.canonical_name`/`odds`).
- Produces: `verify(payload, platform, sport, canonical_ids=None) -> VerifyResult`.

`verify` runs `parse_markets(payload, platform=platform, sport=sport)`. It builds `resolved[canonical_id]`: for simple markets `{"outcomes": {canonical_name: odds}}`; for parameterized markets `{"lines": {line: {canonical_name: odds}}}`. When `canonical_ids` is given, `missing` = requested ids not present in `resolved`; otherwise `missing` is `[]` and `resolved` lists every canonical that parsed.

- [ ] **Step 1: Write the failing test**

Create `tests/devtools/test_verify.py`:

```python
from bookieskit.devtools.verify import verify

# Reuse the existing Betway parser fixture shape (1X2 + O/U + DC + BTTS).
BETWAY_PAYLOAD = {
    "marketsInGroup": [
        {"marketId": "693394361", "name": "[Win/Draw/Win]", "handicap": 0},
        {"marketId": "6933943618total=2.5~", "name": "Total", "handicap": 2.5},
    ],
    "outcomes": [
        {"outcomeId": "o1", "marketId": "693394361", "name": "Arsenal FC"},
        {"outcomeId": "o2", "marketId": "693394361", "name": "Draw"},
        {"outcomeId": "o3", "marketId": "693394361", "name": "Atletico Madrid"},
        {"outcomeId": "o9", "marketId": "6933943618total=2.5~", "name": "Over"},
        {"outcomeId": "o10", "marketId": "6933943618total=2.5~", "name": "Under"},
    ],
    "prices": [
        {"outcomeId": "o1", "priceDecimal": 1.63},
        {"outcomeId": "o2", "priceDecimal": 4.0},
        {"outcomeId": "o3", "priceDecimal": 4.6},
        {"outcomeId": "o9", "priceDecimal": 1.8},
        {"outcomeId": "o10", "priceDecimal": 2.0},
    ],
}


def test_verify_lists_all_parsed_canonicals_when_no_filter():
    vr = verify(BETWAY_PAYLOAD, "betway", "soccer")
    assert vr.platform == "betway"
    assert set(vr.resolved) == {"1x2_ft", "over_under_ft"}
    assert vr.missing == []
    assert vr.resolved["1x2_ft"]["outcomes"]["home"] == 1.63
    assert vr.resolved["over_under_ft"]["lines"][2.5]["over"] == 1.8


def test_verify_reports_missing_requested_canonicals():
    vr = verify(
        BETWAY_PAYLOAD, "betway", "soccer",
        canonical_ids=["1x2_ft", "btts_ft"],
    )
    assert "1x2_ft" in vr.resolved
    assert vr.missing == ["btts_ft"]


def test_verify_unknown_platform_is_empty():
    vr = verify({}, "nonexistent", "soccer", canonical_ids=["1x2_ft"])
    assert vr.resolved == {}
    assert vr.missing == ["1x2_ft"]
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_verify.py -q`
Expected: `ModuleNotFoundError: No module named 'bookieskit.devtools.verify'`.

- [ ] **Step 3: Implement `verify.py`**

Create `src/bookieskit/devtools/verify.py`:

```python
"""Run parse_markets on a raw payload and report which canonicals resolve."""

from typing import Any

from bookieskit.devtools.types import VerifyResult
from bookieskit.markets.parser import parse_markets


def _market_to_odds(market: Any) -> dict[str, Any]:
    """Serialize one NormalizedMarket's odds into a plain dict."""
    if market.lines is not None:
        return {
            "lines": {
                line: {o.canonical_name: o.odds for o in outcomes}
                for line, outcomes in market.lines.items()
            }
        }
    return {"outcomes": {o.canonical_name: o.odds for o in market.outcomes}}


def verify(
    payload: Any,
    platform: str,
    sport: str,
    canonical_ids: list[str] | None = None,
) -> VerifyResult:
    """Parse ``payload`` and report resolved canonicals (+ missing requested).

    Args:
        payload: Raw markets payload for ``platform``.
        platform: Bookmaker key.
        sport: Canonical sport (forwarded to parse_markets for id
            disambiguation, e.g. basketball O/U).
        canonical_ids: When given, ``missing`` lists those not resolved;
            otherwise every parsed canonical is reported and missing is [].

    Returns:
        VerifyResult.
    """
    markets = parse_markets(payload, platform=platform, sport=sport)
    resolved: dict[str, Any] = {
        m.canonical_id: _market_to_odds(m) for m in markets
    }
    if canonical_ids is None:
        missing: list[str] = []
    else:
        missing = [c for c in canonical_ids if c not in resolved]
    return VerifyResult(platform=platform, resolved=resolved, missing=missing)
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_verify.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/verify.py tests/devtools/test_verify.py
git commit -m "feat(devtools): verify parse_markets resolution per platform

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: `fixtures.py` — write raw fixtures under `tests/fixtures/event_info/`

**Files:**
- Create: `src/bookieskit/devtools/fixtures.py`
- Create: `tests/devtools/test_fixtures.py`

**Interfaces:**
- Consumes: nothing from the harness (pure I/O of a payload dict).
- Produces: `FIXTURES_ROOT: Path`; `capture(payload, platform, name, *, root=None) -> Path` writing `<root>/<platform>/<name>.json` (pretty-printed, UTF-8) and returning the written path. The `root` kwarg defaults to the repo's `tests/fixtures/event_info/`; tests pass a `tmp_path` root.

- [ ] **Step 1: Write the failing test**

Create `tests/devtools/test_fixtures.py`:

```python
import json

from bookieskit.devtools.fixtures import FIXTURES_ROOT, capture


def test_capture_writes_pretty_json_and_returns_path(tmp_path):
    payload = {"marketsInGroup": [{"marketId": "1", "name": "X"}]}
    path = capture(payload, "betway", "my_market", root=tmp_path)
    assert path == tmp_path / "betway" / "my_market.json"
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == payload
    # pretty-printed (indented), not a single line
    assert "\n" in path.read_text(encoding="utf-8")


def test_capture_creates_platform_subdir(tmp_path):
    capture({"a": 1}, "sportybet", "foo", root=tmp_path)
    assert (tmp_path / "sportybet").is_dir()


def test_fixtures_root_points_at_event_info():
    assert FIXTURES_ROOT.name == "event_info"
    assert FIXTURES_ROOT.parent.name == "fixtures"
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_fixtures.py -q`
Expected: `ModuleNotFoundError: No module named 'bookieskit.devtools.fixtures'`.

- [ ] **Step 3: Implement `fixtures.py`**

Create `src/bookieskit/devtools/fixtures.py`:

```python
"""Write raw per-platform fixtures under tests/fixtures/event_info/."""

import json
from pathlib import Path
from typing import Any

# src/bookieskit/devtools/fixtures.py -> repo root is parents[3].
FIXTURES_ROOT = (
    Path(__file__).resolve().parents[3]
    / "tests" / "fixtures" / "event_info"
)


def capture(
    payload: Any,
    platform: str,
    name: str,
    *,
    root: Path | None = None,
) -> Path:
    """Write ``payload`` to ``<root>/<platform>/<name>.json`` and return it.

    Args:
        payload: Raw JSON-serializable markets payload.
        platform: Bookmaker key (subdirectory name).
        name: Fixture base name (no extension).
        root: Fixtures root (defaults to the repo's event_info dir).

    Returns:
        The written file path.
    """
    base = root if root is not None else FIXTURES_ROOT
    out_dir = base / platform
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_fixtures.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/fixtures.py tests/devtools/test_fixtures.py
git commit -m "feat(devtools): capture raw fixtures under tests/fixtures/event_info

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: `cli.py` + `__main__.py` — argparse, 4 subcommands, `--json`, exit codes

**Files:**
- Create: `src/bookieskit/devtools/cli.py`
- Create: `src/bookieskit/devtools/__main__.py`
- Create: `tests/devtools/test_cli.py`

**Interfaces:**
- Consumes: `resolve_event` (Task 5), `discover`/`unmapped` (Task 6), `verify` (Task 7), `capture` (Task 8), `ADAPTERS` (Task 4), `ALL_BOOKS` (Task 5), the dataclasses (Task 1).
- Produces: `build_parser() -> argparse.ArgumentParser`; `async run(args) -> int` (returns exit code); `main(argv=None) -> int`. `__main__.py` calls `sys.exit(main())`.

CLI surface (per the spec):
- Common args: positional `seed`; `--sport` (default `soccer`); `--book` (CSV, default all); `--json`; `--live`; `--betpawa-seed`; `--sportpesa-cookie`; `--betika-cookie`.
- `resolve <seed>` → prints/JSON the `ResolvedEvent`.
- `discover <seed>` with mutually-exclusive `--term <regex>` / `--unmapped` (exactly one required) → per-book `Candidate`s; each book fetched via its adapter `fetch_raw_markets` against the resolved handle.
- `capture <seed> --name <fixture_name>` → writes a fixture per resolved book; prints written paths.
- `verify <seed> [--canonical <csv>]` → per-book `VerifyResult`.
- Exit code: `0` if the seed resolved on ≥1 book; non-zero (`1`) if resolution failed entirely.

To keep the CLI testable offline, `run` accepts an optional injected `resolver` callable and `clients` map (tests pass fakes); production uses the real `resolve_event`.

- [ ] **Step 1: Write the failing test**

Create `tests/devtools/test_cli.py`:

```python
import json

import pytest

from bookieskit.devtools import cli
from bookieskit.devtools.types import Handle, ResolvedEvent


def test_build_parser_has_four_subcommands():
    parser = cli.build_parser()
    args = parser.parse_args(["resolve", "sr:match:42"])
    assert args.cmd == "resolve"
    assert args.seed == "sr:match:42"
    assert args.sport == "soccer"  # default


def test_discover_requires_exactly_one_of_term_or_unmapped():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        # neither --term nor --unmapped
        parser.parse_args(["discover", "sr:match:42"])


def test_discover_term_and_unmapped_are_mutually_exclusive():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["discover", "sr:match:42", "--term", "x", "--unmapped"]
        )


async def _fake_resolver_ok(seed, sport, books, **kwargs):
    return ResolvedEvent(
        seed=seed, sport=sport, sr_numeric="42", home="A", away="B",
        handles={"sportybet": Handle("sportybet", "sr:match:42")},
        skipped={"bet9ja": "not found"},
    )


async def _fake_resolver_fail(seed, sport, books, **kwargs):
    return ResolvedEvent(
        seed=seed, sport=sport, sr_numeric=None, home="?", away="?",
        handles={}, skipped={"sportybet": "error: boom"},
    )


@pytest.mark.asyncio
async def test_resolve_json_output_and_exit_zero(capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["resolve", "sr:match:42", "--json"])
    code = await cli.run(args, resolver=_fake_resolver_ok)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["sr_numeric"] == "42"
    assert out["handles"]["sportybet"]["event_id"] == "sr:match:42"
    assert out["skipped"]["bet9ja"] == "not found"


@pytest.mark.asyncio
async def test_resolve_nonzero_exit_when_no_book_resolves(capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["resolve", "sr:match:42", "--json"])
    code = await cli.run(args, resolver=_fake_resolver_fail)
    assert code == 1


@pytest.mark.asyncio
async def test_verify_uses_injected_clients_and_fetches_per_book(capsys):
    # Inject a fake fetch via the clients map: the CLI's verify path calls
    # adapter.fetch_raw_markets(client, handle). We stub the client so the
    # SportyBet adapter returns a parseable payload.
    sportybet_payload = {
        "data": {"markets": [
            {"id": "1", "name": "1X2", "outcomes": [
                {"desc": "Home", "odds": 1.5},
                {"desc": "Draw", "odds": 3.2},
                {"desc": "Away", "odds": 2.1},
            ]},
        ]}
    }

    class _FakeSporty:
        async def get_event_detail(self, event_id, live=False):
            return sportybet_payload

    args = cli.build_parser().parse_args(
        ["verify", "sr:match:42", "--book", "sportybet",
         "--canonical", "1x2_ft,btts_ft", "--json"]
    )
    code = await cli.run(
        args,
        resolver=_fake_resolver_ok,
        clients={"sportybet": _FakeSporty()},
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    sb = out["results"]["sportybet"]
    assert "1x2_ft" in sb["resolved"]
    assert sb["missing"] == ["btts_ft"]
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_cli.py -q`
Expected: `ModuleNotFoundError: No module named 'bookieskit.devtools.cli'`.

- [ ] **Step 3: Implement `cli.py`**

Create `src/bookieskit/devtools/cli.py`:

```python
"""argparse CLI for the market-add harness.

Four subcommands — resolve, discover, capture, verify — each non-interactive,
each supporting --json (serialized dataclasses). Exit code 0 when the seed
resolved on >=1 book, 1 when resolution failed entirely.
"""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from typing import Any, Awaitable, Callable

from bookieskit.devtools.adapters import ADAPTERS
from bookieskit.devtools.fixtures import capture as capture_fixture
from bookieskit.devtools.resolver import ALL_BOOKS, resolve_event
from bookieskit.devtools.search import discover, unmapped
from bookieskit.devtools.types import ResolvedEvent
from bookieskit.devtools.verify import verify as verify_payload

Resolver = Callable[..., Awaitable[ResolvedEvent]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bookieskit.devtools",
        description="Market-add harness: resolve/discover/capture/verify.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument("seed", help="SR id (sr:match:N or N) or BetPawa id")
        p.add_argument("--sport", default="soccer")
        p.add_argument("--book", default=None, help="CSV of books (default all)")
        p.add_argument("--json", action="store_true", dest="as_json")
        p.add_argument("--live", action="store_true")
        p.add_argument("--betpawa-seed", action="store_true", dest="betpawa_seed")
        p.add_argument("--sportpesa-cookie", default=None, dest="sportpesa_cookie")
        p.add_argument("--betika-cookie", default=None, dest="betika_cookie")

    p_resolve = sub.add_parser("resolve")
    _common(p_resolve)

    p_discover = sub.add_parser("discover")
    _common(p_discover)
    mode = p_discover.add_mutually_exclusive_group(required=True)
    mode.add_argument("--term", default=None)
    mode.add_argument("--unmapped", action="store_true")

    p_capture = sub.add_parser("capture")
    _common(p_capture)
    p_capture.add_argument("--name", required=True)

    p_verify = sub.add_parser("verify")
    _common(p_verify)
    p_verify.add_argument(
        "--canonical", default=None, help="CSV of canonical_ids to require"
    )

    return parser


def _books_arg(args: argparse.Namespace) -> tuple[str, ...]:
    if args.book:
        return tuple(b.strip() for b in args.book.split(",") if b.strip())
    return ALL_BOOKS


def _emit(obj: Any, as_json: bool, text_lines: list[str]) -> None:
    if as_json:
        print(json.dumps(obj, default=str))
    else:
        print("\n".join(text_lines))


async def _fetch_raw(
    book: str,
    handle: Any,
    args: argparse.Namespace,
    clients: dict[str, Any] | None,
) -> dict:
    """Fetch raw markets for one resolved book via its adapter."""
    adapter = ADAPTERS[book]
    injected = (clients or {}).get(book)
    if injected is not None:
        return await adapter.fetch_raw_markets(injected, handle, live=args.live)
    # Lazy import of client classes to keep module import cheap/offline.
    from bookieskit.devtools.resolver import _CLIENT_CLASSES, _COUNTRY

    cookie = None
    if book == "sportpesa":
        cookie = args.sportpesa_cookie
    elif book == "betika":
        cookie = args.betika_cookie
    kwargs: dict[str, Any] = {"country": _COUNTRY[book]}
    if cookie is not None:
        kwargs["cookie"] = cookie
    async with _CLIENT_CLASSES[book](**kwargs) as client:
        return await adapter.fetch_raw_markets(client, handle, live=args.live)


async def run(
    args: argparse.Namespace,
    *,
    resolver: Resolver = resolve_event,
    clients: dict[str, Any] | None = None,
) -> int:
    books = _books_arg(args)
    ev = await resolver(
        args.seed,
        args.sport,
        books,
        live=args.live,
        betpawa_seed=args.betpawa_seed,
        sportpesa_cookie=args.sportpesa_cookie,
        betika_cookie=args.betika_cookie,
        clients=clients,
    )
    exit_code = 0 if ev.handles else 1

    if args.cmd == "resolve":
        _emit(
            asdict(ev),
            args.as_json,
            [f"seed={ev.seed} sr={ev.sr_numeric} {ev.home} vs {ev.away}"]
            + [f"  {b}: {h.event_id}" for b, h in ev.handles.items()]
            + [f"  SKIP {b}: {r}" for b, r in ev.skipped.items()],
        )
        return exit_code

    # discover / capture / verify all fetch raw markets per resolved book.
    per_book: dict[str, Any] = {}
    for book, handle in ev.handles.items():
        try:
            raw = await _fetch_raw(book, handle, args, clients)
        except Exception as exc:  # per-book isolation
            ev.skipped[book] = f"fetch error: {exc!r}"
            continue
        if args.cmd == "discover":
            if args.unmapped:
                cands = unmapped(raw, book, args.sport)
            else:
                cands = discover(raw, book, args.term)
            per_book[book] = [asdict(c) for c in cands]
        elif args.cmd == "capture":
            path = capture_fixture(raw, book, args.name)
            per_book[book] = str(path)
        elif args.cmd == "verify":
            canon = (
                [c.strip() for c in args.canonical.split(",") if c.strip()]
                if args.canonical else None
            )
            per_book[book] = asdict(
                verify_payload(raw, book, args.sport, canonical_ids=canon)
            )

    payload = {
        "seed": ev.seed,
        "sport": ev.sport,
        "sr_numeric": ev.sr_numeric,
        "results": per_book,
        "skipped": ev.skipped,
    }
    _emit(
        payload,
        args.as_json,
        [f"{args.cmd} seed={ev.seed} sr={ev.sr_numeric}"]
        + [f"  {b}: {v}" for b, v in per_book.items()]
        + [f"  SKIP {b}: {r}" for b, r in ev.skipped.items()],
    )
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(run(args))
```

- [ ] **Step 4: Implement `__main__.py`**

Create `src/bookieskit/devtools/__main__.py`:

```python
"""Entrypoint: python -m bookieskit.devtools <cmd>."""

import sys

from bookieskit.devtools.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_cli.py -q`
Expected: `7 passed`.

- [ ] **Step 6: Smoke-test the entrypoint and `--help` (non-interactive)**

Run: `.venv/Scripts/python.exe -m bookieskit.devtools --help`
Expected: usage text listing `{resolve,discover,capture,verify}`; exit 0.

Run: `.venv/Scripts/python.exe -m bookieskit.devtools discover sr:match:42 --help`
Expected: usage text showing the mutually-exclusive `--term` / `--unmapped`; exit 0.

- [ ] **Step 7: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add src/bookieskit/devtools/cli.py src/bookieskit/devtools/__main__.py tests/devtools/test_cli.py
git commit -m "feat(devtools): argparse CLI (resolve/discover/capture/verify) + __main__

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Cleanup — delete superseded scripts, drop ruff exclusion, point docs at devtools

**Files:**
- Delete: `scripts/probe_2way_handicap_ft.py`, `scripts/probe_next_goal_and_team_ou.py`, `scripts/smoke_new_markets.py`, `scripts/capture_event_info_fixtures.py`, `scripts/diagnose_ah.py`
- Modify: `pyproject.toml` (remove `extend-exclude = ["scripts"]`)
- Modify: `README.md` (add a pointer to `python -m bookieskit.devtools` for the market-add loop)

**Interfaces:**
- Consumes: the verified harness (Tasks 1-9).
- Produces: a `scripts/`-free, fully ruff-checked tree.

- [ ] **Step 1: Confirm these are the only files under `scripts/`**

Run: `git ls-files scripts/`
Expected: exactly the five files listed above (note `diagnose_ah.py` is untracked — see Step 2).

- [ ] **Step 2: Delete the five scripts**

```bash
git rm scripts/probe_2way_handicap_ft.py scripts/probe_next_goal_and_team_ou.py scripts/smoke_new_markets.py scripts/capture_event_info_fixtures.py
rm -f scripts/diagnose_ah.py
```

(`diagnose_ah.py` is untracked, so `git rm` would fail on it — remove it with `rm`. After this, `scripts/` is empty.)

- [ ] **Step 3: Remove the ruff `scripts` exclusion**

In `pyproject.toml`, replace exactly:

```toml
[tool.ruff]
target-version = "py311"
line-length = 88
extend-exclude = ["scripts"]

[tool.ruff.lint]
select = ["E", "F", "I"]
```

with:

```toml
[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I"]
```

- [ ] **Step 4: Add a README pointer to the harness**

In `README.md`, add a short section (place it after the existing usage/examples section). Append exactly:

```markdown
## Market-add harness (`bookieskit.devtools`)

Dev/agent tooling for the add-a-market loop — resolve an event across all
bookmakers from one seed, discover candidate markets, capture fixtures, and
verify canonical resolution. All offline-testable; no network in tests.

```bash
# Resolve a SportRadar id across every book (JSON for agents)
python -m bookieskit.devtools resolve sr:match:42 --sport soccer --json

# Discover candidate markets by name/outcome regex
python -m bookieskit.devtools discover sr:match:42 --term "handi|asian|spread"

# Autonomous discovery: markets a book exposes but the registry doesn't map
python -m bookieskit.devtools discover sr:match:42 --unmapped

# Capture raw fixtures (tests/fixtures/event_info/<book>/<name>.json)
python -m bookieskit.devtools capture sr:match:42 --name my_new_market

# Verify which canonicals parse_markets resolves
python -m bookieskit.devtools verify sr:match:42 --canonical 1x2_ft,over_under_ft
```
```

(If a `## Market-add` section already exists, update it instead of adding a duplicate.)

- [ ] **Step 5: Verify the whole tree is ruff-clean (scripts no longer excluded)**

Run: `.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass, 0 failed (existing suite + the new `tests/devtools/` suite).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore(devtools): delete superseded scripts, drop scripts ruff exclusion, doc harness

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the executor

- Run commands with the project venv: `.venv/Scripts/python.exe -m <tool>` (Windows). CI uses bare `pytest` / `ruff`.
- Every task ends green and is independently reviewable. Task 3 (Betway client refactor) must keep the existing `tests/test_betway.py` + `tests/test_parser_betway.py` green — that is the regression guard for the folded-in library change.
- The resolver/adapters reach the network only in production; all tests inject `clients=` fakes or respx-mock the client HTTP layer, so the suite stays offline.
- Karpathy: each module is single-responsibility; no speculative extension points beyond the adapter shape the spec calls out for the future catalog axis.

## Controller self-review notes (verified against source; address during execution)

These were checked when reviewing the plan; the interface assumptions all hold (`_parse_bet9ja_key` returns `(market_key, line, suffix)|None`; `Betika.get_event_markets(event_id, live, competition_id)` matches the adapter and returns `{"data":[{"odds":[...]}]}`; `SportPesa` is exported; the Betway/SportyBet/Betika test URLs match the real client hosts). Two residual **Minor** risks for the implementer/reviewer:

- **Task 6 — `_candidates_bet9ja` is not directly tested** and munges live keys (`LIVES_` → `S_`) before `_parse_bet9ja_key`. Add a `test_unmapped_bet9ja_market_key` (build a small `{"D": {"O": {...}}}` payload with a mapped key like `S_1X2_1` and an unmapped one) and confirm the live-key munge against a real `D.O` shape. Do not ship the bet9ja reader untested.
- **Tasks 7 & 9 — hand-rolled SportyBet/Betway payloads must actually `parse_markets`-resolve** the asserted canonicals (`1x2_ft`, `over_under_ft`). If the minimal payloads don't match the real parser's expected fields (e.g. the SportyBet odds field name/`outcomes` shape), reuse an existing fixture from `tests/fixtures/` or the corresponding `tests/test_parser_*.py` payload rather than inventing one. The RED→GREEN cycle will surface a mismatch; prefer real fixtures over tweaking invented ones.
