# SportyBet

## Supported Countries

| Code | Country | API Path |
|------|---------|----------|
| `ng` | Nigeria | `/api/ng/...` |
| `gh` | Ghana | `/api/gh/...` |
| `ke` | Kenya | `/api/ke/...` |

All countries share the same `https://www.sportybet.com` base — the country segment lives in the URL path under `/api/{country}/factsCenter/...`.

### Country expansion (deferred)

SportyBet publicly operates in additional markets (Tanzania, Uganda, Zambia, South Africa, Côte d'Ivoire, etc.). A v0.8.0 enumeration attempt was blocked by anti-bot / TLS-cert issues when probing from outside an African residential IP, so those entries are **not** added to the `DOMAINS` dict — adding them speculatively would expose `UnsupportedCountryError`-free code paths that fail at the first HTTP call. Open an issue or PR with a successful probe transcript to land another country.

## Provider ids (SportRadar + BetGenius)

SportyBet exposes provider info two ways. The primary (typed) source on event-detail responses:

| Path | Meaning |
|---|---|
| `data.eventSource.preMatchSource.sourceType` ∈ `{BET_RADAR, BET_GENIUS}` | Which provider routed the prematch markets |
| `data.eventSource.preMatchSource.sourceId` | The provider's raw id (numeric string) |
| `data.eventSource.liveSource.{sourceType, sourceId}` | Same shape, may differ from the prematch source |
| `data.bgEvent` (bool) | Quick flag — `True` when this is a BetGenius event |

Fallback / cross-check: `data.eventId` carries `sr:match:<sr_id>` for SR events and `sr:match:11111111<genius_id>` for BetGenius events (eight leading `1`s mark the synthetic encoding). When both signals are present and disagree, `extract_event_ids` logs a `WARNING` via the `bookieskit.matching.extractor` logger and prefers `eventSource`.

For direct lookups by SR id, pass `event_id="sr:match:<numeric>"` to `get_event_detail`. For Genius events, you can also pass the synthetic `sr:match:11111111<genius_id>` form.

## Methods

| Method | HTTP | Path | When to use |
|--------|------|------|-------------|
| `get_sports(live=False)` | GET | `/api/{country}/factsCenter/popularAndSportList` | Top-level sport list. `live=True` flips `productId` to 1. |
| `get_countries(sport_id, live=False)` | GET | (same endpoint) | Categories + tournaments under one sport. |
| `get_tournaments(sport_id, live=False)` | GET | (same endpoint) | Alias for `get_countries` — same data. |
| `get_events(tournament_id, ...)` | POST | `/api/{country}/factsCenter/pcEvents` | Events for a tournament with selected market ids. |
| `get_event_detail(event_id, live=False)` | GET | `/api/{country}/factsCenter/event` | Full event detail. **`live=True` is required for in-play markets.** |
| `get_markets(event_id)` | (calls `get_event_detail`) | — | Inherited convenience. |
| `get_sportradar_id(event_id)` | (calls `get_event_detail`) | — | Inherited convenience. |

### `get_sports(live: bool = False) -> dict`

Top-level sport list with eventSize counts per sport. Pass `live=True` for live counts (flips `productId` from 3 to 1). Response shape: `data.sportList[]`, each entry has `id`, `name`, `eventSize`, `categories[]`.

### `get_countries(sport_id: str = "sr:sport:1", live: bool = False) -> dict`

Same endpoint as `get_sports` but with a `sportId` filter — returns the categories and tournaments under one sport. Default sport is Soccer (`sr:sport:1`).

### `get_tournaments(sport_id: str = "sr:sport:1", live: bool = False) -> dict`

Returns the same payload as `get_countries`. The endpoint nests categories and tournaments together; both methods are kept for naming symmetry across the lib.

### `get_events(tournament_id, sport_id="sr:sport:1", market_ids="1,18,10,29,11,26,36,14") -> dict`

Events for one tournament. `market_ids` is a comma-separated list of SportyBet market ids to include in each event payload (defaults cover the main markets).

POST body shape: `[{"sportId": ..., "marketId": ..., "tournamentId": [[<id>]]}]`. Response: `data[0].events[]`. Each event has `eventId` (= `sr:match:<numeric>`), `homeTeamName`, `awayTeamName`, `markets[]`.

### `get_event_detail(event_id: str, live: bool = False) -> dict`

Full event payload with all markets. The `live` flag is critical:
- `live=False` (default): `productId=3` — prematch markets. For in-play events, this returns ONLY player-prop markets (id 800xxx range), not 1X2/OU/BTTS/DC.
- `live=True`: `productId=1` — full live market book including the main markets.

Response: `data.markets[]` with `id`, `desc`, `specifier` (line for parameterized markets), `outcomes[]`.

### Inherited: `get_markets(event_id, registry=None) -> list[NormalizedMarket]`

Calls `get_event_detail(live=False)` and runs `parse_markets(..., platform="sportybet")`. To get LIVE normalized markets, fetch the raw response with `get_event_detail(event_id, live=True)` and call `parse_markets(...)` directly.

### Inherited: `get_sportradar_id(event_id) -> str | None`

Calls `get_event_detail(live=False)` and reads `data.eventId`, stripping `sr:match:`.

## Quirks

- `live=True` flips `productId` from 3 (prematch) to 1 (live) on `get_sports` AND `get_event_detail`. **For in-play events the main markets only exist under `productId=1`.**
- Outcome name field is `desc` (not `description`).
- Specifier field is `specifier` (singular).
- Parameterized markets repeat the same `id` once per line, with `specifier` like `total=2.5` or `hcp=-0.5`.
- The `_t` query parameter is a millisecond timestamp for cache busting (set automatically).

## Recipes

### List soccer tournaments and pick one

```python
import asyncio
from bookieskit import SportyBet

async def main():
    async with SportyBet(country="ng") as sb:
        raw = await sb.get_countries(sport_id="sr:sport:1")
        cats = (raw.get("data", {}).get("sportList", [{}])[0]).get("categories", [])
        for c in cats[:5]:
            for t in c.get("tournaments", [])[:3]:
                print(f"{c['name']}/{t['name']} (id: {t['id']})")

asyncio.run(main())
```

### Get normalized live markets for one event

```python
import asyncio
from bookieskit import SportyBet
from bookieskit.markets import parse_markets

async def main():
    async with SportyBet(country="ng") as sb:
        # Live event — must use live=True or the response is player-props only.
        detail = await sb.get_event_detail(
            event_id="sr:match:69339436",
            live=True,
        )
        markets = parse_markets(detail, platform="sportybet")
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

### Cross-bookmaker compare via SR id

See `examples/odds_for_sr_id.py` — it queries SportyBet, MSport, Betway and Bet9ja for the same SR id, side-by-side.

## See also

- `examples/odds_for_sr_id.py`
- [docs/markets.md](markets.md) — registry, builtins.
- [docs/matching.md](matching.md) — `extract_sportradar_id`, `match_events`.
