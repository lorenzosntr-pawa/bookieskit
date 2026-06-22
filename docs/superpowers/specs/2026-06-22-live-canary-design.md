# Live Canary (`bookieskit.devtools.canary`) — Design

**Date:** 2026-06-22
**Status:** Approved (pending written-spec review)
**Sub-project:** 3 of 5 in the project-workflow track. Umbrella: `2026-06-22-agent-company-north-star.md`. (1=CI ✅, 2=market-add harness ✅, 3=this, 4=release automation, 5=orchestration + Slack cockpit.)

## Problem

`bookieskit` parses live bookmaker APIs that change without notice. The fixture-backed test suite catches regressions in *our* code, but nothing detects when a bookmaker silently changes its payload shape or drops a market — the lib keeps "passing" while returning wrong/empty results in production. The canary is the **signal** in the agent loop (*Signal → Work → Gate → Ship*): a scheduled probe of real endpoints that turns API drift into an actionable alert.

## Goals

- On a schedule, fetch **real** bookmaker payloads and detect drift: a payload whose structure changed, or a core market that stopped resolving.
- Distinguish **drift** (reachable but broken → actionable) from **transient unreachability** (network blip → soft warning), so the alert doesn't cry wolf.
- Survive daily event churn with **zero manual upkeep** (dynamic seed discovery).
- Reuse the harness core (`resolve_event`, `ADAPTERS`, `verify`) — no duplicated fan-out.
- Be **agent-runnable**: `--json` report, meaningful exit code; the report schema is the contract the future orchestrator turns into GitHub Issues.
- All checker logic **offline-testable**; the only networked path is the scheduled workflow.

## Non-goals

- Auto-filing GitHub Issues / Slack alerts on drift — that is the orchestrator (sub-project 5). v1 emits a report + non-zero exit; the scheduled workflow failure is the notification.
- Basketball/tennis (v1 is soccer only; `run_canary` is parameterized over sport so they bolt on later).
- SportPesa (cookie-gated; no Akamai cookie in CI → always `skipped`).
- Checking deep/long-tail markets — v1 holds each book to a small **core** set only.
- Catalog/sport/competition drift (that is the scout, sub-project 5).

## Decisions

| Decision | Choice |
|---|---|
| What it asserts | Both **structure** (parser-critical keys present) **and** canonical **resolution** (core markets still parse via `verify`) |
| Seed selection | **Dynamic** each run: discover a current top BetPawa soccer event (most markets + SportRadar widget) |
| Drift action (v1) | Structured report (`--json` + human) + **non-zero exit on drift**; scheduled-workflow failure is the notification |
| Resolution baseline | **Curated core**: `{1x2_ft, over_under_ft, btts_ft, double_chance_ft}`, intersected per book with what the registry maps for (book, soccer) |
| Location / invocation | `src/bookieskit/devtools/canary.py` + `python -m bookieskit.devtools canary` |
| Cadence | **Daily**, scheduled by the in-region orchestrator (NOT a GitHub cron — see "Run environment"; bookmakers geo-block US runners) |
| Sport scope (v1) | **Soccer only** (`run_canary` parameterized over sport for later) |
| Flakiness | Per-book classify `ok`/`drift`/`unreachable`/`skipped`; **only `drift` fails the run**; fetch retried a couple times before `unreachable` |

## Architecture

New module `src/bookieskit/devtools/canary.py`, plus a `canary` subcommand on the existing CLI. Dataclasses live in `canary.py` (canary-specific).

### Dataclasses

```python
@dataclass
class BookCheck:
    platform: str
    status: str                  # "ok" | "drift" | "unreachable" | "skipped"
    reason: str                  # human explanation (empty when ok)
    expected_canonicals: list[str]   # the core subset this book should resolve
    resolved_canonicals: list[str]   # what actually resolved
    missing_canonicals: list[str]    # expected - resolved (drift driver)
    structure_ok: bool

@dataclass
class CanaryReport:
    sport: str
    seed: str | None             # the BetPawa event id used (None if discovery failed)
    sr_numeric: str | None
    checks: list[BookCheck]
    drifted: bool                # any check.status == "drift"
```

### Constants & contracts

- `CORE_CANONICALS = ("1x2_ft", "over_under_ft", "btts_ft", "double_chance_ft")`.
- `STRUCTURE_PREDICATES: dict[str, Callable[[dict], bool]]` — one predicate per book asserting the parser-critical shape:
  - `betpawa`: `isinstance(payload.get("markets"), list)`
  - `sportybet` / `msport`: `isinstance((payload.get("data") or {}).get("markets"), list)`
  - `betway`: all of `marketsInGroup` / `outcomes` / `prices` are lists
  - `bet9ja`: `isinstance((payload.get("D") or {}).get("O"), dict)`
  - `betika`: `payload.get("data")` is a non-empty list and `data[0].get("odds")` is a list
  - `sportpesa`: payload is a non-empty dict whose first value is a list

### Functions

```python
def expected_core(platform: str, sport: str, registry: MarketRegistry) -> list[str]:
    """CORE_CANONICALS intersected with what the registry maps for (platform, sport)."""

def check_book(payload: dict, platform: str, sport: str,
               registry: MarketRegistry | None = None) -> BookCheck:
    """Structure predicate + verify(core). Reachable-but-broken => status 'drift'."""

async def run_canary(sport: str = "soccer", *, seed: str | None = None,
                     max_candidates: int = 3,
                     clients: dict | None = None) -> CanaryReport:
    """Discover a seed (unless given), resolve across books, check each reachable
    book, classify, and assemble the report. clients= injects fakes for tests."""

async def _discover_seed(bp_client, sport, max_candidates) -> str | None:
    """List BetPawa upcoming events for the sport; return the id of the best
    candidate (most markets, has SportRadar widget). None if none qualify."""
```

### Run flow

1. `_discover_seed` (unless `--seed`) → BetPawa event id (the seed is always a BetPawa internal id).
2. `resolve_event(seed, sport, books=ALL_BOOKS, betpawa_seed=True, clients=clients)` → `sr_numeric` + per-book handles + skips. The resolver skips `betpawa` in its fan-out (it is the seed anchor) and `sportpesa` (no cookie).
3. Build the **check set** = the resolver's `handles` **plus** an explicit BetPawa handle `Handle("betpawa", event_id=seed)` (BetPawa is checked via its own adapter using the seed id — the same fetch+check path as every other book, no reliance on resolver internals).
4. For each book in the check set: fetch raw markets via `ADAPTERS[book].fetch_raw_markets` with up to 2 retries on transient error. On persistent fetch error → `BookCheck(status="unreachable")`. On success → `check_book(...)`.
5. Books in the resolver's `skipped` map (e.g. SportPesa "cookie missing", or a book whose SR id wasn't found) → `BookCheck(status="skipped", reason=<resolver reason>)`. A book whose `expected_core` is empty (registry maps none of the core for it) → `skipped` ("no core markets mapped").
5. Assemble `CanaryReport`; `drifted = any(c.status == "drift")`.

### CLI

`python -m bookieskit.devtools canary [--sport soccer] [--json] [--seed <id>] [--max-candidates 3]`
- Human mode: per-book status table + summary.
- `--json`: serialized `CanaryReport`.
- Exit code: `1` if `report.drifted` or seed discovery failed entirely; else `0` (unreachable-only runs exit 0 with warnings printed).

## Run environment (REVISED — geo-restriction finding, 2026-06-23)

**The canary runs from an in-region environment, NOT GitHub-hosted runners.**

A scheduled `.github/workflows/canary.yml` (daily cron on `ubuntu-latest`) was implemented and tried — and the first live run surfaced a hard constraint: the African bookmakers geo-filter their APIs. From GitHub Actions' US-based runner IPs, BetPawa returns `403 Access Restricted` (an HTML WAF page), so canary seed-discovery can't even begin from that network. The library works from an in-region network (where it is developed and run) but not from generic US cloud.

Decision: the GitHub canary workflow is **removed**. The canary's live execution belongs to the **in-region orchestrator** (sub-project 5), which runs `python -m bookieskit.devtools canary --json` on a schedule from a network that can reach the bookmakers. This generalizes: **every live-bookmaker operation in the agent company — canary, scout, harness live probes, the orchestrator's networked dispatches — must run in-region.** GitHub Actions remains the *gate* (CI: offline tests + lint) and the *publisher* (release build + GitHub Release), neither of which touches bookmaker endpoints.

The canary CLI/logic is unchanged and fully functional locally; only its scheduling host moved. A self-hosted in-region Actions runner remains an option for re-adding a GitHub-native schedule later.

Drift semantics are unchanged: a `drift` exit (non-zero) is the alert (surfaced by the orchestrator / its caller); `unreachable`-only runs exit 0.

## Error handling / flakiness

- **Per-book isolation**: one book's fetch/parse failure never aborts the others (same pattern as the resolver/CLI).
- **Transient vs drift**: fetch errors (network/timeout/5xx) are retried (2 attempts, short backoff); persistent failure → `unreachable` (soft, run still passes). Only a *successful* fetch whose structure or core resolution is broken → `drift` (run fails).
- **Seed discovery failure**: if no candidate event yields an SR id after `max_candidates`, the report has `seed=None` and the run exits non-zero with a clear "could not discover a seed event" reason (this is itself a signal — BetPawa listing may have drifted).

## Testing approach

Offline unit tests under `tests/devtools/test_canary.py` (respx + injected clients/fixtures):
- Each `STRUCTURE_PREDICATES` entry: a valid payload → True; a broken one (missing/renamed key) → False.
- `expected_core`: returns the right subset per book (e.g. a book mapping only 1x2_ft+O/U gets just those).
- `check_book`: ok (structure + all core resolve), drift via missing core (payload that parses fewer than expected), drift via broken structure.
- `run_canary` with injected fake clients: a mix of ok / drift / unreachable / skipped books → correct `CanaryReport` and `drifted` flag.
- `_discover_seed`: mocked BetPawa `get_events` → picks the best candidate; returns None when none qualify.
- CLI: `canary --json` serialization + exit code (drift → 1, all-ok → 0, unreachable-only → 0) via injected `run_canary`/clients.
- No live network in any test. The scheduled workflow is the only networked path and is not run in PR CI.

## Success criteria

- `python -m bookieskit.devtools canary --help` works; `--json` emits a `CanaryReport`; exit code is 1 on drift / seed-failure, 0 otherwise.
- New `tests/devtools/test_canary.py` passes; full suite + `ruff check .` green in CI.
- Seed discovery degrades gracefully: a fetch error (e.g. a geo-block 403) yields a clean `seed=None` report and exit 1 — never a traceback (regression-tested).
- Run **from an in-region environment** (where the bookmakers are reachable): the canary reports per-book `ok`/`skipped` against live endpoints. (No GitHub-hosted canary workflow — see "Run environment".)

## Reuse hooks for later sub-projects

- **Orchestrator (sub-project 5):** consumes `CanaryReport` (the `--json` output) and turns each `drift` `BookCheck` into a GitHub Issue / Slack `#canary-alerts` message — the report schema is the stable contract.
- **Scout (sub-project 5):** reuses `_discover_seed` + `ADAPTERS` to walk catalogs for the expansion stream; the canary's structural predicates are the seed of catalog-level shape checks.
