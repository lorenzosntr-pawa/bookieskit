# BetPawa

## Supported Countries

| Code | Country | Domain | `x-pawa-brand` |
|------|---------|--------|----------------|
| `ng` | Nigeria | https://www.betpawa.ng | `betpawa-nigeria` |
| `gh` | Ghana | https://www.betpawa.com.gh | `betpawa-ghana` |
| `ke` | Kenya | https://www.betpawa.co.ke | `betpawa-kenya` |
| `ug` | Uganda | https://www.betpawa.co.ug | `betpawa-uganda` |
| `tz` | Tanzania | https://www.betpawa.co.tz | `betpawa-tanzania` |
| `zm` | Zambia | https://www.betpawa.co.zm | `betpawa-zambia` |
| `rw` | Rwanda | https://www.betpawa.rw | `betpawa-rwanda` |
| `cm` | Cameroon | https://www.betpawa.cm | `betpawa-cameroon` |
| `sl` | Sierra Leone | https://www.betpawa.sl | `betpawa-sierraleone` |

Each country pairs a subdomain TLD with a brand header — both move together in `DOMAINS` and `_BRAND_MAP` in `bookmakers/betpawa.py`. The three additions in 0.8.0 (`rw`, `cm`, `sl`) were verified against the live sportsbook API. Other African TLDs (`bf`, `ci`, `sn`, `cd`, `cg`, `ss`, `ml`, `bi`, `et`) either don't resolve or return 4xx and are not currently supported.

## SportRadar id

BetPawa hides the SR id inside `widgets[]` on the event-detail response — look for the entry with `type == "SPORTRADAR"`, then read `id` (preferred) or `value` (legacy). The library's `extract_sportradar_id(response, platform="betpawa")` does this and strips the `sr:match:` prefix. There is **no** SR-id-to-BetPawa-id reverse search yet — start workflows from a BetPawa internal id.

## Methods

| Method | HTTP | Path | When to use |
|--------|------|------|-------------|
| `get_sports()` | GET | `/api/sportsbook/v3/categories/list/all` | Top-level sport list with prematch/live counts. |
| `get_countries(sport_id)` | GET | `/api/sportsbook/v3/categories/list/{sport_id}?includeRegions=true` | Regions + competitions under a sport. |
| `get_tournaments(sport_id)` | GET | (same as get_countries) | Alias — same data as `get_countries`, kept for naming symmetry. |
| `get_events(...)` | POST | (varies by params) | Events for a tournament or sport, prematch or live. |
| `get_event_detail(event_id)` | GET | event detail with markets and widgets | Full event data; SR id lives in `widgets[]`. |
| `get_markets(event_id)` | (calls `get_event_detail`) | — | Inherited convenience: returns `list[NormalizedMarket]`. |
| `get_sportradar_id(event_id)` | (calls `get_event_detail`) | — | Inherited convenience: returns the SR id as a numeric string. |

### `get_sports() -> dict`

Top-level sport categories. Response carries `onlyMeta[]` with one entry per sport, including `eventCounts.upcoming` and `eventCounts.live`. No params.

### `get_countries(sport_id: str) -> dict`

Regions and competitions under one sport. Response shape: `withRegions[].regions[].competitions[]`. Each region is a country, each competition is a tournament.

### `get_tournaments(sport_id: str) -> dict`

Same data as `get_countries`. Both methods hit the same endpoint with the same params; tournaments are nested under `competitions[]` in the response.

### `get_events(tournament_id=None, event_type=None, sport_id=None) -> dict`

Events for a tournament or for a whole sport.
- Pass `tournament_id` to filter to one competition.
- Pass `sport_id` + `event_type="LIVE"` for live events of a whole sport.

Response: `responses[0].responses[]` — list of events. Each event has `id` (BetPawa internal), `participants` (`[{name: home}, {name: away}]`), `competition`, `region`.

### `get_event_detail(event_id: str) -> dict`

Full event payload, including `markets[]` and `widgets[]`. The SR id lives in the SPORTRADAR widget.

### Inherited: `get_markets(event_id, registry=None) -> list[NormalizedMarket]`

Calls `get_event_detail`, then `parse_markets(response, platform="betpawa", registry=registry)`. Returns the normalized markets — only those whose `betpawa_id` is registered (4 of the 6 builtins by default; the 1Up/2Up variants are not yet wired for BetPawa).

### Inherited: `get_sportradar_id(event_id) -> str | None`

Calls `get_event_detail`, then extracts the SR id from the SPORTRADAR widget. Returns the numeric id (no `sr:match:` prefix), or `None` if no widget is present.

## Quirks

- `x-pawa-brand` header varies per country (`betpawa-nigeria`, `betpawa-ghana`, etc.) and is set automatically by the client.
- BetPawa's parameterized markets store the line as `formattedHandicap` (display) and `handicap` (internal value × 4). The parser handles both.
- Outcome odds live under `prices[].price` (not `odds`).
- No SR-id reverse search yet — BetPawa is the seed, not a target, in cross-bookmaker workflows.

## Recipes

### List all events in a competition

```python
import asyncio
from bookieskit import BetPawa

async def main():
    async with BetPawa(country="ng") as bp:
        raw = await bp.get_events(tournament_id="12546")
        events = (raw.get("responses") or [{}])[0].get("responses", [])
        for ev in events:
            parts = ev.get("participants", [])
            home = parts[0]["name"] if parts else "?"
            away = parts[1]["name"] if len(parts) > 1 else "?"
            print(f"{ev['id']}  {home} vs {away}")

asyncio.run(main())
```

### Normalized markets and SR id from one event

```python
import asyncio
from bookieskit import BetPawa
from bookieskit.matching import extract_sportradar_id

async def main():
    async with BetPawa(country="ng") as bp:
        detail = await bp.get_event_detail(event_id="34716684")
        sr_id = extract_sportradar_id(detail, platform="betpawa")
        markets = await bp.get_markets(event_id="34716684")
        print(f"SR id: {sr_id}")
        for m in markets:
            outcomes = m.outcomes if m.outcomes else (m.lines.get(2.5) if m.lines else [])
            print(f"  {m.name}: {len(outcomes)} outcomes")

asyncio.run(main())
```

### Use a BetPawa id as the seed for cross-bookmaker comparison

See `examples/odds_from_betpawa_id.py` for the complete script. Flow:
1. Fetch BetPawa event detail.
2. Extract SR id from the SPORTRADAR widget.
3. Use that SR id to query SportyBet, MSport, Betway directly (their event ids ARE the SR id).
4. Look up Bet9ja's internal id via `Bet9ja.find_event_id_by_sr_id` (live) or `build_prematch_event_map` (prematch).

## See also

- `examples/odds_from_betpawa_id.py`
- `examples/odds_for_betpawa_competition.py`
- [docs/markets.md](markets.md) — registry, builtins, custom mappings.
- [docs/matching.md](matching.md) — `extract_sportradar_id`, `match_events`.
