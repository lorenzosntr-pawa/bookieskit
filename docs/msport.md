# MSport Client

`MSport` is the HTTP client for MSport's sportsbook API.

## Countries

| Code | Domain |
|------|-----------------------|
| `ng` | https://www.msport.com |
| `gh` | https://www.msport.com |
| `ke` | https://www.msport.com |

All countries share the same domain; the country segment lives in the
URL path (`/api/{country}/facts-center/query/frontend/...`).

## Methods

| Method | HTTP | Path |
|--------|------|------|
| `get_sports()` | GET | `/sports` |
| `get_events(sport_id="sr:sport:1")` | GET | `/sports-matches-list?sportId=...` |
| `get_event_detail(event_id)` | GET | `/match/detail?eventId=...&productId=3` |
| `get_live_sports()` | GET | `/live-matches/sports` |
| `get_live_events(sport_id="sr:sport:1")` | GET | `/live-matches/list?sportId=...` |

## Quirks

- Outcome name field is `description` (not `desc` like SportyBet).
- Specifier field is `specifiers` plural (not `specifier`).
- Prematch matches are returned grouped by tournament for the entire
  sport in one call — there is no per-tournament endpoint.
- Live events use the richer `/live-matches/list` endpoint, which
  includes `tournaments`, `events`, and `comingSoons`.

## Example

```python
import asyncio
from bookieskit import MSport

async def main():
    async with MSport(country="ng") as client:
        sports = await client.get_sports()
        events = await client.get_events(sport_id="sr:sport:1")
        markets = await client.get_markets(
            event_id=events["data"]["tournaments"][0]["events"][0]["eventId"]
        )
        for m in markets:
            print(m.canonical_id, m.name)

asyncio.run(main())
```

## Headers

```
operid: 2
clientid: web
platform: web
```

(Identical to SportyBet — both rely on the same SportRadar-fed feed
infrastructure under the hood.)

## Underlying research

`docs/specs/msport-api-research.md` documents the full API survey —
endpoints, response shapes, market IDs, comparison with SportyBet.
