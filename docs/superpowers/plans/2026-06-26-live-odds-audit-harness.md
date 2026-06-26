# Live Odds Audit Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable `python -m bookieskit.devtools audit` command that probes every mapped football market across all 7 bookmakers on a set of fixtures and emits an odds-coverage report (markdown + JSON), classifying each market×book as MAPPED+PRICED / NOT OFFERED, plus a per-book MIS-MAP review surface (raw market groups the registry doesn't map).

**Architecture:** A new pure module `src/bookieskit/devtools/audit.py` layers over the already-tested primitives — `coverage_matrix()` (expected coverage), `verify()` (parsed odds), and `unmapped()` (raw-present-but-unmapped groups). The classification/report logic is 100% offline and TDD'd against captured fixtures; a thin async `run_audit()` runner reuses the canary's resolve/fetch/discover machinery for the in-region live probe. The CLI wires two modes: `audit --prematch <seeds…>` (given fixtures) and `audit --live` (auto-discover in-play events).

**Tech Stack:** Python 3.11+, argparse, asyncio, dataclasses, pytest. No new dependencies.

## Global Constraints

- `src/` stays 100% ruff-clean (`ruff check .`).
- Run tests with `.venv/Scripts/python.exe -m pytest`; CI uses bare `pytest`/`ruff` on 3.11/3.12/3.13.
- TDD; frequent conventional-commit commits.
- **In-region only** for the live probe (live books geo-block US/cloud — BetPawa 403). Offline classification/report logic must never require the network.
- The 7 books, in display order: `betpawa, sportybet, bet9ja, betway, msport, sportpesa, betika` (reuse `coverage.PLATFORMS`).
- **Betway caveat:** `unmapped()` over-reports for Betway (registry indexes Betway by NAME, candidates carry numeric ids — see `search.py` docstring). Betway's MIS-MAP surface (`unmapped_groups`) is therefore left empty with a recorded reason; Betway odds still appear in the matrix via `verify()`.
- A library/CLI-facing change → curated `## [Unreleased]` CHANGELOG entry + README/docs update (the docs-sync CI gate enforces this).

---

### Task 1: Audit dataclasses + per-book classification

**Files:**
- Create: `src/bookieskit/devtools/audit.py`
- Test: `tests/devtools/test_audit.py`

**Interfaces:**
- Consumes: `coverage.coverage_matrix()` → `dict[str, dict[str, bool]]`; `coverage.PLATFORMS`; `verify.verify(payload, platform, sport, canonical_ids=...)` → `VerifyResult(resolved: dict, missing: list)`; `search.unmapped(payload, platform, sport)` → `list[Candidate]`.
- Produces:
  - `@dataclass MarketAudit(canonical_id: str, status: str, odds: dict | None)` — `status ∈ {"mapped_priced","not_offered"}`.
  - `@dataclass UnmappedGroup(market_id: str | None, name: str, outcomes: list[str])`.
  - `@dataclass BookAudit(platform: str, status: str, reason: str, markets: list[MarketAudit], unmapped_groups: list[UnmappedGroup])` — `status ∈ {"ok","unreachable","skipped"}`.
  - `expected_canonicals(platform, matrix=None) -> list[str]` — coverage canonicals (sorted) the platform maps.
  - `classify_book(raw, platform, sport, *, matrix=None, registry=None) -> BookAudit` (status `"ok"`).

- [ ] **Step 1: Write the failing test**

```python
# tests/devtools/test_audit.py
from dataclasses import asdict

from bookieskit.devtools.audit import (
    BookAudit,
    MarketAudit,
    UnmappedGroup,
    classify_book,
    expected_canonicals,
)

# Betway 1X2 + O/U (parses) — reuse the verify fixture shape.
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


def test_expected_canonicals_betway_includes_core_and_is_sorted():
    exp = expected_canonicals("betway")
    assert "1x2_ft" in exp and "over_under_ft" in exp
    assert exp == sorted(exp)


def test_classify_book_marks_parsed_markets_priced_with_odds():
    ba = classify_book(BETWAY_PAYLOAD, "betway", "soccer")
    assert isinstance(ba, BookAudit)
    assert ba.platform == "betway" and ba.status == "ok"
    by_id = {m.canonical_id: m for m in ba.markets}
    assert by_id["1x2_ft"].status == "mapped_priced"
    assert by_id["1x2_ft"].odds["outcomes"]["home"] == 1.63
    assert by_id["over_under_ft"].odds["lines"][2.5]["over"] == 1.8


def test_classify_book_marks_unparsed_expected_market_not_offered():
    # btts_ft is mapped for betway in the registry but absent from this payload.
    ba = classify_book(BETWAY_PAYLOAD, "betway", "soccer")
    by_id = {m.canonical_id: m for m in ba.markets}
    assert by_id["btts_ft"].status == "not_offered"
    assert by_id["btts_ft"].odds is None


def test_classify_book_betway_unmapped_groups_empty_by_caveat():
    ba = classify_book(BETWAY_PAYLOAD, "betway", "soccer")
    assert ba.unmapped_groups == []


def test_classify_book_surfaces_unmapped_groups_for_non_betway():
    # sportybet payload carrying one registry-unknown market group.
    payload = {"data": {"markets": [
        {"id": "999999", "name": "Some Exotic Market",
         "outcomes": [{"desc": "Yes"}, {"desc": "No"}]},
    ]}}
    ba = classify_book(payload, "sportybet", "soccer")
    assert ba.status == "ok"
    assert any(
        g.name == "Some Exotic Market" for g in ba.unmapped_groups
    )
    assert all(isinstance(g, UnmappedGroup) for g in ba.unmapped_groups)


def test_bookaudit_round_trips_through_asdict():
    ba = classify_book(BETWAY_PAYLOAD, "betway", "soccer")
    d = asdict(ba)
    assert d["platform"] == "betway"
    assert isinstance(d["markets"], list)
    assert d["markets"][0]["canonical_id"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_audit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bookieskit.devtools.audit'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/bookieskit/devtools/audit.py
"""Live odds audit: probe every mapped market across all books on a set of
fixtures and classify each market×book as MAPPED+PRICED / NOT OFFERED, plus a
per-book MIS-MAP review surface (raw market groups the registry does not map).

All classification/report logic here is pure and offline-testable. The only
networked path is ``run_audit`` (the in-region live probe), which reuses the
canary's resolve/fetch/discover machinery.

Betway caveat: ``search.unmapped`` over-reports for Betway (registry indexes
Betway by NAME but candidates carry numeric ids — see search.py). Betway's
``unmapped_groups`` is therefore always empty; Betway odds still appear via
``verify``.
"""

from dataclasses import dataclass, field

from bookieskit.devtools.coverage import PLATFORMS, coverage_matrix
from bookieskit.devtools.search import unmapped
from bookieskit.devtools.verify import verify
from bookieskit.markets.registry import MarketRegistry


@dataclass
class MarketAudit:
    """One canonical market's verdict for one book on one fixture."""

    canonical_id: str
    status: str  # "mapped_priced" | "not_offered"
    odds: dict | None  # verify() odds dict when priced, else None


@dataclass
class UnmappedGroup:
    """A raw market group present on the payload but not mapped by the registry."""

    market_id: str | None
    name: str
    outcomes: list[str]


@dataclass
class BookAudit:
    """Per-book audit: market verdicts + MIS-MAP review surface."""

    platform: str
    status: str  # "ok" | "unreachable" | "skipped"
    reason: str
    markets: list[MarketAudit] = field(default_factory=list)
    unmapped_groups: list[UnmappedGroup] = field(default_factory=list)


def expected_canonicals(
    platform: str, matrix: dict[str, dict[str, bool]] | None = None
) -> list[str]:
    """Coverage canonicals (sorted) that ``platform`` maps per the registry."""
    if matrix is None:
        matrix = coverage_matrix()
    return sorted(c for c, support in matrix.items() if support.get(platform))


def classify_book(
    raw,
    platform: str,
    sport: str,
    *,
    matrix: dict[str, dict[str, bool]] | None = None,
    registry: MarketRegistry | None = None,
) -> BookAudit:
    """Classify each expected canonical for one reachable book payload."""
    if registry is None:
        registry = MarketRegistry()
    expected = expected_canonicals(platform, matrix)
    vr = verify(raw, platform, sport, canonical_ids=expected)
    markets = [
        MarketAudit(
            canonical_id=c,
            status="mapped_priced" if c in vr.resolved else "not_offered",
            odds=vr.resolved.get(c),
        )
        for c in expected
    ]
    # MIS-MAP review surface: raw groups the registry doesn't map. Betway's
    # unmapped() is unreliable (see module docstring) -> always empty.
    groups: list[UnmappedGroup] = []
    if platform != "betway":
        groups = [
            UnmappedGroup(
                market_id=c.market_id, name=c.name, outcomes=list(c.outcomes)
            )
            for c in unmapped(raw, platform, sport, registry)
        ]
    return BookAudit(
        platform=platform,
        status="ok",
        reason="",
        markets=markets,
        unmapped_groups=groups,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_audit.py -v`
Expected: PASS (6 tests). If `test_expected_canonicals_betway_includes_core_and_is_sorted` reveals the registry maps fewer canonicals than assumed, keep only the `1x2_ft`/`over_under_ft` assertions (both are mapped for every book).

- [ ] **Step 5: Run ruff**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools/audit.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/audit.py tests/devtools/test_audit.py
git commit -m "feat(audit): per-book market classification (priced/not-offered + unmapped surface)"
```

---

### Task 2: Fixture-level audit + report aggregation

**Files:**
- Modify: `src/bookieskit/devtools/audit.py`
- Test: `tests/devtools/test_audit.py`

**Interfaces:**
- Consumes: `BookAudit`, `classify_book` (Task 1); `coverage.PLATFORMS`.
- Produces:
  - `@dataclass FixtureAudit(label: str, sr_numeric: str | None, books: list[BookAudit])`.
  - `@dataclass AuditReport(sport: str, mode: str, fixtures: list[FixtureAudit], summary: dict[str, int])`.
  - `audit_fixture(label, sr_numeric, raws: dict[str, dict], skipped: dict[str, str], sport, *, matrix=None, registry=None) -> FixtureAudit` — one `BookAudit` per book in `PLATFORMS`: classified when present in `raws`, else `status="skipped"` (or `"unreachable"` when the skip reason starts with `"fetch"`) with the reason.
  - `build_report(fixtures: list[FixtureAudit], *, sport: str, mode: str) -> AuditReport` — computes `summary` counts: `mapped_priced`, `not_offered`, `unmapped_groups`, `books_ok`, `books_skipped`, `books_unreachable`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/devtools/test_audit.py
from bookieskit.devtools.audit import (
    AuditReport,
    FixtureAudit,
    audit_fixture,
    build_report,
)


def test_audit_fixture_classifies_present_and_skips_absent_books():
    raws = {"betway": BETWAY_PAYLOAD}
    skipped = {"sportpesa": "no cookie", "msport": "fetch failed: Timeout()"}
    fa = audit_fixture("seed-1", "68995116", raws, skipped, "soccer")
    by_book = {b.platform: b for b in fa.books}
    assert by_book["betway"].status == "ok"
    assert by_book["sportpesa"].status == "skipped"
    assert by_book["sportpesa"].reason == "no cookie"
    assert by_book["msport"].status == "unreachable"
    # Books neither present nor skipped are reported as skipped (not probed).
    assert by_book["betpawa"].status == "skipped"


def test_build_report_counts_summary():
    fa = audit_fixture("seed-1", "68995116", {"betway": BETWAY_PAYLOAD}, {},
                       "soccer")
    rep = build_report([fa], sport="soccer", mode="prematch")
    assert isinstance(rep, AuditReport)
    assert rep.mode == "prematch"
    assert rep.summary["mapped_priced"] >= 2  # 1x2 + O/U on betway
    assert rep.summary["books_ok"] == 1
    assert rep.summary["books_skipped"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_audit.py -k "fixture or summary" -v`
Expected: FAIL — `ImportError` for `FixtureAudit`/`audit_fixture`/`build_report`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/bookieskit/devtools/audit.py

@dataclass
class FixtureAudit:
    """All per-book audits for one fixture."""

    label: str
    sr_numeric: str | None
    books: list[BookAudit] = field(default_factory=list)


@dataclass
class AuditReport:
    """The full audit run: fixtures + roll-up summary."""

    sport: str
    mode: str  # "prematch" | "live"
    fixtures: list[FixtureAudit] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


def audit_fixture(
    label: str,
    sr_numeric: str | None,
    raws: dict[str, dict],
    skipped: dict[str, str],
    sport: str,
    *,
    matrix: dict[str, dict[str, bool]] | None = None,
    registry: MarketRegistry | None = None,
) -> FixtureAudit:
    """Classify every book for one fixture (present -> classify, else skipped)."""
    if matrix is None:
        matrix = coverage_matrix()
    if registry is None:
        registry = MarketRegistry()
    books: list[BookAudit] = []
    for platform in PLATFORMS:
        if platform in raws:
            books.append(
                classify_book(
                    raws[platform], platform, sport,
                    matrix=matrix, registry=registry,
                )
            )
            continue
        reason = skipped.get(platform, "not probed")
        status = "unreachable" if reason.startswith("fetch") else "skipped"
        books.append(BookAudit(platform=platform, status=status, reason=reason))
    return FixtureAudit(label=label, sr_numeric=sr_numeric, books=books)


def build_report(
    fixtures: list[FixtureAudit], *, sport: str, mode: str
) -> AuditReport:
    """Aggregate fixtures into a report with summary counts."""
    summary = {
        "mapped_priced": 0, "not_offered": 0, "unmapped_groups": 0,
        "books_ok": 0, "books_skipped": 0, "books_unreachable": 0,
    }
    for fa in fixtures:
        for ba in fa.books:
            summary[f"books_{ba.status}"] = (
                summary.get(f"books_{ba.status}", 0) + 1
            )
            summary["unmapped_groups"] += len(ba.unmapped_groups)
            for m in ba.markets:
                summary[m.status] = summary.get(m.status, 0) + 1
    return AuditReport(
        sport=sport, mode=mode, fixtures=fixtures, summary=summary
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_audit.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/devtools/audit.py tests/devtools/test_audit.py
git commit -m "feat(audit): fixture-level audit + report aggregation with summary"
```

---

### Task 3: Markdown report renderer

**Files:**
- Modify: `src/bookieskit/devtools/audit.py`
- Test: `tests/devtools/test_audit.py`

**Interfaces:**
- Consumes: `AuditReport`, `FixtureAudit`, `BookAudit` (Tasks 1–2).
- Produces: `render_markdown(report: AuditReport) -> str` — a human-readable report: title with mode/sport, a summary line, then per fixture an odds matrix (canonical × book, cells = price summary or `—` for not-offered / `·` for skipped) followed by a "MIS-MAP review" section listing each book's `unmapped_groups`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/devtools/test_audit.py
from bookieskit.devtools.audit import render_markdown


def test_render_markdown_has_title_summary_and_fixture():
    fa = audit_fixture("Arsenal vs Atletico", "68995116",
                       {"betway": BETWAY_PAYLOAD}, {}, "soccer")
    rep = build_report([fa], sport="soccer", mode="prematch")
    md = render_markdown(rep)
    assert "# bookieskit — Live Odds Audit" in md
    assert "prematch" in md
    assert "Arsenal vs Atletico" in md
    assert "1x2_ft" in md
    assert "betway" in md
    # not-offered markets render as the em dash placeholder
    assert "—" in md


def test_render_markdown_lists_unmapped_groups_section():
    payload = {"data": {"markets": [
        {"id": "999999", "name": "Exotic Market",
         "outcomes": [{"desc": "Yes"}, {"desc": "No"}]},
    ]}}
    fa = audit_fixture("F1", None, {"sportybet": payload}, {}, "soccer")
    rep = build_report([fa], sport="soccer", mode="prematch")
    md = render_markdown(rep)
    assert "MIS-MAP review" in md
    assert "Exotic Market" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_audit.py -k render -v`
Expected: FAIL — `ImportError: cannot import name 'render_markdown'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/bookieskit/devtools/audit.py

def _odds_cell(market: MarketAudit) -> str:
    """One matrix cell: compact priced summary, or a not-offered placeholder."""
    if market.status != "mapped_priced" or market.odds is None:
        return "—"
    odds = market.odds
    if "outcomes" in odds:
        return "/".join(str(v) for v in odds["outcomes"].values())
    # lines: show the first line's prices.
    lines = odds.get("lines") or {}
    if not lines:
        return "✓"
    first = next(iter(lines.values()))
    return "/".join(str(v) for v in first.values())


def render_markdown(report: AuditReport) -> str:
    """Render an AuditReport as a human-readable markdown report."""
    s = report.summary
    lines = [
        f"# bookieskit — Live Odds Audit ({report.mode}, {report.sport})",
        "",
        f"_Summary: {s.get('mapped_priced', 0)} priced, "
        f"{s.get('not_offered', 0)} not-offered, "
        f"{s.get('unmapped_groups', 0)} unmapped groups across "
        f"{len(report.fixtures)} fixture(s)._",
        "",
    ]
    for fa in report.fixtures:
        lines.append(f"## {fa.label}"
                     + (f" (sr:{fa.sr_numeric})" if fa.sr_numeric else ""))
        lines.append("")
        ok_books = [b for b in fa.books if b.status == "ok"]
        canonicals = sorted({
            m.canonical_id for b in ok_books for m in b.markets
        })
        header = "| market | " + " | ".join(b.platform for b in ok_books) + " |"
        sep = "| --- | " + " | ".join("---" for _ in ok_books) + " |"
        lines += [header, sep]
        for canonical in canonicals:
            cells = []
            for b in ok_books:
                m = next((x for x in b.markets if x.canonical_id == canonical),
                         None)
                cells.append(_odds_cell(m) if m else "·")
            lines.append(f"| {canonical} | " + " | ".join(cells) + " |")
        # Skipped/unreachable books noted below the matrix.
        for b in fa.books:
            if b.status != "ok":
                lines.append(f"- _{b.platform}: {b.status} — {b.reason}_")
        # MIS-MAP review surface.
        lines += ["", "### MIS-MAP review (raw groups we don't map)", ""]
        any_unmapped = False
        for b in ok_books:
            if not b.unmapped_groups:
                continue
            any_unmapped = True
            lines.append(f"- **{b.platform}**:")
            for g in b.unmapped_groups:
                lines.append(
                    f"  - `{g.market_id}` {g.name} "
                    f"[{', '.join(g.outcomes)}]"
                )
        if not any_unmapped:
            lines.append("_None._")
        lines.append("")
    lines.append("_Generated by `python -m bookieskit.devtools audit`._")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_audit.py -k render -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/devtools/audit.py tests/devtools/test_audit.py
git commit -m "feat(audit): markdown report renderer (odds matrix + MIS-MAP review)"
```

---

### Task 4: Async live runner (`run_audit`)

**Files:**
- Modify: `src/bookieskit/devtools/audit.py`
- Test: `tests/devtools/test_audit.py`

**Interfaces:**
- Consumes: `resolver.resolve_event`, `resolver.ALL_BOOKS`; `canary._fetch_for_book` pattern (but honoring a `live` flag); `canary._discover_seed` (prematch UPCOMING) — for live mode reuse the same listing with `event_type="LIVE"`; `audit_fixture`, `build_report`.
- Produces:
  - `async def run_audit(mode, *, seeds=None, sport="soccer", books=ALL_BOOKS, max_live=4, betpawa_seed=False, sportpesa_cookie=None, betika_cookie=None, clients=None, discover=None) -> AuditReport`
    - `mode="prematch"`: requires `seeds` (list); resolve+fetch each via the prematch path (`live=False`), then `audit_fixture` per seed.
    - `mode="live"`: ignores `seeds`; calls `discover` (defaults to a betpawa LIVE lister) to get up to `max_live` betpawa event ids, then resolves with `betpawa_seed=True` and fetches via the live path (`live=True`).
  - Must isolate per-book fetch errors into the fixture's skipped map (never crash the run).

- [ ] **Step 1: Write the failing test (injected clients, fully offline)**

```python
# append to tests/devtools/test_audit.py
import asyncio


class _FakeBetway:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def test_run_audit_prematch_builds_report_from_injected_clients(monkeypatch):
    from bookieskit.devtools import audit as audit_mod

    async def fake_resolve(seed, sport, books, **kw):
        from bookieskit.devtools.types import Handle, ResolvedEvent
        return ResolvedEvent(
            seed=seed, sport=sport, sr_numeric="68995116",
            home="Arsenal", away="Atletico",
            handles={"betway": Handle(platform="betway", event_id="e1")},
            skipped={"sportpesa": "no cookie"},
        )

    async def fake_fetch(book, handle, clients, *, live):
        assert live is False
        return BETWAY_PAYLOAD

    monkeypatch.setattr(audit_mod, "resolve_event", fake_resolve)
    monkeypatch.setattr(audit_mod, "_fetch_book", fake_fetch)

    rep = asyncio.run(audit_mod.run_audit("prematch", seeds=["123"]))
    assert rep.mode == "prematch"
    assert len(rep.fixtures) == 1
    by_book = {b.platform: b for b in rep.fixtures[0].books}
    assert by_book["betway"].status == "ok"
    assert by_book["sportpesa"].status == "skipped"


def test_run_audit_prematch_requires_seeds():
    import pytest
    with pytest.raises(ValueError):
        asyncio.run(__import__(
            "bookieskit.devtools.audit", fromlist=["run_audit"]
        ).run_audit("prematch", seeds=None))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_audit.py -k run_audit -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'run_audit'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add imports at top of audit.py
from typing import Any, Awaitable, Callable

from bookieskit.devtools.adapters import ADAPTERS
from bookieskit.devtools.resolver import ALL_BOOKS, resolve_event
from bookieskit.devtools.types import Handle

# add to audit.py

async def _fetch_book(
    book: str, handle: Handle, clients: dict[str, Any] | None, *, live: bool
) -> dict:
    """Fetch raw markets for one book via its adapter (injected or built)."""
    adapter = ADAPTERS[book]
    injected = (clients or {}).get(book)
    if injected is not None:
        return await adapter.fetch_raw_markets(injected, handle, live=live)
    from bookieskit.devtools.resolver import _CLIENT_CLASSES, _COUNTRY

    async with _CLIENT_CLASSES[book](country=_COUNTRY[book]) as client:
        return await adapter.fetch_raw_markets(client, handle, live=live)


async def _audit_one_seed(
    seed: str, sport: str, books, *, live: bool, betpawa_seed: bool,
    sportpesa_cookie, betika_cookie, clients, matrix, registry,
) -> FixtureAudit:
    """Resolve + fetch one seed across books, then classify the fixture."""
    ev = await resolve_event(
        seed, sport, books, live=live, betpawa_seed=betpawa_seed,
        sportpesa_cookie=sportpesa_cookie, betika_cookie=betika_cookie,
        clients=clients,
    )
    raws: dict[str, dict] = {}
    skipped = dict(ev.skipped)
    for book, handle in ev.handles.items():
        try:
            raws[book] = await _fetch_book(book, handle, clients, live=live)
        except Exception as exc:  # per-book isolation
            skipped[book] = f"fetch error: {exc!r}"
    label = f"{ev.home} vs {ev.away}".strip() or seed
    return audit_fixture(
        label, ev.sr_numeric, raws, skipped, sport,
        matrix=matrix, registry=registry,
    )


async def run_audit(
    mode: str,
    *,
    seeds: list[str] | None = None,
    sport: str = "soccer",
    books: tuple[str, ...] = ALL_BOOKS,
    max_live: int = 4,
    betpawa_seed: bool = False,
    sportpesa_cookie: str | None = None,
    betika_cookie: str | None = None,
    clients: dict[str, Any] | None = None,
    discover: Callable[..., Awaitable[list[str]]] | None = None,
) -> AuditReport:
    """Probe all books across fixtures and build an AuditReport.

    mode="prematch": requires ``seeds``; prematch path (live=False).
    mode="live": auto-discovers up to ``max_live`` in-play betpawa events
    (via ``discover``) and probes the live path (live=True).
    """
    matrix = coverage_matrix()
    registry = MarketRegistry()
    live = mode == "live"

    if mode == "prematch":
        if not seeds:
            raise ValueError("prematch mode requires at least one seed")
        seed_list = list(seeds)
        bp_seed = betpawa_seed
    elif mode == "live":
        if discover is None:
            discover = _discover_live
        seed_list = await discover(sport, max_live, clients)
        bp_seed = True  # live discovery yields betpawa event ids
    else:
        raise ValueError(f"unknown audit mode: {mode!r}")

    fixtures: list[FixtureAudit] = []
    for seed in seed_list:
        fixtures.append(await _audit_one_seed(
            seed, sport, books, live=live, betpawa_seed=bp_seed,
            sportpesa_cookie=sportpesa_cookie, betika_cookie=betika_cookie,
            clients=clients, matrix=matrix, registry=registry,
        ))
    return build_report(fixtures, sport=sport, mode=mode)


async def _discover_live(
    sport: str, max_live: int, clients: dict[str, Any] | None
) -> list[str]:
    """Return up to ``max_live`` in-play betpawa event ids (in-region only).

    Lists LIVE betpawa events for the sport, ranked by marketsCount desc, and
    returns their ids. Returns [] when the listing is unreachable (e.g. a
    geo-blocked 403 from out of region) — a clean "no live events" signal.
    """
    from bookieskit.devtools.sports import sport_id as _sport_id

    bp_sport_id = _sport_id("betpawa", sport) or "2"
    bp = (clients or {}).get("betpawa")
    if bp is None:
        from bookieskit import BetPawa

        async with BetPawa(country="ng") as bp_client:
            return await _list_live_seeds(bp_client, bp_sport_id, max_live)
    return await _list_live_seeds(bp, bp_sport_id, max_live)


async def _list_live_seeds(bp_client, sport_id: str, max_live: int) -> list[str]:
    """Pull LIVE betpawa events and return up to ``max_live`` ids."""
    from bookieskit.devtools.canary import _list_betpawa_events

    try:
        payload = await bp_client.get_events(
            sport_id=sport_id, event_type="LIVE"
        )
    except Exception:
        return []
    events = _list_betpawa_events(payload)
    events.sort(key=lambda e: e.get("marketsCount") or 0, reverse=True)
    out: list[str] = []
    for event in events[:max_live]:
        eid = event.get("id")
        if eid is not None:
            out.append(str(eid))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_audit.py -k run_audit -v`
Expected: PASS. Verify `resolve_event` is imported at module scope (so `monkeypatch.setattr(audit_mod, "resolve_event", ...)` patches the name the runner calls).

- [ ] **Step 5: Run full audit test module + ruff**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_audit.py -v && .venv/Scripts/python.exe -m ruff check src/bookieskit/devtools/audit.py`
Expected: all PASS, no ruff errors.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/audit.py tests/devtools/test_audit.py
git commit -m "feat(audit): async run_audit (prematch seeds + live auto-discovery)"
```

---

### Task 5: CLI wiring (`audit` subcommand) + file output

**Files:**
- Modify: `src/bookieskit/devtools/cli.py`
- Test: `tests/devtools/test_cli.py`

**Interfaces:**
- Consumes: `audit.run_audit`, `audit.render_markdown`, `audit.AuditReport`.
- Produces: an `audit` subcommand:
  - `--prematch` (flag) with positional `seeds` (nargs="*"), mutually exclusive with `--live`.
  - `--live` (flag).
  - `--sport` (default soccer), `--max-live` (int, default 4), `--betpawa-seed`, `--sportpesa-cookie`, `--betika-cookie`, `--json`, `--out` (optional path; default `docs/audits/<date>-wc-<mode>-audit.md`).
  - Runs `run_audit`, writes the markdown report + a `.json` sidecar to `--out`, prints the path (or the JSON when `--json`). Returns 0 when ≥1 fixture audited, else 1.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/devtools/test_cli.py
import json as _json

from bookieskit.devtools import cli as cli_mod


def test_audit_prematch_writes_report(tmp_path, monkeypatch):
    from bookieskit.devtools.audit import (
        AuditReport, BookAudit, FixtureAudit, MarketAudit,
    )

    async def fake_run_audit(mode, **kw):
        fa = FixtureAudit("Arsenal vs Atletico", "68995116", [
            BookAudit("betway", "ok", "", [
                MarketAudit("1x2_ft", "mapped_priced",
                            {"outcomes": {"home": 1.63}}),
            ], []),
        ])
        return AuditReport("soccer", mode, [fa],
                           {"mapped_priced": 1, "not_offered": 0})

    monkeypatch.setattr(cli_mod, "run_audit", fake_run_audit)
    out = tmp_path / "audit.md"
    rc = cli_mod.main(["audit", "--prematch", "123", "--out", str(out)])
    assert rc == 0
    assert out.exists()
    assert "Arsenal vs Atletico" in out.read_text(encoding="utf-8")
    sidecar = out.with_suffix(".json")
    assert sidecar.exists()
    data = _json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["mode"] == "prematch"


def test_audit_requires_a_mode(capsys):
    import pytest
    with pytest.raises(SystemExit):
        cli_mod.main(["audit", "123"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_cli.py -k audit -v`
Expected: FAIL — argparse rejects `audit` (unknown subcommand) / `run_audit` not importable in cli.

- [ ] **Step 3: Write minimal implementation**

In `cli.py`, add the import and subparser, and an `audit` branch in `run()`:

```python
# at top of cli.py with the other devtools imports
from bookieskit.devtools.audit import AuditReport, render_markdown, run_audit
```

```python
# in build_parser(), after p_check:
    p_audit = sub.add_parser("audit")
    amode = p_audit.add_mutually_exclusive_group(required=True)
    amode.add_argument("--prematch", action="store_true")
    amode.add_argument("--live", action="store_true")
    p_audit.add_argument("seeds", nargs="*", help="prematch seeds (SR/BetPawa ids)")
    p_audit.add_argument("--sport", default="soccer")
    p_audit.add_argument("--max-live", type=int, default=4, dest="max_live")
    p_audit.add_argument("--betpawa-seed", action="store_true",
                         dest="betpawa_seed")
    p_audit.add_argument("--sportpesa-cookie", default=None,
                         dest="sportpesa_cookie")
    p_audit.add_argument("--betika-cookie", default=None, dest="betika_cookie")
    p_audit.add_argument("--out", default=None)
    p_audit.add_argument("--json", action="store_true", dest="as_json")
```

```python
# in run(), before the resolve/discover/capture/verify block (early-return):
    if args.cmd == "audit":
        from dataclasses import asdict

        mode = "live" if args.live else "prematch"
        report = await run_audit(
            mode,
            seeds=args.seeds or None,
            sport=args.sport,
            max_live=args.max_live,
            betpawa_seed=args.betpawa_seed,
            sportpesa_cookie=args.sportpesa_cookie,
            betika_cookie=args.betika_cookie,
        )
        out_path = _audit_out_path(args.out, mode)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_markdown(report), encoding="utf-8")
        out_path.with_suffix(".json").write_text(
            json.dumps(asdict(report), default=str, indent=2),
            encoding="utf-8",
        )
        if args.as_json:
            print(json.dumps(asdict(report), default=str))
        else:
            print(f"audit ({mode}): {len(report.fixtures)} fixture(s) -> "
                  f"{out_path}")
        return 0 if report.fixtures else 1
```

```python
# module-level helper near _default_notes:
def _audit_out_path(out: str | None, mode: str) -> Path:
    """Resolve the audit report path (default: dated docs/audits/ file)."""
    if out is not None:
        return Path(out)
    from datetime import date

    stamp = date.today().isoformat()
    return Path("docs/audits") / f"{stamp}-wc-{mode}-audit.md"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_cli.py -k audit -v`
Expected: PASS.

- [ ] **Step 5: Run full suite + ruff**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check .`
Expected: all PASS, no ruff errors.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/cli.py tests/devtools/test_cli.py
git commit -m "feat(audit): wire 'audit' CLI subcommand with dated report output"
```

---

### Task 6: Docs, CHANGELOG, graph refresh

**Files:**
- Modify: `CHANGELOG.md` (`## [Unreleased]`)
- Modify: `README.md` (devtools command list)
- Create: `docs/audits/README.md` (what the audit harness is + how to run in-region)
- Modify: `src/graphify-out/graph.json`, `src/graphify-out/GRAPH_REPORT.md` (new module added structure)

**Interfaces:** None (docs only).

- [ ] **Step 1: Add CHANGELOG entry**

Under `## [Unreleased]` add:

```markdown
### Added
- `python -m bookieskit.devtools audit` — reusable live-odds audit harness:
  probes every mapped football market across all 7 bookmakers on a set of
  fixtures (`--prematch <seeds…>`) or auto-discovered in-play events
  (`--live`), emitting a markdown odds matrix + JSON sidecar under
  `docs/audits/`. Each market×book is classified MAPPED+PRICED / NOT OFFERED,
  with a per-book MIS-MAP review surface (raw groups the registry doesn't map).
  In-region only for the live probe; classification logic is offline-tested.
```

- [ ] **Step 2: Add README devtools entry**

Find the devtools command list in `README.md` and add an `audit` bullet mirroring the CHANGELOG summary (one or two lines, with the two example invocations).

- [ ] **Step 3: Write `docs/audits/README.md`**

```markdown
# Live Odds Audits

Reports produced by `python -m bookieskit.devtools audit` (see the harness in
`src/bookieskit/devtools/audit.py`).

- `audit --prematch <seeds…>` — probe the given upcoming fixtures (prematch path).
- `audit --live` — auto-discover in-play events and probe the live feed.

Each report is an odds matrix (canonical market × bookmaker) plus a MIS-MAP
review surface (raw market groups a book sent that the registry does not map —
the only signal worth filing an Issue over; genuinely-absent markets are
reported, never filed). **Run in-region** — live bookmakers geo-block US/cloud
IPs.
```

- [ ] **Step 4: Refresh the structural graph**

Run: `graphify update src` then stage `src/graphify-out/graph.json` and `src/graphify-out/GRAPH_REPORT.md`.

- [ ] **Step 5: Verify the docs-sync gate passes**

Run: `.venv/Scripts/python.exe -m bookieskit.devtools check-docs-sync --changed "src/bookieskit/devtools/audit.py,src/bookieskit/devtools/cli.py,README.md,CHANGELOG.md"`
Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md README.md docs/audits/README.md src/graphify-out/
git commit -m "docs(audit): CHANGELOG, README, audits guide, graph refresh"
```

---

## Self-Review notes

- **Spec coverage:** reusable harness ✓ (Task 4 `run_audit` + Task 5 CLI); two modes prematch/live ✓; auto-discover live ✓ (Task 4 `_discover_live`); 3-state classification ✓ (MAPPED+PRICED / NOT OFFERED in Task 1; MIS-MAP review surface via `unmapped_groups`); markdown + JSON output under `docs/audits/` ✓ (Task 5); in-region constraint honored (offline core, networked runner only) ✓; cookies for SportPesa/Betika ✓ (CLI flags, Task 5).
- **Assumption (for the PR):** MIS-MAP is surfaced as a per-book list of registry-unmapped raw groups for the cycle's human review rather than auto-classified per canonical — this honors "the cycle reviews MIS-MAP suspects and files one new Issue per genuine mismatch" and avoids fragile heuristics. NOT-OFFERED = a canonical the registry maps for the book but `verify()` didn't resolve on this fixture (the legit-missing case). Betway's `unmapped_groups` is intentionally empty (its `unmapped()` over-reports — documented caveat).
- **Type consistency:** `MarketAudit`/`BookAudit`/`FixtureAudit`/`AuditReport`, `classify_book`/`audit_fixture`/`build_report`/`render_markdown`/`run_audit`/`_fetch_book` names match across tasks.
