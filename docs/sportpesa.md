# SportPesa

## Supported Countries

| Code | Country |
|------|---------|
| `ke` | Kenya |
| `tz` | Tanzania |

Country is honoured via subdomain (`www.ke.sportpesa.com`, `www.tz.sportpesa.com`) and the `x-app-timezone` request header (`Africa/Nairobi` for `ke`, `Africa/Dar_es_Salaam` for `tz`). The client only supports `ke` and `tz` — any other code raises `UnsupportedCountryError`.

## SportRadar id

SportPesa event ids are SportPesa-internal integers (e.g. `"8868005"`), NOT SportRadar ids. The SR id is carried inside the event-detail response. The exact JSON path is fixture-resolved — see `tests/fixtures/event_info/sportpesa/RESOLVED.md` (when captured) for the confirmed key path. The default extractor probes four candidate locations until a fixture-driven pruning lands.

- `extract_sportradar_id(response, platform="sportpesa")` returns the bare numeric SR id (no `sr:match:` prefix), or `None` if not present.
- `SportPesa.get_sportradar_id(event_id)` fetches event-detail and runs the extractor.

## Methods

| Method | HTTP | Path | When to use |
|--------|------|------|-------------|
| `get_sports()` | GET | `/api/live/sports` | Live sport list with per-sport `eventNumber` (note: that counter is unreliable — see Quirks). SportPesa has no prematch-only sports endpoint; use `get_navigation()` for the prematch catalogue. |
| `get_navigation()` | GET | `/api/navigation` | Full sport → country → league tree in one call. The only known way to enumerate the complete league catalogue. |
| `get_events(sport_id, league_id=None, live=False, pag_count=None)` | GET | `/api/upcoming/games` (prematch) / `/api/highlights/{sport_id}?live=true` (live) | Event list. Pass `league_id` to walk past the rolling-100-event window (see Quirks). |
| `get_event_detail(event_id, live=False)` | GET | `/api/upcoming/games?gameId=...` | Event metadata + SR id. Returns a list of length 1. Same endpoint for prematch and live; the `live` parameter is accepted for symmetry. |
| `get_event_markets(event_id)` | GET | `/api/games/markets?games=...&markets=all` | Full markets feed for an event. Returns `{<event_id>: [<market>, ...]}`. |
| `get_live_events_started(sport_id)` | GET | `/api/live/sports/{sport_id}/events/started` | Authoritative currently-in-play events for one sport. |
| `get_live_sport_events(sport_id)` | GET | `/api/live/sports/{sport_id}/events` | All events offering live markets (broader than `_started`: includes near-future events). |
| `iter_all_prematch_events()` | async iterator | (navigation tree + per-league fan-out) | Yields `PrematchEventStub(event_id, league_id, sport_id)` for every event in the full prematch catalogue. The complete-catalogue entry point. |
| `get_markets(event_id, registry=None)` | (calls `get_event_markets`) | — | Inherited convenience overridden — calls the markets endpoint, runs the parser. |
| `get_sportradar_id(event_id, live=False)` | (calls `get_event_detail`) | — | Fetches detail, extracts `[0].betradarId`. |
| `set_cookie(cookie)` | — | — | Inherited from `BaseBookmaker`. Sets/refreshes the `Cookie:` header for subsequent requests; works pre- and post-context. The `cookie=` constructor kwarg is equivalent for pre-context setup. |

## Quirks

- **Akamai Bot Manager.** SportPesa endpoints are gated by Akamai. The client does NOT solve the challenge. Callers must supply warmed cookies harvested from a browser session, either as a constructor kwarg or via `set_cookie()`:
  ```python
  # Constructor (preferred)
  async with SportPesa(country="ke", cookie="<full Cookie: header from a browser tab>") as sp:
      markets = await sp.get_markets(event_id="8868005")

  # Or refresh mid-session
  async with SportPesa(country="ke") as sp:
      sp.set_cookie("<full Cookie: header from a browser tab>")
      markets = await sp.get_markets(event_id="8868005")
  ```
- **Markets and event detail are SEPARATE endpoints.** `get_event_detail` returns metadata + SR id only — NO markets. Use `get_event_markets` (or the `get_markets` convenience) for odds.
- **Country via subdomain**, not via a query parameter. The `x-app-timezone` header switches per country.
- **Rolling-window cap on the per-sport games endpoint (≈100 per sport).** `/api/upcoming/games?sportId=N` hard-caps responses at 100 events spanning a rolling ~24h window. No pagination convention walks past it: `page` / `pageNumber` / `offset` / `start` / `from` / `skip` / `pag_offset` / `pag_start` / `cursor` / `lastId` / `after` / `dateFrom` / `startDate` / `dayOffset` / `period` all return the same first-100. **Use `leagueId` instead** — `/api/upcoming/games?sportId=N&leagueId=L` walks past the rolling window and returns the full per-league catalogue. (Caveat: `competitionId` is silently ignored — it accepts the parameter but returns the unfiltered rolling 100. Only `leagueId` actually filters.) Enumerate every league via `get_navigation()` then fan out per-league for the complete catalogue.
- **Navigation tree.** `get_navigation()` (calling `/api/navigation`) returns the full sport → country → league hierarchy in a single call. This is the only known way to discover the complete league catalogue — the per-sport endpoints expose only the rolling window. As of writing the tree spans 13 sports and 302 leagues.

## Recipes

### List soccer competitions for Kenya

SportPesa has no dedicated tournaments-list endpoint; use `get_navigation()` and walk the tree:

```python
import asyncio
from bookieskit import SportPesa

async def main():
    async with SportPesa(country="ke", cookie="<warmed cookie>") as sp:
        nav = await sp.get_navigation()
        soccer = next((s for s in nav if s.get("id") == 1), None)
        if soccer:
            for country in soccer.get("countries", [])[:3]:
                for league in country.get("leagues", []):
                    print(f"{country['name']:<20} {league['id']:<6} {league['name']}")

asyncio.run(main())
```

### Normalized markets for one event

```python
import asyncio
from bookieskit import SportPesa

async def main():
    async with SportPesa(country="ke", cookie="<warmed cookie>") as sp:
        markets = await sp.get_markets(event_id="8868005")
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

### Inspect raw markets payload

```python
import asyncio
from bookieskit import SportPesa

async def main():
    async with SportPesa(country="ke", cookie="<warmed cookie>") as sp:
        raw = await sp.get_event_markets(event_id="8868005")
        games = raw.get("data", [])
        if games:
            markets = games[0].get("markets", [])
            print(f"markets on event: {len(markets)}")
            for m in markets[:5]:
                print(f"  id={m.get('id')} name={m.get('name')}")

asyncio.run(main())
```

## See also

- `examples/odds_for_sr_id.py` — cross-bookmaker SR-id fan-out (includes SportPesa).
- [docs/markets.md](markets.md) — canonical market mapping reference.
- [docs/matching.md](matching.md) — SR-id extraction reference per platform.
