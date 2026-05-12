# SportPesa Bookmaker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `SportPesa` as the 6th supported bookmaker in `bookieskit`, with country-symmetric KE / TZ support, prematch + live, the 4 universal canonical markets (1X2, O/U, BTTS, DC), and full parity across client / parser / extractor / event-info / matcher / registry / tests / docs / examples.

**Architecture:** Symmetric clone of the existing per-bookmaker pattern (Betway / MSport are the closest siblings). New `SportPesa(BaseBookmaker)` client; new `_parse_sportpesa` / `_extract_sportpesa` / `_kickoff_sportpesa` / `_participants_sportpesa` / `_live_info_sportpesa` branches in the existing dispatch modules; new `sportpesa` / `sportpesa_id` columns on `OutcomeMapping` / `MarketMapping`; new `_by_sportpesa` index on `MarketRegistry`; new `sportpesa` field on `MatchedEvent`. Bookmaker-discriminator key is the literal string `"sportpesa"`.

**Tech Stack:** Python 3.11+, `httpx` async, `pytest`, `pytest-asyncio`, `respx` for HTTP mocking. No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-05-12-sportpesa-bookmaker-design.md` (commit `739a351`).

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `tests/fixtures/event_info/sportpesa/prematch.json` | create | Captured event-detail (prematch) — drives event-info + extractor tests. |
| `tests/fixtures/event_info/sportpesa/live.json` | create | Captured event-detail (live). |
| `tests/fixtures/event_info/sportpesa/markets.json` | create | Captured `/api/games/markets` payload — drives parser tests. |
| `tests/fixtures/event_info/sportpesa/RESOLVED.md` | create | Phase-0 decision record: confirmed endpoint paths, SR-id key path, kickoff / participants / live-info keys, market ids, outcome name strings, line-value field name, probability field presence. Every subsequent task reads this file to bind hypothesis branches. |
| `scripts/capture_event_info_fixtures.py` | modify | Add a SportPesa-capture block guarded by `SPORTPESA_COOKIE` env var; gracefully skip when absent. |
| `src/bookieskit/markets/types.py` | modify | Add `sportpesa: str = ""` to `OutcomeMapping`; add `sportpesa_id: str \| None = None` to `MarketMapping`. |
| `src/bookieskit/markets/registry.py` | modify | Add `_by_sportpesa` index + `sportpesa_id=None` kwarg on `add()` + `"sportpesa"` row in `get_by_platform_id` dispatch. |
| `src/bookieskit/markets/builtin_mappings.py` | modify | Populate the 4 universal mappings with `sportpesa_id=...` and `sportpesa="..."` on each outcome. Set `sportpesa_id=None` + `sportpesa=""` on the two 1Up/2Up mappings. |
| `src/bookieskit/matching/matcher.py` | modify | Add `sportpesa: dict \| None = None` field on `MatchedEvent`; add the `sportpesa=platforms.get("sportpesa")` line in `match_events`. |
| `src/bookieskit/matching/extractor.py` | modify | Add `_extract_sportpesa` + dispatch row. |
| `src/bookieskit/markets/parser.py` | modify | Add `_parse_sportpesa` + `_parse_sportpesa_simple` + `_parse_sportpesa_parameterized` + `_resolve_outcome_sportpesa` + dispatch row. |
| `src/bookieskit/event_info.py` | modify | Add `_kickoff_sportpesa` + `_participants_sportpesa` + `_live_info_sportpesa` + three dispatch rows. |
| `src/bookieskit/bookmakers/sportpesa.py` | create | `SportPesa(BaseBookmaker)` with 8 public methods. |
| `src/bookieskit/config.py` | modify | Add `SPORTPESA_MAX_CONCURRENT = 15` and `SPORTPESA_REQUEST_DELAY = 0.05`. |
| `src/bookieskit/__init__.py` | modify | Export `SportPesa`; bump `__version__` to `"0.5.0"`. |
| `pyproject.toml` | modify | Bump `version` to `0.5.0`; update description to mention SportPesa and "6 African sportsbooks". |
| `tests/test_types.py` | modify | Mirror the existing `*_msport_*` tests for sportpesa: `OutcomeMapping(sportpesa=...)` + `MarketMapping(sportpesa_id=...)` round-trip. |
| `tests/test_registry.py` | modify | `get_by_platform_id("sportpesa", "1")` resolves to `1x2_ft`; `add(sportpesa_id=...)` round-trip. |
| `tests/test_matcher.py` | modify | `match_events` populates `MatchedEvent.sportpesa` when fed a `("sportpesa", [...])` tuple. |
| `tests/test_extractor.py` | modify | SR-id extraction from the captured `prematch.json` fixture; missing-field → `None`; `sr:match:` prefix stripped. |
| `tests/test_parser_sportpesa.py` | create | Parser tests against the captured `markets.json` fixture. |
| `tests/test_event_info.py` | modify | Add sportpesa cases to the per-platform tests; extend the parametrize list at L312 and `ALL_PLATFORMS` at L344. |
| `tests/test_probability.py` | modify | Extend the parametrize list at L63 to include `"sportpesa"`. |
| `tests/test_sportpesa.py` | create | `@respx.mock` tests per public method on `SportPesa`. |
| `tests/test_convenience.py` | modify | Assert `SportPesa.get_markets()` calls `get_event_markets` (not `get_event_detail`). |
| `docs/sportpesa.md` | create | Bookmaker doc — same structure as `docs/betway.md`. |
| `docs/markets.md` | modify | Add sportpesa column to the platform-id table; update dispatcher prose at L73; update "Adding a new platform" recipe at L111. |
| `docs/matching.md` | modify | Add sportpesa row to the field-path table at L9-16; update the `MatchedEvent` snippet at L24-31. |
| `docs/examples.md` | modify | Refresh bookmaker-count references. |
| `README.md` | modify | Tagline `5 → 6`; supported-bookmakers row; built-in-markets column; Akamai limitation bullet. |
| `examples/odds_for_sr_id.py` | modify | Add SportPesa to the per-bookmaker fan-out. |
| `examples/count_5bookies.py` | modify | Add SportPesa (file name kept). |
| `examples/odds_from_betpawa_id.py` | modify | Add SportPesa fan-out + CSV column. |
| `examples/odds_for_betpawa_competition.py` | modify | Add SportPesa fan-out + CSV column. |

**Left untouched:** `examples/monitor_competitions.py` (curated 4-bookmaker subset), `examples/test_live_flow.py`, `examples/audit_full.py`, `examples/final_audit.py`, `examples/full_audit_4bookies.py`, `examples/full_audit_v2.py` (legacy from pre-Betway / pre-MSport eras). These stay in the tree for git context.

Each task ends with a commit so the work integrates incrementally.

---

# Phase 0 — Fixture capture & payload-shape resolution

This phase is **manual**: SportPesa's API is gated by Akamai Bot Manager. The engineer must capture fixtures from a warmed browser session and commit them, then write down the resolved field paths so every later task has concrete values to bind to.

## Task 1: Capture SportPesa fixtures from a warmed browser session

**Files:**
- Create: `tests/fixtures/event_info/sportpesa/prematch.json`
- Create: `tests/fixtures/event_info/sportpesa/live.json`
- Create: `tests/fixtures/event_info/sportpesa/markets.json`

- [ ] **Step 1: Open a warmed browser session against `https://www.ke.sportpesa.com`**

Browse to a soccer prematch event (e.g., `https://www.ke.sportpesa.com/games/<gameId>/markets?sportId=1&section=markets`). Solve the Akamai challenge by interacting normally. Open DevTools → Network → filter for `/api/`.

- [ ] **Step 2: Capture prematch event-detail JSON**

From DevTools, right-click the request to `/api/upcoming/games?gameId=<id>&sportId=1&section=markets&pag_count=1` → "Save response as…" → save the raw JSON body (not the cURL) to `tests/fixtures/event_info/sportpesa/prematch.json`. Pretty-print it (`python -m json.tool prematch.json > prematch.json.tmp && mv prematch.json.tmp prematch.json`).

- [ ] **Step 3: Capture markets JSON**

Capture the request to `/api/games/markets?games=<id>&markets=all` from the same page; save to `tests/fixtures/event_info/sportpesa/markets.json`. Pretty-print.

- [ ] **Step 4: Find a live event and capture its event-detail JSON**

Browse to a live in-play soccer event. Capture `/api/live/games?gameId=<id>&...` (or whatever path the live page calls — note the exact path in `RESOLVED.md` later). Save body to `tests/fixtures/event_info/sportpesa/live.json`. Pretty-print.

- [ ] **Step 5: Commit fixtures**

```bash
git add tests/fixtures/event_info/sportpesa/
git commit -m "test(sportpesa): capture prematch, live, markets fixtures from warmed session"
```

## Task 2: Resolve fixture-derived field paths

**Files:**
- Create: `tests/fixtures/event_info/sportpesa/RESOLVED.md`

- [ ] **Step 1: Inspect prematch.json and find the SR-id**

Open `tests/fixtures/event_info/sportpesa/prematch.json`. Search (`Ctrl+F`) for `sr:match:`, then `sportradar`, `betradar`, `sr_id`, `external_id`. Note the JSON path that holds the SR id (e.g., `data[0].additional_info.sportradar_id`). If the value carries the `sr:match:` prefix, note that.

- [ ] **Step 2: Locate kickoff, participants, and live-info keys**

In `prematch.json`, identify:
- The kickoff time — JSON path (e.g., `data[0].date` — likely Unix-epoch seconds — or `data[0].start_time` ISO string).
- Home team name — JSON path (e.g., `data[0].home_team` or `data[0].competitors[0].name`).
- Away team name — JSON path.

In `live.json`, identify the live-info block:
- Match minute (e.g., `data[0].live_info.match_time`).
- Period (e.g., `data[0].live_info.period`).
- Score — single `"H:A"` string or separate home/away ints?

- [ ] **Step 3: Locate market structure in markets.json**

In `markets.json`, identify:
- Path to the markets list (e.g., `data[0].markets`).
- The market id field (e.g., `markets[].id`).
- Concrete values: which `id` is 1X2? Over/Under? BTTS? Double Chance? (Likely `"1"`, `"18"`, `"29"`, `"10"` — copy the actual strings.)
- The outcome name field (e.g., `selections[].name`).
- Outcome name strings: 1X2 home/draw/away (likely `"1"` / `"X"` / `"2"`); Over/Under (likely `"Over"` / `"Under"`); BTTS (`"Yes"` / `"No"`); DC (`"1X"` / `"X2"` / `"12"`).
- The line-value field for Over/Under (e.g., `special_bet_value` or `special_bet_values`).
- Whether per-outcome `probability` and/or `void_probability` fields exist.

- [ ] **Step 4: Write the resolution table**

Create `tests/fixtures/event_info/sportpesa/RESOLVED.md` with this content (filled in from steps 1-3):

```markdown
# SportPesa fixture-resolved values

## Endpoints

| Method | Path |
|---|---|
| get_event_detail (prematch) | /api/upcoming/games?gameId={id}&sportId=1&section=markets&pag_count=1 |
| get_event_detail (live) | <FILL FROM CAPTURE — e.g. /api/live/games?gameId={id}&sportId=1> |
| get_event_markets | /api/games/markets?games={id}&markets=all |
| get_sports (prematch) | <FILL — likely /api/sports or similar> |
| get_sports (live) | <FILL> |
| get_countries (prematch) | <FILL — likely /api/upcoming/categories?sportId={sport_id}> |
| get_tournaments (prematch) | <FILL — likely /api/upcoming/competitions?sportId={sport_id}&categoryId={cat}> |
| get_events (prematch) | <FILL — likely /api/upcoming/games?sportId={sport_id}&competitionId={comp}&...> |

## Event-detail JSON keys

| Item | JSON path | Notes |
|---|---|---|
| SR id | <FILL> | <prefixed with sr:match: ? yes/no> |
| kickoff | <FILL> | <unix-epoch seconds / ms / ISO string> |
| home team | <FILL> | |
| away team | <FILL> | |

## Live-info JSON keys

| Item | JSON path | Notes |
|---|---|---|
| match minute | <FILL> | |
| period | <FILL> | |
| home score | <FILL> | <single "H:A" string or separate fields> |
| away score | <FILL> | |

## Markets JSON keys

| Item | JSON path / value | Notes |
|---|---|---|
| markets list | <FILL — e.g. data[0].markets> | |
| market id field | <FILL — e.g. id> | |
| 1X2 id | <FILL — e.g. "1"> | |
| O/U id | <FILL — e.g. "18"> | |
| BTTS id | <FILL — e.g. "29"> | |
| DC id | <FILL — e.g. "10"> | |
| outcome list field | <FILL — e.g. selections> | |
| outcome name field | <FILL — e.g. name> | |
| outcome odds field | <FILL — e.g. odds> | <string-typed? yes/no> |
| 1X2 outcome strings | <FILL — home / draw / away> | |
| O/U outcome strings | <FILL — over / under> | |
| BTTS outcome strings | <FILL — yes / no> | |
| DC outcome strings | <FILL — 1X / X2 / 12> | |
| line-value field (O/U) | <FILL — e.g. special_bet_value> | |
| probability field | <FILL — present or absent> | |
| void_probability field | <FILL — present or absent> | |
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/event_info/sportpesa/RESOLVED.md
git commit -m "docs(sportpesa): record fixture-resolved field paths and endpoint URLs"
```

## Task 3: Extend the capture script for future re-captures

**Files:**
- Modify: `scripts/capture_event_info_fixtures.py`

- [ ] **Step 1: Read the existing capture script**

Open `scripts/capture_event_info_fixtures.py`. Note the 5-way `async with` block (around `bp / sb / b9 / bw / ms`) and the `_save("<platform>", phase, ...)` calls.

- [ ] **Step 2: Add SportPesa import and a cookie-gated capture helper**

At the top of the file, add to the imports:

```python
import os
from bookieskit import SportPesa
```

After the existing `_save` helper, add:

```python
async def _capture_sportpesa(phase: str, event_id: str) -> None:
    """Capture SportPesa prematch/live for one event.

    Requires the SPORTPESA_COOKIE env var (Akamai bot manager).
    Skips quietly when the env var is missing or any request fails.
    """
    cookie = os.environ.get("SPORTPESA_COOKIE")
    if not cookie:
        print(f"  [sportpesa/{phase}] SPORTPESA_COOKIE not set — skipping")
        return
    try:
        async with SportPesa(country="ke") as sp:
            # Inject the cookie header for this session.
            sp._http_client.headers["cookie"] = cookie
            detail = await sp.get_event_detail(event_id=event_id, live=(phase == "live"))
            _save("sportpesa", phase, detail)
    except Exception as e:
        print(f"  [sportpesa/{phase}] capture failed: {e!r}")
```

- [ ] **Step 3: Wire the helper into the existing per-phase capture flow**

In the function that drives per-phase captures (the one that iterates over the 5 existing bookmakers), add at the end:

```python
    # SportPesa needs its own event id — Akamai-warmed cookie required.
    sp_event_id = os.environ.get(f"SPORTPESA_{phase.upper()}_EVENT_ID")
    if sp_event_id:
        await _capture_sportpesa(phase, sp_event_id)
```

- [ ] **Step 4: Document the env vars in the script's module docstring**

At the top of the file, extend the docstring to mention:

```
For SportPesa capture (optional — script otherwise skips it):
    SPORTPESA_COOKIE — full Cookie: header value from a warmed browser
    SPORTPESA_PREMATCH_EVENT_ID — game id of a prematch event to capture
    SPORTPESA_LIVE_EVENT_ID — game id of a live event to capture
```

- [ ] **Step 5: Smoke-run the script to make sure existing capture still works**

```bash
python scripts/capture_event_info_fixtures.py
```

Expected: existing 5 bookmakers run normally; SportPesa lines print "SPORTPESA_COOKIE not set — skipping" and the script exits 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/capture_event_info_fixtures.py
git commit -m "feat(scripts): optional SportPesa fixture capture gated by SPORTPESA_COOKIE env"
```

---

# Phase 1 — Types, registry, builtin mappings, matcher

Single commit's-worth of structural changes that ripple into every later phase. Each task is TDD: failing test first, then minimal code, then green, then commit.

## Task 4: Add `sportpesa` field to OutcomeMapping

**Files:**
- Modify: `src/bookieskit/markets/types.py`
- Modify: `tests/test_types.py`

- [ ] **Step 1: Write the failing test**

Open `tests/test_types.py`, find the test cluster for `OutcomeMapping` (search `OutcomeMapping(`). Add at the end of the file:

```python
def test_outcome_mapping_sportpesa_field_defaults_to_empty():
    from bookieskit.markets.types import OutcomeMapping
    om = OutcomeMapping(canonical_name="home", betpawa="1", sportybet="Home", bet9ja="1")
    assert om.sportpesa == ""


def test_outcome_mapping_sportpesa_field_round_trips():
    from bookieskit.markets.types import OutcomeMapping
    om = OutcomeMapping(
        canonical_name="home", betpawa="1", sportybet="Home", bet9ja="1",
        betway="__HOME__", msport="Home", sportpesa="1",
    )
    assert om.sportpesa == "1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_types.py::test_outcome_mapping_sportpesa_field_defaults_to_empty -v
```

Expected: FAIL with `AttributeError` or `TypeError` mentioning `sportpesa`.

- [ ] **Step 3: Add the field**

In `src/bookieskit/markets/types.py`, find the `OutcomeMapping` dataclass and add the new field as the last entry (defaulted, so existing positional/keyword call sites keep working):

```python
@dataclass(frozen=True)
class OutcomeMapping:
    """Maps one outcome across platforms."""

    canonical_name: str
    betpawa: str
    sportybet: str
    bet9ja: str
    betway: str = ""
    msport: str = ""
    sportpesa: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_types.py -v
```

Expected: PASS (all tests, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/types.py tests/test_types.py
git commit -m "feat(types): add sportpesa field to OutcomeMapping"
```

## Task 5: Add `sportpesa_id` field to MarketMapping

**Files:**
- Modify: `src/bookieskit/markets/types.py`
- Modify: `tests/test_types.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_types.py`:

```python
def test_market_mapping_sportpesa_id_defaults_to_none():
    from bookieskit.markets.types import MarketMapping
    mm = MarketMapping(
        canonical_id="1x2_ft", name="1X2 - Full Time",
        betpawa_id="3743", sportybet_id="1", bet9ja_key="S_1X2",
    )
    assert mm.sportpesa_id is None


def test_market_mapping_sportpesa_id_round_trips():
    from bookieskit.markets.types import MarketMapping
    mm = MarketMapping(
        canonical_id="1x2_ft", name="1X2 - Full Time",
        betpawa_id="3743", sportybet_id="1", bet9ja_key="S_1X2",
        betway_id="[Win/Draw/Win]", msport_id="1", sportpesa_id="1",
    )
    assert mm.sportpesa_id == "1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_types.py::test_market_mapping_sportpesa_id_defaults_to_none -v
```

Expected: FAIL with `TypeError` (unexpected keyword) or `AttributeError`.

- [ ] **Step 3: Add the field**

In `src/bookieskit/markets/types.py`, update `MarketMapping` — insert `sportpesa_id` after `msport_id` and before `outcomes` (keep `outcomes` last because it has a `field(default_factory=dict)`):

```python
@dataclass(frozen=True)
class MarketMapping:
    """Defines how one market maps across platforms."""

    canonical_id: str
    name: str
    betpawa_id: str | None
    sportybet_id: str | None
    bet9ja_key: str | None
    betway_id: str | None = None
    msport_id: str | None = None
    sportpesa_id: str | None = None
    outcomes: dict[str, OutcomeMapping] = field(default_factory=dict)
    parameterized: bool = False
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_types.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/types.py tests/test_types.py
git commit -m "feat(types): add sportpesa_id field to MarketMapping"
```

## Task 6: Extend MarketRegistry with sportpesa index

**Files:**
- Modify: `src/bookieskit/markets/registry.py`
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_registry.py`:

```python
def test_registry_resolves_by_sportpesa_id():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry(load_builtins=False)
    registry.add(
        canonical_id="test_market",
        name="Test",
        sportpesa_id="42",
    )
    m = registry.get_by_platform_id("sportpesa", "42")
    assert m is not None
    assert m.canonical_id == "test_market"


def test_registry_sportpesa_lookup_returns_none_for_unknown_id():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry(load_builtins=False)
    assert registry.get_by_platform_id("sportpesa", "999") is None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_registry.py::test_registry_resolves_by_sportpesa_id -v
```

Expected: FAIL — `add()` doesn't accept `sportpesa_id`, or `get_by_platform_id("sportpesa", ...)` returns `None` even when registered.

- [ ] **Step 3: Wire the registry**

In `src/bookieskit/markets/registry.py`:

1. In `__init__`, after `self._by_msport`:
```python
        self._by_sportpesa: dict[str, MarketMapping] = {}
```

2. In `_register`, after the msport block:
```python
        if mapping.sportpesa_id:
            self._by_sportpesa[mapping.sportpesa_id] = mapping
```

3. In `add()` signature and body — append `sportpesa_id`:
```python
    def add(
        self,
        canonical_id: str,
        name: str,
        betpawa_id: str | None = None,
        sportybet_id: str | None = None,
        bet9ja_key: str | None = None,
        betway_id: str | None = None,
        msport_id: str | None = None,
        sportpesa_id: str | None = None,
        outcomes: dict[str, OutcomeMapping] | None = None,
        parameterized: bool = False,
    ) -> None:
```

And in the body, pass it through:
```python
        mapping = MarketMapping(
            canonical_id=canonical_id,
            name=name,
            betpawa_id=betpawa_id,
            sportybet_id=sportybet_id,
            bet9ja_key=bet9ja_key,
            betway_id=betway_id,
            msport_id=msport_id,
            sportpesa_id=sportpesa_id,
            outcomes=outcomes or {},
            parameterized=parameterized,
        )
```

4. In `get_by_platform_id`, add the `"sportpesa"` row to the dispatch dict:
```python
        index = {
            "betpawa": self._by_betpawa,
            "sportybet": self._by_sportybet,
            "bet9ja": self._by_bet9ja,
            "betway": self._by_betway,
            "msport": self._by_msport,
            "sportpesa": self._by_sportpesa,
        }.get(platform, {})
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_registry.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/registry.py tests/test_registry.py
git commit -m "feat(registry): add sportpesa index and add() kwarg"
```

## Task 7: Populate builtin mappings for SportPesa

**Files:**
- Modify: `src/bookieskit/markets/builtin_mappings.py`
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Open `RESOLVED.md` and read the market ids and outcome strings for the 4 universal markets**

Note the values for: `1X2 id`, `O/U id`, `BTTS id`, `DC id`, and the 11 outcome strings (home/draw/away, over/under, yes/no, 1X/X2/12).

- [ ] **Step 2: Write the failing test**

Append to `tests/test_registry.py` (using the values from `RESOLVED.md`; the values below are the *expected* values if they match the spec's best-evidence — substitute the actual fixture-resolved strings if they differ):

```python
def test_builtin_1x2_ft_has_sportpesa_mapping():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    # Read RESOLVED.md for the actual id; default is "1".
    m = registry.get_by_platform_id("sportpesa", "1")
    assert m is not None
    assert m.canonical_id == "1x2_ft"
    assert m.outcomes["home"].sportpesa  # any non-empty string


def test_builtin_over_under_ft_has_sportpesa_mapping():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    m = registry.get_by_platform_id("sportpesa", "18")
    assert m is not None
    assert m.canonical_id == "over_under_ft"
    assert m.parameterized is True


def test_builtin_btts_ft_has_sportpesa_mapping():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    m = registry.get_by_platform_id("sportpesa", "29")
    assert m is not None
    assert m.canonical_id == "btts_ft"


def test_builtin_dc_ft_has_sportpesa_mapping():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    m = registry.get_by_platform_id("sportpesa", "10")
    assert m is not None
    assert m.canonical_id == "double_chance_ft"


def test_builtin_1up_2up_have_no_sportpesa_mapping():
    from bookieskit.markets.registry import MarketRegistry
    registry = MarketRegistry()
    one_up = registry.get_by_canonical("1x2_1up_ft")
    two_up = registry.get_by_canonical("1x2_2up_ft")
    assert one_up.sportpesa_id is None
    assert two_up.sportpesa_id is None
    for om in one_up.outcomes.values():
        assert om.sportpesa == ""
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/test_registry.py -v -k builtin
```

Expected: 4 failures (`get_by_platform_id` returns `None` for sportpesa).

- [ ] **Step 4: Update the four universal mappings**

In `src/bookieskit/markets/builtin_mappings.py`, for each of the four universal mappings, add `sportpesa_id="..."` and `sportpesa="..."` on each outcome. **Use the exact values from `RESOLVED.md`.** The values below are the spec's best-evidence starting point; replace them if `RESOLVED.md` says otherwise:

```python
MarketMapping(
    canonical_id="1x2_ft",
    name="1X2 - Full Time",
    betpawa_id="3743",
    sportybet_id="1",
    bet9ja_key="S_1X2",
    betway_id="[Win/Draw/Win]",
    msport_id="1",
    sportpesa_id="1",
    outcomes={
        "home": OutcomeMapping(
            canonical_name="home",
            betpawa="1", sportybet="Home", bet9ja="1",
            betway="__HOME__", msport="Home", sportpesa="1",
        ),
        "draw": OutcomeMapping(
            canonical_name="draw",
            betpawa="X", sportybet="Draw", bet9ja="X",
            betway="Draw", msport="Draw", sportpesa="X",
        ),
        "away": OutcomeMapping(
            canonical_name="away",
            betpawa="2", sportybet="Away", bet9ja="2",
            betway="__AWAY__", msport="Away", sportpesa="2",
        ),
    },
    parameterized=False,
),
MarketMapping(
    canonical_id="over_under_ft",
    name="Over/Under - Full Time",
    betpawa_id="5000",
    sportybet_id="18",
    bet9ja_key="S_OU",
    betway_id="[Total Goals]",
    msport_id="18",
    sportpesa_id="18",
    outcomes={
        "over": OutcomeMapping(
            canonical_name="over",
            betpawa="Over", sportybet="Over", bet9ja="O",
            betway="Over", msport="Over", sportpesa="Over",
        ),
        "under": OutcomeMapping(
            canonical_name="under",
            betpawa="Under", sportybet="Under", bet9ja="U",
            betway="Under", msport="Under", sportpesa="Under",
        ),
    },
    parameterized=True,
),
MarketMapping(
    canonical_id="btts_ft",
    name="Both Teams To Score - Full Time",
    betpawa_id="3795",
    sportybet_id="29",
    bet9ja_key="S_GGNG",
    betway_id="[Both Teams To Score]",
    msport_id="29",
    sportpesa_id="29",
    outcomes={
        "yes": OutcomeMapping(
            canonical_name="yes",
            betpawa="Yes", sportybet="Yes", bet9ja="Y",
            betway="Yes", msport="Yes", sportpesa="Yes",
        ),
        "no": OutcomeMapping(
            canonical_name="no",
            betpawa="No", sportybet="No", bet9ja="N",
            betway="No", msport="No", sportpesa="No",
        ),
    },
    parameterized=False,
),
MarketMapping(
    canonical_id="double_chance_ft",
    name="Double Chance - Full Time",
    betpawa_id="4693",
    sportybet_id="10",
    bet9ja_key="S_DC",
    betway_id="[Double Chance]",
    msport_id="10",
    sportpesa_id="10",
    outcomes={
        "home_draw": OutcomeMapping(
            canonical_name="home_draw",
            betpawa="1X", sportybet="Home or Draw", bet9ja="1X",
            betway="__POS_1__", msport="1 X", sportpesa="1X",
        ),
        "draw_away": OutcomeMapping(
            canonical_name="draw_away",
            betpawa="X2", sportybet="Draw or Away", bet9ja="X2",
            betway="__POS_3__", msport="X 2", sportpesa="X2",
        ),
        "home_away": OutcomeMapping(
            canonical_name="home_away",
            betpawa="12", sportybet="Home or Away", bet9ja="12",
            betway="__POS_2__", msport="1 2", sportpesa="12",
        ),
    },
    parameterized=False,
),
```

For the two 1Up/2Up mappings, on every existing `OutcomeMapping(...)` add `sportpesa=""` (preserving the existing pattern used for the unmapped MSport entries).

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_registry.py tests/test_types.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/builtin_mappings.py tests/test_registry.py
git commit -m "feat(markets): wire sportpesa ids on the 4 universal builtin mappings"
```

## Task 8: Add sportpesa field to MatchedEvent

**Files:**
- Modify: `src/bookieskit/matching/matcher.py`
- Modify: `tests/test_matcher.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_matcher.py`:

```python
def test_match_events_populates_sportpesa_field():
    from bookieskit.matching.matcher import match_events

    # Each event needs a SR id that extract_sportradar_id can pull.
    # Betway carries the SR id in sportEvent.eventId; SportPesa we don't
    # know yet at unit-test time — we monkey-patch the extractor to keep
    # this test pure-data (no fixture dependency).
    # Use Betway as the side with a known shape, and a stub for the new platform.
    bw_event = {"sportEvent": {"eventId": "12345"}}
    sp_event = {"data": [{"additional_info": {"sportradar_id": "12345"}}]}

    results = match_events(
        ("betway", [bw_event]),
        ("sportpesa", [sp_event]),
    )

    assert len(results) == 1
    me = results[0]
    assert me.sportradar_id == "12345"
    assert me.betway is bw_event
    assert me.sportpesa is sp_event
```

(Note: this test depends on Task 9 below — the extractor needs to know how to read sportpesa SR ids. The test will start failing at Step 2 here, become a different failure once Task 9 lands, and finally pass. That's intentional — it's the contract enforcing Task 9's correctness too. If the engineer prefers, run Task 9 first, then come back to this step.)

- [ ] **Step 2: Run the test**

```bash
pytest tests/test_matcher.py::test_match_events_populates_sportpesa_field -v
```

Expected: FAIL — `MatchedEvent` has no `sportpesa` attribute, or the extractor doesn't recognize `"sportpesa"` yet.

- [ ] **Step 3: Add the field and the branch**

In `src/bookieskit/matching/matcher.py`:

```python
@dataclass
class MatchedEvent:
    """An event matched across multiple platforms."""

    sportradar_id: str
    betpawa: dict | None = None
    sportybet: dict | None = None
    bet9ja: dict | None = None
    betway: dict | None = None
    msport: dict | None = None
    sportpesa: dict | None = None
```

And inside `match_events`, in the `MatchedEvent(...)` construction:

```python
        results.append(
            MatchedEvent(
                sportradar_id=sr_id,
                betpawa=platforms.get("betpawa"),
                sportybet=platforms.get("sportybet"),
                bet9ja=platforms.get("bet9ja"),
                betway=platforms.get("betway"),
                msport=platforms.get("msport"),
                sportpesa=platforms.get("sportpesa"),
            )
        )
```

- [ ] **Step 4: Run the test again**

```bash
pytest tests/test_matcher.py -v
```

Expected: the new test still FAILs because the extractor for `"sportpesa"` returns `None` (Task 9 fixes that). All previously-existing tests still PASS. Mark this acceptable and move on; the test will turn green at Task 9.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/matching/matcher.py tests/test_matcher.py
git commit -m "feat(matcher): add sportpesa field to MatchedEvent and match_events branch"
```

---

# Phase 2 — Extractor, parser, event_info

Three independent file additions; can be executed in parallel by different subagents.

## Task 9: Implement SR-id extractor for SportPesa

**Files:**
- Modify: `src/bookieskit/matching/extractor.py`
- Modify: `tests/test_extractor.py`

- [ ] **Step 1: Read `RESOLVED.md` to find the SR-id JSON path**

Note the value of the "SR id" row in `tests/fixtures/event_info/sportpesa/RESOLVED.md`.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_extractor.py`:

```python
def test_extract_sportradar_id_sportpesa_from_fixture():
    import json
    from pathlib import Path
    from bookieskit.matching.extractor import extract_sportradar_id

    fixture = Path(__file__).parent / "fixtures" / "event_info" / "sportpesa" / "prematch.json"
    response = json.loads(fixture.read_text(encoding="utf-8"))

    sr = extract_sportradar_id(response, platform="sportpesa")
    assert sr is not None
    assert sr.isdigit()  # bare numeric, no sr:match: prefix


def test_extract_sportradar_id_sportpesa_missing_returns_none():
    from bookieskit.matching.extractor import extract_sportradar_id
    assert extract_sportradar_id({}, platform="sportpesa") is None
    assert extract_sportradar_id({"data": []}, platform="sportpesa") is None
    assert extract_sportradar_id({"data": [{}]}, platform="sportpesa") is None


def test_extract_sportradar_id_sportpesa_strips_prefix():
    from bookieskit.matching.extractor import extract_sportradar_id
    response = {"data": [{"additional_info": {"sportradar_id": "sr:match:12345"}}]}
    assert extract_sportradar_id(response, platform="sportpesa") == "12345"
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/test_extractor.py -v -k sportpesa
```

Expected: all 3 FAIL (`extractor` doesn't know `"sportpesa"`).

- [ ] **Step 4: Implement the extractor**

In `src/bookieskit/matching/extractor.py`:

1. Add the function, **adjusting the JSON path to what `RESOLVED.md` says**. The version below assumes `data[0].additional_info.sportradar_id` per the spec's best-evidence; substitute the resolved path if it differs:

```python
def _extract_sportpesa(response: dict) -> str | None:
    """Extract from SportPesa data[0].additional_info.sportradar_id.

    Adjust this path to whatever RESOLVED.md confirmed from the captured
    prematch fixture — and prune the unused candidates.
    """
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

After running the tests against the real fixture, **delete the unused fallback branches** so the function only checks the one path that actually exists in the fixture.

2. Add the dispatch row at the top of the file:

```python
    extractors = {
        "betpawa": _extract_betpawa,
        "sportybet": _extract_sportybet,
        "bet9ja": _extract_bet9ja,
        "betway": _extract_betway,
        "msport": _extract_msport,
        "sportpesa": _extract_sportpesa,
    }
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_extractor.py tests/test_matcher.py -v
```

Expected: PASS (including the matcher test from Task 8 that now finds the SR id on the sportpesa side).

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/matching/extractor.py tests/test_extractor.py
git commit -m "feat(extractor): add sportpesa SR-id extraction"
```

## Task 10: Implement event_info extractors (kickoff)

**Files:**
- Modify: `src/bookieskit/event_info.py`
- Modify: `tests/test_event_info.py`

- [ ] **Step 1: Read `RESOLVED.md` for the kickoff JSON path and format**

Note whether kickoff is epoch-seconds, epoch-milliseconds, or an ISO string, and the JSON path that holds it.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_event_info.py` (the file has an existing `_load` helper at the top):

```python
def test_extract_kickoff_sportpesa_prematch():
    from datetime import timezone
    d = _load("sportpesa", "prematch")
    k = extract_kickoff(d, "sportpesa")
    assert k is not None
    assert k.tzinfo is not None  # tz-aware
    assert k.tzinfo.utcoffset(k) == timezone.utc.utcoffset(k)


def test_extract_kickoff_sportpesa_live_missing_kickoff_returns_none_or_real():
    # Live payloads may carry kickoff (it just happened) or omit it.
    # Either is acceptable; just don't raise.
    d = _load("sportpesa", "live")
    extract_kickoff(d, "sportpesa")  # must not raise


def test_extract_kickoff_sportpesa_malformed_returns_none():
    assert extract_kickoff({}, "sportpesa") is None
    assert extract_kickoff({"data": []}, "sportpesa") is None
    assert extract_kickoff({"data": [{"date": "not-a-number"}]}, "sportpesa") is None
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/test_event_info.py -v -k "kickoff_sportpesa"
```

Expected: FAIL (`extract_kickoff` doesn't know `"sportpesa"`, returns `None` for everything, malformed test passes vacuously).

- [ ] **Step 4: Implement the kickoff extractor**

In `src/bookieskit/event_info.py`, add **after the `_kickoff_msport` function** (adjust JSON path per `RESOLVED.md`):

```python
def _kickoff_sportpesa(response: dict, _mode: Mode | None) -> datetime | None:
    data = response.get("data") or []
    if not isinstance(data, list) or not data:
        return None
    game = data[0]
    # Epoch first (RESOLVED.md confirms unit: seconds or ms).
    epoch = game.get("date")
    if isinstance(epoch, (int, float)):
        try:
            # If RESOLVED.md says milliseconds, divide by 1000 here.
            return datetime.fromtimestamp(epoch, tz=timezone.utc)
        except (ValueError, OSError):
            pass
    iso = game.get("start_time") or game.get("startTime")
    if isinstance(iso, str):
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None
```

After confirming with the real fixture, **delete the branch that didn't fire** (either the epoch branch or the ISO branch — not both).

Then add the dispatch row:

```python
_KICKOFF_DISPATCH: dict[str, Callable[[dict, Mode | None], datetime | None]] = {
    "betpawa": _kickoff_betpawa,
    "sportybet": _kickoff_sportybet,
    "bet9ja": _kickoff_bet9ja,
    "betway": _kickoff_betway,
    "msport": _kickoff_msport,
    "sportpesa": _kickoff_sportpesa,
}
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_event_info.py -v -k "kickoff_sportpesa"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/event_info.py tests/test_event_info.py
git commit -m "feat(event_info): add sportpesa kickoff extraction"
```

## Task 11: Implement event_info extractors (participants)

**Files:**
- Modify: `src/bookieskit/event_info.py`
- Modify: `tests/test_event_info.py`

- [ ] **Step 1: Read `RESOLVED.md` for home/away JSON paths**

- [ ] **Step 2: Write the failing tests**

Append:

```python
def test_extract_participants_sportpesa_prematch():
    d = _load("sportpesa", "prematch")
    p = extract_participants(d, "sportpesa")
    assert p.home is not None and p.home != ""
    assert p.away is not None and p.away != ""


def test_extract_participants_sportpesa_malformed_returns_empty():
    p = extract_participants({}, "sportpesa")
    assert p.home is None and p.away is None
    p = extract_participants({"data": []}, "sportpesa")
    assert p.home is None and p.away is None
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/test_event_info.py -v -k "participants_sportpesa"
```

Expected: FAIL.

- [ ] **Step 4: Implement the participants extractor**

Append to `src/bookieskit/event_info.py` (after `_kickoff_sportpesa`):

```python
def _participants_sportpesa(response: dict, _mode: Mode | None) -> Participants:
    data = response.get("data") or []
    if not isinstance(data, list) or not data:
        return _EMPTY_PARTICIPANTS
    game = data[0]
    home = game.get("home_team") or game.get("homeTeam")
    away = game.get("away_team") or game.get("awayTeam")
    if not home and not away:
        comps = game.get("competitors") or []
        if isinstance(comps, list) and len(comps) >= 2:
            home = (comps[0] or {}).get("name")
            away = (comps[1] or {}).get("name")
    return Participants(home=home or None, away=away or None)
```

After confirming with the fixture, **prune the branches that didn't fire**.

Add the dispatch row:

```python
_PARTICIPANTS_DISPATCH: dict[str, Callable[[dict, Mode | None], Participants]] = {
    "betpawa": _participants_betpawa,
    "sportybet": _participants_sportybet,
    "bet9ja": _participants_bet9ja,
    "betway": _participants_betway,
    "msport": _participants_msport,
    "sportpesa": _participants_sportpesa,
}
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_event_info.py -v -k "participants_sportpesa"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/event_info.py tests/test_event_info.py
git commit -m "feat(event_info): add sportpesa participants extraction"
```

## Task 12: Implement event_info extractors (live_info)

**Files:**
- Modify: `src/bookieskit/event_info.py`
- Modify: `tests/test_event_info.py`

- [ ] **Step 1: Read `RESOLVED.md` for live-info JSON paths**

Note: live-info block path, minute path, period path, score format (single `"H:A"` or split fields).

- [ ] **Step 2: Write the failing tests**

Append:

```python
def test_extract_live_info_sportpesa_prematch_returns_empty():
    d = _load("sportpesa", "prematch")
    li = extract_live_info(d, "sportpesa", mode="prematch")
    assert li.minute is None
    assert li.period is None
    assert li.score_home is None
    assert li.score_away is None


def test_extract_live_info_sportpesa_live_populated():
    d = _load("sportpesa", "live")
    li = extract_live_info(d, "sportpesa", mode="live")
    # At least one of (minute, period, score_home, score_away) should be non-None for a real live event.
    assert any(v is not None for v in [li.minute, li.period, li.score_home, li.score_away])


def test_extract_live_info_sportpesa_auto_detect_prematch():
    d = _load("sportpesa", "prematch")
    li = extract_live_info(d, "sportpesa")  # mode=None auto-detect
    assert li.minute is None and li.score_home is None
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/test_event_info.py -v -k "live_info_sportpesa"
```

- [ ] **Step 4: Implement the live_info extractor**

Append to `src/bookieskit/event_info.py`:

```python
def _live_info_sportpesa(response: dict, mode: Mode | None) -> LiveInfo:
    if mode == "prematch":
        return _EMPTY_LIVE_INFO
    data = response.get("data") or []
    if not isinstance(data, list) or not data:
        return _EMPTY_LIVE_INFO
    game = data[0]
    live = game.get("live_info") or game.get("scoreboard") or {}
    if not live and mode is None:
        return _EMPTY_LIVE_INFO
    minute = _try_int(live.get("match_time") or live.get("minute"))
    period = live.get("period") or live.get("status") or None
    score_home, score_away = _split_score(live.get("score"))
    if score_home is None and score_away is None:
        score_home = _try_int(live.get("home_score"))
        score_away = _try_int(live.get("away_score"))
    return LiveInfo(
        minute=minute, period=period,
        score_home=score_home, score_away=score_away,
    )
```

After confirming with the fixture, **prune the dead branches**.

Add the dispatch row:

```python
_LIVE_INFO_DISPATCH: dict[str, Callable[[dict, Mode | None], LiveInfo]] = {
    "betpawa": _live_info_betpawa,
    "sportybet": _live_info_sportybet,
    "bet9ja": _live_info_bet9ja,
    "betway": _live_info_betway,
    "msport": _live_info_msport,
    "sportpesa": _live_info_sportpesa,
}
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_event_info.py -v -k "live_info_sportpesa"
```

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/event_info.py tests/test_event_info.py
git commit -m "feat(event_info): add sportpesa live_info extraction"
```

## Task 13: Extend test_event_info parametrize lists

**Files:**
- Modify: `tests/test_event_info.py`

- [ ] **Step 1: Open the file and locate the hard-coded platform lists**

Line ~312: `@pytest.mark.parametrize("platform", ["betpawa", "sportybet", "bet9ja", "betway", "msport"])`.
Line ~344: `ALL_PLATFORMS = ["betpawa", "sportybet", "bet9ja", "betway", "msport"]`.
Lines ~401 and ~410: two more parametrize decorators with a 3-platform list `["betpawa", "sportybet", "msport"]`.

- [ ] **Step 2: Extend the 5-platform lists to 6**

Add `"sportpesa"` to the lists at L312 and L344.

For the two 3-platform lists at L401 / L410: these enumerate platforms whose live response carries kickoff/participants payloads. Add `"sportpesa"` to both **only if** `RESOLVED.md` confirms the live fixture has kickoff + participants populated. Otherwise leave them as 3-platform lists and add a comment: `# sportpesa not included — live payload lacks kickoff/participants (see RESOLVED.md)`.

- [ ] **Step 3: Run the full event_info suite**

```bash
pytest tests/test_event_info.py -v
```

Expected: PASS. (If the L401/L410 tests fail for sportpesa, it means the live fixture *does* have kickoff/participants and the decision in Step 2 needs flipping. If they fail in a way that means the fixture genuinely lacks them, leave sportpesa out of those two parametrize lists.)

- [ ] **Step 4: Commit**

```bash
git add tests/test_event_info.py
git commit -m "test(event_info): include sportpesa in cross-platform parametrize lists"
```

## Task 14: Implement the parser — dispatch and simple-market path

**Files:**
- Modify: `src/bookieskit/markets/parser.py`
- Create: `tests/test_parser_sportpesa.py`

- [ ] **Step 1: Read `RESOLVED.md` for markets JSON structure**

Note: markets list path, market id field, outcome list field, outcome name field, outcome odds field, line-value field name, probability/void-probability field presence.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_parser_sportpesa.py`:

```python
"""Parser tests for SportPesa markets payload."""

import json
from pathlib import Path

import pytest

from bookieskit.markets.parser import parse_markets

FIXTURE = Path(__file__).parent / "fixtures" / "event_info" / "sportpesa" / "markets.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_sportpesa_returns_list():
    result = parse_markets(_load(), platform="sportpesa")
    assert isinstance(result, list)


def test_parse_sportpesa_includes_1x2_ft():
    result = parse_markets(_load(), platform="sportpesa")
    canonical_ids = [m.canonical_id for m in result]
    assert "1x2_ft" in canonical_ids


def test_parse_sportpesa_1x2_has_three_outcomes():
    result = parse_markets(_load(), platform="sportpesa")
    one_x_two = next(m for m in result if m.canonical_id == "1x2_ft")
    names = sorted(o.canonical_name for o in one_x_two.outcomes)
    assert names == ["away", "draw", "home"]
    for o in one_x_two.outcomes:
        assert o.odds > 1.0
        assert o.odds < 100.0


def test_parse_sportpesa_includes_btts_and_dc():
    result = parse_markets(_load(), platform="sportpesa")
    canonical_ids = {m.canonical_id for m in result}
    assert "btts_ft" in canonical_ids
    assert "double_chance_ft" in canonical_ids


def test_parse_sportpesa_empty_response_returns_empty_list():
    assert parse_markets({}, platform="sportpesa") == []
    assert parse_markets({"data": []}, platform="sportpesa") == []
    assert parse_markets({"data": [{}]}, platform="sportpesa") == []


def test_parse_sportpesa_unknown_platform_returns_empty():
    # Sanity: the dispatch defaults to [] for unknown platform.
    assert parse_markets(_load(), platform="nosuch") == []
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/test_parser_sportpesa.py -v
```

Expected: 4-5 FAIL (`parser` doesn't know `"sportpesa"`).

- [ ] **Step 4: Implement the simple-market parser**

In `src/bookieskit/markets/parser.py`, after `_resolve_outcome_msport` (the last MSport helper), add:

```python
def _parse_sportpesa(
    response: dict, registry: MarketRegistry, mode: ProbabilityMode = "off"
) -> list[NormalizedMarket]:
    """Parse SportPesa markets payload.

    Shape (per RESOLVED.md): {"data": [{"markets": [{"id": ..., "selections": [...]}]}]}
    Parameterized markets repeat the same id once per line, with the line value
    in `special_bet_value` (resolve key from RESOLVED.md).
    """
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


def _parse_sportpesa_simple(
    market_data: dict, mapping: MarketMapping, mode: ProbabilityMode = "off"
) -> NormalizedMarket:
    """Parse a simple SportPesa market (1X2, BTTS, DC)."""
    outcomes: list[Outcome] = []

    for sel in market_data.get("selections", []):
        name = str(sel.get("name", ""))
        try:
            odds = float(sel.get("odds", 0))
        except (TypeError, ValueError):
            continue
        canonical = _resolve_outcome_sportpesa(name, mapping)
        if canonical:
            true_p = void_p = None
            if mode != "off":
                true_p = _try_float(sel.get("probability"))
                if mode == "with_void":
                    void_p = _try_float(sel.get("void_probability"))
            outcomes.append(
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=name,
                    true_probability=true_p,
                    void_probability=void_p,
                )
            )

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=outcomes,
        lines=None,
    )


def _parse_sportpesa_parameterized(
    entries: list[dict], mapping: MarketMapping, mode: ProbabilityMode = "off"
) -> NormalizedMarket:
    """Parse a parameterized SportPesa market (Over/Under, handicaps).

    The line value comes from `special_bet_value` (or the field RESOLVED.md
    confirms). Each entry is a single market dict with a list of selections.
    """
    lines: dict[float, list[Outcome]] = {}

    for entry in entries:
        line_str = entry.get("special_bet_value") or entry.get("special_bet_values")
        if line_str is None:
            continue
        try:
            line = float(line_str)
        except (TypeError, ValueError):
            continue

        line_outcomes: list[Outcome] = []
        for sel in entry.get("selections", []):
            name = str(sel.get("name", ""))
            try:
                odds = float(sel.get("odds", 0))
            except (TypeError, ValueError):
                continue
            canonical = _resolve_outcome_sportpesa(name, mapping)
            if canonical:
                true_p = void_p = None
                if mode != "off":
                    true_p = _try_float(sel.get("probability"))
                    if mode == "with_void":
                        void_p = _try_float(sel.get("void_probability"))
                line_outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=name,
                        true_probability=true_p,
                        void_probability=void_p,
                    )
                )

        if line_outcomes:
            lines[line] = line_outcomes

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=[],
        lines=lines,
    )


def _resolve_outcome_sportpesa(
    platform_name: str, mapping: MarketMapping
) -> str | None:
    """Find canonical outcome name from a SportPesa selection name.

    Exact match first, then prefix match (handles "Over 2.5" → "Over").
    """
    for om in mapping.outcomes.values():
        if om.sportpesa == platform_name:
            return om.canonical_name
    for om in mapping.outcomes.values():
        if om.sportpesa and platform_name.startswith(om.sportpesa):
            return om.canonical_name
    return None
```

After confirming against the fixture, **prune the `special_bet_value` / `special_bet_values` fallback** to whichever key is real, and **remove the `void_probability` branch** if the fixture confirms SportPesa doesn't expose it.

Add the dispatch row in `parse_markets`:

```python
    parsers = {
        "betpawa": _parse_betpawa,
        "sportybet": _parse_sportybet,
        "bet9ja": _parse_bet9ja,
        "betway": _parse_betway,
        "msport": _parse_msport,
        "sportpesa": _parse_sportpesa,
    }
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_parser_sportpesa.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_parser_sportpesa.py
git commit -m "feat(parser): add sportpesa branch with simple and parameterized markets"
```

## Task 15: Verify Over/Under parameterized parsing

**Files:**
- Modify: `tests/test_parser_sportpesa.py`

- [ ] **Step 1: Write the failing test for O/U**

Append to `tests/test_parser_sportpesa.py`:

```python
def test_parse_sportpesa_over_under_has_lines():
    result = parse_markets(_load(), platform="sportpesa")
    ou = next((m for m in result if m.canonical_id == "over_under_ft"), None)
    assert ou is not None
    assert ou.lines is not None
    assert len(ou.lines) >= 1
    # Each line should have an "over" and an "under" outcome.
    for line, outcomes in ou.lines.items():
        names = sorted(o.canonical_name for o in outcomes)
        assert names == ["over", "under"]
        # Lines for full-time O/U are typically half-integers (0.5, 1.5, 2.5, ...).
        assert line > 0


def test_parse_sportpesa_over_under_lines_are_floats():
    result = parse_markets(_load(), platform="sportpesa")
    ou = next(m for m in result if m.canonical_id == "over_under_ft")
    for line in ou.lines:
        assert isinstance(line, float)
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_parser_sportpesa.py -v -k over_under
```

Expected: depends on whether the fixture contains an O/U market. If PASS, great. If FAIL because the fixture only has one line, that's fine — the assertion `len >= 1` already accommodates that.

- [ ] **Step 3: If tests fail, fix the parser or the line-key resolution**

If `RESOLVED.md` named a different line-value key than the parser uses, update `_parse_sportpesa_parameterized` accordingly. Re-run.

- [ ] **Step 4: Commit**

```bash
git add tests/test_parser_sportpesa.py
git commit -m "test(parser): cover sportpesa Over/Under parameterized lines"
```

## Task 16: Extend test_probability parametrize list

**Files:**
- Modify: `tests/test_probability.py`

- [ ] **Step 1: Open the file and locate the parametrize list**

The 5-platform list at L63: `@pytest.mark.parametrize("platform", ["betpawa", "sportybet", "bet9ja", "betway", "msport"])`.

- [ ] **Step 2: Add `"sportpesa"`**

Change to: `["betpawa", "sportybet", "bet9ja", "betway", "msport", "sportpesa"]`.

- [ ] **Step 3: Locate the 3-platform list at L292**

`@pytest.mark.parametrize("platform", ["betpawa", "sportybet", "msport"])` — this enumerates platforms that expose `true_probability`. **Add `"sportpesa"` only if `RESOLVED.md` confirms** the markets fixture contains a `probability` field on selections.

- [ ] **Step 4: Run the probability suite**

```bash
pytest tests/test_probability.py -v
```

Expected: PASS. If a sportpesa case fails because the fixture/parser doesn't have `probability` fields and the test asserts they exist, the parser correctly leaves them `None` — verify the test logic accepts that for platforms that lack probability (mirroring how it handles Bet9ja / Betway).

- [ ] **Step 5: Commit**

```bash
git add tests/test_probability.py
git commit -m "test(probability): include sportpesa in cross-platform parametrize"
```

---

# Phase 3 — Client + public-API wiring

## Task 17: Add config constants

**Files:**
- Modify: `src/bookieskit/config.py`

- [ ] **Step 1: Open the file and read existing platform constants**

The pattern: `<PLATFORM>_MAX_CONCURRENT = N` and `<PLATFORM>_REQUEST_DELAY = X` for each of the 5 existing bookmakers.

- [ ] **Step 2: Append the sportpesa constants**

After `MSPORT_REQUEST_DELAY = 0.0`:

```python
SPORTPESA_MAX_CONCURRENT = 15
SPORTPESA_REQUEST_DELAY = 0.05  # 50ms — Akamai-conservative
```

- [ ] **Step 3: Commit**

```bash
git add src/bookieskit/config.py
git commit -m "feat(config): add SportPesa rate-limit constants"
```

## Task 18: Implement SportPesa client — boilerplate, country resolution, headers

**Files:**
- Create: `src/bookieskit/bookmakers/sportpesa.py`
- Create: `tests/test_sportpesa.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sportpesa.py`:

```python
import pytest
import respx

from bookieskit.bookmakers.sportpesa import SportPesa


def test_sportpesa_country_ke_resolves_domain():
    client = SportPesa(country="ke")
    assert client.base_url == "https://www.ke.sportpesa.com"


def test_sportpesa_country_tz_resolves_domain():
    client = SportPesa(country="tz")
    assert client.base_url == "https://www.tz.sportpesa.com"


def test_sportpesa_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError
    with pytest.raises(UnsupportedCountryError):
        SportPesa(country="xx")


def test_sportpesa_ke_timezone_header():
    client = SportPesa(country="ke")
    headers = client._build_headers()
    assert headers["x-app-timezone"] == "Africa/Nairobi"


def test_sportpesa_tz_timezone_header():
    client = SportPesa(country="tz")
    headers = client._build_headers()
    assert headers["x-app-timezone"] == "Africa/Dar_es_Salaam"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_sportpesa.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the client skeleton**

Create `src/bookieskit/bookmakers/sportpesa.py`:

```python
"""SportPesa client — supports ke, tz."""

from typing import Any

from bookieskit.base import BaseBookmaker
from bookieskit.config import SPORTPESA_MAX_CONCURRENT, SPORTPESA_REQUEST_DELAY


class SportPesa(BaseBookmaker):
    """HTTP client for SportPesa sportsbook API.

    SportPesa uses country-specific subdomains (www.ke.sportpesa.com,
    www.tz.sportpesa.com). Country also drives the `x-app-timezone`
    request header.

    The API is gated by Akamai Bot Manager. This client does NOT solve the
    challenge — callers must supply warmed cookies (e.g. by injecting
    `Cookie:` into `self._http_client.headers` after `__aenter__`).

    Event IDs are SportPesa-internal integers (e.g. "8868005"), NOT
    SportRadar ids. `get_sportradar_id` fetches event-detail and pulls the
    SR id from the response.

    Args:
        country: Country code (ke, tz)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 15)
        request_delay: Delay between requests in seconds (default: 0.05)
    """

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
    MAX_CONCURRENT = SPORTPESA_MAX_CONCURRENT
    REQUEST_DELAY = SPORTPESA_REQUEST_DELAY
    NAME = "SportPesa"
    PLATFORM_KEY = "sportpesa"

    _TIMEZONE_PER_COUNTRY = {
        "ke": "Africa/Nairobi",
        "tz": "Africa/Dar_es_Salaam",
    }

    def _build_headers(self) -> dict[str, str]:
        headers = dict(self.DEFAULT_HEADERS)
        headers["x-app-timezone"] = self._TIMEZONE_PER_COUNTRY.get(
            self._country, "Africa/Nairobi"
        )
        return headers
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sportpesa.py -v
```

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/bookmakers/sportpesa.py tests/test_sportpesa.py
git commit -m "feat(sportpesa): client skeleton with country resolution and headers"
```

## Task 19: Implement get_event_detail and get_event_markets

**Files:**
- Modify: `src/bookieskit/bookmakers/sportpesa.py`
- Modify: `tests/test_sportpesa.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sportpesa.py`:

```python
@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail_prematch():
    respx.get(
        "https://www.ke.sportpesa.com/api/upcoming/games"
    ).respond(json={"data": [{"id": 8868005, "home_team": "Arsenal"}]})

    async with SportPesa(country="ke") as client:
        result = await client.get_event_detail(event_id="8868005")
    assert result["data"][0]["home_team"] == "Arsenal"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_markets():
    respx.get(
        "https://www.ke.sportpesa.com/api/games/markets"
    ).respond(json={"data": [{"id": 8868005, "markets": []}]})

    async with SportPesa(country="ke") as client:
        result = await client.get_event_markets(event_id="8868005")
    assert result["data"][0]["id"] == 8868005


@pytest.mark.asyncio
@respx.mock
async def test_get_markets_calls_markets_endpoint():
    # get_markets should route through get_event_markets (not get_event_detail).
    markets_called = respx.get(
        "https://www.ke.sportpesa.com/api/games/markets"
    ).respond(json={"data": [{"id": 8868005, "markets": []}]})
    detail_called = respx.get(
        "https://www.ke.sportpesa.com/api/upcoming/games"
    ).respond(json={"data": [{"id": 8868005}]})

    async with SportPesa(country="ke") as client:
        await client.get_markets(event_id="8868005")

    assert markets_called.called
    assert not detail_called.called
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_sportpesa.py -v -k "event_detail or event_markets or get_markets"
```

Expected: FAIL (methods don't exist).

- [ ] **Step 3: Implement the methods**

Append to `src/bookieskit/bookmakers/sportpesa.py`:

```python
    async def get_event_detail(
        self, event_id: str, live: bool = False
    ) -> dict[str, Any]:
        """Get event detail (metadata + SR id, NOT full markets).

        Args:
            event_id: SportPesa internal game id (e.g., "8868005")
            live: If True, query the live endpoint family.

        Returns:
            Raw JSON. SR id lives at <RESOLVED.md path>.
        """
        path = "/api/live/games" if live else "/api/upcoming/games"
        return await self._request(
            "GET",
            path,
            params={
                "gameId": event_id,
                "sportId": "1",
                "section": "markets",
                "pag_count": "1",
            },
        )

    async def get_event_markets(self, event_id: str) -> dict[str, Any]:
        """Get the full markets payload for one event.

        Args:
            event_id: SportPesa internal game id

        Returns:
            Raw JSON with data[0].markets[].
        """
        return await self._request(
            "GET",
            "/api/games/markets",
            params={
                "games": event_id,
                "markets": "all",
            },
        )

    async def get_markets(self, event_id: str, registry: Any = None) -> list:
        """Fetch markets and return normalized markets.

        Overrides the base because SportPesa uses a separate markets
        endpoint, same pattern as Betway.

        Args:
            event_id: SportPesa internal game id
            registry: MarketRegistry (default: built-in)

        Returns:
            List of NormalizedMarket for recognized markets.
        """
        from bookieskit.markets.parser import parse_markets

        raw = await self.get_event_markets(event_id=event_id)
        return parse_markets(raw, platform=self.PLATFORM_KEY, registry=registry)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sportpesa.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/bookmakers/sportpesa.py tests/test_sportpesa.py
git commit -m "feat(sportpesa): get_event_detail, get_event_markets, get_markets override"
```

## Task 20: Implement the list-endpoint family (sports, countries, tournaments, events)

**Files:**
- Modify: `src/bookieskit/bookmakers/sportpesa.py`
- Modify: `tests/test_sportpesa.py`

- [ ] **Step 1: Open `RESOLVED.md` and read the exact paths for these 4 endpoints**

If the engineer hasn't been able to confirm them (network access limited), use the best-evidence defaults below and mark them with a `# fixture-resolve` comment for the next maintainer to verify.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_sportpesa.py`:

```python
@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get("https://www.ke.sportpesa.com/api/sports").respond(
        json={"data": [{"id": 1, "name": "Football"}]}
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_sports()
    assert result["data"][0]["name"] == "Football"


@pytest.mark.asyncio
@respx.mock
async def test_get_countries():
    respx.get("https://www.ke.sportpesa.com/api/upcoming/categories").respond(
        json={"data": [{"id": 100, "name": "England"}]}
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_countries(sport_id="1")
    assert result["data"][0]["name"] == "England"


@pytest.mark.asyncio
@respx.mock
async def test_get_tournaments():
    respx.get("https://www.ke.sportpesa.com/api/upcoming/competitions").respond(
        json={"data": [{"id": 200, "name": "Premier League"}]}
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_tournaments(sport_id="1", category_id="100")
    assert result["data"][0]["name"] == "Premier League"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get("https://www.ke.sportpesa.com/api/upcoming/games").respond(
        json={"data": [{"id": 8868005, "home_team": "Arsenal"}]}
    )
    async with SportPesa(country="ke") as client:
        result = await client.get_events(sport_id="1", competition_id="200")
    assert result["data"][0]["home_team"] == "Arsenal"
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/test_sportpesa.py -v -k "get_sports or get_countries or get_tournaments or get_events"
```

- [ ] **Step 4: Implement the list endpoints**

Append to `src/bookieskit/bookmakers/sportpesa.py`:

```python
    async def get_sports(self, live: bool = False) -> dict[str, Any]:
        """Get all available sports.

        Args:
            live: If True, fetch the live-sports endpoint.

        Returns:
            Raw JSON.
        """
        # fixture-resolve: confirm exact path per RESOLVED.md
        path = "/api/live/sports" if live else "/api/sports"
        return await self._request("GET", path)

    async def get_countries(
        self, sport_id: str = "1", live: bool = False
    ) -> dict[str, Any]:
        """Get countries/categories for a sport.

        Args:
            sport_id: SportPesa sport id (default "1" for Football)
            live: If True, query the live endpoint family.

        Returns:
            Raw JSON.
        """
        # fixture-resolve: confirm exact path per RESOLVED.md
        path = "/api/live/categories" if live else "/api/upcoming/categories"
        return await self._request("GET", path, params={"sportId": sport_id})

    async def get_tournaments(
        self,
        sport_id: str = "1",
        category_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Get tournaments/competitions for a sport.

        Args:
            sport_id: SportPesa sport id (default "1" for Football)
            category_id: Optional country/category id filter
            live: If True, query the live endpoint family.

        Returns:
            Raw JSON.
        """
        # fixture-resolve: confirm exact path per RESOLVED.md
        path = "/api/live/competitions" if live else "/api/upcoming/competitions"
        params: dict[str, Any] = {"sportId": sport_id}
        if category_id:
            params["categoryId"] = category_id
        return await self._request("GET", path, params=params)

    async def get_events(
        self,
        sport_id: str = "1",
        competition_id: str | None = None,
        live: bool = False,
        page: int = 0,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """Get events for a sport / competition.

        Args:
            sport_id: SportPesa sport id (default "1" for Football)
            competition_id: Optional competition id filter
            live: If True, query the live endpoint family.
            page: Pagination page (default 0)
            per_page: Page size (default 50)

        Returns:
            Raw JSON.
        """
        # fixture-resolve: confirm exact path + param names per RESOLVED.md
        path = "/api/live/games" if live else "/api/upcoming/games"
        params: dict[str, Any] = {
            "sportId": sport_id,
            "page": str(page),
            "per_page": str(per_page),
        }
        if competition_id:
            params["competitionId"] = competition_id
        return await self._request("GET", path, params=params)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_sportpesa.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/bookmakers/sportpesa.py tests/test_sportpesa.py
git commit -m "feat(sportpesa): list endpoints (sports, countries, tournaments, events)"
```

## Task 21: Wire SportPesa into the top-level package

**Files:**
- Modify: `src/bookieskit/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sportpesa.py`:

```python
def test_sportpesa_exported_from_top_level():
    from bookieskit import SportPesa as SP
    from bookieskit.bookmakers.sportpesa import SportPesa as SP2
    assert SP is SP2


def test_top_level_version_bumped():
    import bookieskit
    assert bookieskit.__version__ == "0.5.0"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_sportpesa.py -v -k "exported or version"
```

Expected: FAIL (`ImportError` and version mismatch).

- [ ] **Step 3: Update `src/bookieskit/__init__.py`**

```python
"""Bookieskit — HTTP clients for betting data scraping."""

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.betway import Betway
from bookieskit.bookmakers.msport import MSport
from bookieskit.bookmakers.sportpesa import SportPesa
from bookieskit.bookmakers.sportybet import SportyBet
from bookieskit.event_info import (
    LiveInfo,
    Mode,
    Participants,
    extract_kickoff,
    extract_live_info,
    extract_participants,
    is_live_now,
)
from bookieskit.markets.parser import ProbabilityMode

__version__ = "0.5.0"
__all__ = [
    "BetPawa",
    "SportyBet",
    "Bet9ja",
    "Betway",
    "MSport",
    "SportPesa",
    "LiveInfo",
    "Mode",
    "Participants",
    "ProbabilityMode",
    "extract_kickoff",
    "extract_live_info",
    "extract_participants",
    "is_live_now",
    "__version__",
]
```

- [ ] **Step 4: Update `pyproject.toml`**

Change `version = "0.4.0"` to `version = "0.5.0"`. Change the `description` line from `"5 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport)..."` to `"6 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport, SportPesa)..."` (preserve the rest of the description's content after the parenthesis).

- [ ] **Step 5: Run tests and verify the install metadata**

```bash
pytest tests/test_sportpesa.py -v
python -c "import bookieskit; print(bookieskit.__version__, bookieskit.SportPesa.__name__)"
```

Expected: PASS; the print outputs `0.5.0 SportPesa`.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/__init__.py pyproject.toml tests/test_sportpesa.py
git commit -m "feat(pkg): export SportPesa and bump version to 0.5.0"
```

## Task 22: Extend the convenience test

**Files:**
- Modify: `tests/test_convenience.py`

- [ ] **Step 1: Open the file and find the existing Betway/MSport convenience tests**

Search for `Betway.get_markets` or similar — the test that asserts `get_markets` routes through `get_event_markets`.

- [ ] **Step 2: Add the analogous sportpesa test**

Append to `tests/test_convenience.py`:

```python
@pytest.mark.asyncio
@respx.mock
async def test_sportpesa_get_markets_routes_to_event_markets_endpoint():
    """SportPesa.get_markets must call /api/games/markets, not the detail endpoint."""
    from bookieskit import SportPesa

    markets_route = respx.get(
        "https://www.ke.sportpesa.com/api/games/markets"
    ).respond(json={"data": [{"id": 8868005, "markets": []}]})
    detail_route = respx.get(
        "https://www.ke.sportpesa.com/api/upcoming/games"
    ).respond(json={"data": [{"id": 8868005}]})

    async with SportPesa(country="ke") as client:
        await client.get_markets(event_id="8868005")

    assert markets_route.called
    assert not detail_route.called
```

(If the file's existing tests import `pytest` and `respx` at the top, these imports are already in scope.)

- [ ] **Step 3: Run the test**

```bash
pytest tests/test_convenience.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_convenience.py
git commit -m "test(convenience): SportPesa.get_markets routes to markets endpoint"
```

---

# Phase 4 — Docs + examples

## Task 23: Write `docs/sportpesa.md`

**Files:**
- Create: `docs/sportpesa.md`

- [ ] **Step 1: Use `docs/betway.md` as a template**

Open `docs/betway.md` and use it as the structural template. Write `docs/sportpesa.md` with these sections:

```markdown
# SportPesa

## Supported Countries

| Code | Country |
|------|---------|
| `ke` | Kenya |
| `tz` | Tanzania |

Country is honoured via subdomain (`www.ke.sportpesa.com`, `www.tz.sportpesa.com`) and the `x-app-timezone` header (`Africa/Nairobi` for `ke`, `Africa/Dar_es_Salaam` for `tz`).

## SportRadar id

SportPesa event ids are SportPesa-internal integers (e.g. `"8868005"`), NOT SportRadar ids. The SR id is carried inside event-detail at `<JSON path from RESOLVED.md>`. `SportPesa.get_sportradar_id(event_id)` fetches event-detail and pulls the SR id from the response.

## Methods

| Method | HTTP | Path | When to use |
|--------|------|------|-------------|
| `get_sports(live=False)` | GET | `/api/sports` / `/api/live/sports` | Top-level sport list. |
| `get_countries(sport_id, live=False)` | GET | `/api/upcoming/categories` | Country/category list. |
| `get_tournaments(sport_id, category_id, live=False)` | GET | `/api/upcoming/competitions` | Competition/league list. |
| `get_events(sport_id, competition_id, live=False, page, per_page)` | GET | `/api/upcoming/games` | Event list. |
| `get_event_detail(event_id, live=False)` | GET | `/api/upcoming/games?gameId=...` | Metadata + SR id — **no markets**. |
| `get_event_markets(event_id)` | GET | `/api/games/markets?games=...&markets=all` | Full markets feed. |
| `get_markets(event_id, registry=None)` | (calls `get_event_markets`) | — | Inherited convenience overridden — calls markets endpoint. |
| `get_sportradar_id(event_id, live=False)` | (calls `get_event_detail`) | — | Fetches detail, runs the extractor. |

## Quirks

- **Akamai Bot Manager.** SportPesa endpoints require warmed cookies. The client does not solve the challenge. See "Limitations" in the README.
- **Markets and event detail are SEPARATE endpoints**: `get_event_detail` returns no markets. Use `get_event_markets` (or `get_markets`) for odds.
- **Country via subdomain**, not via query parameter.

## Recipes

[Three recipes mirroring docs/betway.md: list leagues for a country; normalized markets for one event; inspect raw markets payload.]

## See also

- [docs/markets.md](markets.md)
- [docs/matching.md](matching.md)
```

Substitute the SR-id JSON path from `RESOLVED.md` into the "SportRadar id" section.

- [ ] **Step 2: Commit**

```bash
git add docs/sportpesa.md
git commit -m "docs(sportpesa): add bookmaker documentation"
```

## Task 24: Update docs/markets.md, docs/matching.md, docs/examples.md

**Files:**
- Modify: `docs/markets.md`
- Modify: `docs/matching.md`
- Modify: `docs/examples.md`

- [ ] **Step 1: docs/markets.md**

- Add a `SportPesa` column to the platform-id table (search for table containing `betpawa | sportybet | bet9ja | betway | msport`).
- L73 prose enumerating dispatcher platforms — extend to include `"sportpesa"`.
- L111 "Adding a new platform" recipe — sanity-check that it now references the 6-platform world consistently.

- [ ] **Step 2: docs/matching.md**

- L9-16 field-path table — add a row: `sportpesa | <JSON path from RESOLVED.md>`.
- L24-31 `MatchedEvent` snippet — add `sportpesa=...` to the example.

- [ ] **Step 3: docs/examples.md**

Grep for `5 bookmakers` / `5 platforms` / `five bookmakers` and update to 6.

- [ ] **Step 4: Verify**

```bash
grep -rn "5 African\|5 bookmakers\|5 platforms\|five bookmakers" docs/
```

Expected: no remaining hits (or a deliberate historical mention that should be left).

- [ ] **Step 5: Commit**

```bash
git add docs/markets.md docs/matching.md docs/examples.md
git commit -m "docs: extend markets/matching/examples docs for SportPesa"
```

## Task 25: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the tagline (top of file)**

Change `5 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport)` → `6 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport, SportPesa)`.

- [ ] **Step 2: Add SportPesa to the supported-bookmakers table**

In the table that currently lists the 5 bookmakers, add a final row:

```markdown
| SportPesa | ke, tz | [docs/sportpesa.md](docs/sportpesa.md) |
```

- [ ] **Step 3: Add a SportPesa column to the "Built-in markets" table**

The existing table has columns `BetPawa | SportyBet | Bet9ja | Betway | MSport`. Add a final `SportPesa` column with ✅ for the 4 universal markets and `—` for `1x2_1up_ft` / `1x2_2up_ft`.

- [ ] **Step 4: Add an Akamai limitation bullet**

In the "Limitations / known gaps" section, add:

```markdown
- **SportPesa endpoints are gated by Akamai Bot Manager.** The client does not solve the challenge. Callers must supply warmed cookies harvested from a browser session (e.g., by setting `self._http_client.headers["cookie"] = "..."` after `__aenter__`). Same posture as the BetPawa SR-id reverse-search gap.
```

- [ ] **Step 5: Verify no stale "5 bookmakers" references remain**

```bash
grep -n "5 African\|5 bookmakers" README.md
```

Expected: no hits.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs(README): announce SportPesa as 6th bookmaker; document Akamai gap"
```

## Task 26: Fan SportPesa into the cross-bookmaker examples

**Files:**
- Modify: `examples/odds_for_sr_id.py`
- Modify: `examples/count_5bookies.py`
- Modify: `examples/odds_from_betpawa_id.py`
- Modify: `examples/odds_for_betpawa_competition.py`

- [ ] **Step 1: examples/odds_for_sr_id.py**

Add `SportPesa` to the import (`from bookieskit import ..., SportPesa, ...`) and to the bookmaker fan-out (wherever the existing 5 clients are instantiated and `get_markets` is called). Add the SportPesa output to whatever the existing display format is.

- [ ] **Step 2: examples/count_5bookies.py**

Same pattern. File name stays.

- [ ] **Step 3: examples/odds_from_betpawa_id.py**

Add SportPesa to the fan-out and to the CSV columns.

- [ ] **Step 4: examples/odds_for_betpawa_competition.py**

Same as Step 3.

- [ ] **Step 5: Smoke-run the four examples (will hit Akamai for SportPesa)**

```bash
python examples/count_5bookies.py 2>&1 | head -50
```

SportPesa block will likely fail with an HTTP-403 or HTML-instead-of-JSON error unless cookies are supplied. That's expected; document it in a top-of-file comment if the script doesn't gracefully handle it. The other 5 bookmakers should still report normally.

- [ ] **Step 6: Commit**

```bash
git add examples/odds_for_sr_id.py examples/count_5bookies.py examples/odds_from_betpawa_id.py examples/odds_for_betpawa_competition.py
git commit -m "feat(examples): fan SportPesa into the four cross-bookmaker scripts"
```

---

# Phase 5 — Full suite + smoke + ship

## Task 27: Full pytest and ruff

- [ ] **Step 1: Run the full test suite**

```bash
pytest -v
```

Expected: all green. If any test fails, fix it before proceeding — do not commit failing tests.

- [ ] **Step 2: Run ruff**

```bash
ruff check src tests
```

Expected: clean. Fix any lint errors.

- [ ] **Step 3: Verify zero remaining "5 African" / "5 bookmakers" in committed docs**

```bash
grep -rn "5 African\|5 bookmakers\|5 platforms" docs/ README.md examples/
```

If anything legitimate remains (e.g. in legacy `examples/audit_full.py`), confirm it's intentional (legacy artifact) and skip. Otherwise update.

## Task 28: Manual smoke run from a warmed session

- [ ] **Step 1: Export warmed cookies into the environment**

From a browser session against `www.ke.sportpesa.com`, copy the full `Cookie:` header value (Developer Tools → Network → any request → Headers → Request Headers → cookie). Then:

```bash
export SPORTPESA_COOKIE='<full cookie string>'
```

- [ ] **Step 2: Smoke-run against one prematch event**

Pick a real upcoming game id from `https://www.ke.sportpesa.com/`. Run:

```python
python -c "
import asyncio
from bookieskit import SportPesa
import os

async def main():
    async with SportPesa(country='ke') as sp:
        sp._http_client.headers['cookie'] = os.environ['SPORTPESA_COOKIE']
        markets = await sp.get_markets(event_id='<game id>')
        sr_id = await sp.get_sportradar_id(event_id='<game id>')
        print(f'SR id: {sr_id}')
        for m in markets:
            print(f'  {m.canonical_id}: {len(m.outcomes or [])} outcomes, lines={list((m.lines or {}).keys())[:3]}')

asyncio.run(main())
"
```

Expected: prints a numeric SR id and ≥1 `NormalizedMarket` line.

- [ ] **Step 3: Optional — smoke `country="tz"`**

Repeat Step 2 with a Tanzania event id and `country="tz"`. The cookie may be country-specific; if so, capture a fresh one from `www.tz.sportpesa.com`.

- [ ] **Step 4: Open the PR**

Push the branch and open a PR. In the PR description include:

- The Phase 0 resolution table (copy from `tests/fixtures/event_info/sportpesa/RESOLVED.md`).
- A checklist of methods exercised in the manual smoke (event-detail, markets, SR id; KE and ideally TZ).
- Note the Akamai limitation and what callers need to do.

```bash
git push -u origin <branch-name>
gh pr create --title "feat: add SportPesa as 6th supported bookmaker" --body "$(cat <<'EOF'
## Summary

- Adds `SportPesa(BaseBookmaker)` client supporting `ke` and `tz`.
- Adds parser / SR-id extractor / event-info / matcher / registry / mapping wiring for the new `sportpesa` platform key.
- 4 universal markets wired in builtin mappings: 1X2, O/U, BTTS, DC.
- Akamai Bot Manager documented as a known limitation — callers must supply warmed cookies.
- Bumps version to 0.5.0.

## Test plan

- [x] Phase 0 fixture-resolved values committed at `tests/fixtures/event_info/sportpesa/RESOLVED.md`
- [x] `pytest -v` green
- [x] `ruff check src tests` clean
- [x] Manual smoke: prematch event on KE — SR id and ≥1 normalized market returned
- [ ] Manual smoke: TZ event (optional)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## Task 29: Tag and ship

- [ ] **Step 1: After PR merges, tag**

```bash
git checkout main
git pull
git tag v0.5.0
git push --tags
```

---

## Self-review

**Spec coverage** — Every section of the spec maps to at least one task:

| Spec section | Plan task(s) |
|---|---|
| §3 Confirmed endpoints | Task 1, Task 19, Task 20 (Phase 0 + impl) |
| §5.1 Client | Task 17, 18, 19, 20 |
| §5.2 SR-id extractor | Task 9 |
| §5.3 Parser | Task 14, 15 |
| §5.4 Types & registry | Tasks 4, 5, 6 |
| §5.5 Builtin mappings | Task 7 |
| §5.6 event_info | Tasks 10, 11, 12, 13 |
| §5.7 Matcher | Task 8 |
| §6 Public-API | Task 21 |
| §7 Testing | Tasks 1 (fixtures), 4, 5, 6, 8, 9, 10–13, 14, 15, 16, 18, 19, 20, 22 |
| §8 Docs/examples/packaging | Tasks 21, 23, 24, 25, 26 |
| §9 Known gaps | Task 25 (README), Task 23 (docs) |
| §11 Phases 0–5 | Phases 0–5 in this plan map 1:1 |

**Placeholder scan** — Every step contains either concrete code or a concrete command. Hypothesis-branch values (JSON paths, market ids, outcome strings) are deferred to `RESOLVED.md` (Task 2), and every task that uses those values references `RESOLVED.md` explicitly. Best-evidence defaults are provided everywhere so the engineer is never blocked.

**Type consistency** — `OutcomeMapping.sportpesa: str = ""` and `MarketMapping.sportpesa_id: str | None = None` are added in Tasks 4/5 and consumed by registry (Task 6), builtin mappings (Task 7), and parser (Task 14). Field names match throughout. `MatchedEvent.sportpesa: dict | None = None` is added in Task 8 and consumed by matcher tests. The platform key `"sportpesa"` is used uniformly across extractor, parser, event_info, matcher, registry — no aliases.
