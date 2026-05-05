# Documentation Refresh & Code Cleanup — Design

**Status:** approved, ready for implementation plan
**Date:** 2026-05-05
**Goal:** Bring the library's public face — README, per-bookmaker docs, cross-cutting docs, project metadata — up to date with everything that has shipped (live-event support across SportyBet/MSport/Bet9ja, MSport client, 1X2 1Up/2Up builtins, Bet9ja prematch SR-id search, Betway DC fix). At the same time, do a static-analysis and consistency pass on the source so the docs describe a tidy code surface.

## Scope

**In scope**
- Code audit & cleanup of `src/bookieskit/`, `tests/`, `examples/`.
- Project metadata fix (`pyproject.toml`).
- README rewrite from scratch (replaces the current 48-line stub).
- Rewrite of all 5 per-bookmaker docs to a unified template.
- Refresh of `docs/markets.md` and `docs/matching.md`.
- New `docs/examples.md` index for the 4 example scripts.

**Out of scope**
- Adding mypy / strict typing.
- Adding a coverage tool.
- Refactoring the parser dispatcher or splitting `parser.py`.
- Adding new bookmakers, new market mappings, or new public methods.
- Wiring BetPawa's 1X2 1Up / 2Up — explicitly deferred to production cutover.

## Phases

The work runs in two ordered phases. Code first, docs second — because audit fixes may touch public method signatures or rename things, and we don't want to rewrite docs twice.

### Phase A — Code audit & cleanup

1. Fix `pyproject.toml`:
   - Bump version `0.3.0` → `0.4.0` (matches `bookieskit.__version__`).
   - Update description to enumerate all 5 bookmakers (currently only 3).
   - Sweep dependencies / metadata for staleness.
2. Run `ruff check src/ tests/ examples/ --fix`. Address remaining warnings manually. Don't expand the rule set (currently E/F/I).
3. Manual sweep:
   - Unused imports / dead methods (a method defined but never called from src/, tests/, or examples/). Remove or justify with a comment.
   - Missing docstrings on public methods. Every public method must have a docstring with `Args` and `Returns` blocks.
   - Type-hint completeness on public method signatures.
   - Naming: snake_case for our identifiers (camelCase in API responses is unavoidable and fine).
   - Underscore prefix consistency on internal helpers.
4. Verify each `BaseBookmaker` subclass declares `DOMAINS`, `DEFAULT_HEADERS`, `MAX_CONCURRENT`, `REQUEST_DELAY`, `NAME`, `PLATFORM_KEY`.
5. Test-coverage sanity check (no formal coverage tool — just a grep): no public method without at least one test exercising it.
6. Error-handling sanity check: no `except: pass` or silent-`return None` patterns inside `_request` callers.
7. Commit cleanup as one or a few small commits, each scoped to one concern.

### Phase B — Documentation rewrite

1. **README** — full rewrite (~200 lines). New sections per the outline below.
2. **Per-bookmaker docs** — rewrite all 5 to the unified template (~150 lines each).
3. **`docs/markets.md`** — refresh covering the two dataclasses (with `msport_id`/`msport` fields), the 6 builtins + coverage matrix, parser dispatcher, position sentinels, custom-mapping recipe.
4. **`docs/matching.md`** — refresh covering `extract_sportradar_id`, `match_events`, an end-to-end matching example.
5. **`docs/examples.md`** (new) — short index pointing at the 4 example scripts.
6. Commit docs as one focused commit per file, or a single bundled commit if churn is small.

## Per-bookmaker doc template

Each `docs/<bookmaker>.md` follows this exact structure:

```
# <Bookmaker>

## Supported Countries
| Code | Domain | Notes |

## Rate Limits          (only if non-default)
- max_concurrent: <N>
- request_delay: <N>s

## SportRadar ID
One paragraph on how this bookmaker exposes (or hides) the SR id.

## Methods
Compact summary table: method | HTTP | path | when to use it.

### `method_name(args)`
- One-sentence purpose.
- Signature with type hints.
- Args block.
- Returns block describing the SHAPE the caller cares about.
- Notes block for quirks (e.g. live=True flips productId).

(Repeat for each public method.)

## Quirks
Bullet list of bookmaker-specific gotchas — field-name divergences,
endpoint sharps, in-place gotchas users will hit.

## Recipes
2-3 ready-to-paste async snippets, ~10-25 lines each. Recipes
demonstrate real workflows. Candidates per bookmaker:
  - List a tournament's events and print team names.
  - Get normalized markets for one event.
  - Resolve a SportRadar id to the bookmaker's internal id
    (where applicable — Bet9ja, BetPawa).

## See also
- examples/<relevant_script>.py
- docs/markets.md (cross-platform mappings)
- docs/matching.md (SR-id extraction)
```

## README outline

```
# bookieskit
One-paragraph hook: 5 normalized bookmakers, async, SR-id matching.

## Installation
pip install + dev extras.

## Quick start
Three short async snippets:
  1. Markets for one event from one bookmaker.
  2. Compare odds across all 5 by SR id.
  3. Competition walk -> CSV.
Each links to the corresponding example script.

## Supported Bookmakers
Bookmaker | countries | per-bookmaker doc link.

## How the lib is structured
Three short paragraphs:
  - Clients   (bookmakers/) -> per-platform HTTP wrappers
  - Markets   (markets/)    -> registry + parser + 6 builtins
  - Matching  (matching/)   -> SR-id extraction
Each paragraph links to its docs page.

## Built-in markets
The 6 shipped: 1X2, Over/Under, BTTS, Double Chance, 1X2 1Up, 1X2 2Up.
Coverage matrix: which bookmakers each market is wired to.

## Examples
One paragraph per example script (count_5bookies, odds_for_sr_id,
odds_from_betpawa_id, odds_for_betpawa_competition) + run command.

## Extending
Two-paragraph note on `MarketRegistry.add(...)` + 5-line snippet.

## Limitations / known gaps
- BetPawa SR-id reverse search not implemented.
- Bet9ja prematch SR-id search walks all soccer tournaments
  (~few seconds first call).
- Betway live event-detail returns only scoreboard; markets via
  get_markets().
- SportyBet/MSport get_event_detail needs live=True for live markets.
- GeniusSport-sourced matches are not handled. Cross-bookmaker
  matching is built on SportRadar ids; events fed from GeniusSport
  don't carry an SR id, so they won't appear in matched results.
- Anything else surfaced during the audit.
```

## Cross-cutting docs

**`docs/markets.md`** covers:
- `MarketMapping` and `OutcomeMapping` dataclasses, with the platform fields including `msport_id` / `msport`.
- The 6 builtins + coverage matrix.
- The platform dispatcher in `parse_markets()` and how to add a new platform's parser.
- One worked example registering a custom market via `MarketRegistry.add(...)`.
- Position-sentinel notes (`__HOME__`, `__POS_1__`, …).

**`docs/matching.md`** covers:
- `extract_sportradar_id(response, platform)` for all 5 platforms — where each stores the SR id, what prefix gets stripped.
- `match_events(*event_lists)` for grouping events across platforms.
- One end-to-end example: fetch lists from 3 bookmakers, group by SR id, count overlaps.

**`docs/examples.md`** is a new ~30-line index. One paragraph per script:
- `count_5bookies.py` — totals (sports / tournaments / events) per bookmaker.
- `odds_for_sr_id.py` — odds for a SR id across all 5.
- `odds_from_betpawa_id.py` — start from a BetPawa internal id, CSV out.
- `odds_for_betpawa_competition.py` — every event in a competition, CSV out.

Each entry: one-line purpose + the exact command to run.

## Risk and follow-ups

- **Phase A may surface real bugs**, not just style nits. If found, decide case-by-case: fix in this scope if small (one-line, well-bounded), defer to a follow-up if not.
- **Test-coverage gaps** found during the audit are *recorded* in the limitations list; they are not necessarily filled in this scope.
- **MSport DC outcome strings** were considered for the limitations list but are NOT a real limitation — both prematch and live use the compact `"1 X"`/`"1 2"`/`"X 2"` form, and the registry now matches both.
- **GeniusSport feed coverage** is recorded as a known gap in the README. The library does not currently inspect alternative widget types (only the SPORTRADAR widget on BetPawa, EXTID on Bet9ja, etc.). A future iteration could add `extract_geniussport_id` and a parallel matching path, but it requires per-bookmaker research into where GS ids are exposed (not all bookmakers necessarily expose them) and is deliberately out of scope here.
