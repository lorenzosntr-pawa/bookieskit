# Betika bookmaker — design

**Status:** Design approved 2026-05-13. Awaiting implementation plan.
**Scope:** Add Betika as the 7th supported bookmaker in `bookieskit`, with parity to the existing 6 (client, parser, SR-id extractor, event-info, matcher participation, registry/mapping fields, catalogue iterator, tests, docs, examples). Version bumps `0.6.0 → 0.7.0`.
**Out of scope:** Adding new canonical markets beyond the 4 universals. Refactoring the bookmaker dispatch pattern. Any change to how the existing 6 clients work.

## 1. Motivation

Betika is a major operator across Kenya, Uganda, Tanzania, Malawi and Ghana. Crucially, **Betika's `parent_match_id` is the bare numeric SportRadar id** — verified against SportyBet (`70784812` resolved to "Man City vs Crystal Palace" on both). That means Betika participates in cross-bookmaker matching out of the box; no SR-id-gap caveat.

## 2. Decisions taken at brainstorm

| Decision | Outcome |
|---|---|
| Architectural shape | Option A — symmetric clone of the existing per-bookmaker pattern. Same shape as SportPesa in 0.6.0. |
| SR-id strategy | Use `data[0].parent_match_id` as the SR id. `match_id` is Betika's internal id, `parent_match_id` is the SR canonical id. Verified by cross-reference with SportyBet. |
| Country support | All 5 codes: `ke`, `ug`, `tz`, `mw`, `gh`. All map to the same `https://api.betika.com` base — the API doesn't differentiate by country. `country` is a label only; documented in client docstring. |
| Live + prematch | Both. Live lives at `https://live.betika.com/v1/uo/matches`; prematch at `https://api.betika.com/v1/uo/matches`. Same response shape. |
| Markets in v1 | Four universal markets only: `1x2_ft` (sub_type_id=1), `over_under_ft` (18), `btts_ft` (29), `double_chance_ft` (10). 1Up/2Up not exposed by Betika; left unmapped per the MSport/SportPesa precedent. |
| O/U line parsing | Parse from the `display` label (`"OVER 2.5"` → line=2.5, outcome=over). Mirrors the SportPesa parser's prefix-match approach. Case-insensitive comparison throughout. |
| Examples | Full parity. README + supported-bookmakers table → 7. Fan Betika into `count_5bookies.py`, `odds_for_sr_id.py`, `odds_from_betpawa_id.py`, `odds_for_betpawa_competition.py`. Legacy scripts (`monitor_competitions.py`, `audit_*.py`, `test_live_flow.py`) left untouched. |
| Version bump | `0.6.0 → 0.7.0` — additive feature, no breaking changes anticipated. |

## 3. Empirically confirmed endpoints

All `200` from `https://api.betika.com` over plain HTTPS, no auth, no Cloudflare gate on the JSON paths (the SPA frontend at `www.betika.com` is Cloudflare-gated but the API isn't):

| Endpoint | Returns |
|---|---|
| `GET /v1/sports` | `{data: [{sport_id, sport_name, categories: [{category_id, category_name, competitions: [...]}], top_leagues: []}], meta: {limit, current_page}}`. 20 sports. The `categories` tree IS the navigation tree — no separate `/api/navigation` needed (unlike SportPesa). |
| `GET /v1/uo/matches` | `{data: [<match>...], meta: {total, limit, current_page, sports, filters, ...}}`. Default: 100 events on page 1. `meta.total` is honest (709 at probe time across all sports). |
| `GET /v1/uo/matches?sport_id=14&page=2&limit=100&sub_type_id=18&competition_id=222` | Same shape, filtered. `sport_id=14`=Soccer→257 prematch events. `sub_type_id` filters which market is embedded in each match's `odds[]` array. |
| `GET /v1/uo/matches?match_id=10846988&limit=1` | Same shape, `data` length 1. Single-match lookup. |
| `GET https://live.betika.com/v1/uo/matches` | Same shape, live catalogue. 92 events at probe. |

**Each match object** (from `data[]`):
```json
{
  "home_team": "Man City", "away_team": "Crystal Palace",
  "match_id": "10846988",            // Betika internal id
  "parent_match_id": "70784812",     // SportRadar match id (bare numeric)
  "game_id": "84168",                // short id, used in URLs
  "start_time": "2026-05-13 22:00:00",  // UTC naive ISO
  "competition_name": "Premier League",
  "competition_id": "222",
  "sport_id": "14", "sport_name": "Soccer",
  "category": "England",
  "home_odd": "1.22", "neutral_odd": "7.80", "away_odd": "12.00",  // pre-baked 1X2
  "side_bets": "8",                  // count of side-bet groups (string, not the list)
  "is_esport": false, "is_srl": false,
  "odds": [                          // ONE market group by default (1X2); use sub_type_id filter for others
    {"sub_type_id": "1", "name": "1X2", "odds": [
      {"display": "1", "odd_key": "Man City", "odd_value": "1.22", "outcome_id": "1", "special_bet_value": ""},
      ...
    ]}
  ]
}
```

**Market sub_type_ids** (confirmed via `sub_type_id=N` filter probes):

| `sub_type_id` | Name | Outcome `display` strings |
|---|---|---|
| `"1"` | `"1X2"` | `"1"`, `"X"`, `"2"` |
| `"10"` | `"DOUBLE CHANCE"` | `"1/X"`, `"X/2"`, `"1/2"` |
| `"18"` | `"TOTAL"` | `"OVER 1.5"`, `"UNDER 1.5"`, `"OVER 2.5"`, `"UNDER 2.5"`, ... (line in label) |
| `"29"` | `"BOTH TEAMS TO SCORE (GG/NG)"` | `"YES"`, `"NO"` (case varies — sometimes `"Yes"`/`"No"`) |
| `"60"` | `"1ST HALF - 1X2"` | `"1"`, `"X"`, `"2"` — not wired in v1 |

**No bot challenge.** `__cf_bm` cookie is set on the HTML root but API calls don't require it. No rate limits observed.

**No SportRadar id field is named `sr_id` / `betradar_id` / `external_id`** — only `parent_match_id`, which IS the SR id. Cross-verified.

## 4. Architecture

Same fan-out shape as the SportPesa addition. Files touched:

```
src/bookieskit/
├── __init__.py                              [+ Betika export, __version__ bump to 0.7.0]
├── config.py                                [+ BETIKA_MAX_CONCURRENT=50, BETIKA_REQUEST_DELAY=0.0]
├── event_info.py                            [+ _kickoff/_participants/_live_info_betika + dispatch rows]
├── bookmakers/
│   ├── betika.py                            [NEW — Betika(BaseBookmaker)]
│   └── types.py                             [no change — PrematchEventStub already shipped]
├── markets/
│   ├── types.py                             [+ `betika` field on OutcomeMapping, `betika_id` on MarketMapping]
│   ├── registry.py                          [+ _by_betika index, add() kwarg, get_by_platform_id dispatch]
│   ├── builtin_mappings.py                  [+ betika_id + betika= on 4 universal mappings; None/"" on 1Up/2Up]
│   └── parser.py                            [+ _parse_betika branch + helpers + _resolve_outcome_betika]
└── matching/
    ├── extractor.py                         [+ _extract_betika + dispatch row]
    └── matcher.py                           [+ betika field on MatchedEvent + branch in match_events]

tests/
├── test_betika.py                           [NEW — client wiring + @respx.mock tests per method]
├── test_parser_betika.py                    [NEW — parser tests bound to captured markets fixture]
├── test_extractor.py                        [+ betika SR-id cases]
├── test_event_info.py                       [+ betika in empty-dict parametrize, 3 betika-specific tests]
├── test_registry.py                         [+ betika lookup + 1Up/2Up unmapping tests]
├── test_convenience.py                      [+ Betika.get_markets routing test]
├── test_matcher.py                          [+ MatchedEvent.betika populates from ("betika", [...])]
├── test_probability.py                      [+ betika in parametrize at L63]
├── test_types.py                            [+ betika field round-trip on OutcomeMapping/MarketMapping]
├── test_iterators.py                        [+ test_betika_iter_all_prematch_events]
└── fixtures/event_info/betika/
    ├── prematch.json                        [NEW — captured Man City vs Crystal Palace]
    ├── live.json                            [NEW — captured live single-match]
    ├── markets.json                         [NEW — captured single match with all 4 universal markets aggregated]
    └── RESOLVED.md                          [NEW — decision record]

docs/
├── betika.md                                [NEW]
├── markets.md                               [+ Betika column in platform-id table]
├── matching.md                              [+ betika row in field-path table; MatchedEvent snippet]
└── examples.md                              [refresh bookmaker counts]

examples/
├── count_5bookies.py                        [+ count_betika using iter_all_prematch_events]
├── odds_for_sr_id.py                        [+ odds_betika direct-lookup]
├── odds_from_betpawa_id.py                  [+ Betika fan-out + CSV column]
└── odds_for_betpawa_competition.py          [+ Betika fan-out + CSV column]

scripts/
└── capture_event_info_fixtures.py           [+ unconditional Betika capture; no env-var guard needed]

CHANGELOG.md                                  [+ [0.7.0] section]
pyproject.toml                                [version 0.6.0 -> 0.7.0; description 6 -> 7 sportsbooks]
README.md                                     [tagline 6 -> 7; supported table; built-in markets column]
```

**Left untouched** (legacy / curated subsets): `monitor_competitions.py`, `test_live_flow.py`, `audit_full.py`, `final_audit.py`, `full_audit_4bookies.py`, `full_audit_v2.py`. Same posture as the SportPesa addition.

## 5. Component-level design

### 5.1 Client — `src/bookieskit/bookmakers/betika.py`

```python
class Betika(BaseBookmaker):
    """HTTP client for the Betika sportsbook API.

    Betika's API at api.betika.com is country-agnostic — every country
    code in DOMAINS maps to the same base URL because the API serves the
    same catalogue regardless of country. The `country` kwarg is accepted
    for symmetry with the other clients and is informational only.

    Prematch lives at api.betika.com; live lives at live.betika.com.

    Args:
        country: Country code (ke, ug, tz, mw, gh) — informational.
        timeout / max_retries / backoff_factor / max_concurrent /
        request_delay / cookie: inherited from BaseBookmaker.
    """
    DOMAINS = {
        "ke": "https://api.betika.com",
        "ug": "https://api.betika.com",
        "tz": "https://api.betika.com",
        "mw": "https://api.betika.com",
        "gh": "https://api.betika.com",
    }
    _LIVE_BASE_URL = "https://live.betika.com"
    DEFAULT_HEADERS = {
        "accept": "application/json",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/144.0.0.0 Safari/537.36"
        ),
    }
    MAX_CONCURRENT = BETIKA_MAX_CONCURRENT       # 50
    REQUEST_DELAY = BETIKA_REQUEST_DELAY         # 0.0
    NAME = "Betika"
    PLATFORM_KEY = "betika"
```

**Methods** (all async, all returning raw JSON dict unless noted):

| Method | HTTP | Path | Notes |
|---|---|---|---|
| `get_sports()` | GET | `/v1/sports` | Sport list with nested `categories[].competitions[]`. |
| `get_navigation()` | (alias) | — | Returns `get_sports()` verbatim. Convenience name — the sports response IS the navigation tree. |
| `get_matches(sport_id="14", page=1, limit=100, sub_type_id=None, competition_id=None)` | GET | `/v1/uo/matches` | Paginated prematch list. |
| `get_live_matches(sport_id="14", page=1, limit=100, sub_type_id=None)` | GET | `https://live.betika.com/v1/uo/matches` | Same shape, live subdomain. Uses a per-call `httpx.AsyncClient` (mirrors how Betway calls its `_CONFIG_BASE_URL`). |
| `get_event_detail(event_id, live=False)` | GET | `/v1/uo/matches?match_id={id}&limit=1` | Returns the single-match wrapper. SR id at `data[0].parent_match_id`. |
| `get_event_markets(event_id, live=False)` | (composite) | — | Aggregates per-sub_type_id calls into one response with all 4 universal markets populated in `data[0].odds`. Runs 4 calls concurrently under the existing semaphore. |
| `get_markets(event_id, registry=None) -> list[NormalizedMarket]` | (calls `get_event_markets`) | — | Standard convenience. |
| `get_sportradar_id(event_id, live=False) -> str \| None` | (calls `get_event_detail`) | — | Reads `parent_match_id`. |
| `iter_all_prematch_events() -> AsyncIterator[PrematchEventStub]` | (composite) | — | Full catalogue walk; see §5.6. |

`country` is honoured by being stored on the instance for introspection; it does not change request behaviour.

### 5.2 SR-id extractor — `src/bookieskit/matching/extractor.py`

```python
def _extract_betika(response) -> str | None:
    """Extract from Betika data[0].parent_match_id.

    The match endpoints return ``{"data": [<match>], "meta": {...}}``.
    `match_id` is Betika's internal id; `parent_match_id` is the SR
    canonical id (bare numeric, no `sr:match:` prefix).
    """
    if isinstance(response, dict):
        data = response.get("data") or []
    elif isinstance(response, list):
        data = response
    else:
        return None
    if not isinstance(data, list) or not data:
        return None
    match = data[0]
    if not isinstance(match, dict):
        return None
    sr = match.get("parent_match_id")
    if sr in (None, 0, "0", ""):
        return None
    return _strip_sr_prefix(str(sr))
```

Added under `"betika"` in the `extractors` dispatch dict. Total function (never raises).

### 5.3 Parser — `src/bookieskit/markets/parser.py`

```python
def _parse_betika(response, registry, _mode):
    data = response.get("data") if isinstance(response, dict) else None
    if not isinstance(data, list) or not data:
        return []
    match = data[0]
    if not isinstance(match, dict):
        return []
    market_groups = match.get("odds") or []

    results: list[NormalizedMarket] = []
    parameterized_groups: dict[str, list[dict]] = {}
    for group in market_groups:
        sub_type_id = str(group.get("sub_type_id", ""))
        mapping = registry.get_by_platform_id("betika", sub_type_id)
        if mapping is None:
            continue
        if mapping.parameterized:
            parameterized_groups.setdefault(sub_type_id, []).append(group)
        else:
            results.append(_parse_betika_simple(group, mapping))
    for sub_type_id, groups in parameterized_groups.items():
        mapping = registry.get_by_platform_id("betika", sub_type_id)
        if mapping:
            results.append(_parse_betika_parameterized(groups, mapping))
    return results
```

Helpers:
- **`_parse_betika_simple`** — reads each `group["odds"][i]["display"]`, casts `odd_value` to `float`, resolves outcome via `_resolve_outcome_betika`.
- **`_parse_betika_parameterized`** — flattens all odd entries across the group(s), extracts the line from `display` (`"OVER 2.5"` → `("over", 2.5)`), buckets by line into `lines: dict[float, list[Outcome]]`.
- **`_extract_line_from_betika_display(display: str) -> tuple[str, float] | None`** — splits the display label on the last whitespace, casts the suffix to float. Returns `None` on parse failure (the outcome is silently dropped).
- **`_resolve_outcome_betika(display: str, mapping: MarketMapping) -> str | None`** — case-insensitive exact match against `OutcomeMapping.betika`. For O/U, additionally strips any trailing whitespace + line from the display before matching (so `"OVER 2.5"` matches `OutcomeMapping.betika = "Over"`).

Probability mode is accepted but a no-op: Betika selections don't expose `probability` / `void_probability` fields, so both `Outcome.true_probability` and `Outcome.void_probability` stay `None` regardless of `mode`. Pinned in `test_parser_betika.test_parse_betika_probability_mode_passes_through`.

Dispatch row added under `"betika"`.

### 5.4 Types & registry

`OutcomeMapping.betika: str = ""` and `MarketMapping.betika_id: str | None = None` added with defaults — existing call sites compile unchanged.

`MarketRegistry`:
- `self._by_betika: dict[str, MarketMapping] = {}` in `__init__`.
- `if mapping.betika_id: self._by_betika[mapping.betika_id] = mapping` in `_register`.
- `betika_id: str | None = None` parameter on `add()`.
- `"betika": self._by_betika` row in `get_by_platform_id`'s dispatch dict.

### 5.5 Builtin mappings

| Canonical id | `betika_id` | Outcomes (canonical → `betika`) |
|---|---|---|
| `1x2_ft` | `"1"` | home=`"1"`, draw=`"X"`, away=`"2"` |
| `over_under_ft` | `"18"` | over=`"Over"`, under=`"Under"` |
| `btts_ft` | `"29"` | yes=`"Yes"`, no=`"No"` |
| `double_chance_ft` | `"10"` | home_draw=`"1/X"`, draw_away=`"X/2"`, home_away=`"1/2"` |
| `1x2_1up_ft` | `None` | all `""` |
| `1x2_2up_ft` | `None` | all `""` |

The parser's `_resolve_outcome_betika` is case-insensitive, so `"YES"` / `"Yes"` / `"yes"` all match `"Yes"`.

### 5.6 Catalogue iterator

```python
async def iter_all_prematch_events(self) -> AsyncIterator[PrematchEventStub]:
    sports_resp = await self.get_sports()
    sport_ids = [
        str(s.get("sport_id"))
        for s in sports_resp.get("data", []) or []
        if s.get("sport_id") is not None
    ]

    async def _fetch_page(sport_id: str, page: int) -> list:
        try:
            resp = await self.get_matches(
                sport_id=sport_id, page=page, limit=100
            )
            return resp.get("data", []) or []
        except Exception:
            return []

    async def _walk_sport(sport_id: str) -> list[tuple[str, str, str]]:
        page1 = await self.get_matches(sport_id=sport_id, page=1, limit=100)
        events = page1.get("data", []) or []
        total = int((page1.get("meta") or {}).get("total", 0) or 0)
        if total <= 100:
            page_lists = [events]
        else:
            n_pages = (total + 99) // 100
            extra = await asyncio.gather(
                *[_fetch_page(sport_id, p) for p in range(2, n_pages + 1)]
            )
            page_lists = [events] + list(extra)
        out: list[tuple[str, str, str]] = []
        for evs in page_lists:
            for ev in evs:
                eid = ev.get("match_id")
                cid = ev.get("competition_id")
                if eid is not None and cid is not None:
                    out.append((sport_id, str(cid), str(eid)))
        return out

    walks = await asyncio.gather(*[_walk_sport(sid) for sid in sport_ids])
    seen: set[str] = set()
    for sport_results in walks:
        for sport_id, league_id, event_id in sport_results:
            if event_id in seen:
                continue
            seen.add(event_id)
            yield PrematchEventStub(
                event_id=event_id, league_id=league_id, sport_id=sport_id,
            )
```

Three Betika-specific advantages over the existing iterators:
1. `meta.total` is honest — first page tells us the page count upfront, so the entire fan-out can be planned and dispatched in one `asyncio.gather` round.
2. `page=N` actually advances (unlike SportPesa's `page=` which is ignored).
3. No bot challenge / cookie warming.

Yields `PrematchEventStub(event_id=match_id, league_id=competition_id, sport_id=sport_id)`.

### 5.7 Event-info extractors — `src/bookieskit/event_info.py`

Three functions plus dispatch rows. Key fields:

| Function | Returns | Source |
|---|---|---|
| `_kickoff_betika` | tz-aware `datetime` or `None` | `data[0].start_time` — string `"2026-05-13 22:00:00"`, parsed as naive ISO and tagged UTC. |
| `_participants_betika` | `Participants(home, away)` | `data[0].home_team` / `data[0].away_team`. |
| `_live_info_betika` | `LiveInfo(...)` | Fixture-resolved. Probes plausible candidates (`minute`, `match_minute`, `period`, `match_status`, `home_score`, `away_score`); the implementation phase captures one live fixture and prunes the dead branches. Returns `_EMPTY_LIVE_INFO` for `mode="prematch"` and when no live fields are populated. |

All total functions — never raise on bad input.

### 5.8 Matcher

`MatchedEvent.betika: dict | None = None` field added in `matching/matcher.py`, plus `betika=platforms.get("betika")` in the `MatchedEvent(...)` construction inside `match_events`. Betika is a first-class cross-bookmaker participant because `parent_match_id` IS the SR id.

## 6. Public API additions

```python
# bookieskit/__init__.py
from bookieskit.bookmakers.betika import Betika
__all__ = [..., "Betika", ...]
__version__ = "0.7.0"

# Usage parity with the other 7 clients:
async with Betika(country="ke") as bk:
    markets = await bk.get_markets(event_id="10846988")
    sr_id = await bk.get_sportradar_id(event_id="10846988")
    async for ev in bk.iter_all_prematch_events():
        ...
```

## 7. Testing

| Test file | Coverage |
|---|---|
| `tests/test_betika.py` (NEW) | Country resolution (all 5 codes), unsupported-country error, `@respx.mock` per method (URL + query params + round-trip), top-level export check, version pin to `"0.7.0"`. |
| `tests/test_parser_betika.py` (NEW) | All 4 universal markets present; 1X2 outcomes; BTTS case-insensitive (`YES`/`yes`/`Yes` all match); DC pair outcomes; O/U parameterized with float-keyed `lines` dict; synthetic edge cases (empty payload, unknown sub_type_id, malformed odds, unknown display, probability mode passthrough). Bound to a captured `markets.json` fixture. |
| `tests/test_extractor.py` (extend) | SR-id from `data[0].parent_match_id`; missing / `0` / empty → `None`; `sr:match:` prefix stripped (defensive); bare-list shape works. |
| `tests/test_event_info.py` (extend) | `betika` added to the `test_empty_dict_does_not_raise` parametrize at L312; three betika-specific tests (`kickoff_prematch`, `participants_prematch`, `live_info_returns_empty_until_fixture_lands`). |
| `tests/test_registry.py` (extend) | `get_by_platform_id("betika", "1")` resolves to `1x2_ft`; `"18"` → `over_under_ft` (parameterized); `"29"` → `btts_ft`; `"10"` → `double_chance_ft`; 1Up/2Up have `betika_id=None` + `betika=""`. |
| `tests/test_convenience.py` (extend) | `Betika.get_markets()` routes through `get_event_markets` (aggregates per-sub_type_id), not raw event-detail. |
| `tests/test_matcher.py` (extend) | `match_events` populates `MatchedEvent.betika` when fed a `("betika", [...])` tuple containing `parent_match_id`. |
| `tests/test_probability.py` (extend) | `betika` added at L63 parametrize — kwarg accepted across all 7 platforms in all 3 modes. |
| `tests/test_types.py` (extend) | `OutcomeMapping(betika=...)` and `MarketMapping(betika_id=...)` round-trip; default values. |
| `tests/test_iterators.py` (extend) | `test_betika_iter_all_prematch_events` — mock `/v1/sports` + paginated `/v1/uo/matches`, verify `meta.total`-driven page count, distinct event_ids, and exactly one call per (sport, page). |
| `tests/fixtures/event_info/betika/{prematch,live,markets}.json` (NEW) | Captured Man City vs Crystal Palace + a live event + the aggregated markets payload. |
| `tests/fixtures/event_info/betika/RESOLVED.md` (NEW) | Field-path decision record. |

**Coverage gate**: every public method on `Betika` is exercised. No silent gaps.

**Capture script**: `scripts/capture_event_info_fixtures.py` gets one extra `_save("betika", phase, betika_detail)` call per phase. No env-var guard required (no Akamai gate).

## 8. Docs, examples, packaging

| File | Change |
|---|---|
| `docs/betika.md` (NEW) | Structure mirrors `docs/sportpesa.md`. Countries (5, all informational), SR-id at `parent_match_id`, methods table (incl. `get_sports`, `get_navigation` alias, `get_matches`, `get_live_matches`, `get_event_detail`, `get_event_markets`, `get_markets`, `get_sportradar_id`, `iter_all_prematch_events`, inherited `set_cookie`), quirks (single-domain API, country is a label, prematch+live on different subdomains, case-mixed outcome labels), recipes. |
| `docs/markets.md` | Extend platform-id table with `Betika` column; update dispatcher prose to enumerate `"betika"`. |
| `docs/matching.md` | Add `betika \| data[0].parent_match_id` row to the field-path table. Update the `MatchedEvent` snippet to include `betika`. |
| `docs/examples.md` | Refresh bookmaker counts (6 → 7 where relevant). |
| `README.md` | Tagline `6 → 7`. Supported-bookmakers table grows `Betika ke, ug, tz, mw, gh`. Built-in markets table grows a `Betika` column (✅ × 4, — × 2). Limitations section: no Betika-specific gaps. |
| `pyproject.toml` | `version "0.7.0"`; description updated to "7 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport, SportPesa, Betika)...". |
| `src/bookieskit/__init__.py` | Export `Betika`, bump `__version__`. |
| `CHANGELOG.md` | New `[0.7.0]` section: added Betika, types gained `betika`/`betika_id` columns, `MatchedEvent.betika`, full example parity. No breaking changes. |
| `examples/count_5bookies.py` | Add `count_betika()` using `iter_all_prematch_events`; add to the iteration tuple. |
| `examples/odds_for_sr_id.py` | Add `odds_betika(sr_numeric, sr_prefixed, *, live)` — for now uses catalogue walk + `parent_match_id` match (Betika has no direct `parent_match_id=X` filter on the matches endpoint; implementation phase verifies and adjusts). |
| `examples/odds_from_betpawa_id.py` / `odds_for_betpawa_competition.py` | Add Betika to the fan-out + CSV column. |
| `scripts/capture_event_info_fixtures.py` | Capture Betika unconditionally. |

## 9. Known gaps / limitations

1. **Live-info field paths are fixture-resolved.** `_live_info_betika` probes plausible candidate fields (`minute`, `match_minute`, `period`, `match_status`, `home_score`, `away_score`). The implementation phase captures one live fixture and prunes the dead branches. Until then, the function returns `_EMPTY_LIVE_INFO` if no fields are populated.
2. **No atomic markets-detail endpoint.** `/v1/uo/matches?match_id=X&limit=1` returns the match but its `odds[]` array carries only one market group (default 1X2). To get all 4 universal markets, `get_event_markets` issues 4 parallel calls (one per `sub_type_id` of interest) and merges. Documented; not a defect, just an API quirk.
3. **Outcome `display` labels are case-mixed across endpoints** (`"YES"` vs `"Yes"`, `"OVER 2.5"` vs `"Over 2.5"`). Parser resolves case-insensitively; pinned in tests.
4. **SR-id lookup from a SR id is indirect.** Betika has no observed `parent_match_id=X` filter on `/v1/uo/matches`. For `odds_for_sr_id.py`-style cross-bookmaker lookups, the example walks the catalogue and filters in memory. Implementation phase: try `?parent_match_id=X` first; if the API accepts it, use it; otherwise fall back to catalogue walk + filter.

## 10. Migration & compatibility

- `OutcomeMapping` and `MarketMapping` gain new defaulted fields (`betika: str = ""`, `betika_id: str | None = None`). All existing user code continues to compile.
- `MarketRegistry.add(...)` gains a defaulted `betika_id=None` kwarg. Existing call sites unaffected.
- `MatchedEvent` gains a defaulted `betika: dict | None = None` field. Existing constructors unaffected.
- Version bumps `0.6.0 → 0.7.0`. **No breaking changes.** Anyone upgrading from 0.6.0 sees Betika as a pure addition; their existing code with 6-bookmaker workflows runs unchanged.

## 11. Implementation phases (preview — full plan in writing-plans phase)

**Phase 0 — Fixture capture (~5 min, no warmed cookies needed).** Extend `scripts/capture_event_info_fixtures.py` to save Betika prematch + live fixtures plus an aggregated `markets.json`. Inspect captured payloads and lock in: kickoff/participants/live-info field paths; pin the BTTS/O/U display-string case variants. Write `tests/fixtures/event_info/betika/RESOLVED.md`.

**Phase 1 — Types, registry, builtin mappings, matcher (single commit).** Add `betika`/`betika_id` columns, `_by_betika` index, the 4 universal mappings populated, `MatchedEvent.betika`. Tests in `test_types.py`, `test_registry.py`, `test_matcher.py`.

**Phase 2 — Extractor, parser, event_info (internally parallel).** `_extract_betika`, `_parse_betika` + helpers + `_resolve_outcome_betika`, three event_info functions + dispatch rows. Bind to Phase 0 fixtures; prune hypothesis branches. Tests in `test_extractor.py`, `test_parser_betika.py`, `test_event_info.py`, `test_probability.py`.

**Phase 3 — Client + iterator + public-API wiring.** `src/bookieskit/bookmakers/betika.py` with all 9 methods. `iter_all_prematch_events` using the `meta.total`-driven concurrent fan-out. `__init__.py` export + `__version__` bump. `pyproject.toml` version+description. `tests/test_betika.py`, `tests/test_convenience.py`, `tests/test_iterators.py`.

**Phase 4 — Docs + examples.** `docs/betika.md`, `docs/markets.md`, `docs/matching.md`, `docs/examples.md`, `README.md`. Fan Betika into `count_5bookies.py`, `odds_for_sr_id.py`, `odds_from_betpawa_id.py`, `odds_for_betpawa_competition.py`. Legacy scripts untouched.

**Phase 5 — CHANGELOG + smoke + ship.** Author the `[0.7.0]` entry. `pytest -x` clean; `ruff check src tests examples` clean. Live smoke against `api.betika.com`: full `count_5bookies` run with all 7 bookmakers reporting consistent numbers; one `Betika.get_markets()` against a real match; one `match_events` call mixing Betika and SportyBet events to confirm cross-matching via `parent_match_id`. Commit, tag `v0.7.0`, push.
