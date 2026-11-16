# Mapping v2 — Steps 0–2 (correctness, safety net, measurement) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the three audited silent-wrong-output bugs, freeze the fixed parser output as a golden snapshot, and add the capture + coverage scripts that measure every later step.

**Architecture:** Surgical fixes inside today's `markets/parser.py` and the clients' `get_markets`; one central post-parse completeness filter in `parse_markets`; a JSON golden snapshot per fixture under `tests/golden/`; two stdlib scripts under `scripts/`. No new model yet (that is Step 3's plan).

**Tech Stack:** Python 3.11–3.13, httpx, pytest + pytest-asyncio + respx, ruff.

**Spec:** `docs/superpowers/specs/2026-11-16-mapping-parser-v2-design.md` (evidence: `2026-11-16-mapping-gap-audit.md`).

## Global Constraints

- Run Python as `.venv/Scripts/python.exe -X utf8 -m pytest …`; `ruff check .` stays clean.
- Public API is additive only: `parse_markets(...)` signature, `NormalizedMarket`/`Outcome` fields, existing `canonical_id` strings, `MarketRegistry` methods, client classes.
- Any output change for existing markets must be an intended bug fix, listed in the commit body.
- Suspended rule (Lorenzo, option A): odds ≤ 1.0 or missing on **any** outcome → drop the whole line (parameterized) or whole market (simple); a parameterized market left with no lines is dropped.
- Offline tests only; fixtures committed in the same commit that uses them; never open `sportpesa_cookie.txt`, `.env`, `.mcp.json`.
- Commit messages: conventional commits, short and plain, **no AI attribution lines** (Lorenzo's rule, overrides harness defaults).
- Work on branch `feat/mapping-v2` (already created, holds the design commit). Never push or tag without Lorenzo's OK.

## Review Focus

1. A Betway child row whose suffix is a *different* market starting with letters+`=` but under a shorter parent — rule accepts only `^[a-z]+=` suffixes; test pins `16hcp=-0.5~` accepted, `1601xup=1~`/`165`/`184` rejected (Task 2).
2. A line where one side is simply absent from the payload (Bet9ja one-sided O/U 8.5) — must be dropped like a suspended one (Task 4).
3. Odds of exactly `1.0` vs `1.01` — `1.0` dropped, `1.01` kept (Task 4).
4. `get_markets(event_id)` called with no `sport` (every existing consumer) — behaviour identical to today (Task 3).
5. A consumer-registered custom market whose `OutcomeMapping` has empty labels for some books — completeness counts only outcomes with a non-empty label for that platform (Task 4).

---

### Task 1: Bring in `feat/book-compare-support`

**Files:** merge of branch `feat/book-compare-support` (6 commits: 1X2 2UP mapping `28000850`, `base_url` override in `base.py`, `pricing.py` de-vig helpers, fixture `tests/fixtures/event_info/betpawa/1x2_2up_ft.json`).

- [ ] **Step 1:** `git merge --no-ff feat/book-compare-support` on `feat/mapping-v2`. Expected: conflicts (`git merge-tree` reports CONFLICT).
- [ ] **Step 2:** Resolve: `tests/devtools/test_coverage.py` → keep deleted (`git rm`); `CHANGELOG.md` → keep both entries under `[Unreleased]`; any other file → take the branch's change on top of `main`.
- [ ] **Step 3:** Run full suite + ruff. Expected: all pass, including `tests/test_pricing.py`, `tests/test_base.py`, the 2UP test in `tests/test_parser_betpawa.py`.
- [ ] **Step 4:** Commit the merge (`merge: book-compare support (1X2 2UP, base_url, de-vig helpers)`).

### Task 2: Betway marketId attribution only for specifier suffixes

**Files:**
- Modify: `src/bookieskit/markets/parser.py` (Pass 2 prefix loop ~766-773; `_build_betway_parameterized` ~912-925 parent/child selection)
- Test: `tests/test_parser_betway.py`

**Interfaces:** Produces `_is_betway_child_market_id(child: str, parent: str) -> bool` in `parser.py` — True iff `child` starts with `parent` and the remainder matches `^[a-z]+=`.

- [ ] **Step 1: Failing tests**

```python
from bookieskit.markets.parser import _is_betway_child_market_id, parse_markets

def test_child_suffix_must_be_a_specifier():
    assert _is_betway_child_market_id("6645701416hcp=-0.5~", "6645701416")
    assert _is_betway_child_market_id("6645701418total=2.5~", "6645701418")
    assert not _is_betway_child_market_id("66457014184", "6645701418")      # 1st Goal & 1X2
    assert not _is_betway_child_market_id("66457014165", "6645701416")      # Corner Handicap
    assert not _is_betway_child_market_id("664570141601xup=1~", "6645701416")  # 1X2 (3Up)
    assert not _is_betway_child_market_id("6645701416", "6645701416")

def test_wc_nf_goal_handicap_and_ou_are_the_real_markets():
    out = {m.canonical_id: m for m in parse_markets(load("betway/wc_nf.json"), "betway", sport="soccer")}
    assert "over_under_ft" in out
    hcp = out["2way_handicap_ft"].lines
    assert -0.5 in hcp
    assert [o.odds for o in hcp[0.5]] == [2.25, 1.61]   # not corner-handicap 2.20/1.60
```

(`load` = the fixture loader already used in `tests/test_parser_betway.py`; outcome order follows the existing home/away order of that test file.)

- [ ] **Step 2:** Run `pytest tests/test_parser_betway.py -k "specifier or wc_nf_goal" -v` → FAIL.
- [ ] **Step 3:** Implement `_is_betway_child_market_id` (`re.match(r"[a-z]+=", child[len(parent):])`) and use it in both places that currently use bare `startswith`. In `_build_betway_parameterized`, the parent row is the one whose marketId equals the mapping's parent id, not "last handicap == 0".
- [ ] **Step 4:** Full suite. Expected: PASS; also `over_under_ft` now present in `betway/2way_handicap_ft.json` — if an existing test asserted its absence, update it and name it in the commit body.
- [ ] **Step 5:** Commit `fix(betway): attribute child markets only by specifier suffix`.

### Task 3: `sport` reaches the parser from every client

**Files:**
- Modify: `src/bookieskit/base.py:237-256`, `bookmakers/betika.py:289-303`, `bookmakers/betway.py:319-342`, `bookmakers/sportpesa.py:120-136`
- Test: `tests/test_base.py` (+ one SportPesa test in `tests/test_sportpesa.py`)

**Interfaces:** Produces `async def get_markets(self, event_id: str, registry: MarketRegistry | None = None, *, sport: str | None = None) -> list[NormalizedMarket]` on `BaseBookmaker` and the three overrides; each passes `sport=sport` to `parse_markets`.

- [ ] **Step 1: Failing tests** — with the client's fetch method monkeypatched to return a fixture:
  - `test_get_markets_passes_sport`: SportPesa with `tennis.json` and `sport="tennis"` → no canonical id contains `basketball`; at least one contains `tennis`.
  - `test_get_markets_without_sport_unchanged`: same call without `sport` → result equals `parse_markets(raw, "sportpesa")` (Review Focus 4).
  - Parametrize the pass-through check over BetPawa (base), Betika, Betway, SportPesa by spying on `parse_markets` and asserting `sport="basketball"` arrived.
- [ ] **Step 2:** Run → FAIL (unexpected keyword `sport`).
- [ ] **Step 3:** Add the keyword-only parameter to the four methods; update their docstrings (`sport`: same meaning as in `parse_markets`).
- [ ] **Step 4:** Full suite → PASS.
- [ ] **Step 5:** Commit `fix(clients): pass sport through get_markets to the parser`.

*Deviation from spec, recorded for Lorenzo:* deriving the sport from the payload is deferred to Step 3, where each book adapter owns its payload shape; Step 1 only adds the explicit parameter.

### Task 4: Completeness filter (suspended / missing prices)

**Files:**
- Modify: `src/bookieskit/markets/parser.py` (`parse_markets`, after `parser(response, registry, mode)`)
- Test: create `tests/test_parser_completeness.py`

**Interfaces:** Produces `_keep_complete(markets: list[NormalizedMarket], registry: MarketRegistry, platform: str) -> list[NormalizedMarket]`. Expected outcome set for a market = canonical names of `registry.get_by_canonical(m.canonical_id).outcomes` whose label for `platform` is non-empty. A simple market is kept iff every expected outcome is present with odds > 1.0; a line is kept iff the same holds for the line; a parameterized market with no lines left is dropped. Markets with no registry mapping pass through unchanged. Uses `dataclasses.replace` (types are frozen).

- [ ] **Step 1: Failing tests** (build `NormalizedMarket`s by hand against the built-in registry):
  - `test_simple_market_with_zero_odds_dropped` — 1X2 with draw at `0.0` → `[]`.
  - `test_simple_market_with_one_point_zero_dropped_one_point_zero_one_kept` (Review Focus 3).
  - `test_line_with_missing_side_dropped_others_kept` — O/U with 2.5 complete and 8.5 over-only → only 2.5 remains (Review Focus 2).
  - `test_parameterized_market_with_no_lines_dropped`.
  - `test_custom_mapping_counts_only_nonempty_labels` — `MarketRegistry().add(...)` with an outcome whose `bet9ja` label is `""`; a Bet9ja market without that outcome is kept (Review Focus 5).
  - Fixture tests: `betpawa/live.json` → no outcome anywhere with odds ≤ 1.0; `bet9ja/wc_nf.json` → `over_under_ft` has no 0.5 line (O=1) and no 8.5 line (one-sided).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `_keep_complete` and apply it as the last line of `parse_markets` (registry before sport-scoping wrapper is fine: `get_by_canonical` is not sport-scoped).
- [ ] **Step 4:** Full suite. Existing tests that asserted a suspended/partial outcome are intended changes: update each and list them in the commit body.
- [ ] **Step 5:** Commit `fix(markets): drop lines and markets with suspended or missing prices`.

### Task 5: Golden snapshot of parser output

**Files:**
- Create: `scripts/regen_golden.py`, `tests/golden/manifest.json`, `tests/golden/<book>__<fixture>.json`, `tests/test_golden.py`

**Interfaces:**
- `scripts/regen_golden.py` exposes `snapshot(fixture_path: Path, platform: str, sport: str) -> dict` and `main() -> None`. Sport per fixture: filename starts with `basketball` → `"basketball"`, `tennis` → `"tennis"`, else `"soccer"`. A fixture is included iff `parse_markets(..., sport=sport, probability="with_void")` returns ≥ 1 market. `main()` rewrites the manifest (`{"<book>/<file>": "<sport>"}`) and every snapshot file.
- Snapshot JSON: list sorted by `canonical_id`; each market `{canonical_id, name, outcomes: [...], lines: {str(line): [...]} | null}`, lines sorted numerically; each outcome `{canonical_name, platform_name, odds, true_probability, void_probability}`; `json.dumps(..., indent=1, sort_keys=True)` + trailing newline.

- [ ] **Step 1: Failing test** — `tests/test_golden.py`: parametrized over `manifest.json`; `assert snapshot(path, book, sport) == json.loads(golden_file.read_text())`; plus `test_manifest_covers_all_parseable_fixtures` (the manifest equals what discovery would produce).
- [ ] **Step 2:** Run → FAIL (no manifest).
- [ ] **Step 3:** Implement `regen_golden.py`; run `python -X utf8 scripts/regen_golden.py`.
- [ ] **Step 4:** Run `pytest tests/test_golden.py -v` → PASS. Sanity: count of manifest entries ≥ 30, and `git diff --stat` shows only `tests/golden/` + new files.
- [ ] **Step 5:** Commit `test: golden snapshot of parse_markets output for every fixture`.

### Task 6: Coverage report

**Files:**
- Create: `scripts/coverage_report.py` (seed: the audit's `coverage.py` in the scratchpad `phase2/` folder), `tests/test_coverage_report.py`
- Modify: `docs/coverage.md` (regenerated), `CLAUDE.md` (one line under Rules on how to regenerate)

**Interfaces:** `coverage_rows(manifest: dict[str, str]) -> list[dict]` with keys `book, sport, raw_types, mapped_types, mapped_pct`; `render(rows) -> str` (markdown table + the canonical × book ✓/— matrix kept from today's `docs/coverage.md`); `main()` writes `docs/coverage.md`. "Raw types" = distinct market ids/names in the payload, counted with the same per-book rules the audit used.

- [ ] **Step 1: Failing test** — `test_rows_for_betpawa_prematch`: row exists with `raw_types > mapped_types > 0` and `mapped_pct == round(100*mapped/raw, 1)`; `test_render_has_one_row_per_book_sport`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run tests; run `python -X utf8 scripts/coverage_report.py`; check `docs/coverage.md` BetPawa soccer prematch shows the audit's order of magnitude (~14% types mapped, before Step 4 breadth).
- [ ] **Step 5:** Commit `feat(scripts): offline mapping coverage report`.

### Task 7: Fixture capture script

**Files:** Create `scripts/capture_fixtures.py`, `tests/test_capture_fixtures.py`

**Interfaces:** `async def capture(clients: dict[str, BaseBookmaker], ids: dict[str, str], name: str, out_dir: Path) -> dict[str, str]` — for each book with an id, fetch the same raw payload its `get_markets` parses (Betika `get_event_markets`, Betway `get_event_markets_all`, SportPesa `get_event_markets`, others `get_event_detail`), write `out_dir/<book>/<name>.json` (UTF-8, indent=1), return `{book: "ok" | "<error class>: <msg>"}`; one book failing never stops the others. `main()` takes `--name`, `--sport`, and `--<book> <event_id>` per book (argparse), plus `--country` (default `ng`).

- [ ] **Step 1: Failing tests** with fake client objects (no network): writes files for the books given; a raising client yields an error string and the other files still exist; nothing is written for books without an id.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(scripts): capture raw fixtures from every book`.

### Task 8: In-region capture round (needs Lorenzo's network)

- [ ] **Step 1:** Smoke check from Lorenzo's machine: `BetPawa(country="ng").get_event_detail(<any upcoming id>)` returns 200. If 403/timeouts → stop, report, and leave Step 4 scoped to existing fixtures (spec rule).
- [ ] **Step 2:** Pick ≥ 3 soccer, 2 basketball, 2 tennis **upcoming** events present on BetPawa, resolve each book's id (SportRadar id via `bookieskit.matching`), run `capture_fixtures.py` per event with names `prematch_<sport>_<n>` (prematch, never live).
- [ ] **Step 3:** `python -X utf8 scripts/regen_golden.py` and `scripts/coverage_report.py`; review new snapshot files for absurd odds (≤ 1.0 must not appear; spot-check 3 markets against the site).
- [ ] **Step 4:** Full suite + ruff → PASS. Commit fixtures + snapshots + coverage together: `test: fresh prematch fixtures for all books (<date>)`; list books that could not be captured in the body.

### Task 9: Close Step 0–2

- [ ] **Step 1:** CHANGELOG `[Unreleased]`: Fixed (Betway attribution, sport pass-through, suspended filter) and Added (`get_markets(sport=)`, scripts). Note the behaviour change for consumers: partial/suspended markets no longer returned.
- [ ] **Step 2:** Run `python-reviewer` + `bp-reviewer` on `main...feat/mapping-v2`; fix confirmed findings as separate commits.
- [ ] **Step 3:** Hand Lorenzo the review pack (commit list, diff stat, test result). Version bump / tag / push only on his OK.
