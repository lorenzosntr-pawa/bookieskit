# Market-Add Harness (`bookieskit.devtools`) — Design

**Date:** 2026-06-22
**Status:** Approved (pending written-spec review)
**Sub-project:** 2 of 5 in the project-workflow track. See umbrella: `2026-06-22-agent-company-north-star.md`. (1=CI ✅, 2=this, 3=live canary, 4=release automation, 5=orchestration + Slack cockpit.)

## Problem

Every recent feature commit follows the same loop: *investigate a bookmaker's live API → identify the per-bookmaker market id/key + outcome strings → add a `MarketMapping` → capture fixtures → write parser tests → confirm `parse_markets` resolves it.* That loop currently lives in throwaway scripts — `scripts/probe_2way_handicap_ft.py`, `probe_next_goal_and_team_ou.py`, `smoke_new_markets.py`, `capture_event_info_fixtures.py`, `diagnose_ah.py` — which share ~80% of their logic (the cross-bookmaker event fan-out) copy-pasted, and one of which is still untracked. There is no reusable, tested, agent-runnable tool for the loop.

This sub-project replaces that sprawl with one tool. Critically, its **resolver + per-bookmaker raw-fetcher core is the shared substrate the live canary (sub-project 3) and the expansion scout (north-star) will reuse** — so it is foundational, not just convenience.

## Goals

- One tool covering the whole loop: **resolve, discover, capture, verify**.
- Generic over **any search term and any sport** — no code change to investigate a new market/sport/bookmaker.
- **Autonomous market discovery:** a diff mode that surfaces markets a book exposes but the registry does *not* map yet — no search term needed (the seed of the scout).
- **Agent-runnable**: non-interactive, `--json` structured output, meaningful exit codes, no prompts.
- Per-bookmaker failures isolated; cookie-gated books degrade gracefully.
- All logic unit-tested **offline** (respx); CI-safe.
- Eliminate the script sprawl and the `scripts/` ruff-exclusion debt.

## Non-goals

- A live CI job (that is sub-project 3, canary — it reuses this core but is its own spec).
- Auto-writing `MarketMapping` entries or test files (the human/agent still authors the mapping after `discover`; the harness informs, it does not edit `builtin_mappings.py`).
- A GUI or Slack integration (sub-project 5).
- Shipping a public, stability-guaranteed API — `devtools` is dev/agent tooling.
- **Non-market discovery axes** — sports (`get_sports`), competitions/tournaments (`get_tournaments`/`get_countries`), matching-widget / id-provider drift (SportRadar / BetGenius), and client features/endpoints (live betting, bet-builder, cashout, new event types). These belong to the **scout** (multi-axis *catalog* diffing, north-star expansion stream), designed at sub-project 5 or as its own sub-project. v1 stays markets-scoped; the adapter core (below) is built so a catalog axis bolts on without rework.

## Decisions

| Decision | Choice |
|---|---|
| Capabilities (v1) | resolve + discover (term-driven **and** `--unmapped` diff) + capture + verify |
| Non-market axes | Deferred to the scout; adapter core built to extend to a catalog axis without rework |
| Location / invocation | `src/bookieskit/devtools/` subpackage, `python -m bookieskit.devtools <cmd>` CLI |
| Generality | Generic over an arbitrary search term/regex and a canonical sport |
| Betway client fix | Extract the existing pagination-merge loop into `get_event_markets_all()` returning the **raw merged** payload; refactor `get_markets()` to use it; the harness adapter consumes it |
| Old scripts | Delete all 5 once superseded; drop the `extend-exclude = ["scripts"]` ruff entry |

## Architecture

New subpackage `src/bookieskit/devtools/`, decomposed into focused, independently testable units:

| Module | Responsibility | Key interface |
|---|---|---|
| `sports.py` | Sport registry: canonical sport → per-bookmaker sport id. | `SPORT_IDS: dict[str, dict[str, str \| None]]`; `sport_id(platform, sport) -> str \| None` |
| `adapters.py` | One adapter per bookmaker; same tiny interface so the resolver, canary, and scout all reuse it. | per platform: `resolve(client, sr_numeric, sport) -> Handle \| None`; `fetch_raw_markets(client, handle) -> dict` |
| `resolver.py` | Orchestrates the fan-out. Seed (BetPawa event id **or** raw SR id `sr:match:N`/`N`) + sport → `ResolvedEvent`. | `async resolve_event(seed, sport, books=ALL, *, live=False, cookies=None) -> ResolvedEvent` |
| `search.py` | Regex-search a raw payload for candidate markets, **and** diff against the registry. | `discover(payload, platform, term) -> list[Candidate]`; `unmapped(payload, platform, sport, registry=None) -> list[Candidate]` (every candidate whose platform id/key is not in the registry for that sport) |
| `fixtures.py` | Write per-platform raw fixtures. | `capture(payload, platform, name, *, live=False) -> Path` |
| `verify.py` | Run `parse_markets` per platform; report which canonicals resolve, with odds. | `verify(payload, platform, sport, canonical_ids=None) -> VerifyResult` |
| `cli.py` / `__main__.py` | argparse CLI: 4 subcommands, `--json`, `--sport`, `--book`, `--live`, cookie flags. | `python -m bookieskit.devtools <cmd> ...` |

### Data types (in `types.py`)

```python
@dataclass
class Handle:
    """Per-bookmaker identifier(s) needed to fetch markets for the resolved event."""
    platform: str
    event_id: str | None          # the id to fetch with (SR-prefixed, numeric, or internal)
    extra: dict[str, Any] = field(default_factory=dict)  # e.g. betika competition_id

@dataclass
class ResolvedEvent:
    seed: str
    sport: str
    sr_numeric: str | None
    home: str
    away: str
    handles: dict[str, Handle]    # platform -> handle (present only where resolved)
    skipped: dict[str, str]       # platform -> human reason (cookie missing, not found, error)

@dataclass
class Candidate:
    platform: str
    market_id: str | None         # id (SportyBet/MSport/BetPawa) or key (Bet9ja) or marketId (Betway) or sub_type_id (Betika)
    name: str
    specifier: str | None
    outcomes: list[str]

@dataclass
class VerifyResult:
    platform: str
    resolved: dict[str, Any]      # canonical_id -> {lines/outcomes with odds}
    missing: list[str]            # requested canonical_ids that did NOT parse
```

### The four commands

All accept a seed plus `--sport <name>` (default `soccer`), `--book <csv>` (default all), `--json`, and cookie flags (`--sportpesa-cookie`, `--betika-cookie`) for the gated books.

1. `resolve <seed>` → the `ResolvedEvent` (SR id, home/away, per-book handles, skip reasons).
2. `discover <seed>` — two modes (mutually exclusive):
   - `--term "<regex>"` → `Candidate`s matching the term per book (read off ids/keys/outcomes for a known/suspected market).
   - `--unmapped` → every `Candidate` the book exposes whose id/key the registry does **not** map for the sport. Autonomous discovery; no term needed. (Exactly one of `--term`/`--unmapped` is required.)
3. `capture <seed> --name <fixture_name> [--live]` → writes `tests/fixtures/event_info/<platform>/<name>.json` per resolved book; prints written paths.
4. `verify <seed> [--canonical <csv>]` → per-book `VerifyResult`; with no `--canonical`, lists every canonical that parsed.

`--json` emits a single structured object (the dataclasses serialized) so the scout/canary and other agents consume it directly. Exit code: 0 if the seed resolved on ≥1 book; non-zero if resolution failed entirely.

## Library change (folded in)

`src/bookieskit/bookmakers/betway.py`: the multi-page merge loop currently *inside* `get_markets()` (betway.py:297-317) is the only way to get all pages, but it returns parsed `NormalizedMarket`s — there is no way to get the **raw merged** payload, which is why every script hand-rolls `range(0, 600, 100)`. Extract that loop into:

```python
async def get_event_markets_all(self, event_id: str) -> dict[str, Any]:
    """Auto-paginate get_event_markets and return the raw merged payload
    (marketsInGroup / outcomes / prices / sportEvent) across all pages."""
```

Refactor `get_markets()` to call `get_event_markets_all()` then `parse_markets` (behavior unchanged; covered by existing Betway tests). The harness Betway adapter calls `get_event_markets_all()`. No other client changes.

## Error handling

- **Per-book isolation:** the resolver runs each book independently; an exception or timeout on one book records `skipped[platform] = reason` and never aborts the others (mirrors the scripts' `safe()` wrapper).
- **Cookie-gated books:** SportPesa (Akamai cookie) and Betika (when its host needs one) skip with a clear reason if no cookie is supplied; supplying `--sportpesa-cookie`/`--betika-cookie` enables them.
- **Seed not found on a book:** recorded as a skip, not an error (e.g., Bet9ja SR→internal miss, Betika listing-scan miss after N pages).
- The CLI prints skips prominently and includes them in `--json`.

## Testing approach

- **Offline unit tests** under `tests/devtools/` using respx-mocked client responses and the existing `tests/fixtures/`:
  - `sports.py`: registry lookups for each sport/platform.
  - `adapters.py`: each adapter's `fetch_raw_markets` against a mocked response → expected raw shape; `resolve` mapping logic.
  - `resolver.py`: fan-out with a mix of resolving/failing/cookie-missing books → correct `handles`/`skipped`.
  - `search.py`: `discover` against fixture payloads → expected `Candidate`s for a known term; `unmapped` against a fixture with a deliberately-unmapped market → that market appears and registry-mapped ones do not.
  - `verify.py`: `verify` against fixture payloads → expected resolved canonicals / `missing`.
  - `cli.py`: argument parsing and `--json` serialization (invoking command functions with mocked resolver, not network).
- **Betway client:** existing tests must stay green after the `get_markets` refactor; add one test that `get_event_markets_all` merges multiple pages and stops on a short page.
- No live network in tests. Live use of the harness is manual/agent-driven.

## Cleanup

After the harness is verified, delete the superseded scripts: `scripts/probe_2way_handicap_ft.py`, `scripts/probe_next_goal_and_team_ou.py`, `scripts/smoke_new_markets.py`, `scripts/capture_event_info_fixtures.py`, `scripts/diagnose_ah.py`. Remove `extend-exclude = ["scripts"]` from the ruff config (the directory is then empty or gone), resolving the CI review's finding that the exclusion masked F-class lint. Update `README.md`/docs to point at `python -m bookieskit.devtools` for the market-add loop.

## Success criteria

- `python -m bookieskit.devtools {resolve,discover,capture,verify} --help` work; each runs non-interactively and supports `--json`.
- Against a live seed (manual check): `discover --term` surfaces the same candidate markets the old `probe_*` scripts did; `discover --unmapped` lists markets present on the event but absent from the registry; `verify` reports canonical resolution like the old `smoke_*`; `capture` writes the same fixture files.
- `get_event_markets_all` returns the full merged payload; `get_markets` behavior unchanged (existing tests green).
- New offline `tests/devtools/` suite passes; full suite + `ruff check .` green in CI.
- The 5 scripts are gone and `scripts/` is no longer ruff-excluded.

## Reuse hooks for later sub-projects

- **Canary (sub-proj 3):** imports `resolver` + `adapters.fetch_raw_markets` to fetch live payloads and assert shape; imports `verify` to assert known canonicals still resolve.
- **Scout (north-star expansion stream):** imports `resolver` + `search.unmapped` to find markets a book exposes but the registry doesn't map, and files tasks for them. For the **non-market axes** (sports/competitions/widgets/features), the scout adds a *catalog adapter* layer alongside `adapters.py` — each bookmaker's adapter already isolates per-book client calls, so a parallel `catalog_fetch(client) -> catalog` method extends the same pattern without touching the markets path. This is the extensibility the core is designed for.
