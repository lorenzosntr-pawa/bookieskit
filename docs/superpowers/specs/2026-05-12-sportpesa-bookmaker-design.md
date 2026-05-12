# SportPesa bookmaker — design

**Status:** Design approved 2026-05-12. Awaiting implementation plan.
**Scope:** Add SportPesa as the 6th supported bookmaker in bookieskit, with full parity (sports, tournaments, events, event detail, markets, SR-id resolution, event-info, normalized markets, tests, docs).
**Out of scope:** Refactoring the bookmaker-dispatch pattern into a plugin registry. Adding SportPesa-only markets beyond the 4 universal ones. Solving Akamai Bot Manager challenges inside the client.

## 1. Motivation

bookieskit ships clients for 5 African sportsbooks normalized via SportRadar ids. SportPesa is the most-used Kenyan operator and the most-used Tanzanian operator — adding it raises cross-bookmaker coverage materially in two existing supported markets (ke, tz).

## 2. Decisions taken at brainstorm

| Decision | Outcome |
|---|---|
| Country domains | `ke` and `tz`. No `za`. |
| Live vs prematch | Both, parity with the other 5 clients. |
| Canonical markets in v1 | The 4 universal markets only: `1x2_ft`, `over_under_ft`, `btts_ft`, `double_chance_ft`. No `1x2_1up_ft` / `1x2_2up_ft`. |
| Bot-challenge handling | Document the limitation. No in-client warming/cookie harvesting. Same posture as the existing "BetPawa SR-id reverse search not implemented" gap. |
| Examples / scripts | Update README + supported-bookmakers table. Add SportPesa to `examples/odds_for_sr_id.py`, `count_5bookies.py`, `odds_from_betpawa_id.py`, `odds_for_betpawa_competition.py` (file names stay — no rename). **Left untouched (legacy / curated subsets):** `examples/monitor_competitions.py` (curated 4-bookmaker subset, MSport already excluded by design), `examples/test_live_flow.py` and `examples/audit_full.py` (3-bookmaker legacy from pre-Betway/MSport era), `examples/final_audit.py` / `examples/full_audit_4bookies.py` / `examples/full_audit_v2.py` (4-bookmaker legacy from pre-MSport era). These are historical artifacts kept for git context; canonical example set is the four scripts named at the start of this row. |
| Probability mode | Fixture-conditional. Spec wires the branches; implementation prunes the branches the payload doesn't expose. |
| Architectural shape | Option A — symmetric clone of the existing per-bookmaker pattern. No plugin refactor in this work. |

## 3. Confirmed endpoints (from user-supplied cURLs)

Two endpoints are confirmed verbatim. Every other URL in this spec is **fixture-resolved** — implementation captures the real path against a warmed session before merge.

| Confirmed endpoint | Purpose |
|---|---|
| `GET /api/upcoming/games?gameId={id}&sportId=1&section=markets&pag_count=1` | Event detail (carries SR id, kickoff, participants). |
| `GET /api/games/markets?games={id}&markets=all` | Full markets payload for one game. |

Base host: `www.ke.sportpesa.com` for `ke`, `www.tz.sportpesa.com` for `tz`. Country is honoured via subdomain — no `countryCode` query param.

## 4. Architecture

Six surfaces change in lockstep. The shape is identical to the work already done five times (Betway / MSport are the closest siblings).

```
src/bookieskit/
├── __init__.py                              [+ SportPesa export]
├── config.py                                [+ SPORTPESA_MAX_CONCURRENT, SPORTPESA_REQUEST_DELAY]
├── event_info.py                            [+ _kickoff/_participants/_live_info_sportpesa + dispatch rows]
├── bookmakers/
│   └── sportpesa.py                         [NEW — SportPesa(BaseBookmaker)]
├── markets/
│   ├── types.py                             [+ sportpesa field on OutcomeMapping, sportpesa_id on MarketMapping]
│   ├── registry.py                          [+ _by_sportpesa index, add() kwarg, get_by_platform_id dispatch]
│   ├── builtin_mappings.py                  [+ sportpesa_id + sportpesa= on the 4 universal mappings]
│   └── parser.py                            [+ _parse_sportpesa branch and helpers, dispatch row]
└── matching/
    ├── extractor.py                         [+ _extract_sportpesa + dispatch row]
    └── matcher.py                           [+ sportpesa field on MatchedEvent + branch in match_events]

tests/
├── test_sportpesa.py                        [NEW — client wiring + per-endpoint @respx.mock tests]
├── test_parser_sportpesa.py                 [NEW — parser tests]
├── test_extractor.py                        [+ sportpesa cases]
├── test_event_info.py                       [+ sportpesa cases + extend parametrize lists at L312 & L344]
├── test_registry.py                         [+ sportpesa lookup tests]
├── test_convenience.py                      [+ SportPesa.get_markets routes to markets endpoint]
├── test_matcher.py                          [+ sportpesa branch coverage in match_events]
├── test_probability.py                      [+ extend parametrize list at L63 to include "sportpesa"]
├── test_types.py                            [+ mirror existing *_msport_* tests for sportpesa]
└── fixtures/event_info/sportpesa/
    ├── prematch.json                        [NEW — captured]
    └── live.json                            [NEW — captured]

docs/
├── sportpesa.md                             [NEW]
├── markets.md                               [+ SportPesa column in platform-id table]
├── matching.md                              [+ SportPesa SR-id extraction paragraph]
└── examples.md                              [refresh if it mentions a fixed bookmaker count]

examples/
├── odds_for_sr_id.py                        [+ SportPesa fan-out]
├── count_5bookies.py                        [+ SportPesa fan-out, file name unchanged]
├── odds_from_betpawa_id.py                  [+ SportPesa fan-out]
└── odds_for_betpawa_competition.py          [+ SportPesa fan-out]

scripts/
└── capture_event_info_fixtures.py           [+ save sportpesa prematch + live]

pyproject.toml                               [version 0.4.0 → 0.5.0; description "6 African sportsbooks (..., SportPesa)"]
README.md                                    [bookmaker count 5→6, table row, markets table column, Akamai gap]
```

## 5. Component-level design

### 5.1 Client — `src/bookieskit/bookmakers/sportpesa.py`

```python
class SportPesa(BaseBookmaker):
    DOMAINS = {
        "ke": "https://www.ke.sportpesa.com",
        "tz": "https://www.tz.sportpesa.com",
    }
    DEFAULT_HEADERS = {
        "accept": "application/json, text/plain, */*",
        "x-requested-with": "XMLHttpRequest",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/144.0.0.0 Safari/537.36"
        ),
    }
    MAX_CONCURRENT = SPORTPESA_MAX_CONCURRENT   # 15
    REQUEST_DELAY = SPORTPESA_REQUEST_DELAY     # 0.05
    NAME = "SportPesa"
    PLATFORM_KEY = "sportpesa"

    def _build_headers(self) -> dict[str, str]:
        headers = dict(self.DEFAULT_HEADERS)
        headers["x-app-timezone"] = (
            "Africa/Dar_es_Salaam" if self._country == "tz" else "Africa/Nairobi"
        )
        return headers
```

**Methods** (all async, all returning raw JSON dict unless noted; default `live=False`):

| Method | HTTP | Path | Source of truth |
|---|---|---|---|
| `get_sports(live=False)` | GET | `/api/sports` (prematch) / `/api/live/sports` (live) | **Fixture-resolved.** If the API uses a different path family (e.g. an embedded list under `/api/upcoming/categories?sportId=…`), the client falls back to that during implementation. |
| `get_countries(sport_id="1", live=False)` | GET | `/api/upcoming/categories?sportId={sport_id}` (or `/api/live/...`) | **Fixture-resolved.** |
| `get_tournaments(sport_id="1", category_id=None, live=False)` | GET | `/api/upcoming/competitions?sportId={sport_id}[&categoryId={category_id}]` | **Fixture-resolved.** |
| `get_events(sport_id="1", competition_id=None, live=False, page=0, per_page=50)` | GET | `/api/upcoming/games` or `/api/live/games` with `sportId`, `competitionId?`, `page?`, `per_page?` (param names fixture-resolved) | **Fixture-resolved.** |
| `get_event_detail(event_id, live=False)` | GET | `/api/upcoming/games?gameId={id}&sportId=1&section=markets&pag_count=1` (live variant `/api/live/games?gameId=...`) | ✅ **Confirmed (prematch).** Live variant fixture-resolved. |
| `get_event_markets(event_id)` | GET | `/api/games/markets?games={id}&markets=all` | ✅ **Confirmed.** |
| `get_markets(event_id, registry=None) -> list[NormalizedMarket]` | (calls `get_event_markets`) | — | Overrides base: markets feed is a separate endpoint, same pattern as Betway. |
| `get_sportradar_id(event_id, live=False) -> str \| None` | (calls `get_event_detail`) | — | Inherits the base flow: fetch detail, run extractor. No identity short-circuit (unlike Betway). |

Country code:
- `ke` → `Africa/Nairobi` timezone header, `www.ke.sportpesa.com` host.
- `tz` → `Africa/Dar_es_Salaam` timezone header, `www.tz.sportpesa.com` host.
- Anything else → `UnsupportedCountryError`.

Rate-limit defaults (`config.py`):
```python
SPORTPESA_MAX_CONCURRENT = 15   # Akamai-conservative; mirror Bet9ja's stance
SPORTPESA_REQUEST_DELAY = 0.05  # 50ms between requests
```

### 5.2 SR-id extractor — `src/bookieskit/matching/extractor.py`

```python
def _extract_sportpesa(response: dict) -> str | None:
    games = response.get("data") or response.get("games") or []
    if not isinstance(games, list) or not games:
        return None
    game = games[0]
    info = game.get("additional_info") or {}
    sr = (
        info.get("sportradar_id")
        or info.get("betradar_id")
        or info.get("sr_id")
        or game.get("external_id")
    )
    if not sr:
        return None
    return _strip_sr_prefix(str(sr))
```

Added to the `extractors` dispatch dict under key `"sportpesa"`. Total function — never raises; returns `None` for any malformed input or absent SR id.

**Fixture-resolved:** the exact key holding the SR id. The function as written probes four candidates; implementation deletes the dead branches once the real key is confirmed against the captured prematch payload.

### 5.3 Parser — `src/bookieskit/markets/parser.py`

```python
def _parse_sportpesa(response, registry, mode):
    results: list[NormalizedMarket] = []
    data = response.get("data") or []
    if not isinstance(data, list) or not data:
        return []
    game = data[0]
    markets = game.get("markets", [])
    parameterized_groups: dict[str, list[dict]] = {}
    for md in markets:
        market_id = str(md.get("id", ""))
        mapping = registry.get_by_platform_id("sportpesa", market_id)
        if mapping is None:
            continue
        if mapping.parameterized:
            parameterized_groups.setdefault(market_id, []).append(md)
        else:
            results.append(_parse_sportpesa_simple(md, mapping, mode))
    for market_id, entries in parameterized_groups.items():
        mapping = registry.get_by_platform_id("sportpesa", market_id)
        if mapping:
            results.append(_parse_sportpesa_parameterized(entries, mapping, mode))
    return results
```

Added to the `parsers` dispatch under `"sportpesa"`. Helpers `_parse_sportpesa_simple` / `_parse_sportpesa_parameterized` mirror the SportyBet / MSport helpers with three platform-specific differences:

1. **Outcome name:** read from `selections[].name`. Outcome resolver `_resolve_outcome_sportpesa` does exact match against `OutcomeMapping.sportpesa`, then a prefix-match fallback (mirrors SportyBet/MSport — handles `"Over 2.5"` matching `"Over"`).
2. **Odds:** `float(str(selection["odds"]))` — odds are string-typed (like MSport).
3. **Parameterized line:** read `special_bet_value` (preferred) or fall back to extracting from `name` via a per-platform helper. **Fixture-resolved** — the actual key is one of the SportPesa-documented variants (`special_bet_value`, `special_bet_values`, or a value embedded in the selection name).

Probability extraction is **fixture-conditional**:

- If `selections[].probability` exists → populate `Outcome.true_probability` when `mode in ("true", "with_void")`.
- If `selections[].void_probability` (or similarly-named) exists → populate `Outcome.void_probability` when `mode == "with_void"`.
- If neither exists → both fields stay `None` regardless of `mode`. Documented in the docstring exactly like the MSport/Betway behaviour.

### 5.4 Types & registry — `markets/types.py`, `markets/registry.py`

Add a SportPesa column to both dataclasses. Defaulted, so existing call sites (user-extended registries, builtin mappings, tests) continue to compile.

```python
@dataclass(frozen=True)
class OutcomeMapping:
    canonical_name: str
    betpawa: str
    sportybet: str
    bet9ja: str
    betway: str = ""
    msport: str = ""
    sportpesa: str = ""        # NEW

@dataclass(frozen=True)
class MarketMapping:
    canonical_id: str
    name: str
    betpawa_id: str | None
    sportybet_id: str | None
    bet9ja_key: str | None
    betway_id: str | None = None
    msport_id: str | None = None
    sportpesa_id: str | None = None   # NEW
    outcomes: dict[str, OutcomeMapping] = field(default_factory=dict)
    parameterized: bool = False
```

`MarketRegistry`:

```python
self._by_sportpesa: dict[str, MarketMapping] = {}
# in _register:
if mapping.sportpesa_id:
    self._by_sportpesa[mapping.sportpesa_id] = mapping
# in add():
def add(..., sportpesa_id: str | None = None, ...): ...
# in get_by_platform_id():
index = {
    "betpawa": self._by_betpawa,
    "sportybet": self._by_sportybet,
    "bet9ja": self._by_bet9ja,
    "betway": self._by_betway,
    "msport": self._by_msport,
    "sportpesa": self._by_sportpesa,   # NEW
}.get(platform, {})
```

### 5.5 Builtin mappings — `markets/builtin_mappings.py`

Only the 4 universal markets get SportPesa fields. The 1Up / 2Up markets get `sportpesa_id=None` and `sportpesa=""` on every outcome — same posture used for MSport on those markets.

Best-evidence starting values (SportPesa is fed by Sportradar, so its market ids historically match the SR canonical ids that SportyBet and MSport publish):

| Canonical market | `sportpesa_id` | Outcome canonicals → `sportpesa` value |
|---|---|---|
| `1x2_ft` | `"1"` | `home="1"`, `draw="X"`, `away="2"` |
| `over_under_ft` | `"18"` | `over="Over"`, `under="Under"` |
| `btts_ft` | `"29"` | `yes="Yes"`, `no="No"` |
| `double_chance_ft` | `"10"` | `home_draw="1X"`, `draw_away="X2"`, `home_away="12"` |
| `1x2_1up_ft` | `None` | all `""` |
| `1x2_2up_ft` | `None` | all `""` |

**Fixture-resolved before merge.** If SportPesa's outcome names differ (e.g. `"Home"` / `"Draw"` / `"Away"` rather than `"1"` / `"X"` / `"2"`), implementation rebinds the strings against the captured markets fixture and confirms by running `test_parser_sportpesa.py`.

### 5.6 Event-info extractors — `event_info.py`

Three new functions plus three dispatch-table rows. Full source in section 5 of the brainstorming transcript; key behaviours:

| Function | Returns | Source fields (candidate list) |
|---|---|---|
| `_kickoff_sportpesa` | tz-aware UTC `datetime` or `None` | `data[0].date` (epoch seconds) → `data[0].start_time` (ISO string) |
| `_participants_sportpesa` | `Participants(home, away)` | `data[0].home_team` / `away_team` → `data[0].competitors[0/1].name` |
| `_live_info_sportpesa` | `LiveInfo(minute, period, score_home, score_away)` | `data[0].live_info` or `data[0].scoreboard`; minute from `match_time`/`minute`, period from `period`/`status`, score from `score` (`"H:A"`) or `home_score`/`away_score` |

All total — never raise. `_live_info_sportpesa` short-circuits to `_EMPTY_LIVE_INFO` when `mode == "prematch"` or when auto-detecting and no live block is present.

**Fixture-resolved:** every "or" fallback is a hypothesis. Implementation captures both `prematch.json` and `live.json` (via the updated `scripts/capture_event_info_fixtures.py`) and prunes the parser to the one branch that's real — no permanent compatibility shims.

### 5.7 Matcher — `src/bookieskit/matching/matcher.py`

`MatchedEvent` is a dataclass with one `dict | None`-typed field per supported platform. Adding SportPesa means a new field and a new branch in `match_events`:

```python
@dataclass
class MatchedEvent:
    sportradar_id: str
    betpawa: dict | None = None
    sportybet: dict | None = None
    bet9ja: dict | None = None
    betway: dict | None = None
    msport: dict | None = None
    sportpesa: dict | None = None   # NEW

# match_events(): inside the conversion loop
MatchedEvent(
    sportradar_id=sr_id,
    betpawa=platforms.get("betpawa"),
    sportybet=platforms.get("sportybet"),
    bet9ja=platforms.get("bet9ja"),
    betway=platforms.get("betway"),
    msport=platforms.get("msport"),
    sportpesa=platforms.get("sportpesa"),   # NEW
)
```

The extractor dispatch already handles unknown platforms by returning `None` (`matching/extractor.py:24-26`), so the new `"sportpesa"` key is purely additive. Without this update, calling `match_events(("sportpesa", events), ...)` would silently drop SportPesa results.

## 6. Public-API additions

```python
# bookieskit/__init__.py
from bookieskit.bookmakers.sportpesa import SportPesa
__all__ = [..., "SportPesa", ...]

# Usage parity with the other 5:
async with SportPesa(country="ke") as sp:
    markets = await sp.get_markets(event_id="8868005")
    sr_id = await sp.get_sportradar_id(event_id="8868005")
```

## 7. Testing

| Test file | Coverage |
|---|---|
| `tests/test_sportpesa.py` (NEW) | Country resolution, headers (`x-app-timezone` per country), unsupported-country error. `@respx.mock` test per public method asserting URL + query params and one round-tripped field. |
| `tests/test_parser_sportpesa.py` (NEW) | 1X2, BTTS, DC (simple); Over/Under (parameterized, multi-line); unknown market id silently skipped; empty `data` → `[]`; malformed odds → coerced or skipped without raising; probability modes (`off` / `true` / `with_void`) — populated **iff** the markets fixture exposes those fields, else asserts `None` and documents the no-op. |
| `tests/test_extractor.py` (extend) | SR-id-bearing fixture → bare numeric; missing field → `None`; `sr:match:` prefix stripped. |
| `tests/test_event_info.py` (extend) | Prematch + live + malformed fixtures for each of kickoff / participants / live_info. **Also extend the hard-coded parametrize lists** at L312 (`"platform", [...]`) and L344 (`ALL_PLATFORMS = [...]`) to include `"sportpesa"`. The two `parametrize` decorators at L401 / L410 only enumerate platforms that expose live data with kickoff/participants payloads — add `"sportpesa"` only if the live fixture confirms parity (fixture-resolved). |
| `tests/test_registry.py` (extend) | `get_by_platform_id("sportpesa", "1")` resolves to `1x2_ft` (after fixture confirms id); `add(sportpesa_id=…)` round-trip. |
| `tests/test_convenience.py` (extend) | `SportPesa.get_markets()` calls the markets endpoint, not event-detail (mirrors the Betway convenience test). |
| `tests/test_matcher.py` (extend) | Add a `match_events` test that includes `("sportpesa", [...])` in `event_lists` and asserts the resulting `MatchedEvent.sportpesa` field is populated. |
| `tests/test_probability.py` (extend) | Extend the parametrize list at L63 (`"platform", ["betpawa", "sportybet", "bet9ja", "betway", "msport"]`) to include `"sportpesa"`. Same call shape — `parse_markets(..., probability=mode)` must accept the new platform key without raising. The L292 parametrize lists only platforms that expose `true_probability` — add `"sportpesa"` only if the fixture confirms it does. |
| `tests/test_types.py` (extend) | Mirror existing `*_msport_*` tests for sportpesa: constructing `OutcomeMapping(..., sportpesa="...")` and `MarketMapping(..., sportpesa_id="...")` round-trips. |
| `tests/fixtures/event_info/sportpesa/{prematch,live}.json` (NEW) | Captured raw responses driving `test_event_info.py`. |

**Coverage gate:** every public method on `SportPesa` is exercised. No silent gaps. The README's "test-coverage gaps" section does NOT grow.

**Fixture capture** — `scripts/capture_event_info_fixtures.py` is extended to also save SportPesa prematch + live responses (one extra `_save("sportpesa", phase, sp_detail)` call per phase). Requires SportPesa cookies harvested into the runner's environment; documented in the script's docstring as a precondition.

## 8. Docs, examples, packaging

| File | Change |
|---|---|
| `docs/sportpesa.md` (NEW) | Same structure as `docs/betway.md`: countries table, SR-id behaviour, methods table, per-method notes, quirks (Akamai, two-step markets fetch, subdomain country), recipes. |
| `docs/markets.md` | Extend the platform-id table to include SportPesa. |
| `docs/matching.md` | Add a SportPesa-SR-id paragraph. |
| `docs/examples.md` | Refresh any bookmaker-count references. |
| `README.md` | Tagline `5 → 6`; supported-bookmakers table row; built-in markets table column (✅ × 4 + — × 2 for 1Up/2Up); Limitations bullet for Akamai. |
| `pyproject.toml` | `version = "0.5.0"`; description string (currently `"5 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport)..."` at L8) updated to `"6 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport, SportPesa)..."`. |
| `src/bookieskit/__init__.py` | Export `SportPesa`, bump `__version__` to `"0.5.0"`. |
| `examples/odds_for_sr_id.py` | Add SportPesa to the per-bookmaker fan-out. |
| `examples/count_5bookies.py` | Add SportPesa to the iteration. File name stays. |
| `examples/odds_from_betpawa_id.py` | Add SportPesa fan-out + CSV column. |
| `examples/odds_for_betpawa_competition.py` | Add SportPesa fan-out + CSV column. |
| `examples/monitor_competitions.py` | **Untouched.** Curated 4-bookmaker subset (MSport already intentionally absent). Reviewer may override during PR review. |
| `examples/test_live_flow.py`, `examples/audit_full.py`, `examples/final_audit.py`, `examples/full_audit_4bookies.py`, `examples/full_audit_v2.py` | **Untouched.** Legacy audit scripts from pre-Betway / pre-MSport eras (3- and 4-bookmaker variants). Kept for git context; canonical examples are the four listed above. |

## 9. Known gaps & limitations

1. **Akamai Bot Manager.** SportPesa endpoints are protected. The client does not solve the challenge: callers must supply a warmed session (cookies harvested from a browser hit). Documented in `README.md` and `docs/sportpesa.md`. Same posture as the existing "BetPawa SR-id reverse search not implemented" gap.
2. **Probability mode is fixture-conditional.** Whether SportPesa exposes `true_probability` / `void_probability` is unknown until the markets fixture is captured. Spec wires the branches in the parser; implementation prunes the unused ones.
3. **Fixture-resolved keys.** Specific JSON keys are listed as candidates in the spec — implementation captures fixtures, picks the correct key, and removes dead candidate branches before merging.
4. **TZ-specific market ids.** Small risk that SportPesa Tanzania publishes different ids than Kenya. Test plan includes one `country="tz"` event to verify; if ids diverge, builtin mappings carry the Kenyan ids and a separate registry override is documented for tz callers.
5. **`examples/monitor_competitions.py` is intentionally not updated.** That script's bookmaker list is hand-curated (MSport already excluded). Adding SportPesa is a separate curation decision; the reviewer can override during PR review.
6. **No SR-id-to-SportPesa-id reverse lookup.** Same gap pattern as BetPawa. SR-id-driven workflows must start from a SportPesa event id.

## 10. Migration & compatibility

- `OutcomeMapping` and `MarketMapping` gain new fields with defaults (`""` and `None`). Existing user code that constructs these directly continues to compile.
- `MarketRegistry.add(...)` gains a defaulted `sportpesa_id=None` kwarg. Existing call sites unaffected.
- `MarketRegistry.get_by_platform_id(platform, …)` returns `None` for unknown `platform` strings (existing behaviour). The `"sportpesa"` key is additive.
- Version bumps to `0.5.0` (feature add, no breaking changes).

## 11. Implementation phases

Six phases. Each phase is independently testable; the test suite passes (or grows in a controlled way) at the end of every phase. The full plan with task-level granularity will be produced by writing-plans on the next pass.

### Phase 0 — Fixture capture & payload-shape resolution (manual; requires warmed cookies)

Extend `scripts/capture_event_info_fixtures.py` to save SportPesa prematch + live event-detail responses (and one captured markets payload) under `tests/fixtures/event_info/sportpesa/`. Wrap the SportPesa block in a `try/except` (Akamai may fail mid-run) and read cookies from an env var (e.g. `SPORTPESA_COOKIE`) so absent cookies skip rather than crash. Run from a browser-warmed session. **Inspect captured payloads and lock in:** the SR-id key path, kickoff / participants / live-info keys, market ids for the 4 universal markets, outcome name strings, the line-value field name (`special_bet_value` vs `special_bet_values` vs embedded-in-name), and whether `probability` / `void_probability` fields exist on selections. **Exit:** committed fixtures + a Phase-0 resolution table in the PR description listing each fixture-resolved item and the chosen value.

### Phase 1 — Types, registry, builtin mappings, matcher (single commit)

Add `sportpesa: str = ""` to `OutcomeMapping`, `sportpesa_id: str | None = None` to `MarketMapping`, `_by_sportpesa` index + `add(sportpesa_id=…)` kwarg + `get_by_platform_id` row in `MarketRegistry`. Populate the 4 universal builtins (`1x2_ft`, `over_under_ft`, `btts_ft`, `double_chance_ft`) with the Phase 0 confirmed ids/outcome strings; set `sportpesa_id=None` + `sportpesa=""` on `1x2_1up_ft` / `1x2_2up_ft`. Add `sportpesa: dict | None = None` to `MatchedEvent` + the corresponding line in `match_events`. Extend `tests/test_types.py`, `tests/test_registry.py`, `tests/test_matcher.py` with sportpesa cases. **Exit:** `pytest tests/test_types.py tests/test_registry.py tests/test_matcher.py` green.

### Phase 2 — Extractor + parser + event_info branches (internally parallel)

Three independent file additions touching three different modules. Implement:
- `_extract_sportpesa` + dispatch row in `matching/extractor.py` (+ tests in `test_extractor.py`).
- `_parse_sportpesa` + `_parse_sportpesa_simple` + `_parse_sportpesa_parameterized` + `_resolve_outcome_sportpesa` + dispatch row in `markets/parser.py` (+ tests in `test_parser_sportpesa.py`).
- `_kickoff_sportpesa` + `_participants_sportpesa` + `_live_info_sportpesa` + three dispatch rows in `event_info.py` (+ tests added to `test_event_info.py`, plus the parametrize lists at L312 and L344 extended).
- Extend `tests/test_probability.py` L63 parametrize list to include `"sportpesa"`.

Prune all "hypothesis" or-branches against the Phase 0 fixtures — every fallback that didn't fire on real data is deleted. **Exit:** `pytest tests/test_extractor.py tests/test_parser_sportpesa.py tests/test_event_info.py tests/test_probability.py` green.

### Phase 3 — Client + public-API wiring (single commit)

Add `src/bookieskit/bookmakers/sportpesa.py` with `SportPesa(BaseBookmaker)` and all 8 methods (2 verbatim-confirmed paths + 5 Phase-0-resolved paths + the `get_markets` override). Add `SPORTPESA_MAX_CONCURRENT` and `SPORTPESA_REQUEST_DELAY` to `config.py`. Export `SportPesa` from `__init__.py` and bump `__version__` to `"0.5.0"`. Bump `pyproject.toml` version + description. Add `tests/test_sportpesa.py` and extend `tests/test_convenience.py`. **Exit:** `pytest tests/test_sportpesa.py tests/test_convenience.py` green; `python -c "from bookieskit import SportPesa; SportPesa(country='ke')"` succeeds.

### Phase 4 — Docs + examples (single commit)

`docs/sportpesa.md` (NEW), `docs/markets.md` (extend platform-id table + dispatcher prose at L73 + "Adding a new platform" recipe at L111), `docs/matching.md` (field-path table at L9-16 + the `MatchedEvent` snippet at L24-31), `docs/examples.md` (refresh bookmaker-count refs), `README.md` (`5 → 6` tagline, supported-bookmakers row, built-in-markets column, Akamai limitation bullet). Fan SportPesa into `examples/odds_for_sr_id.py`, `examples/count_5bookies.py`, `examples/odds_from_betpawa_id.py`, `examples/odds_for_betpawa_competition.py`. Legacy/curated scripts left untouched per section 2. **Exit:** `grep -r "5 African" .` returns zero hits in docs/README; example scripts run end-to-end against mocked fixtures (no live calls required for CI).

### Phase 5 — Full suite + smoke run + ship

`pytest -x` clean; `ruff check src tests` clean. Manual smoke from a warmed session against one prematch + one live SportPesa Kenya event: verify `get_markets` returns ≥1 `NormalizedMarket` and `get_sportradar_id` returns a numeric string. Optional: same smoke on one Tanzania event to validate the `country="tz"` path. Update the PR description with the Phase 0 resolution table. **Exit:** all green, PR opened, version 0.5.0 ready to tag.
