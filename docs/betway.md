# Betway

## Supported Countries

| Code | Country | `countryCode` param |
|------|---------|---------------------|
| `ng` | Nigeria | `NG` |
| `gh` | Ghana | `GH` |
| `ke` | Kenya | `KE` |
| `tz` | Tanzania | `TZ` |
| `ug` | Uganda | `UG` |
| `zm` | Zambia | `ZM` |
| `za` | South Africa | `ZA` |

All countries share the same data domain (`https://feeds-roa2.betwayafrica.com`); the country is passed via the `countryCode` query parameter on every request. The sports list comes from a separate config domain (`https://config.betwayafrica.com`). `za` was added in 0.8.0 after probing `https://config.betwayafrica.com/cron/sports/ZA/en-US` and getting a populated 200 response.

## SportRadar id

Betway's `eventId` IS the bare numeric SportRadar id (no `sr:match:` prefix). This means:

- `extract_sportradar_id(response, platform="betway")` reads `sportEvent.eventId` and returns it as-is.
- `Betway.get_sportradar_id(event_id)` is a synchronous identity (no API call) — it just returns the input.
- Direct lookups by SR id work: `await betway.get_markets(event_id="69339436")`.

## Methods

| Method | HTTP | Domain | Path | When to use |
|--------|------|--------|------|-------------|
| `get_sports()` | GET | config | `/cron/sports/{countryCode}/en-US` | Top-level sport list with live counts. |
| `get_countries(sport_id)` | GET | feeds | `/br/_apis/sport/v1/Feeds/RegionsAndLeagues/{sport_id}` | Regions + leagues for one sport. |
| `get_tournaments(sport_id)` | GET | feeds | (same) | Alias for `get_countries`. |
| `get_events(...)` | GET | feeds | `BetBook/Highlights/` (unfiltered, ≤29 events) or `BetBook/Filtered/` (when region_id+league_id are set) | Events for a sport / region / league. Highlights is silently capped — for catalogue enumeration use `iter_all_prematch_events`. The `market_types` parameter defaults to `[Win/Draw/Win]` (football 1X2); pass `""` to include sports without that market. |
| `get_live_events(sport_id, skip, take, market_types)` | GET | feeds | `BetBook/LiveInPlay/` | In-play events for one sport. `market_types` defaults to `""` (all) — passing a sport-incompatible filter silently returns zero events. |
| `get_event_detail(event_id)` | GET | feeds | `Feeds/Events/EventAndGameState` | Scoreboard / state info — **no markets**. |
| `get_event_markets(event_id, skip, take)` | GET | feeds | `MarketGroupings/MarketGroupNamesAndMarketsForEvent` | Full markets feed for an event. |
| `iter_all_prematch_events()` | async iterator | feeds | (walks regions/leagues, fans out per-league) | Yields `PrematchEventStub(event_id, league_id, sport_id)` for every event in the full prematch catalogue. Passes `market_types=""` so all sports are covered. |
| `get_markets(event_id, registry=None)` | (calls `get_event_markets`) | — | Inherited convenience overridden — calls the markets endpoint, not event_detail. |
| `get_sportradar_id(event_id)` | (no API call) | — | Returns the input — `event_id` IS the SR numeric id. |
| `set_cookie(cookie)` | — | — | Inherited from `BaseBookmaker`. Rarely needed for Betway (no Akamai gate). |

### `get_sports() -> dict`

Top-level sport list. Uses the config domain (separate httpx client). Filter `sportType == "Sport"` to skip aggregate categories. Each sport has `sportId`, `name`, `liveInPlayCount`, `hasUpcomingEvents`.

### `get_countries(sport_id: str) -> dict`

Regions and leagues under one sport. Response: `regions[].leagues[]`.

### `get_tournaments(sport_id: str) -> dict`

Alias for `get_countries` — returns the same regions+leagues structure.

### `get_events(sport_id=None, region_id=None, league_id=None, market_types=None, ...) -> dict`

Events for a sport / region / league. Filter combinations supported. When both `region_id` and `league_id` are supplied the `BetBook/Filtered/` endpoint is used; otherwise `BetBook/Highlights/`. Response: `events[]` with `eventId`, `homeTeam`, `awayTeam`, `league`, `isLive`, etc.

### `get_event_detail(event_id: str) -> dict`

**Returns scoreboard / metadata only — NOT markets.** Response: `sportEvent` (with `eventId`, `name` like `"Arsenal FC vs. Atletico Madrid"`) and `gameStateTimeScore`. To get odds, use `get_event_markets` (or the convenience `get_markets`).

### `get_event_markets(event_id: str, skip: int = 0, take: int = 100) -> dict`

The actual markets/odds endpoint. Returns denormalized data joined by id:

- `marketsInGroup[]` — each entry has `marketId`, `name` (e.g. `"[Win/Draw/Win]"`, `"1X2 (1Up)"`), `handicap`.
- `outcomes[]` — each entry has `outcomeId`, `marketId`, `name` (e.g. `"Aston Villa"`, `"Over"`).
- `prices[]` — each entry has `outcomeId`, `priceDecimal`.

The library's parser walks all three arrays to produce normalized markets. Pagination via `skip` / `take` for events with very large market books.

### `get_markets(event_id, registry=None) -> list[NormalizedMarket]`

Overrides the base `get_markets`. Calls `get_event_markets` (NOT `get_event_detail`) and runs `parse_markets(..., platform="betway")`. This is the right entry point for normalized odds — `get_event_detail` won't work because it has no markets.

### `get_sportradar_id(event_id) -> str | None`

Overrides the base method. Returns `event_id` directly without an API call — Betway's event ids ARE the SR numeric.

## Quirks

- **Two domains**: sports list from `config.betwayafrica.com`, everything else from `feeds-roa2.betwayafrica.com`. The client manages both transparently.
- **Markets and event detail are SEPARATE endpoints**: `get_event_detail` returns no markets. Use `get_event_markets` (or `get_markets`) for odds.
- **Markets feed is denormalized**: `marketsInGroup[]`, `outcomes[]`, `prices[]` linked by `marketId` and `outcomeId`. The parser handles the join.
- **Position-based outcome resolution** (1X2, DC, 1X2 1Up, 1X2 2Up): outcomes are returned in order without explicit names like "Home"/"Draw"/"Away" — the parser uses `__HOME__` / `__AWAY__` / `__POS_N__` sentinels (see [docs/markets.md](markets.md)).
- **`countryCode` query parameter** is added to every feeds-domain request automatically.

## Recipes

### List soccer leagues for a country

```python
import asyncio
from bookieskit import Betway

async def main():
    async with Betway(country="ng") as bw:
        raw = await bw.get_countries(sport_id="soccer")
        regions = raw.get("regions", [])
        for r in regions[:5]:
            for lg in r.get("leagues", [])[:3]:
                print(f"{r.get('name')}/{lg.get('name')} (id: {lg.get('leagueId')})")

asyncio.run(main())
```

### Normalized markets for one event

```python
import asyncio
from bookieskit import Betway

async def main():
    async with Betway(country="ng") as bw:
        # Betway's event id IS the bare numeric SR id.
        markets = await bw.get_markets(event_id="69339436")
        for m in markets:
            if m.lines:
                lines = sorted(m.lines.keys())[:3]
                for line in lines:
                    odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[line])
                    print(f"  {m.name} [{line}]: {odds}")
            else:
                odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
                print(f"  {m.name}: {odds}")

asyncio.run(main())
```

### Inspect raw markets / outcomes / prices

```python
import asyncio
from bookieskit import Betway

async def main():
    async with Betway(country="ng") as bw:
        raw = await bw.get_event_markets(event_id="69339436")
        print(f"markets: {len(raw.get('marketsInGroup', []))}")
        print(f"outcomes: {len(raw.get('outcomes', []))}")
        print(f"prices: {len(raw.get('prices', []))}")
        # Example: find any 1X2 (1Up) variant
        for m in raw.get("marketsInGroup", []):
            if "1Up" in (m.get("name") or ""):
                print(m)

asyncio.run(main())
```

## See also

- `examples/odds_from_betpawa_id.py` (uses `Betway.get_markets`).
- [docs/markets.md](markets.md) — position sentinels section.
- [docs/matching.md](matching.md).
