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
| `get_sports(live=False)` | GET | `/api/sports` / `/api/live/sports` | Top-level sport list. |
| `get_countries(sport_id, live=False)` | GET | `/api/upcoming/categories` / `/api/live/categories` | Country/category list. |
| `get_tournaments(sport_id, category_id, live=False)` | GET | `/api/upcoming/competitions` / `/api/live/competitions` | Competition/league list. |
| `get_events(sport_id, competition_id, live=False, page, per_page)` | GET | `/api/upcoming/games` / `/api/live/games` | Event list (paginated). |
| `get_event_detail(event_id, live=False)` | GET | `/api/upcoming/games?gameId=...` | Metadata + SR id — **no markets**. |
| `get_event_markets(event_id)` | GET | `/api/games/markets?games=...&markets=all` | Full markets feed. |
| `get_markets(event_id, registry=None)` | (calls `get_event_markets`) | — | Inherited convenience overridden — calls the markets endpoint. |
| `get_sportradar_id(event_id, live=False)` | (calls `get_event_detail`) | — | Fetches detail, runs the extractor. |

Endpoint paths for `get_sports`, `get_countries`, `get_tournaments`, and `get_events` are fixture-resolved best-evidence defaults pending capture. The paths for `get_event_detail` (prematch) and `get_event_markets` are confirmed from real captured requests.

## Quirks

- **Akamai Bot Manager.** SportPesa endpoints are gated by Akamai. The client does NOT solve the challenge. Callers must supply warmed cookies harvested from a browser session — for example, after entering the async context:
  ```python
  async with SportPesa(country="ke") as sp:
      sp._http_client.headers["cookie"] = "<full Cookie: header from a browser tab>"
      markets = await sp.get_markets(event_id="8868005")
  ```
- **Markets and event detail are SEPARATE endpoints.** `get_event_detail` returns metadata + SR id only — NO markets. Use `get_event_markets` (or the `get_markets` convenience) for odds.
- **Country via subdomain**, not via a query parameter. The `x-app-timezone` header switches per country.
- **Rolling-window event cap (≈100 per sport).** `/api/upcoming/games?sportId=N` hard-caps responses at 100 events spanning a rolling ~24h window. Verified empirically that *no* pagination convention walks past it: `page` / `pageNumber` / `offset` / `start` / `from` / `skip` / `pag_offset` / `pag_start` / `cursor` / `lastId` / `after` / `dateFrom` / `startDate` / `dayOffset` / `period` all return the same first-100. The `/api/highlights/{sportId}` endpoint surfaces a few featured events but is largely a subset of upcoming. `countryId` and `competitionId` filters return subsets of the rolling window (post-hoc filtering, not catalogue expansion). To enumerate the multi-day catalogue you would need either repeated polling over time + dedup, or a private/partner API not exposed to web clients. This is a SportPesa product/API design choice, not a scraping limitation.

## Recipes

### List soccer competitions for Kenya

```python
import asyncio
from bookieskit import SportPesa

async def main():
    async with SportPesa(country="ke") as sp:
        sp._http_client.headers["cookie"] = "<warmed cookie>"
        raw = await sp.get_tournaments(sport_id="1")
        for t in raw.get("data", [])[:5]:
            print(f"{t.get('id')}: {t.get('name')}")

asyncio.run(main())
```

### Normalized markets for one event

```python
import asyncio
from bookieskit import SportPesa

async def main():
    async with SportPesa(country="ke") as sp:
        sp._http_client.headers["cookie"] = "<warmed cookie>"
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
    async with SportPesa(country="ke") as sp:
        sp._http_client.headers["cookie"] = "<warmed cookie>"
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
