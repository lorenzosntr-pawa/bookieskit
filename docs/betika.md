# Betika

## Supported Countries

| Code | Country |
|------|---------|
| `ke` | Kenya |
| `ug` | Uganda |
| `tz` | Tanzania |
| `mw` | Malawi |
| `gh` | Ghana |

Betika's API is country-agnostic: every supported country code resolves to the same `api.betika.com` (prematch) and `live.betika.com` (in-play) hosts. The `country` argument is preserved on the instance for informational use (logging, UI labels) but does not drive any URL, header, or filtering behaviour. Any other code raises `UnsupportedCountryError`.

## SportRadar id

Betika exposes the SR id directly on the event-detail payload at `data[0].parent_match_id` (Betika's own `match_id` is a different, internal identifier). Cross-verified against SportyBet: `parent_match_id="70784812"` resolves to Man City vs Crystal Palace on both platforms.

- `extract_sportradar_id(response, platform="betika")` returns the bare numeric SR id (no `sr:match:` prefix), or `None` if not present.
- `Betika.get_sportradar_id(event_id)` fetches event-detail and runs the extractor.

The `parent_match_id` field is a string in prematch responses and an integer in live responses; the extractor handles both via `str()` coercion.

## Methods

| Method | HTTP | Path | When to use |
|--------|------|------|-------------|
| `get_sports()` | GET | `/v1/sports` | Sport catalogue. Football is `id=14`. |
| `get_navigation()` | (alias) | — | Alias for `get_sports()`. Betika has no single sport → category → competition tree endpoint; the alias is preserved so cross-bookmaker code that calls `get_navigation()` still gets *something* useful. |
| `get_matches(sport_id=14, page=1, limit=100, sub_type_id=None, competition_id=None, match_id=None)` | GET | `/v1/uo/matches` | Prematch list. `meta.total` is authoritative — use it to drive pagination. `sub_type_id` filters which market group is embedded in each match's `odds` (default 1X2). |
| `get_live_matches(sport_id=14, page=1, limit=100, match_id=None)` | GET | `live.betika.com/v1/uo/matches` | Currently-live matches. Same shape as `get_matches`, plus the in-play scoreboard fields (`match_time`, `event_status`, `current_score` etc.). |
| `get_event_detail(event_id, live=False, competition_id=None)` | GET | `/v1/uo/matches?match_id=...&limit=1` | One event's metadata + SR id. Pass `live=True` to fetch from the live host. `competition_id` is strongly recommended (see "match_id is not globally unique" below). |
| `get_event_markets(event_id, live=False, competition_id=None)` | (4-call aggregation) | `/v1/uo/matches?match_id=...&sub_type_id=N` × 4 | Full universal market set. Fans out one call per `sub_type_id` ∈ {1, 10, 18, 29} concurrently and stitches their `odds` groups into one match-shaped response. `competition_id` (when supplied) is forwarded on every sub-call. |
| `get_markets(event_id, registry=None)` | (calls `get_event_markets`) | — | Inherited convenience overridden — runs the 4-call aggregator, then the parser. |
| `iter_all_prematch_events(sport_id=14, limit=100)` | async iterator | (page=1 + concurrent fan-out) | Yields `PrematchEventStub(event_id, league_id, sport_id)` for every match. The first page's `meta.total` drives the page count; remaining pages are fetched in parallel under the client's `MAX_CONCURRENT` semaphore. |
| `get_sportradar_id(event_id, live=False)` | (calls `get_event_detail`) | — | Fetches detail, extracts `data[0].parent_match_id`. |

## Quirks

- **Open API.** No Cloudflare gate, no warmed cookies, no observed rate limit under bursty traffic. Default `MAX_CONCURRENT=50` / `REQUEST_DELAY=0.0`.
- **Country is informational.** All five supported country codes hit the same host. There is no per-country timezone header to set.
- **Two hosts, one client.** Prematch endpoints live on `api.betika.com`; in-play endpoints live on `live.betika.com`. The Betika class binds its `base_url` to `api.betika.com` and forwards live calls via `_live_request()` (which passes an absolute URL to the same retry / semaphore stack).
- **`match_id` is unique only per `(sport_id, competition_id)`.** Within a sport, multiple matches can share the same `match_id`; the API only disambiguates when `competition_id` is also supplied. A bare lookup by `match_id + sport_id` may resolve to a different match — observed live on tennis where match_id `10945420` resolves to either Svrcina/Den Ouden (French Open) or Tsitsipas/Mpetshi (ATP Geneva) depending on which competition is in scope first. **Always pass `competition_id` when you have it** (the listing endpoint includes it on every match row as `competition_id`). The example index builder in `examples/compare_betpawa_competition_full.py:build_betika_index` shows the pattern: index entries are `{sr_id: (match_id, competition_id)}` tuples, and the fetcher forwards `competition_id` on every per-match call.
- **`match_id` is not globally unique across sports either.** Pass `sport_id` too — the same numeric `match_id` is reused per-sport (e.g. tennis match_id `10945420` and soccer match_id `10945420` are different events).
- **One market per call.** `/v1/uo/matches` returns exactly one market group (typically 1X2) per match by default. To get a different market you must repeat the call with `&sub_type_id=N`. `get_event_markets` handles this for you by fanning out the four universal `sub_type_ids` concurrently.
- **Universal `sub_type_id` mapping (soccer):** `1` = 1X2, `10` = Double Chance, `18` = Over/Under, `29` = BTTS.
- **Other sports use different `sub_type_id`s:** basketball uses `219` (ML) / `225` (O/U); tennis uses `186` (Winner) / `187` (Game Handicap) / `189` (Total Games) / `188` (Set Handicap). The lib's `get_event_markets` is hardcoded to the four soccer ids — for other sports, call `_request("GET", "/v1/uo/matches", ...)` per sub_type_id yourself or use the `fetch_betika_markets_sportaware` helper in `examples/compare_betpawa_competition_full.py`.
- **Parameterized markets carry the line in the display label.** Over/Under selections come back as `display="OVER 2.5"` / `display="UNDER 2.5"`. The parser prefers `special_bet_value` when present and falls back to extracting the first number from the label.
- **Outcome resolution is case-insensitive.** Betika's BTTS feed has been observed returning `"YES"` / `"NO"` and `"Yes"` / `"No"` interchangeably; the parser lowercases both sides before comparing.
- **`parent_match_id` type varies.** String in prematch, integer in live. The extractor coerces via `str()`.

## Recipes

### Normalized markets for one event

```python
import asyncio
from bookieskit import Betika

async def main():
    async with Betika(country="ke") as bk:
        markets = await bk.get_markets(event_id="10846988")
        for m in markets:
            if m.lines:
                for line in sorted(m.lines.keys())[:3]:
                    odds = ", ".join(
                        f"{o.canonical_name}={o.odds}" for o in m.lines[line]
                    )
                    print(f"  {m.name} [{line}]: {odds}")
            else:
                odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
                print(f"  {m.name}: {odds}")

asyncio.run(main())
```

### Enumerate the full prematch catalogue

```python
import asyncio
from bookieskit import Betika

async def main():
    async with Betika(country="ke") as bk:
        async for stub in bk.iter_all_prematch_events():
            print(stub.event_id, stub.league_id)

asyncio.run(main())
```

### Cross-reference with another bookmaker via SR id

```python
import asyncio
from bookieskit import Betika, SportyBet
from bookieskit.matching import match_events

async def main():
    async with Betika(country="ke") as bk, SportyBet(country="ke") as sb:
        bk_event = await bk.get_event_detail(event_id="10846988")
        sb_event = await sb.get_event_detail(event_id="sr:match:70784812")
        matched = match_events(("betika", [bk_event]), ("sportybet", [sb_event]))
        for m in matched:
            print(m.sportradar_id, "→ betika", bool(m.betika), "sportybet", bool(m.sportybet))

asyncio.run(main())
```

## See also

- `examples/odds_for_sr_id.py` — cross-bookmaker SR-id fan-out (includes Betika).
- [docs/markets.md](markets.md) — canonical market mapping reference.
- [docs/matching.md](matching.md) — SR-id extraction reference per platform.
