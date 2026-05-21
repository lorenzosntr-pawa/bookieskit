# Next Goal + Team Over/Under markets — design

**Status:** Design approved 2026-05-21. Awaiting implementation plan.
**Scope:** Add three new canonical soccer markets to `bookieskit`'s built-in registry — `next_goal_ft` (covers both prematch "1st Goal" and live "Nth Goal"), `home_over_under_ft`, and `away_over_under_ft` — mapped across all 7 supported bookmakers. Includes a small extension to the SportyBet/MSport specifier parser (`goalnr=` key) and a new Betway parser feature (`[Home Team]` / `[Away Team]` placeholder substitution).
**Out of scope:** Changes to `NormalizedMarket` or `OutcomeMapping` shapes. Half-time variants. Per-player markets. Generalising the team-name placeholder feature beyond Betway. Splitting `next_goal_ft` into separate prematch / live canonicals.
**Target version bump:** 0.13.1 → 0.14.0 (additive feature, no breaking changes).

## 1. Motivation

The current registry covers six universal soccer markets (`1x2_ft`, `over_under_ft`, `btts_ft`, `double_chance_ft`, `1x2_1up_ft`, `1x2_2up_ft`). Three more are top-coverage soccer markets that every bookmaker we support exposes in some form:

- **1st Goal / Next Goal** ("which team scores the next goal?") is offered prematch as "1st Goal" and during live play becomes "2nd Goal", "3rd Goal", etc. as goals are scored. Bookmakers ship the goal number as a specifier (SportyBet: `goalnr=N`; BetPawa: `formattedHandicap="N"`).
- **Home Team Over/Under** and **Away Team Over/Under** ("over/under N goals scored by one specific team") are shipped by every bookmaker as **two separate market IDs** — one per team. Identical structure to the existing `over_under_ft`, just per-team.

Adding these three closes obvious gaps in the canonical soccer coverage and gives downstream consumers a uniform shape for arbitrage / EV analysis across these high-volume markets.

## 2. Decisions taken at brainstorm

| Decision | Outcome |
|---|---|
| 1st Goal outcomes | 3-way: `home` / `none` / `away`. Matches SR convention and what every bookmaker actually ships. |
| 1st/Nth Goal goal-number model | **Parameterized market, line = goal number** (1.0 = 1st, 2.0 = 2nd, ...). Reuses the existing `lines: dict[float, list[Outcome]]` infrastructure with zero changes to `NormalizedMarket`. Prematch always has `lines = {1.0: [home, none, away]}`; live can carry multiple goal numbers under one canonical id. |
| Team O/U shape | **Two canonicals:** `home_over_under_ft` + `away_over_under_ft`. Mirrors the wire shape on every bookmaker (each ships two distinct market IDs, one per team). Avoids inventing nested-line types or four-outcome-per-line shapes. |
| Betway team-name placeholders | **Literal placeholder substitution.** Set `betway_id="[Home Team] Total Goals"` / `betway_id="[Away Team] Total Goals"` in the canonical mappings. At parse-time, a thin `_TeamScopedBetwayRegistry` wrapper substitutes the literal tokens with the actual team names from `sportEvent.homeTeam` / `awayTeam`. Mirrors the existing `_SportScopedRegistry` shape — re-scope a registry view without mutating the underlying object. |
| Coverage scope | **All 7 bookmakers fully mapped in v1.** Live-probe Bet9ja, MSport, SportPesa, Betika, Betway against a real fixture before merging; lock IDs into the registry; mark a per-bookmaker field `None` only where the bookmaker genuinely does not expose that market (mirrors the existing Betika-basketball-handicap None convention). |

## 3. Empirically confirmed wire shapes

Captured from existing fixtures under `tests/fixtures/event_info/`. The IDs below are locked-in for SportyBet and BetPawa; the other 5 bookmakers ship as `🔍 to-probe` placeholders in the initial registry entries and become locked-in values after the live-probe step.

### `next_goal_ft`

**SportyBet** — `tests/fixtures/event_info/sportybet/prematch.json` lines 792-834:
```json
{
  "id": "8",
  "specifier": "goalnr=1",
  "name": "Next Goal",
  "desc": "1st Goal",
  "outcomes": [
    {"desc": "Home", "odds": "1.93", ...},
    {"desc": "None", "odds": "11.00", ...},
    {"desc": "Away", "odds": "2.20", ...}
  ]
}
```

**BetPawa** — `tests/fixtures/event_info/betpawa/prematch.json` lines 253-329:
```json
{
  "marketType": {
    "id": "28000224",
    "name": "{handicap} Goal",
    "displayName": "Next Goal (Goal {handicap})"
  },
  "row": [{
    "handicap": 4,
    "formattedHandicap": "1",
    "prices": [
      {"name": "1", "price": 1.94, ...},
      {"name": "None", "displayName": "No Goal", "price": 11.04, ...},
      {"name": "2", "price": 2.20, ...}
    ]
  }]
}
```

### `home_over_under_ft`

**SportyBet** — same prematch fixture, lines 1295-1469: `id=19`, `name="Home O/U"`, `specifier="total=X.X"`, outcomes `Over X.X` / `Under X.X`.

**BetPawa** — same prematch fixture, lines 579-715: `marketType.id=5006`, `name="Total Score Over/Under - FT - Home Team"`, lines via `handicap`/4 (the existing parameterized parser already handles this), outcomes `name="Over"` / `name="Under"`.

### `away_over_under_ft`

**SportyBet** — lines 1435-1469: `id=20`, `name="Away O/U"`, otherwise identical to home.

**BetPawa** — lines 716+: `marketType.id=5003`, `name="Total Score Over/Under - FT - Away Team"`, otherwise identical to home.

### Betway placeholder shape (inferred from basketball/tennis fixtures)

`tests/fixtures/event_info/betway/basketball.json` lines 696 and 749 confirm Betway uses literal team-name brackets in market names:
```json
{"name": "[Home Team] Total (incl. overtime)"},
{"name": "[Away Team] Total (incl. overtime)"}
```

The soccer equivalent is expected to follow the same shape (`"[Home Team] Total Goals"` / `"[Away Team] Total Goals"`) and will be confirmed during the live-probe step.

## 4. Per-bookmaker registry plan

| Canonical | BetPawa | SportyBet | Bet9ja | Betway | MSport | SportPesa | Betika |
|---|---|---|---|---|---|---|---|
| `next_goal_ft` | `28000224` ✅ | `8` ✅ | 🔍 to-probe | 🔍 to-probe | 🔍 to-probe | 🔍 to-probe | 🔍 to-probe |
| `home_over_under_ft` | `5006` ✅ | `19` ✅ | 🔍 to-probe | `[Home Team] Total Goals` 🔍 | 🔍 to-probe | 🔍 to-probe | 🔍 to-probe |
| `away_over_under_ft` | `5003` ✅ | `20` ✅ | 🔍 to-probe | `[Away Team] Total Goals` 🔍 | 🔍 to-probe | 🔍 to-probe | 🔍 to-probe |

Probe results that genuinely return "market not exposed" land as `None` with a one-line code comment, following the existing Betika-basketball-handicap precedent.

## 5. Code changes

### `markets/types.py` — none

The existing `MarketMapping` / `OutcomeMapping` fields are sufficient. The Betway team-name placeholder lives in the **value** of `betway_id`; no new field needed.

### `markets/registry.py` — none

The three new mappings go into `BUILTIN_MAPPINGS` like any other entry. The flat per-platform indexes and the `(platform, sport, id)` sport-scoped index work as-is.

### `markets/builtin_mappings.py` — +3 entries

Appended to `BUILTIN_MAPPINGS`:

```python
MarketMapping(
    canonical_id="next_goal_ft",
    name="Next Goal - Full Time",
    betpawa_id="28000224",
    sportybet_id="8",
    bet9ja_key=None,          # locked-in via probe
    # msport_id="8" is a tentative SR-code mirror (MSport already uses
    # "8" for several SR-codes elsewhere in the registry); probe confirms
    # or replaces.
    msport_id="8",
    betway_id=None,           # locked-in via probe
    sportpesa_id=None,        # locked-in via probe
    betika_id=None,           # locked-in via probe
    sport="soccer",
    outcomes={
        "home": OutcomeMapping(
            canonical_name="home",
            betpawa="1", sportybet="Home", bet9ja="1",
            betway="__HOME__", msport="Home",
            sportpesa="1", betika="1",
        ),
        # The none-outcome strings for bet9ja / sportpesa / betika are
        # tentative best-guesses (SR convention "X"); probe confirms or
        # replaces.
        "none": OutcomeMapping(
            canonical_name="none",
            betpawa="None", sportybet="None", bet9ja="X",
            betway="__POS_2__", msport="None",
            sportpesa="X", betika="None",
        ),
        "away": OutcomeMapping(
            canonical_name="away",
            betpawa="2", sportybet="Away", bet9ja="2",
            betway="__AWAY__", msport="Away",
            sportpesa="2", betika="2",
        ),
    },
    parameterized=True,
),
MarketMapping(
    canonical_id="home_over_under_ft",
    name="Over/Under Home Team - Full Time",
    betpawa_id="5006",
    sportybet_id="19",
    bet9ja_key=None,                       # locked-in via probe
    betway_id="[Home Team] Total Goals",   # placeholder substituted at parse-time; format confirmed via probe
    msport_id="19",                        # tentative SR-code mirror; probe confirms
    sportpesa_id=None,                     # locked-in via probe
    betika_id=None,                        # locked-in via probe
    sport="soccer",
    outcomes={
        "over": OutcomeMapping(
            canonical_name="over",
            betpawa="Over", sportybet="Over", bet9ja="O",
            betway="Over", msport="Over",
            sportpesa="OV", betika="Over",
        ),
        "under": OutcomeMapping(
            canonical_name="under",
            betpawa="Under", sportybet="Under", bet9ja="U",
            betway="Under", msport="Under",
            sportpesa="UN", betika="Under",
        ),
    },
    parameterized=True,
),
MarketMapping(
    canonical_id="away_over_under_ft",
    name="Over/Under Away Team - Full Time",
    betpawa_id="5003",
    sportybet_id="20",
    bet9ja_key=None,                       # locked-in via probe
    betway_id="[Away Team] Total Goals",   # placeholder substituted at parse-time; format confirmed via probe
    msport_id="20",                        # tentative SR-code mirror; probe confirms
    sportpesa_id=None,                     # locked-in via probe
    betika_id=None,                        # locked-in via probe
    sport="soccer",
    outcomes={  # identical over/under shape to home_over_under_ft
        ...
    },
    parameterized=True,
),
```

The tentative `msport_id` values (`"8"` / `"19"` / `"20"`) mirror MSport's existing SR-code convention (it already uses `"219"` for basketball ML, `"225"` for basketball O/U, etc.). The probe step confirms or replaces them.

### `markets/parser.py` — two targeted changes

**Change 1 — extend `_extract_line_from_specifier` to recognise `goalnr=`:**

```python
def _extract_line_from_specifier(specifier: str) -> float | None:
    for part in specifier.split("|"):
        if "=" in part:
            key, value = part.split("=", 1)
            if key in ("total", "hcp", "goalnr"):   # +goalnr
                try:
                    return float(value)
                except ValueError:
                    continue
    return None
```

Shared by SportyBet and MSport. The existing `parameterized_groups` dict-of-lists infrastructure handles the "3 outcomes per line" shape without modification (it iterates outcomes inside the entry; there's no assumption that N=2).

**Change 2 — new `_TeamScopedBetwayRegistry` wrapper + hook in `_parse_betway`:**

```python
class _TeamScopedBetwayRegistry:
    """Wraps a MarketRegistry to substitute [Home Team] / [Away Team]
    placeholders in Betway mapping keys with the actual team names from
    the current event payload. Used only for the duration of one
    _parse_betway call.

    Mirrors _SportScopedRegistry: re-scope a view of the registry
    without mutating the underlying indexes.
    """

    _PLACEHOLDER_HOME = "[Home Team]"
    _PLACEHOLDER_AWAY = "[Away Team]"

    def __init__(self, inner, home_team: str, away_team: str) -> None:
        self._inner = inner
        self._home = home_team
        self._away = away_team

    def get_by_platform_id(self, platform, platform_id, sport=None):
        # Direct lookup first — covers every non-team-named market.
        result = self._inner.get_by_platform_id(
            platform, platform_id, sport=sport,
        )
        if result is not None:
            return result
        if platform != "betway":
            return None
        # Fallback: iterate mappings that carry a placeholder token (at
        # most a handful) and try the substituted form. O(n_team_markets),
        # not O(all_markets).
        for mapping in self._inner.list_markets():
            bid = mapping.betway_id
            if not bid or (
                self._PLACEHOLDER_HOME not in bid
                and self._PLACEHOLDER_AWAY not in bid
            ):
                continue
            substituted = (
                bid.replace(self._PLACEHOLDER_HOME, self._home)
                   .replace(self._PLACEHOLDER_AWAY, self._away)
            )
            if substituted == platform_id:
                return mapping
        return None

    def list_markets(self):
        return self._inner.list_markets()

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _parse_betway(response, registry, _mode="off"):
    sport_event = response.get("sportEvent", {})
    home_team = str(sport_event.get("homeTeam", ""))
    away_team = str(sport_event.get("awayTeam", ""))
    if home_team and away_team:
        registry = _TeamScopedBetwayRegistry(
            registry, home_team, away_team,
        )
    # ...rest of the function unchanged
```

Properties of this design:
- **The direct lookup is unchanged.** Non-team-named Betway markets (the vast majority) take the fast path and never enter the placeholder loop.
- **Composes with `_SportScopedRegistry`.** When both wrappers are needed (e.g. a future Betway basketball team-total), wrap inner → sport → team; each layer adds its own scoping.
- **Empty team names skip wrapping.** Defensive; should never happen on a real Betway event-markets payload, but the safe default is "no substitution".
- **Iterates `list_markets()` only on miss.** The hot path is one dict lookup; the placeholder scan only runs when the direct lookup returns None.

### No other parser changes

- `_parse_betpawa` — `formattedHandicap` already drives `lines` keys; `name="1"` / `"None"` / `"2"` match the new `OutcomeMapping.betpawa` strings; `name="Over"` / `"Under"` match the team-O/U strings. Zero changes.
- `_parse_bet9ja` — `_parse_bet9ja_key` already splits `S_KEY@LINE_OUTCOME`. As long as the live-probed key matches `bet9ja_key`, the existing flow works.
- `_parse_sportpesa`, `_parse_betika` — same conclusion: `id` / `sub_type_id`-keyed lookups already handle the new markets once the IDs are registered.

## 6. Live-probe step (gates the merge)

Mirrors the discovery work done for the basketball and tennis builtins. A small one-off script (`examples/probe_next_goal_and_team_ou.py`) walks all 7 bookmakers against a single live (or near-live) soccer event and prints, per bookmaker:

1. Every raw market id / key / name on the event.
2. Filtered candidates whose name or key contains `"Next Goal"` / `"1st Goal"` / `"Home Total Goals"` / `"Away Total Goals"` / `"Home O/U"` / `"Away O/U"` (and common aliases).
3. The exact outcome strings on each candidate.

The output of that probe locks in the `🔍 to-probe` placeholder IDs in the registry entries. Bookmakers that genuinely don't expose a market keep the `None` value with a one-line comment explaining why (e.g. `bet9ja_key=None,  # Bet9ja does not currently expose Next Goal at full match level`).

Captured fixtures from the probe become test fixtures under `tests/fixtures/event_info/<bookmaker>/`.

## 7. Tests

| File | New tests |
|---|---|
| `tests/test_registry.py` | 3 — `get_by_canonical` smoke tests for each new canonical id. |
| `tests/test_parser_betpawa.py` | 3 — `next_goal_ft`, `home_over_under_ft`, `away_over_under_ft` against existing `betpawa/prematch.json`. |
| `tests/test_parser_sportybet.py` | 3 — same against existing `sportybet/prematch.json`; +1 for `_extract_line_from_specifier` recognising `goalnr=`. |
| `tests/test_parser_msport.py` | 3 — fixture-backed once MSport is live-probed. |
| `tests/test_parser_bet9ja.py` | up to 3 — one per market that Bet9ja exposes. |
| `tests/test_parser_betway.py` | 2 + 1 — `home_over_under_ft` and `away_over_under_ft` against a Betway fixture (resolves `[Home Team]` placeholder); +1 targeted unit test for `_TeamScopedBetwayRegistry`. `next_goal_ft` if probed. |
| `tests/test_parser_sportpesa.py` | up to 3. |
| `tests/test_parser_betika.py` | up to 3. |

Tests for markets a bookmaker genuinely doesn't expose: an `xfail_if_unmapped`-style assertion or a simple "registry entry has bookmaker_id=None, parser returns no market" smoke test, mirroring how the existing Betika basketball-handicap gap is verified.

## 8. Docs

### `docs/markets.md`

1. Bump the canonical-market count in the opening paragraph and the per-sport count summary: 13 → 16, soccer 6 → 9.
2. Add three rows to the **Soccer (full time)** support matrix, with ✅ / — populated from probe results.
3. Add a short subsection under Soccer explaining the `next_goal_ft` line semantic ("line = goal number, 1.0 prematch, ≥1.0 live as goals are scored") with a worked example.
4. Add a Betway-specific note under the "Position sentinels (Betway)" section (or a new sibling section) explaining the `[Home Team]` / `[Away Team]` placeholder convention, pointing to `_TeamScopedBetwayRegistry`.

### `README.md`

1. Headline: "13 markets ship as builtins" → "16 markets ship as builtins across 3 sports (9 soccer + 3 basketball + 4 tennis)". Same edit in any other counts elsewhere in README.
2. Soccer section under "Built-in markets" — append three rows.
3. Limitations / known gaps — if any bookmaker comes up genuinely unmapped after probing, document it with one line per gap (mirroring the existing 1Up/2Up unmapped-bookmaker note).

### `CHANGELOG.md`

New entry under **0.14.0**:
- Added `next_goal_ft`, `home_over_under_ft`, `away_over_under_ft` canonical soccer markets (mapped across all 7 bookmakers where exposed).
- Betway parser now resolves `[Home Team]` / `[Away Team]` literal placeholders against the event payload's team names.
- `_extract_line_from_specifier` now recognises `goalnr=` alongside `total=` and `hcp=`.

## 9. Out of scope

- Modifying `NormalizedMarket` or `OutcomeMapping` shapes.
- Generalising the team-name placeholder beyond Betway. Other bookmakers don't use this pattern; we'd be adding speculative abstraction.
- Splitting `next_goal_ft` into separate `1st_goal_ft` (prematch) and `nth_goal_ft` (live) canonicals. **One canonical with goal-number-as-line** is strictly simpler and matches the wire shape on every bookmaker we've checked.
- Half-time variants (`next_goal_1h`, `home_over_under_1h`, etc.). Could be added later following the same pattern; not requested here.
- Per-player goal markets (1st goalscorer, anytime goalscorer). Different shape; out of scope.

## 10. Summary table

| Surface | Change |
|---|---|
| `markets/types.py` | none |
| `markets/registry.py` | none |
| `markets/builtin_mappings.py` | +3 `MarketMapping` entries |
| `markets/parser.py` | (a) `+goalnr` in `_extract_line_from_specifier`; (b) new `_TeamScopedBetwayRegistry` class; (c) wrap `registry` in `_parse_betway` |
| Tests | +3 in `test_registry.py`; +3 per bookmaker (×7); +1 specifier test; +1 Betway placeholder unit test |
| `docs/markets.md` | counts, soccer table rows, two new subsections |
| `README.md` | counts, soccer table rows, gaps section if any |
| `CHANGELOG.md` | one entry under 0.14.0 |
| Live probe | one-off script that locks-in the `🔍 to-probe` IDs for Bet9ja / MSport / SportPesa / Betika / Betway before merge |
