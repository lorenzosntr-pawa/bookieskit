# MSport Bookmaker — Design

**Status:** approved, ready for implementation plan
**Date:** 2026-05-05
**Related research:** `docs/specs/msport-api-research.md`

## Goal

Add MSport as the fifth bookmaker client in `bookieskit`, alongside BetPawa, SportyBet, Bet9ja, and Betway. The MSport API is structurally close to SportyBet (same SportRadar IDs, same headers, same market/outcome IDs), but the endpoint shape and a few field names differ — those differences must be preserved rather than papered over.

## Scope

- Prematch coverage: sports list, events grouped by tournament, full event detail.
- Live coverage: live sports list, live events grouped by tournament.
- Country footprint: `ng`, `gh`, `ke` — all served by `https://www.msport.com` with a `/api/{country}/...` path prefix.
- Built-in market parsing for the 4 mappings already shipped (1X2, Over/Under, BTTS, Double Chance) — IDs and outcomes are identical to SportyBet's.
- SportRadar ID extraction for cross-bookmaker matching.

Out of scope for this design (follow-up phases):
- A 5-bookie variant of `examples/full_audit_4bookies.py`.
- A live-flow demo under `examples/`.
- Mappings for additional MSport markets beyond the 4 builtins.

## Architecture

MSport plugs into the existing per-platform pattern. No structural changes to the library; one new module per existing concern, plus per-platform fields on the two mapping types.

```
src/bookieskit/
├── bookmakers/
│   ├── msport.py            ← NEW: MSport client (subclasses BaseBookmaker)
│   └── __init__.py          ← export MSport
├── markets/
│   ├── parser.py            ← add _parse_msport + dispatcher entry
│   ├── types.py             ← MarketMapping.msport_id, OutcomeMapping.msport
│   ├── registry.py          ← add _by_msport index + lookup branch
│   └── builtin_mappings.py  ← add msport_id / msport on the 4 builtins
├── matching/extractor.py    ← add _extract_msport + dispatcher entry
├── config.py                ← MSPORT_MAX_CONCURRENT, MSPORT_REQUEST_DELAY
└── __init__.py              ← export MSport
```

Class identity:
- Class name: `MSport`
- `PLATFORM_KEY = "msport"`
- `NAME = "MSport"`
- Domain mapping: `{"ng", "gh", "ke"}` all → `https://www.msport.com`; country differentiates via the `/api/{country}/...` path prefix.

## Client method surface

`MSport(BaseBookmaker)` — base path: `/api/{country}/facts-center/query/frontend`.
Headers identical to SportyBet:
```
operid: 2
clientid: web
platform: web
accept: */*
accept-language: en
user-agent: <Chrome desktop UA>
```

Methods (all `async`, all return raw JSON dicts — normalization happens via `BaseBookmaker.get_markets()` / `get_sportradar_id()`, both already inherited):

```python
async def get_sports() -> dict
    GET /sports
    # data.sports: [{sportId, sportName, count}, ...]   (~31 sports)

async def get_events(sport_id: str = "sr:sport:1") -> dict
    GET /sports-matches-list?sportId={sport_id}
    # data.tournaments: [{category, tournament, tournamentId, events: [...]}]
    # All matches for a sport, grouped by tournament — no per-tournament endpoint.

async def get_event_detail(event_id: str) -> dict
    GET /match/detail?eventId={event_id}&productId=3
    # data: {eventId, homeTeam, awayTeam, markets: [...]}  (~407 markets per match)

async def get_live_sports() -> dict
    GET /live-matches/sports
    # data.sports: [{sportId, sportName, count}, ...]   (~24 sports with live counts)

async def get_live_events(sport_id: str = "sr:sport:1") -> dict
    GET /live-matches/list?sportId={sport_id}
    # data: {tournaments, events, comingSoons}
```

Notes on shape decisions:
- `get_events(sport_id)` not `get_events(tournament_id, sport_id)`. The MSport API returns all matches for a sport in one call, grouped by tournament — there is no per-tournament fetch. Pre-existing SportyBet shape does not apply here.
- Live uses `/live-matches/list?sportId=` (the richer variant) rather than `/live-matches?sportId=` (bare events). Symmetric with prematch grouping; the extra `comingSoons` is preserved when present.
- All sport-scoped methods default `sport_id="sr:sport:1"` (Soccer) for ergonomics, matching the SportyBet/Bet9ja pattern. Callers can pass any of the 31 prematch / 24 live sport IDs.
- No timestamp `_t` cache-buster on the GETs (research did not show one being required). Trivial to add later if caching issues appear in practice.

Rate limits: `MSPORT_MAX_CONCURRENT = 50`, `MSPORT_REQUEST_DELAY = 0.0` — mirror SportyBet defaults until evidence suggests otherwise.

## Registry types — additive changes

`markets/types.py`:
```python
@dataclass(frozen=True)
class MarketMapping:
    ...
    msport_id: str | None = None       # NEW

@dataclass(frozen=True)
class OutcomeMapping:
    ...
    msport: str = ""                   # NEW
```

`markets/registry.py`:
- Add `self._by_msport: dict[str, MarketMapping] = {}` in `__init__`.
- In `_register`: if `mapping.msport_id`, index it.
- In `add(...)`: accept `msport_id: str | None = None` kwarg and pass through.
- In `get_by_platform_id`: extend the dispatch dict with `"msport": self._by_msport`.

`markets/builtin_mappings.py` — the 4 existing builtins gain:
| Canonical | `msport_id` | `msport` outcome strings |
|-----------|-------------|--------------------------|
| `1x2_ft` | `"1"` | home="Home", draw="Draw", away="Away" |
| `over_under_ft` | `"18"` | over="Over", under="Under" |
| `btts_ft` | `"29"` | yes="Yes", no="No" |
| `double_chance_ft` | `"10"` | home_draw="Home or Draw", draw_away="Draw or Away", home_away="Home or Away" |

Values are identical to the SportyBet column. They are duplicated rather than shared because the codebase consistently treats each platform as independent, and a future divergence on one side should not force an unwind on the other.

## Parser — `_parse_msport`

Near-twin of `_parse_sportybet`, with the following concrete differences:

| Aspect | SportyBet | MSport |
|--------|-----------|--------|
| Outcome name field | `outcome["desc"]` | `outcome["description"]` |
| Specifier field | `market["specifier"]` | `market["specifiers"]` |
| Platform key | `"sportybet"` | `"msport"` |
| Outcome resolution | reads `om.sportybet` | reads `om.msport` |

Everything else is the same:
- Reads markets from `data.markets` (with top-level `markets` fallback).
- Looks up by integer-string market id via `registry.get_by_platform_id("msport", market_id)`.
- Parameterized markets are grouped by id across multiple entries (one entry per line), same as SportyBet.
- Specifier parsing reuses the existing `_extract_line_from_specifier` helper — MSport's `specifiers` payload uses the same `total=...|hcp=...` pipe-delimited format.
- `_resolve_outcome_msport` does an exact match first, then a prefix match (handles parameterized payloads where the platform name embeds the line, e.g. `"Over 2.5"`).

The dispatcher in `parse_markets()` gains an `"msport": _parse_msport` entry.

## Extractor — `_extract_msport`

`matching/extractor.py` adds an MSport branch identical in shape to `_extract_sportybet`:
- Reads `response["data"]["eventId"]`.
- Returns `_strip_sr_prefix(str(event_id))` (strips the `sr:match:` prefix).
- Returns `None` when `data` or `eventId` is missing.

Add `"msport": _extract_msport` to the dispatcher.

## Why not share with SportyBet

Two alternatives were considered and rejected:

1. **Route `"msport"` through `_parse_sportybet` via a field-rename shim.** Smaller diff (~30 LOC), but it couples the two platforms: any future SportyBet ID divergence forces the shim to grow special cases. The codebase consistently treats each platform as independent (each gets its own field on `MarketMapping`/`OutcomeMapping` and its own `_parse_X`/`_extract_X`).
2. **Refactor `_parse_sportybet` into a generic `_parse_sr_style(...)` parametrized by field names.** Cleanest long-term, but introduces an abstraction now for a 2-platform case. If a sixth SportRadar-style platform ever appears, this refactor remains an option then.

The chosen approach matches how Bet9ja-vs-SportyBet were left independent despite some structural overlap.

## Configuration

`config.py` adds:
```python
MSPORT_MAX_CONCURRENT = 50
MSPORT_REQUEST_DELAY = 0.0
```

These mirror SportyBet's defaults. Tunable via the standard `max_concurrent` / `request_delay` constructor kwargs on `MSport(...)`.

## Public API

`src/bookieskit/__init__.py` and `src/bookieskit/bookmakers/__init__.py`:
- Import `MSport` from `bookmakers.msport`.
- Add `"MSport"` to `__all__`.

Version bump: `__version__ = "0.3.0"` → `"0.4.0"`.

## Testing

New test files:
- `tests/test_msport.py` — client tests with `respx` mocks. One test each for: domain resolution per country (`ng`, `gh`, `ke`); `UnsupportedCountryError` on bad country code; header verification (`operid`, `clientid`, `platform`); happy path per public method (`get_sports`, `get_events`, `get_event_detail`, `get_live_sports`, `get_live_events`); per-country path prefix (e.g. `/api/gh/facts-center/...`).
- `tests/test_parser_msport.py` — parser unit tests using fixture-style raw responses. Cover: simple markets (1X2, BTTS, DC) parsed via `description` outcome names; parameterized O/U with `specifiers` line extraction; multi-line grouping across multiple entries with the same `id`; unknown-market skip; exact-then-prefix outcome fallback for parameterized markets.

Existing tests to extend:
- `tests/test_extractor.py` — add `_extract_msport` cases: happy path with `data.eventId = "sr:match:12345"` returning `"12345"`; missing `data` returns `None`; missing `eventId` returns `None`.
- `tests/test_registry.py` — verify `msport_id` round-trips through `get_by_platform_id("msport", ...)` for the 4 builtins.
- `tests/test_types.py` — verify the two new fields (`msport_id`, `msport`) default correctly and don't break existing equality / frozen-dataclass behaviour.

## Documentation

- `docs/msport.md` — short client reference in the style of `sportybet.md` / `bet9ja.md`: countries, method signatures, sample request/response payloads, notes on quirks. The deeper API research stays at `docs/specs/msport-api-research.md`.
- `README.md` — update bookmaker count (4 → 5) and add MSport to any feature matrices / install snippets that enumerate platforms.

## Risk and follow-ups

- **Cache busting.** If MSport's CDN returns stale data on rapid repeated GETs, add a `_t` timestamp parameter the same way SportyBet does. Detection: a follow-up audit run that flags identical responses across calls separated by minutes.
- **Live `comingSoons`.** Currently surfaced raw on `data.comingSoons` of `get_live_events`. Consumers can ignore. If we later want to normalize them as upcoming-events stream, that's a separate phase.
- **Sport / market coverage beyond the 4 builtins.** The MSport event-detail endpoint returns ~407 markets. Supporting more requires extending `BUILTIN_MAPPINGS` (or registering custom mappings via `MarketRegistry.add(...)`) — out of scope here.
