# Documentation Refresh & Code Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the lib's public face — README, per-bookmaker docs, cross-cutting docs, project metadata — up to date with everything that has shipped, while running a code-quality pass to clean up what the docs would describe.

**Architecture:** Two ordered phases. Phase A audits and tidies `src/`, `tests/`, `examples/` (so docs describe a clean surface). Phase B rewrites all user-facing docs (README, 5 per-bookmaker, markets, matching, new examples index) using a single unified template.

**Tech Stack:** Python 3.11+, ruff (E/F/I lints), pytest. No new tooling introduced.

**Source spec:** `docs/specs/2026-05-05-docs-and-cleanup-design.md`

---

## File Structure

```
Phase A — code audit & cleanup:
Modified:
  pyproject.toml                              — version 0.4.0, description, metadata
  src/bookieskit/                             — docstrings, type hints, dead code, naming
  tests/                                      — only if a stale test references removed code
  examples/                                   — only if a script references removed code

Phase B — documentation:
Rewritten:
  README.md                                   — full rewrite, ~200 lines
  docs/betpawa.md                             — unified template
  docs/sportybet.md                           — unified template
  docs/bet9ja.md                              — unified template
  docs/betway.md                              — unified template
  docs/msport.md                              — unified template
  docs/markets.md                             — refreshed: 6 builtins, 5 platforms, parser dispatch
  docs/matching.md                            — refreshed: 5 extractors, match_events end-to-end

Created:
  docs/examples.md                            — index for the 4 example scripts
```

---

## Task 1: Fix `pyproject.toml` metadata

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update version, description, and project metadata**

Replace the `[project]` table contents with:

```toml
[project]
name = "bookieskit"
version = "0.4.0"
description = "Async HTTP clients for scraping odds from 5 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport) with cross-bookmaker normalization via SportRadar IDs."
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
]
```

Leave `[build-system]`, `[project.optional-dependencies]`, `[tool.pytest.ini_options]`, `[tool.ruff]`, and `[tool.ruff.lint]` untouched.

- [ ] **Step 2: Verify package still imports correctly**

Run: `python -c "import bookieskit; print(bookieskit.__version__)"`
Expected output: `0.4.0`

- [ ] **Step 3: Confirm tests still pass**

Run: `pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: align pyproject metadata with shipped state (v0.4.0, 5 bookmakers)"
```

---

## Task 2: Ruff sweep with auto-fix

**Files:**
- Modify: any files ruff flags

- [ ] **Step 1: Run ruff with auto-fix**

Run: `ruff check src/ tests/ examples/ --fix`
Expected output: either "All checks passed!" or a list of remaining warnings ruff couldn't auto-fix.

- [ ] **Step 2: Manually address remaining warnings**

For each remaining warning:
- If it's a real issue (unused import, undefined name, import ordering not auto-fixed), fix it manually.
- If it's a false positive (e.g. dynamic attribute access ruff can't see), suppress it with `# noqa: <code>` and a one-line comment explaining why.

- [ ] **Step 3: Re-run ruff to confirm clean**

Run: `ruff check src/ tests/ examples/`
Expected: `All checks passed!`

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: ruff clean across src/ tests/ examples/"
```

If ruff already reported clean and made no changes, skip this commit.

---

## Task 3: Audit `src/bookieskit/bookmakers/`

**Files:**
- Modify: `src/bookieskit/bookmakers/betpawa.py`
- Modify: `src/bookieskit/bookmakers/sportybet.py`
- Modify: `src/bookieskit/bookmakers/bet9ja.py`
- Modify: `src/bookieskit/bookmakers/betway.py`
- Modify: `src/bookieskit/bookmakers/msport.py`

Audit checklist for each file. Apply fixes inline; if a fix is more than ~5 lines or changes behaviour, leave it and add a one-line `# AUDIT:` comment so it gets handled in Task 5.

- [ ] **Step 1: Verify required class attributes**

For each `BaseBookmaker` subclass, confirm these six are declared:
- `DOMAINS: dict[str, str]`
- `DEFAULT_HEADERS: dict[str, str]`
- `MAX_CONCURRENT: int`
- `REQUEST_DELAY: float`
- `NAME: str`
- `PLATFORM_KEY: str`

If any are missing, add them. None should be missing per the current state, but verify.

- [ ] **Step 2: Public-method docstring + type-hint pass**

For each public method (signature starts with `async def get_*` or `async def find_*` or `async def build_*`), confirm:
- Has a docstring with a one-sentence purpose, an `Args:` block, and a `Returns:` block.
- Every parameter is type-annotated.
- Return type is annotated as `dict[str, Any]` or a more specific type.

If a docstring is missing or skeletal, write one. Match the style of `MSport.get_event_detail` (already well-documented).

- [ ] **Step 3: Naming and underscore consistency**

In each file:
- Public methods: snake_case, no leading underscore.
- Private helpers: leading underscore (e.g. `_api_prefix`, `_timestamp`).
- Class attributes: SCREAMING_SNAKE_CASE for constants, snake_case for instance state.
- No camelCase identifiers in our own code (camelCase in API responses is unavoidable).

If you find any leak, rename. If the rename touches public surface, leave it and flag in Task 5.

- [ ] **Step 4: Unused-import / dead-code scan**

For each file:
- Run `ruff check <file>` — should already be clean from Task 2.
- Manually verify: every imported name is used somewhere in the file.
- Manually verify: every method is called from at least one of: another method in the same module, another module under `src/`, a test in `tests/`, or an example in `examples/`. Use grep:

```bash
grep -rn "method_name" src/ tests/ examples/
```

If a method has no callers anywhere, mark it for removal — but do NOT remove until Task 5.

- [ ] **Step 5: Run tests**

Run: `pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/bookmakers/
git commit -m "chore(bookmakers): docstring and consistency pass"
```

If no actual changes were made (everything was already clean), skip the commit.

---

## Task 4: Audit `src/bookieskit/markets/`, `matching/`, `base.py`, `config.py`, `exceptions.py`

**Files:**
- Modify: `src/bookieskit/base.py`
- Modify: `src/bookieskit/config.py`
- Modify: `src/bookieskit/exceptions.py`
- Modify: `src/bookieskit/markets/types.py`
- Modify: `src/bookieskit/markets/registry.py`
- Modify: `src/bookieskit/markets/parser.py`
- Modify: `src/bookieskit/markets/builtin_mappings.py`
- Modify: `src/bookieskit/matching/extractor.py`
- Modify: `src/bookieskit/matching/matcher.py`

Same checklist as Task 3, applied to these files.

- [ ] **Step 1: Public-method docstring + type-hint pass**

For each public function (no leading underscore, exported via `__init__.py` or used in tests/examples), confirm docstring quality and type-hint completeness. Fix what's small.

- [ ] **Step 2: Verify `bookieskit/__init__.py` and submodule `__init__.py` exports**

Open each `__init__.py`; confirm `__all__` matches the actual public surface and nothing extra is leaking. Specifically:
- `bookieskit/__init__.py` exports: `BetPawa`, `SportyBet`, `Bet9ja`, `Betway`, `MSport`, `__version__`.
- `bookieskit/bookmakers/__init__.py` exports: same 5 classes.
- Submodule `__init__.py` files (`markets/`, `matching/`) — verify they export the public helpers used by examples (e.g. `parse_markets`, `MarketRegistry`, `extract_sportradar_id`, `match_events`).

If `match_events` or other helpers aren't exported but are used in examples, fix the export.

- [ ] **Step 3: Confirm `_extract_line_from_specifier` docstring is platform-neutral**

The previous fix made this docstring "Used by SportyBet and MSport". Verify it doesn't say "SportyBet only" anymore. (It shouldn't — sanity check.)

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/
git commit -m "chore(core): docstring and export consistency pass"
```

Skip the commit if no changes were made.

---

## Task 5: Address audit findings (deletions, renames, behaviour fixes)

**Files:** depends on findings.

This task handles the items flagged in Tasks 3 and 4 with `# AUDIT:` comments or in your notes.

- [ ] **Step 1: Review audit findings**

Search for `AUDIT:` comments:

```bash
grep -rn "AUDIT:" src/
```

For each finding, decide:
- **Fix in this task** if it's small, well-bounded, and clearly correct.
- **Defer to a follow-up** if it's larger, ambiguous, or risks behaviour change. Move it to the README's "Limitations / known gaps" list (Task 7).

- [ ] **Step 2: Apply small fixes**

Apply each "fix in this task" finding. Run tests after each change:

Run: `pytest tests/ -q`
Expected: PASS after each fix.

- [ ] **Step 3: Remove all `AUDIT:` markers**

After applying fixes, all remaining `# AUDIT:` comments should be either resolved (markers removed) or converted to a `# TODO(post-cleanup):` marker with a short note for the deferred item.

- [ ] **Step 4: Run full suite**

Run: `pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: address audit findings (deletions, small fixes)"
```

Skip the commit if there were no findings.

---

## Task 6: Test-coverage and error-handling sanity check

**Files:** none (read-only audit + notes).

This task records gaps; it doesn't fix them in-scope. Findings feed into the README's "Limitations / known gaps" list (Task 7).

- [ ] **Step 1: Test-coverage grep**

For each public method on the 5 bookmakers and on `BaseBookmaker`:

```bash
grep -rn "<method_name>" tests/
```

Method-by-method check (paste the list below into a scratch note):

```
BetPawa: get_sports, get_countries, get_tournaments, get_events, get_event_detail, get_markets, get_sportradar_id
SportyBet: get_sports, get_countries, get_tournaments, get_events, get_event_detail, get_markets, get_sportradar_id
Bet9ja: get_sports, get_live_sports, get_live_events, get_live_event_detail, get_countries, get_tournaments, get_events, get_event_detail, build_prematch_event_map, find_event_id_by_sr_id, get_markets, get_sportradar_id
Betway: get_sports, get_countries, get_tournaments, get_events, get_event_detail, get_event_markets, get_markets, get_sportradar_id
MSport: get_sports, get_events, get_event_detail, get_live_sports, get_live_events, get_markets, get_sportradar_id
parse_markets, extract_sportradar_id, match_events
```

For each method, note: ✅ has at least one test, or ❌ no test.

- [ ] **Step 2: Error-path grep**

```bash
grep -rn "except: pass\|except Exception: pass\|except.*: *return None" src/
```

For each hit, evaluate:
- Inside `_request` / retry logic — usually fine, swallowing transient errors and retrying.
- Inside parsers / extractors — usually fine, returning None for malformed input.
- Anywhere else — note as a smell.

Also check `examples/odds_for_sr_id.py` and `examples/odds_for_betpawa_competition.py` — they have `try/except: return []` and `try/except: return {"markets": []}` which are intentional (per-event resilience) and fine.

- [ ] **Step 3: Write findings to a temp file**

Create `docs/specs/2026-05-05-audit-findings.md` (NOT committed; this is a working document for Task 7) with two sections:

```markdown
# Audit findings — 2026-05-05

## Test-coverage gaps
- <method>: no test (recommended addition: <one-line>)
- ...

## Error-handling smells
- <file:line>: <description>
- ...
```

- [ ] **Step 4: No commit yet**

Findings get folded into the README in Task 7. Don't commit `audit-findings.md` — it's transient.

---

## Task 7: README rewrite

**Files:**
- Modify: `README.md`

Replace the entire README contents with the structure below. ~200 lines target.

- [ ] **Step 1: Write the new README**

Use this exact section structure. Fill each section with concrete content drawn from the spec, the source code, and your audit findings.

````markdown
# bookieskit

Async HTTP clients for 5 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport), with normalized markets and cross-bookmaker matching by SportRadar id.

## Installation

```bash
pip install git+https://github.com/<user>/bookieskit.git

# Dev (tests + lint)
pip install "bookieskit[dev] @ git+https://github.com/<user>/bookieskit.git"
```

Requires Python 3.11+.

## Quick start

### 1. Markets for one event

```python
import asyncio
from bookieskit import SportyBet

async def main():
    async with SportyBet(country="ng") as sb:
        markets = await sb.get_markets(event_id="sr:match:69339436")
        for m in markets:
            print(m.canonical_id, m.name, len(m.outcomes or []))

asyncio.run(main())
```

### 2. Compare odds across all 5 by SportRadar id

```bash
python examples/odds_for_sr_id.py 69339436
```

See `examples/odds_for_sr_id.py` for the implementation.

### 3. Walk a BetPawa competition into a CSV

```bash
python examples/odds_for_betpawa_competition.py 12546
```

See `examples/odds_for_betpawa_competition.py`.

## Supported Bookmakers

| Bookmaker | Countries | Doc |
|-----------|-----------|------|
| BetPawa   | ng, gh, ke, ug, tz, zm | [docs/betpawa.md](docs/betpawa.md) |
| SportyBet | ng, gh, ke | [docs/sportybet.md](docs/sportybet.md) |
| Bet9ja    | ng | [docs/bet9ja.md](docs/bet9ja.md) |
| Betway    | ng, gh, ke, tz, ug, zm | [docs/betway.md](docs/betway.md) |
| MSport    | ng, gh, ke | [docs/msport.md](docs/msport.md) |

## How the lib is structured

- **Clients** — `bookieskit/bookmakers/`. One subclass of `BaseBookmaker` per platform; methods like `get_sports`, `get_events`, `get_event_detail` return raw JSON. The base class provides retry, rate-limiting, async context management, plus the convenience methods `get_markets()` and `get_sportradar_id()`.
- **Markets** — `bookieskit/markets/`. A `MarketRegistry` holds `MarketMapping` entries (one per canonical market). The parser dispatches by platform key and returns `NormalizedMarket` instances. Six markets ship as builtins. See [docs/markets.md](docs/markets.md).
- **Matching** — `bookieskit/matching/`. `extract_sportradar_id(response, platform)` pulls the SR id out of a raw event-detail response. `match_events(...)` groups events from multiple bookmakers by shared SR id. See [docs/matching.md](docs/matching.md).

## Built-in markets

| Canonical id | Name | BetPawa | SportyBet | Bet9ja | Betway | MSport |
|---|---|---|---|---|---|---|
| `1x2_ft` | 1X2 — Full Time | ✅ | ✅ | ✅ | ✅ | ✅ |
| `over_under_ft` | Over/Under — Full Time | ✅ | ✅ | ✅ | ✅ | ✅ |
| `btts_ft` | Both Teams To Score — Full Time | ✅ | ✅ | ✅ | ✅ | ✅ |
| `double_chance_ft` | Double Chance — Full Time | ✅ | ✅ | ✅ | ✅ | ✅ |
| `1x2_1up_ft` | 1X2 1Up — Full Time | — | ✅ | ✅ | ✅ | — |
| `1x2_2up_ft` | 1X2 2Up — Full Time | — | ✅ | ✅ | ✅ | — |

The 1Up / 2Up markets pay as a 1X2 if your team gets to a 1- or 2-goal lead at any point. BetPawa and MSport are intentionally unmapped (BetPawa to be added at production cutover; MSport doesn't expose this market).

## Examples

Each example is a self-contained async script in `examples/`.

- **`count_5bookies.py`** — totals (sports / tournaments / events) per bookmaker. Run: `python examples/count_5bookies.py`.
- **`odds_for_sr_id.py`** — given a SportRadar id, fetch the mapped odds across all 5 bookmakers. Run: `python examples/odds_for_sr_id.py 69339436` (defaults to live; pass `--prematch` for upcoming).
- **`odds_from_betpawa_id.py`** — given a BetPawa internal id, derive the SR id from the SPORTRADAR widget and fetch all 5. Outputs CSV. Run: `python examples/odds_from_betpawa_id.py 34716684`.
- **`odds_for_betpawa_competition.py`** — for every event in a BetPawa competition, run the above flow. Outputs one CSV row per (event, market, line, outcome). Run: `python examples/odds_for_betpawa_competition.py 12546`.

See [docs/examples.md](docs/examples.md) for more detail.

## Extending

Add custom market mappings via `MarketRegistry.add(...)`:

```python
from bookieskit.markets import MarketRegistry, OutcomeMapping

registry = MarketRegistry()
registry.add(
    canonical_id="draw_no_bet_ft",
    name="Draw No Bet — Full Time",
    sportybet_id="11",
    bet9ja_key="S_DNB",
    outcomes={
        "home": OutcomeMapping(canonical_name="home", betpawa="1", sportybet="Home", bet9ja="1"),
        "away": OutcomeMapping(canonical_name="away", betpawa="2", sportybet="Away", bet9ja="2"),
    },
)
```

Pass `registry=registry` to `client.get_markets(event_id, registry=registry)` or `parse_markets(raw, platform=..., registry=registry)`.

## Limitations / known gaps

- **BetPawa SR-id reverse search not implemented.** The lib can extract a BetPawa event's SR id from the SPORTRADAR widget, but cannot find a BetPawa internal id from a SR id. Workaround: start from a BetPawa id (see `examples/odds_from_betpawa_id.py`).
- **Bet9ja prematch SR-id search.** `Bet9ja.build_prematch_event_map(sport_id="1")` walks every soccer tournament — takes a few seconds on first call. Cache the returned dict if you need to look up many SR ids in one session.
- **Betway live event-detail returns only scoreboard.** `Betway.get_event_detail()` does not include markets. Use `Betway.get_markets(event_id)` (which calls `get_event_markets` under the hood).
- **SportyBet/MSport require `live=True` for live markets.** Default `live=False` uses `productId=3` which returns only player-prop markets for in-play events. Pass `live=True` to use `productId=1`.
- **GeniusSport-fed events are not handled.** Cross-bookmaker matching is built on SportRadar ids; events sourced from the GeniusSport feed don't carry an SR id and won't appear in matched results.
- (Insert any other gaps surfaced in Task 6's audit findings.)

## License

(Whatever the project's license is. Leave a placeholder if not yet set.)
````

- [ ] **Step 2: Fold in audit findings**

If Task 6 found test-coverage gaps or error-handling smells, append them as bullet points to the "Limitations / known gaps" section.

- [ ] **Step 3: Verify Markdown links**

Run:

```bash
grep -oE "\[[^]]+\]\([^)]+\)" README.md | grep -oE "\([^)]+\)" | tr -d "()" | while read p; do [ -e "$p" ] && echo "OK $p" || echo "MISSING $p"; done
```

Expected: every relative link points to an existing file (`docs/*.md`, `examples/*.py`).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README with quick-start, structure, builtins, examples, limitations"
```

---

## Task 8: Rewrite `docs/betpawa.md`

**Files:**
- Modify: `docs/betpawa.md`

- [ ] **Step 1: Read the current source**

```bash
cat src/bookieskit/bookmakers/betpawa.py
```

Note the public methods: `get_sports`, `get_countries`, `get_tournaments`, `get_events`, `get_event_detail`. Plus inherited: `get_markets`, `get_sportradar_id`.

- [ ] **Step 2: Replace `docs/betpawa.md` with the unified template**

Use this exact structure. Fill in the placeholder sections from the source code.

````markdown
# BetPawa

## Supported Countries

| Code | Domain | Notes |
|------|--------|-------|
| `ng` | https://www.betpawa.ng | Nigeria |
| `gh` | https://www.betpawa.com.gh | Ghana |
| `ke` | https://www.betpawa.co.ke | Kenya |
| `ug` | https://www.betpawa.co.ug | Uganda |
| `tz` | https://www.betpawa.co.tz | Tanzania |
| `zm` | https://www.betpawa.co.zm | Zambia |

Country also drives the `x-pawa-brand` request header (e.g. `betpawa-nigeria`).

## SportRadar id

BetPawa hides the SR id inside `widgets[]` on the event-detail response — look for the entry with `type == "SPORTRADAR"`, then read `id` (preferred) or `value` (legacy). The library's `extract_sportradar_id(response, platform="betpawa")` does this for you and strips the `sr:match:` prefix. There is **no** SR-id-to-BetPawa-id reverse search yet — start workflows from a BetPawa internal id.

## Methods

| Method | HTTP | Path | When to use |
|--------|------|------|-------------|
| `get_sports()` | GET | `/api/sportsbook/v3/categories/list/all` | Top-level sport list with prematch/live counts. |
| `get_countries(sport_id)` | GET | `/api/sportsbook/v3/categories/list/{sport_id}?includeRegions=true` | Regions + competitions under a sport. |
| `get_tournaments(sport_id)` | GET | (same as above) | Convenience alias: same data as `get_countries`. |
| `get_events(...)` | POST | (varies) | Events for a tournament or sport, prematch or live. |
| `get_event_detail(event_id)` | GET | event detail with markets and widgets | Full event data; SR id lives in `widgets[]`. |
| `get_markets(event_id)` | (calls `get_event_detail`) | — | Inherited convenience: returns `list[NormalizedMarket]`. |
| `get_sportradar_id(event_id)` | (calls `get_event_detail`) | — | Inherited convenience: returns the SR id as a numeric string. |

### `get_sports() -> dict`

Top-level sport categories. Response carries `onlyMeta[]` with one entry per sport, including `eventCounts.upcoming` and `eventCounts.live`.

### `get_countries(sport_id: str) -> dict`

Regions and competitions under one sport. Response shape: `withRegions[].regions[].competitions[]` — each region is a country, each competition is a tournament.

### `get_tournaments(sport_id: str) -> dict`

Same data as `get_countries`. Kept as an alias for naming symmetry with the other clients.

### `get_events(tournament_id=None, event_type=None, sport_id=None) -> dict`

Events for a tournament or for a whole sport. Pass `tournament_id` to filter to one competition; pass `sport_id` + `event_type="LIVE"` for live events of a sport. Response: `responses[0].responses[]` — list of events, each with `id`, `participants`, `competition`, `region`.

### `get_event_detail(event_id: str) -> dict`

Full event payload, including `markets[]` and `widgets[]`. The SR id lives in the SPORTRADAR widget.

## Quirks

- `x-pawa-brand` header varies per country and is set automatically.
- BetPawa's parameterized markets store the line as `formattedHandicap` (display) and `handicap` (internal value × 4). The parser handles both.
- Outcome odds live under `prices[].price` (not `odds`).
- No SR-id reverse search.

## Recipes

### List all events in a competition

```python
import asyncio
from bookieskit import BetPawa

async def main():
    async with BetPawa(country="ng") as bp:
        raw = await bp.get_events(tournament_id="12546")
        events = (raw.get("responses") or [{}])[0].get("responses", [])
        for ev in events:
            parts = ev.get("participants", [])
            home = parts[0]["name"] if parts else "?"
            away = parts[1]["name"] if len(parts) > 1 else "?"
            print(f"{ev['id']}  {home} vs {away}")

asyncio.run(main())
```

### Normalized markets + SR id from one event

```python
import asyncio
from bookieskit import BetPawa
from bookieskit.matching import extract_sportradar_id

async def main():
    async with BetPawa(country="ng") as bp:
        detail = await bp.get_event_detail(event_id="34716684")
        sr_id = extract_sportradar_id(detail, platform="betpawa")
        markets = await bp.get_markets(event_id="34716684")
        print(f"SR id: {sr_id}")
        for m in markets:
            print(f"  {m.name}: {len(m.outcomes or [])} outcomes")

asyncio.run(main())
```

### Use a BetPawa id as the seed for cross-bookmaker comparison

See `examples/odds_from_betpawa_id.py` for a complete script. The flow:
1. Fetch BetPawa event detail.
2. Extract SR id from the SPORTRADAR widget.
3. Use that SR id to query SportyBet, MSport, Betway directly (their event ids ARE the SR id) and to look up Bet9ja's internal id via `Bet9ja.find_event_id_by_sr_id` or `build_prematch_event_map`.

## See also

- `examples/odds_from_betpawa_id.py`
- `examples/odds_for_betpawa_competition.py`
- [docs/markets.md](markets.md) — registry, builtins, custom mappings.
- [docs/matching.md](matching.md) — `extract_sportradar_id`, `match_events`.
````

- [ ] **Step 3: Verify all referenced methods exist**

Run:

```bash
grep -nE "async def (get_sports|get_countries|get_tournaments|get_events|get_event_detail|get_markets|get_sportradar_id)" src/bookieskit/bookmakers/betpawa.py src/bookieskit/base.py
```

Expected: every method named in the doc is present in source.

- [ ] **Step 4: Commit**

```bash
git add docs/betpawa.md
git commit -m "docs(betpawa): rewrite to unified reference + recipes template"
```

---

## Task 9: Rewrite `docs/sportybet.md`

**Files:**
- Modify: `docs/sportybet.md`

- [ ] **Step 1: Replace contents using the same template**

Section structure mirrors Task 8. Concrete content for SportyBet:

- **Countries**: `ng`, `gh`, `ke` — all on `https://www.sportybet.com`, country in path (`/api/{country}/...`).
- **SR id**: SportyBet's `eventId` IS `sr:match:<numeric>`. `extract_sportradar_id` strips the prefix.
- **Methods table**: `get_sports(live=False)`, `get_countries(sport_id, live=False)`, `get_tournaments(sport_id, live=False)`, `get_events(tournament_id, sport_id, market_ids)`, `get_event_detail(event_id, live=False)`, plus inherited `get_markets`, `get_sportradar_id`.
- **Quirks**:
  - `live=True` flips `productId` from 3 (prematch) to 1 (live). For LIVE events, `productId=3` returns only player props — main markets need `live=True`.
  - Outcome name field is `desc`. Specifier field is `specifier` (singular).
  - Parameterized markets repeat the same `id` once per line, with `specifier` like `total=2.5` or `hcp=-0.5`.
- **Recipes**:
  1. List all soccer tournaments and pick one to fetch events from.
  2. Get normalized markets for a live event (showing the `live=True` flag).
  3. Cross-reference with `examples/odds_for_sr_id.py`.
- **See also**: `examples/odds_for_sr_id.py`, `docs/markets.md`, `docs/matching.md`.

Each recipe must be ~10-25 lines, async, runnable.

- [ ] **Step 2: Verify referenced methods**

Run:

```bash
grep -nE "async def (get_sports|get_countries|get_tournaments|get_events|get_event_detail)" src/bookieskit/bookmakers/sportybet.py
```

Expected: every method exists; signatures match what your recipes call.

- [ ] **Step 3: Commit**

```bash
git add docs/sportybet.md
git commit -m "docs(sportybet): rewrite to unified template, document live=True flag"
```

---

## Task 10: Rewrite `docs/bet9ja.md`

**Files:**
- Modify: `docs/bet9ja.md`

- [ ] **Step 1: Replace contents using the same template**

Concrete content for Bet9ja:

- **Countries**: only `ng`, on `https://sports.bet9ja.com`.
- **Rate limits**: `MAX_CONCURRENT=15`, `REQUEST_DELAY=0.025` (Bet9ja is the most rate-sensitive of the 5).
- **SR id**: Bet9ja exposes the SR id as `EXTID` on every event in both prematch (`get_events(tournament_id)`) and live (`get_live_events`) responses. The lib has both a fast live lookup (`find_event_id_by_sr_id`, scans live events only) and a slower-but-complete prematch builder (`build_prematch_event_map`, walks every soccer tournament).
- **Methods table**: `get_sports`, `get_live_sports`, `get_live_events(sport_id)`, `get_live_event_detail(event_id)`, `get_countries`, `get_tournaments`, `get_events(tournament_id)`, `get_event_detail(event_id)`, `find_event_id_by_sr_id(sr_id, sport_id="3000001")`, `build_prematch_event_map(sport_id="1")`, plus inherited.
- **Quirks**:
  - Prematch and live use **different endpoints**: `GetEvent` (prematch, param `ID`) vs `GetLiveEvent` (live, param `EVENTID`).
  - Odds keys: prematch uses `S_<MARKET>_<OUTCOME>`; live uses `LIVES_<MARKET>_<OUTCOME>` AND wraps odds as `{"v": <float>}` instead of bare strings. The lib parser handles both.
  - Live sport ids are different (e.g. Soccer is `"3000001"` for live, `"1"` for prematch).
- **Recipes**:
  1. List all live soccer events with team names and EXTID.
  2. Look up a SR id in live events (fast path).
  3. Build a full prematch SR-id → internal-id map (slow path, one-time).
- **See also**: `examples/odds_for_betpawa_competition.py` (uses `build_prematch_event_map`), `docs/matching.md`.

- [ ] **Step 2: Verify referenced methods**

Run:

```bash
grep -nE "async def (get_sports|get_live_sports|get_live_events|get_live_event_detail|get_countries|get_tournaments|get_events|get_event_detail|find_event_id_by_sr_id|build_prematch_event_map)" src/bookieskit/bookmakers/bet9ja.py
```

Expected: every named method is present.

- [ ] **Step 3: Commit**

```bash
git add docs/bet9ja.md
git commit -m "docs(bet9ja): rewrite to unified template, document live endpoints and SR-id lookups"
```

---

## Task 11: Rewrite `docs/betway.md`

**Files:**
- Modify: `docs/betway.md`

- [ ] **Step 1: Replace contents using the same template**

Concrete content for Betway:

- **Countries**: `ng, gh, ke, tz, ug, zm` — all on `https://feeds-roa2.betwayafrica.com` for data, plus a separate `https://config.betwayafrica.com` for the sports list. Country passed as `countryCode` query parameter.
- **SR id**: Betway's `eventId` IS the bare numeric SR id (no prefix). `extract_sportradar_id` and `get_sportradar_id` are essentially identity functions for Betway.
- **Methods table**: `get_sports`, `get_countries(sport_id)`, `get_tournaments(sport_id)`, `get_events(...)`, `get_event_detail(event_id)`, `get_event_markets(event_id, skip=0, take=100)`, plus the **overridden** `get_markets(event_id)` and `get_sportradar_id(event_id)`.
- **Quirks**:
  - **Two domains**: sports list comes from the config domain; everything else from feeds.
  - **Markets and event detail are SEPARATE endpoints**: `get_event_detail` returns scoreboard / metadata only — NO markets. Use `get_event_markets` (or `get_markets`) for odds.
  - Markets endpoint returns denormalized data: `marketsInGroup[]`, `outcomes[]`, `prices[]` — linked by `marketId` and `outcomeId`. The parser handles the join.
  - Position-based outcome resolution for 1X2 / DC (uses `__HOME__` / `__AWAY__` / `__POS_N__` sentinels).
- **Recipes**:
  1. List soccer leagues for a country.
  2. Get normalized markets for one event (showing the get_markets vs get_event_detail distinction).
  3. Get raw markets and inspect a parameterized line (Total Goals).
- **See also**: `examples/odds_from_betpawa_id.py`, `docs/markets.md` (position sentinels section).

- [ ] **Step 2: Verify referenced methods**

Run:

```bash
grep -nE "async def (get_sports|get_countries|get_tournaments|get_events|get_event_detail|get_event_markets|get_markets|get_sportradar_id)" src/bookieskit/bookmakers/betway.py
```

Expected: every method present.

- [ ] **Step 3: Commit**

```bash
git add docs/betway.md
git commit -m "docs(betway): rewrite to unified template, document two-domain split and markets endpoint"
```

---

## Task 12: Rewrite `docs/msport.md`

**Files:**
- Modify: `docs/msport.md`

- [ ] **Step 1: Replace contents using the same template**

Concrete content for MSport:

- **Countries**: `ng, gh, ke` — same domain `https://www.msport.com`, country in path.
- **SR id**: MSport's `eventId` IS `sr:match:<numeric>`, same as SportyBet. `extract_sportradar_id` strips the prefix.
- **Methods table**: `get_sports()`, `get_events(sport_id="sr:sport:1")`, `get_event_detail(event_id, live=False)`, `get_live_sports()`, `get_live_events(sport_id="sr:sport:1")`, plus inherited.
- **Quirks**:
  - **No per-tournament events endpoint**: `get_events(sport_id)` returns matches grouped by tournament for the entire sport — `data.tournaments[].events[]`.
  - **Live events use a separate URL**: `/live-matches/list?sportId=...` (richer payload — includes `tournaments`, `events`, `comingSoons`).
  - **`live=True` switches `productId`** the same way as SportyBet (3 → 1) for full live market book.
  - Outcome name field is `description` (not `desc`); specifier field is `specifiers` (plural). Headers identical to SportyBet (`operid`, `clientid`, `platform`).
- **Recipes**:
  1. List sports and pick one to fetch tournaments+events from.
  2. Get normalized live markets for one event (showing `live=True`).
  3. Walk live events for soccer.
- **See also**: `examples/odds_for_sr_id.py`, `docs/markets.md`.

- [ ] **Step 2: Verify referenced methods**

Run:

```bash
grep -nE "async def (get_sports|get_events|get_event_detail|get_live_sports|get_live_events)" src/bookieskit/bookmakers/msport.py
```

Expected: every method present.

- [ ] **Step 3: Commit**

```bash
git add docs/msport.md
git commit -m "docs(msport): rewrite to unified template, document live=True and grouped events"
```

---

## Task 13: Refresh `docs/markets.md`

**Files:**
- Modify: `docs/markets.md`

- [ ] **Step 1: Replace contents**

````markdown
# Markets — registry, builtins, parser

The `bookieskit.markets` package normalizes per-bookmaker market formats into a small set of canonical markets. Three pieces:

- **Types** (`markets/types.py`) — `MarketMapping`, `OutcomeMapping`, `NormalizedMarket`, `Outcome`.
- **Registry** (`markets/registry.py`) — `MarketRegistry` holds `MarketMapping` entries, indexed by canonical id and by each platform's id.
- **Parser** (`markets/parser.py`) — `parse_markets(response, platform, registry=None)` dispatches to a per-platform parser and returns `list[NormalizedMarket]`.

## Built-in mappings

Six markets ship in the default `MarketRegistry`:

| Canonical id | Name | parameterized? | Coverage |
|---|---|---|---|
| `1x2_ft` | 1X2 — Full Time | no | All 5 |
| `over_under_ft` | Over/Under — Full Time | yes (line=goals) | All 5 |
| `btts_ft` | Both Teams To Score — Full Time | no | All 5 |
| `double_chance_ft` | Double Chance — Full Time | no | All 5 |
| `1x2_1up_ft` | 1X2 1Up — Full Time | no | SportyBet, Bet9ja, Betway |
| `1x2_2up_ft` | 1X2 2Up — Full Time | no | SportyBet, Bet9ja, Betway |

## Types

### `MarketMapping`

Frozen dataclass. Fields:
- `canonical_id: str` — unique short id (e.g. `"over_under_ft"`).
- `name: str` — human-readable name.
- `betpawa_id: str | None`
- `sportybet_id: str | None`
- `bet9ja_key: str | None` — the key prefix in Bet9ja's flat odds dict (e.g. `"S_OU"`).
- `betway_id: str | None` — the literal market name as Betway returns it (e.g. `"[Total Goals]"`).
- `msport_id: str | None`
- `outcomes: dict[str, OutcomeMapping]` — keyed by canonical outcome name (`"home"`, `"over"`, etc.).
- `parameterized: bool` — `True` for markets with line variants (Over/Under, handicaps).

### `OutcomeMapping`

Frozen dataclass. One per canonical outcome:
- `canonical_name: str` — e.g. `"home"`, `"draw"`, `"over"`.
- `betpawa: str` — the platform's outcome string (e.g. `"1"`).
- `sportybet: str`
- `bet9ja: str` — the suffix in the flat odds dict (e.g. `"O"` for over).
- `betway: str` — either the literal name (`"Over"`) or a position sentinel.
- `msport: str`

### Position sentinels (Betway)

For markets where Betway uses team names as outcome strings (1X2, DC, the 1Up/2Up variants), the registry stores a sentinel that the parser resolves by index:

| Sentinel | Index | Meaning |
|---|---|---|
| `__HOME__` | 0 | Home (used by 1X2) |
| `__AWAY__` | 2 | Away (used by 1X2) |
| `__POS_1__` | 0 | First outcome |
| `__POS_2__` | 1 | Second outcome |
| `__POS_3__` | 2 | Third outcome |

Use `__HOME__`/`__AWAY__` for clarity on 1X2-shaped markets; use `__POS_N__` when the meaning is purely positional (e.g. Double Chance: home_draw / home_away / draw_away).

## Parser dispatcher

`parse_markets(response, platform, registry=None)` looks up `platform` in the dispatcher dict and calls the right `_parse_<platform>` function. Currently registered: `"betpawa"`, `"sportybet"`, `"bet9ja"`, `"betway"`, `"msport"`. Returns `[]` if `platform` is unknown.

The Bet9ja parser handles BOTH the `S_*` prematch keys and the `LIVES_*` live keys (also unwraps the `{"v": <float>}` odds shape used live).

## Custom mappings

Add a market to the default registry at runtime:

```python
from bookieskit.markets import MarketRegistry, OutcomeMapping

registry = MarketRegistry()  # ships with the 6 builtins
registry.add(
    canonical_id="draw_no_bet_ft",
    name="Draw No Bet — Full Time",
    betpawa_id="4703",
    sportybet_id="11",
    bet9ja_key="S_DNB",
    betway_id="Draw No Bet",
    msport_id="11",
    outcomes={
        "home": OutcomeMapping(canonical_name="home", betpawa="1", sportybet="Home", bet9ja="1", betway="__HOME__", msport="Home"),
        "away": OutcomeMapping(canonical_name="away", betpawa="2", sportybet="Away", bet9ja="2", betway="__AWAY__", msport="Away"),
    },
)
```

Pass the registry into `parse_markets(raw, platform=..., registry=registry)` or `client.get_markets(event_id, registry=registry)`.

## Adding a new platform

To wire a new bookmaker into the parser:
1. Add a `<platform>_id` field to `MarketMapping` and a `<platform>` field to `OutcomeMapping`.
2. Add a `_by_<platform>` index to `MarketRegistry`.
3. Write `_parse_<platform>(response, registry)` in `parser.py`.
4. Add a `"<platform>": _parse_<platform>` entry to the dispatcher dict.
5. Update the 6 builtins (or leave them unmapped if the platform doesn't expose those markets).

## See also

- [docs/matching.md](matching.md) — pairing events across platforms by SR id.
- [docs/examples.md](examples.md) — example scripts that use the registry end-to-end.
````

- [ ] **Step 2: Commit**

```bash
git add docs/markets.md
git commit -m "docs(markets): refresh with 6 builtins, msport_id, position sentinels, custom mapping recipe"
```

---

## Task 14: Refresh `docs/matching.md`

**Files:**
- Modify: `docs/matching.md`

- [ ] **Step 1: Replace contents**

````markdown
# Matching — SportRadar id extraction and cross-bookmaker pairing

The `bookieskit.matching` package finds the same real-world event across multiple bookmakers using SportRadar ids.

## `extract_sportradar_id(response, platform)`

Pulls the SR id out of a raw event-detail response. Returns the bare numeric id (e.g. `"69339436"`), or `None` if not found. Where each bookmaker stores the id:

| Platform | Field path | Notes |
|---|---|---|
| `betpawa` | `widgets[].id` where `type == "SPORTRADAR"` | Falls back to `value` for legacy responses; strips `sr:match:`. |
| `sportybet` | `data.eventId` | Strips `sr:match:`. |
| `bet9ja` | `D.EXTID` | On prematch detail. Live detail uses `D.A.EXTID`. |
| `betway` | `sportEvent.eventId` | The id IS the SR numeric — already prefix-free. |
| `msport` | `data.eventId` | Strips `sr:match:`. |

Unknown platforms return `None`.

## `match_events(*event_lists)`

Groups events from multiple bookmakers by shared SR id. Each argument is a tuple `(platform, [event_response, ...])`. Returns a list of `MatchedEvent` records, one per SR id seen on any input platform.

`MatchedEvent` exposes `sportradar_id: str` plus per-platform `dict | None` fields (`betpawa`, `sportybet`, `bet9ja`).

End-to-end example — fetch event lists from three bookmakers, group by SR id, count overlaps:

```python
import asyncio
from bookieskit import BetPawa, SportyBet, Bet9ja
from bookieskit.matching import match_events

async def main():
    async with BetPawa(country="ng") as bp, SportyBet(country="ng") as sb, Bet9ja(country="ng") as b9:
        # Fetch a small sample from each (in real use you'd loop over tournaments).
        bp_raw = await bp.get_events(tournament_id="12546")
        sb_raw = await sb.get_events(tournament_id="sr:tournament:17")
        # Bet9ja: pick a known soccer tournament id like Premier League.
        b9_raw = await b9.get_events(tournament_id="170880")

    # Each list must be a list of EVENT-DETAIL responses (or anything carrying
    # the SR id where the per-platform extractor expects it).
    bp_events = (bp_raw.get("responses") or [{}])[0].get("responses", [])
    sb_events = ((sb_raw.get("data") or [{}])[0].get("events", []))
    b9_events = (b9_raw.get("D") or {}).get("E", [])

    matched = match_events(
        ("betpawa", bp_events),
        ("sportybet", sb_events),
        ("bet9ja", b9_events),
    )

    overlap = sum(1 for m in matched if m.betpawa and m.sportybet and m.bet9ja)
    print(f"{len(matched)} unique SR ids, {overlap} present on all 3 bookmakers")

asyncio.run(main())
```

## When `extract_sportradar_id` is not enough

For events fed from non-SportRadar providers (notably **GeniusSport**), no SR id is exposed. These events will not show up in `match_events` results and there is no current workaround in this lib.

For SportyBet / MSport / Betway, the platform's event id IS (or contains) the SR id — direct lookups by SR id work:
- `await sportybet.get_event_detail(event_id="sr:match:69339436", live=True)`
- `await msport.get_event_detail(event_id="sr:match:69339436", live=True)`
- `await betway.get_markets(event_id="69339436")`

For BetPawa and Bet9ja, the platform id is internal:
- BetPawa: no SR-id reverse search yet — start workflows from a BetPawa internal id.
- Bet9ja: use `find_event_id_by_sr_id(sr_id)` (live only, fast) or `build_prematch_event_map(sport_id="1")` (prematch, walks tournaments — slower).

## See also

- [docs/markets.md](markets.md) — what to do once you have the per-bookmaker event ids.
- `examples/odds_for_sr_id.py` — single-event compare across all 5.
- `examples/odds_for_betpawa_competition.py` — full-tournament compare via BetPawa as the seed.
````

- [ ] **Step 2: Commit**

```bash
git add docs/matching.md
git commit -m "docs(matching): refresh with 5 extractors, end-to-end example, GeniusSport gap"
```

---

## Task 15: Create `docs/examples.md`

**Files:**
- Create: `docs/examples.md`

- [ ] **Step 1: Write the new file**

````markdown
# Example scripts

The `examples/` directory has runnable scripts that demonstrate the lib end-to-end. Each is async, self-contained, and uses only the public API.

## `count_5bookies.py`

Total counts (sports, prematch tournaments, live tournaments, prematch events, live events) per bookmaker. Hits one or two API calls per bookmaker — useful as a smoke test that everything is wired and reachable.

```bash
python examples/count_5bookies.py
```

## `odds_for_sr_id.py`

Given a SportRadar event id, fetch normalized odds for the mapped markets across all 5 bookmakers. Defaults to live; pass `--prematch` for upcoming events.

```bash
python examples/odds_for_sr_id.py 69339436
python examples/odds_for_sr_id.py 69339436 --prematch
```

Resolution per bookmaker:
- SportyBet, MSport, Betway: direct lookup by SR id.
- Bet9ja: live → `find_event_id_by_sr_id`. Prematch → not implemented in this script (use `odds_for_betpawa_competition.py` if your scope is one BetPawa competition).
- BetPawa: skipped (no SR-id reverse search).

## `odds_from_betpawa_id.py`

Same as above, but seeded with a BetPawa internal id. The script:
1. Hits BetPawa's event detail.
2. Extracts the SR id from the SPORTRADAR widget.
3. Dispatches the other 4 bookmakers in parallel.
4. Writes one CSV row per (market, line, outcome) with five bookmaker columns.

```bash
python examples/odds_from_betpawa_id.py 34716684
python examples/odds_from_betpawa_id.py 34716684 --prematch
python examples/odds_from_betpawa_id.py 34716684 --csv my_event.csv
```

The resulting CSV is a tidy, rectangular grid suitable for opening in Excel / Numbers / Sheets.

## `odds_for_betpawa_competition.py`

Walks every event in a BetPawa competition and produces a CSV with one row per (event, market, line, outcome) and five bookmaker columns.

```bash
python examples/odds_for_betpawa_competition.py 12546
python examples/odds_for_betpawa_competition.py 12546 --live
python examples/odds_for_betpawa_competition.py 12546 --csv epl_today.csv
```

Optimisation: the script pre-builds Bet9ja's SR-id → internal-id map once at startup (`get_live_events` for live mode; `build_prematch_event_map` for prematch). Per-event lookup is then O(1).

## See also

- [README.md](../README.md) — install + quick start.
- [docs/markets.md](markets.md) — what `get_markets()` returns.
- [docs/matching.md](matching.md) — how SR-id matching works.
````

- [ ] **Step 2: Commit**

```bash
git add docs/examples.md
git commit -m "docs(examples): add index page for the four example scripts"
```

---

## Task 16: Final verification

**Files:** none (verification-only).

- [ ] **Step 1: Full test suite**

Run: `pytest tests/ -q`
Expected: all PASS, exact same count as before the audit (or higher if any tests were added).

- [ ] **Step 2: Lint clean**

Run: `ruff check src/ tests/ examples/`
Expected: `All checks passed!`

- [ ] **Step 3: Public API smoke**

Run:

```bash
python -c "
from bookieskit import BetPawa, SportyBet, Bet9ja, Betway, MSport
from bookieskit.markets import MarketRegistry, parse_markets
from bookieskit.matching import extract_sportradar_id, match_events
import bookieskit
assert bookieskit.__version__ == '0.4.0'
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 4: Doc link check**

Run:

```bash
for f in README.md docs/*.md; do
  echo "--- $f ---"
  grep -oE "\[[^]]+\]\([^)]+\)" "$f" | grep -oE "\([^)]+\)" | tr -d "()" | while read p; do
    case "$p" in
      http*|mailto*) ;;
      *) [ -e "$p" ] || [ -e "$f-relative-base/$p" ] || echo "  MISSING: $p" ;;
    esac
  done
done
```
Expected: no `MISSING:` lines (relative paths can vary by OS — eyeball any false positives).

- [ ] **Step 5: Confirm clean tree**

Run: `git status`
Expected: working tree clean.

- [ ] **Step 6: Print commit log for the cleanup branch**

Run: `git log --oneline 06f1c45..HEAD`
Expected: a tidy series of commits — pyproject fix, ruff sweep (optional), audit commits (optional), README, 5 bookmaker docs, markets, matching, examples.

---

## Self-review notes

- **Spec coverage:** every spec section maps to a task. Phase A (audit) → tasks 1-6. Phase B (docs) → tasks 7-15. Final verify → task 16.
- **Placeholders:** none — every step has concrete commands or content.
- **Type/method consistency:** method names referenced in docs are grep-verified before commit in each doc task. Public API surface (`__version__ == "0.4.0"`, 5 client classes, 6 builtins) is verified in task 16.
- **MSport DC:** treated as a corrected case, NOT a limitation, per spec.
- **GeniusSport limitation:** appears in README (task 7) and `docs/matching.md` (task 14), per spec.
- **"AUDIT:" markers:** if a deferred finding remains as a `TODO(post-cleanup):` after task 5, the README's limitations section should reflect it.
