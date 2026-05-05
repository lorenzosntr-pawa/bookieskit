# MSport

## Supported Countries

| Code | Domain | API Path |
|------|--------|----------|
| `ng` | https://www.msport.com | `/api/ng/...` |
| `gh` | https://www.msport.com | `/api/gh/...` |
| `ke` | https://www.msport.com | `/api/ke/...` |

All countries share the same domain — the country segment lives in the URL path under `/api/{country}/facts-center/query/frontend/...`.

## SportRadar id

MSport's `eventId` IS `sr:match:<numeric>` (same as SportyBet). The library's `extract_sportradar_id(response, platform="msport")` reads `data.eventId` and strips the `sr:match:` prefix. Direct lookups by SR id work — pass `event_id="sr:match:<numeric>"` straight to `get_event_detail`.

## Methods

| Method | HTTP | Path | When to use |
|--------|------|------|-------------|
| `get_sports()` | GET | `/sports` | Top-level prematch sport list. |
| `get_events(sport_id)` | GET | `/sports-matches-list?sportId=...` | All matches for a sport, grouped by tournament. No per-tournament endpoint. |
| `get_event_detail(event_id, live=False)` | GET | `/match/detail?eventId=...&productId=...` | Full event detail. **`live=True` is required for in-play markets.** |
| `get_live_sports()` | GET | `/live-matches/sports` | Sports currently in-play with counts. |
| `get_live_events(sport_id)` | GET | `/live-matches/list?sportId=...` | Live events, tournaments, and `comingSoons` for a sport. |
| `get_markets(event_id)` | (calls `get_event_detail`) | — | Inherited convenience. Prematch by default. |
| `get_sportradar_id(event_id)` | (calls `get_event_detail`) | — | Inherited convenience. |

(All paths are relative to `/api/{country}/facts-center/query/frontend`.)

### `get_sports() -> dict`

Top-level prematch sport list. Response: `data.sports[]` with `sportId` (e.g. `"sr:sport:1"` for Soccer), `sportName`, `count` (always 0 in this response — it's not a real count).

### `get_events(sport_id: str = "sr:sport:1") -> dict`

All prematch matches for a sport, grouped by tournament. There is **no per-tournament endpoint** on MSport — you get the entire sport's match list in one call.

Response: `data.tournaments[]` where each tournament has `category`, `tournament`, `tournamentId` (`sr:tournament:<n>`), `events[]`. Each event has `eventId` (`sr:match:<n>`), `homeTeam`, `awayTeam`, etc.

### `get_event_detail(event_id: str, live: bool = False) -> dict`

Full event detail with all markets. The `live` flag matters:
- `live=False` (default): `productId=3` — prematch market book.
- `live=True`: `productId=1` — full live market book. Required for in-play events.

Response: `data` with `eventId`, `homeTeam`, `awayTeam`, `markets[]`. Each market has `id` (e.g. `1`, `18`, `29`, `10` for the main markets), `description`, `name`, `specifiers` (line for parameterized), `outcomes[]`.

### `get_live_sports() -> dict`

Sports currently with in-play action. Response: `data.sports[]` with `sportId`, `sportName`, `count` (real live event count for that sport).

### `get_live_events(sport_id: str = "sr:sport:1") -> dict`

Live events for a sport, grouped by tournament. Uses the richer `/live-matches/list` endpoint (vs the bare `/live-matches`).

Response: `data` with three lists — `tournaments`, `events`, `comingSoons`.

### Inherited: `get_markets(event_id, registry=None)` and `get_sportradar_id(event_id)`

Both call `get_event_detail(live=False)`. For LIVE markets, fetch via `get_event_detail(event_id, live=True)` and call `parse_markets(..., platform="msport")` directly.

## Quirks

- **Outcome name field is `description`** (not `desc` like SportyBet).
- **Specifier field is `specifiers`** (plural, vs SportyBet's singular `specifier`).
- **No per-tournament events endpoint**: `get_events(sport_id)` returns matches grouped by tournament for the entire sport in one call.
- **Live events use a separate URL**: `/live-matches/list?sportId=...` (richer payload — `tournaments`, `events`, `comingSoons`).
- **`live=True` switches `productId`** the same way as SportyBet (3 → 1) for full live market book.
- **Headers identical to SportyBet**: `operid: 2`, `clientid: web`, `platform: web`. The two APIs share infrastructure.
- **Double Chance outcome strings**: live and prematch responses both use compact `"1 X"` / `"X 2"` / `"1 2"` notation. The builtin mapping matches.

## Recipes

### List sports and pick one

```python
import asyncio
from bookieskit import MSport

async def main():
    async with MSport(country="ng") as ms:
        raw = await ms.get_sports()
        for s in raw.get("data", {}).get("sports", [])[:8]:
            print(f"{s['sportId']}  {s['sportName']}")

asyncio.run(main())
```

### Get normalized live markets for one event

```python
import asyncio
from bookieskit import MSport
from bookieskit.markets import parse_markets

async def main():
    async with MSport(country="ng") as ms:
        # Live event — must use live=True for the full market book.
        detail = await ms.get_event_detail(
            event_id="sr:match:69339436",
            live=True,
        )
        markets = parse_markets(detail, platform="msport")
        for m in markets:
            if m.lines:
                for line in sorted(m.lines.keys())[:3]:
                    odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[line])
                    print(f"  {m.name} [{line}]: {odds}")
            else:
                odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
                print(f"  {m.name}: {odds}")

asyncio.run(main())
```

### Walk all live events for soccer

```python
import asyncio
from bookieskit import MSport

async def main():
    async with MSport(country="ng") as ms:
        raw = await ms.get_live_events(sport_id="sr:sport:1")
        data = raw.get("data") or {}
        events = data.get("events") or []
        for ev in events[:10]:
            print(f"{ev.get('eventId')}  {ev.get('homeTeam')} vs {ev.get('awayTeam')}")

asyncio.run(main())
```

## See also

- `examples/odds_for_sr_id.py` (queries MSport with `live=True` for in-play SR ids).
- [docs/markets.md](markets.md) — registry, builtins.
- [docs/matching.md](matching.md) — `extract_sportradar_id`, `match_events`.
