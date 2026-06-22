# 2-way Handicap (soccer) + basketball rename — design

**Status:** Design approved 2026-05-22. Awaiting implementation plan.
**Scope:**
1. Add a new canonical soccer market `2way_handicap_ft` — Asian Handicap with home/away outcomes (no draw) and signed lines from the home team's perspective.
2. Rename the existing `handicap_basketball_ft` canonical to `2way_handicap_basketball_ft` to disambiguate it from any future 3-way (European) handicap variant.

**Out of scope:**
- 3-way European Handicap canonical (`3way_handicap_ft` — BetPawa id=4724, Bet9ja `S_1X2HND`). Explicitly deferred.
- Renaming `handicap_games_tennis_match` — staying as-is.
- Renaming `next_goal_ft` — staying as-is.
- Half-time / per-half variants of either market.
- SportPesa coverage — requires an Akamai cookie unavailable at probe time; stays `None`, same precedent as the three markets shipped in 0.14.0.
- Changes to `NormalizedMarket`, `OutcomeMapping`, or `MarketRegistry` shapes.

**Target version bump:** 0.14.0 → 0.15.0 (the rename is a breaking change for any downstream pinning `canonical_id="handicap_basketball_ft"`; minor bump signals it).

## 1. Motivation

Bookmakers ship two distinct handicap shapes for soccer:
- **Asian Handicap (2-way)** — outcomes home/away only, signed lines (often including quarter lines like 0.25, 0.75). BetPawa's `displayName` for this is literally `"2-Way Handicap | Full Time"`.
- **European Handicap (3-way / 1X2)** — outcomes home/draw/away over a single integer line. BetPawa's `displayName` is `"3-Way Handicap | Full Time"` (id `4724`); Bet9ja calls it `S_1X2HND`.

The existing `handicap_basketball_ft` canonical is already 2-way (basketball can't end in a draw in regulation+OT), but its name doesn't make that explicit. Adding a 2-way soccer handicap without the prefix would invite future ambiguity if/when we add the 3-way variant. Renaming the basketball canonical at the same time keeps the naming convention consistent across sports for the markets where 2-way vs 3-way disambiguation matters.

`handicap_games_tennis_match` and `next_goal_ft` are excluded from the rename because:
- Tennis has no 3-way handicap variant (tennis matches can't end in a draw).
- `next_goal_ft` is genuinely 3-way (home/none/away); a 2-way variant could be added later but the existing canonical isn't ambiguously named.

## 2. Decisions taken at brainstorm

| Decision | Outcome |
|---|---|
| Outcome shape for `2way_handicap_ft` | **2-way: `home` / `away`** (no draw). Mirrors `handicap_basketball_ft`. |
| Line semantic | **Signed lines from home perspective.** `line=-1.5` means home gives 1.5 goals. Both outcomes (home and away) live under that single signed key — same convention as the renamed basketball handicap and the existing tennis game handicap. Quarter-lines (0.25, 0.75 steps) work natively because `lines: dict[float, list[Outcome]]` accepts any float key. |
| Canonicals to rename | **Only basketball.** Tennis handicap and `next_goal_ft` stay as-is per the user. Rename is `handicap_basketball_ft` → `2way_handicap_basketball_ft`. |
| Rename + add in one shipping cycle | **Yes** — single 0.15.0 release. Keeps the naming convention atomic and gives downstream consumers one breakage point to absorb. |
| Coverage target | **All 7 bookmakers fully mapped except SportPesa.** SportPesa stays `None` (same precedent as the three 0.14.0 markets). |
| Live probe vs. design-time guess | **Probe before merging.** Same workflow as 0.14.0 — fixtures + RESOLVED record drive the locked-in IDs. |
| Parser changes | **None.** Handicap is already a fully-supported pattern across every parser. |

## 3. Empirically confirmed wire shapes

### BetPawa — `id=3774` ✅ confirmed

From a live BetPawa upcoming-events probe (2026-05-22):
```json
{
  "marketType": {
    "id": "3774",
    "name": "Asian Handicap - FT",
    "displayName": "2-Way Handicap | Full Time"
  },
  "row": [...]
}
```

BetPawa's `Handicap 1X2 - FT` (id=`4724`, `displayName: "3-Way Handicap | Full Time"`) is the European variant — **excluded**. So is `Draw No Bet - FT` (id=`4703`), which is effectively the line=0 special case of the Asian Handicap but ships as a separate market — also out of scope here.

Line value comes from BetPawa's parameterized row infrastructure (`formattedHandicap` per row, with the existing `_parse_betpawa_parameterized` flow handling sign).

### Bet9ja — `S_AH` ✅ confirmed

From the existing diagnostic against internal id `777762112` (SR `71443804`):
```
S_AH ... 32 odds keys (~16 lines × 2 outcomes)
```

Shape: `S_AH@<signed_line>_1` (home) / `S_AH@<signed_line>_2` (away). The existing `_parse_bet9ja_key` already splits the `@<line>_<outcome>` structure; the outcome strings `1` / `2` resolve via standard `OutcomeMapping.bet9ja` field.

Bet9ja's `S_1X2HND` (3-way European handicap) is the explicitly-excluded variant.

### SportyBet / MSport — `id=16` 🔍 SR-code mirror

The SR canonical code for Asian Handicap is `16`. Both SportyBet and MSport already use SR codes for their existing handicap-family markets (basketball `223`, tennis `187`), so `16` is the highly-likely soccer-handicap id. Probe confirms.

Specifier shape (extrapolated from existing handicap markets): `specifier="hcp=-1.5"` (or `specifiers=` plural on MSport). Both already handled by `_extract_line_from_specifier`.

Outcomes: `desc="Home"` / `desc="Away"`.

### Betway — TBD literal name 🔍 probe-needed

Earlier probes saw Betway label other handicap variants explicitly: `[Handicap] [3-Way]` (the European 3-way), `Handicap 0:4` / `Handicap 3:0` (exact handicap markets), and `2nd Half - Handicap - 2 Way 0.5` (2nd-half 2-way at a single line).

The full-match Asian Handicap likely uses one of:
- `Asian Handicap`
- `Handicap - 2 Way`
- `[Asian Handicap]` (with brackets, matching the existing `[Total Goals]` / `[Win/Draw/Win]` convention)

Probe confirms. Per-line entries with `handicap=<signed>` value; outcomes resolved via `__HOME__` / `__POS_2__` position sentinels (team names on the wire).

### Betika — `sub_type_id=16` 🔍 mirror-confirm

SR-code mirror as elsewhere on Betika. Probe confirms.

Specifier: `special_bet_value=<signed_line>` per selection; outcomes `display="1"` / `display="2"`.

### SportPesa — `None` (not probed)

Same Akamai-cookie gap as the 0.14.0 markets. Mapping stays `None` with a one-line code comment matching the existing precedent.

## 4. Per-bookmaker registry plan

| Canonical | BetPawa | SportyBet | Bet9ja | Betway | MSport | SportPesa | Betika |
|---|---|---|---|---|---|---|---|
| `2way_handicap_ft` | `3774` ✅ | `16` 🔍 | `S_AH` ✅ | TBD literal 🔍 | `16` 🔍 | `None` (not probed) | `16` 🔍 |

Outcome strings:

| Outcome | BetPawa | SportyBet | Bet9ja | Betway | MSport | SportPesa | Betika |
|---|---|---|---|---|---|---|---|
| `home` | `1` | `Home` | `1` | `__HOME__` | `Home` | `1` (tentative) | `1` |
| `away` | `2` | `Away` | `2` | `__POS_2__` | `Away` | `2` (tentative) | `2` |

All values follow the conventions established by the existing handicap markets across sports.

For the **basketball rename**, no ID or outcome changes — only the `canonical_id` string flips from `"handicap_basketball_ft"` to `"2way_handicap_basketball_ft"`. The mapping continues to use the same `betpawa_id="3777"`, `sportybet_id="223"`, etc.

## 5. Code changes

### `markets/types.py` — none

Existing fields suffice.

### `markets/registry.py` — none

The rename is just a different `canonical_id` value passed to `MarketMapping(...)`; the registry's first-wins / sport-scoped indexes work unchanged.

### `markets/parser.py` — none

The handicap pattern is fully supported across every parser:
- BetPawa: `_parse_betpawa_parameterized` reads `formattedHandicap` per row.
- SportyBet / MSport: `_extract_line_from_specifier` already recognises `hcp=<signed>`.
- Bet9ja: `_parse_bet9ja_key` already splits the `S_AH@<line>_<outcome>` form.
- Betway: `_build_betway_parameterized` Case 1 (parent + per-line distribution) handles the standard per-line shape; Case 2 (marketId-line) added in 0.14.0 doesn't fire here.
- Betika: standard parameterized path with `special_bet_value`.

### `markets/builtin_mappings.py` — two changes

**Change 1 — rename the basketball canonical:**

Locate the `handicap_basketball_ft` `MarketMapping` entry. Change `canonical_id="handicap_basketball_ft"` to `canonical_id="2way_handicap_basketball_ft"`. Update the leading comment block to mention the explicit 2-way naming and the reason (room for a hypothetical future 3-way variant).

No other fields change. All `*_id`, `OutcomeMapping`, `parameterized=True`, `sport="basketball"` stay.

**Change 2 — append the new soccer canonical:**

After all existing soccer entries (just after `away_over_under_ft`), append:

```python
    # =================== Soccer — 2-way Asian Handicap ==================
    # Asian Handicap (2-way, home/away). Signed line from home's
    # perspective — line=-1.5 means home gives 1.5 goals. Both outcomes
    # live under a single signed key (same convention as the renamed
    # 2way_handicap_basketball_ft and handicap_games_tennis_match).
    #
    # The "2way_" prefix distinguishes this from a hypothetical future
    # 3way_handicap_ft (the European 1X2 handicap with draw). BetPawa
    # ships both as separate markets (id=3774 vs id=4724); Bet9ja
    # similarly ships S_AH (Asian) vs S_1X2HND (European). The 3-way
    # variant is explicitly out of scope for this release.
    #
    # Quarter lines (0.25 / 0.75 steps) work natively — the lines dict
    # accepts any float key.
    #
    # SportPesa stays None — Akamai cookie unavailable at probe time;
    # same precedent as the 0.14.0 markets.
    MarketMapping(
        canonical_id="2way_handicap_ft",
        name="2-Way Asian Handicap - Full Time",
        betpawa_id="3774",
        sportybet_id="16",        # SR-code mirror; probe confirms
        bet9ja_key="S_AH",
        betway_id=None,           # locked-in via probe (TBD literal)
        msport_id="16",           # SR-code mirror; probe confirms
        sportpesa_id=None,        # NOT PROBED — Akamai cookie unavailable
        betika_id="16",           # mirror; probe confirms
        sport="soccer",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
                betway="__HOME__",
                msport="Home",
                sportpesa="1",
                betika="1",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__POS_2__",
                msport="Away",
                sportpesa="2",
                betika="2",
            ),
        },
        parameterized=True,
    ),
```

### `bookmakers/betika.py` — extend `_UNIVERSAL_SUB_TYPE_IDS`

Current state (after 0.14.0): `_UNIVERSAL_SUB_TYPE_IDS = ("1", "8", "10", "18", "19", "20", "29")` (7 ids).

Add `"16"`:

```python
# Sub-type ids fanned out by get_event_markets to assemble a complete
# per-event market set. Each id maps to one canonical market in the
# built-in registry: 1=1X2, 8=Next Goal, 10=Double Chance, 16=2-Way
# Asian Handicap, 18=O/U, 19=Home O/U, 20=Away O/U, 29=BTTS.
_UNIVERSAL_SUB_TYPE_IDS = ("1", "8", "10", "16", "18", "19", "20", "29")
```

Bump the docstring count from "seven" to "eight" on `get_event_markets` and `get_markets`. Update the parametrized test in `tests/test_betika.py` that pins the expected call count to the length of this tuple.

### `src/bookieskit/__init__.py` + `pyproject.toml`

Bump `__version__` / `version` to `"0.15.0"`.

## 6. Live-probe step (gates the merge)

Mirrors 0.14.0's Phase 0. A small one-off script (`scripts/probe_2way_handicap_ft.py`) walks the 5 bookmakers needing confirmation (SportyBet, MSport, Bet9ja for sanity-check, Betway, Betika) against a current upcoming or live soccer event with rich market coverage.

The script:
1. Picks a current BetPawa upcoming or live soccer event with a SPORTRADAR widget. `marketsCount` is not reliably populated in the listings response, so the script should fetch event details for several candidates and pick the first one whose detail response contains id=3774 (Asian Handicap) — confirming the event is a top-tier match with the relevant market.
2. Extracts the SR id via the SPORTRADAR widget.
3. Per bookmaker, fetches markets and prints candidate ids/keys matching `r"asian|handi|spread"` (with team-name positional notes for Betway).
4. Writes one JSON fixture per bookmaker to `tests/fixtures/event_info/<bookmaker>/2way_handicap_ft.json`.
5. Records the resolved IDs in `tests/fixtures/event_info/RESOLVED_2way_handicap_ft.md`.

Bookmakers whose probe genuinely returns "market not exposed" stay `None` in the mapping with a one-line code comment (same precedent as the existing Betika basketball-handicap gap).

## 7. Tests

| File | New tests |
|---|---|
| `tests/test_registry.py` | (a) Update tests pinning `handicap_basketball_ft` → `2way_handicap_basketball_ft`. (b) Bump builtin count 16→17. (c) Add `test_registry_has_2way_handicap_ft` smoke test. |
| `tests/test_parser_basketball.py` | Update any `assert m.canonical_id == "handicap_basketball_ft"` assertion strings to the new id. |
| `tests/test_parser_betpawa.py` | Add `test_parse_betpawa_2way_handicap_ft_from_real_fixture` — fixture-driven if we capture one during probe, else synthetic. |
| `tests/test_parser_bet9ja.py` | Add `test_parse_bet9ja_2way_handicap_ft_from_probe_fixture` against the existing diagnostic-captured `S_AH` shape. |
| `tests/test_parser_{sportybet,msport,betway,betika}.py` | Add one fixture-driven test each (post-probe). |
| `tests/test_betika.py` | Bump expected `_UNIVERSAL_SUB_TYPE_IDS` fan-out call count 7 → 8 in the two pinned tests. |

Bookmakers whose probe shows the market is genuinely unavailable get either a `pytest.skip(...)` test (with a justification linking to the RESOLVED record) or no test at all (a registry-level None-assertion in `tests/test_registry.py` is sufficient).

## 8. Docs

### `docs/markets.md`

1. Bump count in the opening paragraph: 16 → 17 (10 soccer + 3 basketball + 4 tennis).
2. Add a row to the **Soccer (full time)** support matrix for `2way_handicap_ft` with probe-derived ✅ / `—` cells.
3. Update the **Basketball (full time)** matrix row for the renamed canonical: `handicap_basketball_ft` → `2way_handicap_basketball_ft`. Add an inline note about the renaming rationale (room for a future 3-way).
4. Update the "Handicap line convention" prose subsection to mention the new soccer canonical alongside the existing basketball/tennis ones (one-line addition; the convention itself is unchanged).

### `README.md`

1. Headline count: 16 → 17 markets. Soccer count: 9 → 10.
2. Add row to the soccer table for `2way_handicap_ft`.
3. Update the basketball table row for `2way_handicap_basketball_ft`.
4. If the README contains any inline mention of `handicap_basketball_ft` (e.g. in code examples), update.
5. Limitations / known gaps: add a one-line note if the probe surfaces any bookmaker that genuinely doesn't expose the market (mirroring 0.14.0's Bet9ja team-O/U entry).

### `CHANGELOG.md`

New `## [0.15.0] - 2026-05-22` section. Subheaders:

- **Renamed** — `handicap_basketball_ft` → `2way_handicap_basketball_ft` (breaking change for downstream consumers pinning the old id; reason: room for a potential future 3-way variant). Both names will NOT be kept as aliases; consumers must update.
- **Added** — `2way_handicap_ft` soccer canonical (Asian Handicap, 2-way, signed lines). Per-bookmaker coverage list from the RESOLVED record.
- **Changed** — `Betika._UNIVERSAL_SUB_TYPE_IDS` extended 7→8 (added `16`). `Betika.get_markets()` now surfaces the new soccer canonical.

## 9. Summary table

| Surface | Change |
|---|---|
| `markets/types.py` | none |
| `markets/registry.py` | none |
| `markets/parser.py` | none |
| `markets/builtin_mappings.py` | rename basketball canonical_id; append `2way_handicap_ft` MarketMapping |
| `bookmakers/betika.py` | `_UNIVERSAL_SUB_TYPE_IDS` 7→8 (add `"16"`); docstring counts bumped |
| `__init__.py` / `pyproject.toml` | version 0.14.0 → 0.15.0 |
| `scripts/probe_2way_handicap_ft.py` | new probe harness |
| `tests/fixtures/event_info/<bookmaker>/2way_handicap_ft.json` | captured fixtures (one per probed bookmaker) |
| `tests/fixtures/event_info/RESOLVED_2way_handicap_ft.md` | decision record |
| `tests/test_registry.py` | rename refs + count bump + new smoke test |
| `tests/test_parser_basketball.py` | canonical_id assertion updates |
| `tests/test_parser_*.py` | one new fixture test per confirmed bookmaker |
| `tests/test_betika.py` | sub_type_id fan-out call-count bump 7→8 |
| `docs/markets.md` | count 16→17; soccer +1 row; basketball row rename; convention prose |
| `README.md` | count bumps + table updates |
| `CHANGELOG.md` | new 0.15.0 section (Renamed + Added + Changed) |

## 10. Migration note for downstream consumers

The `handicap_basketball_ft` → `2way_handicap_basketball_ft` rename is a hard break. Any code pinning the old `canonical_id` string (e.g. for filtering / matching by id) must be updated. No deprecation alias is provided — the version bump 0.14.0 → 0.15.0 is the signal. The CHANGELOG entry will document this explicitly under the **Renamed** subheader.
