# Bet9ja

## Supported Countries

| Code | Domain | Notes |
|------|--------|-------|
| `ng` | https://sports.bet9ja.com | Nigeria — only supported country |

## Rate limits

Bet9ja is one of the more rate-sensitive of the 6 bookmakers (alongside SportPesa). The client uses tighter defaults:

- `MAX_CONCURRENT = 15`
- `REQUEST_DELAY = 0.025` (25 ms)

These are tunable via `Bet9ja(country="ng", max_concurrent=..., request_delay=...)` if you have headroom on your end.

## SportRadar id

Bet9ja exposes the SR id as `EXTID` on every event in BOTH prematch and live event-list responses. The library has two ways to look up Bet9ja's internal id from a SR id:

- **Live (fast)**: `find_event_id_by_sr_id(sr_id, sport_id="3000001")` — scans the flat live-events list.
- **Prematch (complete but slower)**: `build_prematch_event_map(sport_id="1")` — walks every soccer tournament once and returns a SR-id → internal-id dict. Takes a few seconds.

Once you have the internal id, use `get_event_detail` (prematch) or `get_live_event_detail` (live) to fetch markets.

## BetGenius id (live only, deferred)

Bet9ja's **live** event-detail response includes `D.A.PRV` (a provider code; `60` is the captured value for a SportRadar event) and `D.A.BRMATCHID` ("BetRadar Match ID"). Other PRV values likely indicate BetGenius events but the binding fixture for a Genius case isn't captured yet, so `extract_event_ids(response, platform="bet9ja").genius` always returns `None` today. Bet9ja **prematch** events do not appear to ship Genius ids at all. Open an issue with a captured Bet9ja-live Genius event payload to land the wiring.

## Methods

| Method | HTTP | Path | When to use |
|--------|------|------|-------------|
| `get_sports()` | GET | `/desktop/feapi/PalimpsestAjax/GetSports` | Full sport / country / tournament hierarchy. |
| `get_countries()` | (alias for `get_sports`) | — | Same data; kept for naming symmetry. |
| `get_tournaments()` | (alias for `get_sports`) | — | Same data; kept for naming symmetry. |
| `get_events(tournament_id)` | GET | `/desktop/feapi/PalimpsestAjax/GetEventsInGroup` | Events for one prematch tournament. Each event has `EXTID`. |
| `get_event_detail(event_id)` | GET | `/desktop/feapi/PalimpsestAjax/GetEvent` | **Prematch** detail with full odds dict. |
| `get_live_sports()` | GET | `/desktop/feapi/PalimpsestLiveAjax/GetLiveEventsV3` | Sports currently in-play (response in `D.S`). |
| `get_live_events(sport_id=None)` | GET | (same endpoint) | Live events for a sport (`D.E`). Each event has `EXTID`. |
| `get_live_event_detail(event_id)` | GET | `/desktop/feapi/PalimpsestLiveAjax/GetLiveEvent` | **Live** detail with full odds dict. Param name: `EVENTID`. |
| `find_event_id_by_sr_id(sr_id, sport_id)` | (calls `get_live_events`) | — | SR id → Bet9ja internal id (live only). |
| `build_prematch_event_map(sport_id)` | (walks all tournaments) | — | SR id → Bet9ja internal id map for prematch. |
| `get_markets(event_id)` | (calls `get_event_detail`) | — | Inherited. Returns `list[NormalizedMarket]` for prematch. |
| `get_sportradar_id(event_id)` | (calls `get_event_detail`) | — | Inherited. Reads `D.EXTID`. |

### `get_sports() -> dict`

Full sport / country / tournament hierarchy. Response: `D.PAL` keyed by sport id (e.g. `"1"` for Soccer). Each sport has `S_DESC`, `NUM` (event count), `SG` (countries → tournaments).

### `get_events(tournament_id: str) -> dict`

Prematch events for one tournament. Response: `D.E[]` (a list). Each event has `ID`, `EXTID` (SR numeric), `DS` (description), `STARTDATE`, `SGID`, `SID`, etc.

### `get_event_detail(event_id: str) -> dict`

**Prematch only.** Response: `D` with `EXTID`, `O` (flat odds dict keyed by `S_<MARKET>_<OUTCOME>` strings, values are bare odds strings).

### `get_live_sports() -> dict`

Sports currently in-play. Response: `D.S` keyed by live sport id (e.g. `"3000001"` for Soccer — different from prematch ids).

### `get_live_events(sport_id: str | None = None) -> dict`

Live events for a sport (defaults to Soccer). Response: `D.E` keyed by internal id, each entry has `EXTID`, `DS`, `STARTDATE`, etc.

### `get_live_event_detail(event_id: str) -> dict`

**Live only.** Note: parameter name is `EVENTID` (uppercase). Response: `D.A` (anchor — score, time, EXTID), `D.O` (live odds dict keyed by `LIVES_<MARKET>_<OUTCOME>`, values wrapped as `{"v": <float>}`).

### `find_event_id_by_sr_id(sr_id, sport_id="3000001") -> str | None`

Live-only SR-id lookup. Scans `get_live_events` once and returns the internal id of the matching event, or `None` if not found.

### `build_prematch_event_map(sport_id="1") -> dict[str, str]`

Walks every prematch tournament under a sport (default `"1"` = Soccer) and builds a SR-numeric → internal-id map. Concurrency is limited by the client's rate-limit semaphore. The full Soccer walk takes a few seconds and yields ~1000 entries on a typical day.

### Inherited: `get_markets(event_id, registry=None)` and `get_sportradar_id(event_id)`

Both call `get_event_detail` (prematch). For LIVE markets, fetch via `get_live_event_detail` and call `parse_markets(..., platform="bet9ja")` directly — the parser handles both `S_*` and `LIVES_*` keys plus the `{"v": <float>}` wrapper.

## Quirks

- **Prematch and live use different endpoints, same param name**: `GetEvent` (prematch) and `GetLiveEvent` (live) both expect the parameter `EVENTID` (uppercase). The endpoints and response shapes differ, but the param name is identical.
- **Odds key prefixes**: prematch uses `S_<MARKET>_<OUTCOME>` (e.g. `S_1X2_1`); live uses `LIVES_<MARKET>_<OUTCOME>` (e.g. `LIVES_1X2_1`).
- **Live odds shape**: live odds values are wrapped as `{"v": <float>}` instead of bare strings. The parser handles both.
- **Live sport ids differ**: Soccer is `"3000001"` for live, `"1"` for prematch.
- **`v_cache_version` query parameter**: hardcoded; set automatically by the client.
- **Tighter rate limits**: 15 concurrent + 25ms delay. Don't override unless you've negotiated headroom.

## Recipes

### List live soccer events with SR ids

```python
import asyncio
from bookieskit import Bet9ja

async def main():
    async with Bet9ja(country="ng") as b9:
        resp = await b9.get_live_events(sport_id="3000001")
        events = (resp.get("D") or {}).get("E") or {}
        for internal_id, ev in list(events.items())[:5]:
            print(f"{internal_id}  EXTID={ev.get('EXTID')}  {ev.get('DS')}")

asyncio.run(main())
```

### SR id → Bet9ja internal id (live, fast)

```python
import asyncio
from bookieskit import Bet9ja

async def main():
    async with Bet9ja(country="ng") as b9:
        internal = await b9.find_event_id_by_sr_id("69339436")
        if internal:
            detail = await b9.get_live_event_detail(event_id=internal)
            print(f"odds entries: {len((detail.get('D') or {}).get('O') or {})}")
        else:
            print("not currently live")

asyncio.run(main())
```

### Build a full prematch SR-id map (slower; one-shot)

```python
import asyncio
from bookieskit import Bet9ja

async def main():
    async with Bet9ja(country="ng") as b9:
        sr_map = await b9.build_prematch_event_map(sport_id="1")
        print(f"{len(sr_map)} prematch SR ids -> Bet9ja internal ids")
        # Use the map to look up many events without re-walking.
        target = "69340230"
        if target in sr_map:
            print(f"{target} -> {sr_map[target]}")

asyncio.run(main())
```

## See also

- `examples/odds_for_betpawa_competition.py` (uses `build_prematch_event_map`).
- `examples/odds_for_sr_id.py` (uses `find_event_id_by_sr_id`).
- [docs/markets.md](markets.md).
- [docs/matching.md](matching.md).
