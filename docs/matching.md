# Matching — SportRadar id extraction and cross-bookmaker pairing

The `bookieskit.matching` package finds the same real-world event across multiple bookmakers using SportRadar ids.

## `extract_sportradar_id(response, platform)`

Pulls the SR id out of a raw event-detail response. Returns the bare numeric id (e.g. `"69339436"`), or `None` if not found. Where each bookmaker stores the id:

| Platform | Field path | Notes |
|---|---|---|
| `betpawa` | `widgets[].id` where `type == "SPORTRADAR"` | Falls back to `value` for legacy responses; strips `sr:match:`. |
| `sportybet` | `data.eventId` | Strips `sr:match:`. |
| `bet9ja` | `D.EXTID` | Prematch detail only. Live detail (`get_live_event_detail`) stores EXTID at `D.A.EXTID` — the extractor does **not** handle that path and returns `None` for live responses. |
| `betway` | `sportEvent.eventId` | The id IS the SR numeric — already prefix-free. |
| `msport` | `data.eventId` | Strips `sr:match:`. |
| `sportpesa` | `data[0].additional_info.sportradar_id` | Best-evidence path; fixture-resolved. The extractor probes three sibling fallbacks (`betradar_id`, `sr_id`, and `data[0].external_id`) until the captured payload confirms one. Strips `sr:match:`. |
| `betika` | `data[0].parent_match_id` | Already prefix-free. Type varies: string in prematch, int in live — coerced via `str()`. Betika's own `match_id` is a separate internal identifier (not the SR id). |

Unknown platforms return `None`.

## `match_events(*event_lists)`

Groups events from multiple bookmakers by shared SR id. Each argument is a tuple `(platform, [event_response, ...])`. Returns a list of `MatchedEvent` records, one per SR id seen on any input platform.

```python
@dataclass
class MatchedEvent:
    sportradar_id: str
    betpawa: dict | None = None
    sportybet: dict | None = None
    bet9ja: dict | None = None
    betway: dict | None = None
    msport: dict | None = None
    sportpesa: dict | None = None
    betika: dict | None = None
```

All 7 per-platform fields default to `None`, so callers can pass any subset of platforms.

## End-to-end example

Fetch event lists from three bookmakers, group by SR id, count overlaps:

```python
import asyncio
from bookieskit import BetPawa, SportyBet, Bet9ja
from bookieskit.matching import match_events

async def main():
    async with BetPawa(country="ng") as bp, SportyBet(country="ng") as sb, Bet9ja(country="ng") as b9:
        # Fetch a small sample from each (in real use you'd loop over tournaments).
        bp_raw = await bp.get_events(tournament_id="12546")
        sb_raw = await sb.get_events(tournament_id="sr:tournament:17")
        # Bet9ja: pick a known soccer tournament id like Premier League.
        b9_raw = await b9.get_events(tournament_id="170880")

    # Each list must be a list of EVENT-DETAIL-shaped responses (or anything
    # carrying the SR id where the per-platform extractor expects it).
    bp_events = (bp_raw.get("responses") or [{}])[0].get("responses", [])
    sb_events = ((sb_raw.get("data") or [{}])[0].get("events", []))
    b9_events = (b9_raw.get("D") or {}).get("E", [])

    matched = match_events(
        ("betpawa", bp_events),
        ("sportybet", sb_events),
        ("bet9ja", b9_events),
    )

    overlap = sum(1 for m in matched if m.betpawa and m.sportybet and m.bet9ja)
    print(f"{len(matched)} unique SR ids, {overlap} present on all 3 bookmakers")

asyncio.run(main())
```

## Direct lookup paths

When you have a SR id, the easiest path differs by platform:

- **SportyBet, MSport**: pass `event_id="sr:match:<numeric>"` directly to `get_event_detail`.
- **Betway**: pass the bare numeric SR id directly to `get_markets(event_id)`.
- **Bet9ja**: SR id → internal id via `find_event_id_by_sr_id` (live, fast) or `build_prematch_event_map(sport_id="1")` (prematch — walks all soccer tournaments).
- **BetPawa**: no SR-id reverse search yet. Start workflows from a BetPawa internal id; extract the SR id from the SPORTRADAR widget on the event-detail response.
- **SportPesa**: no SR-id reverse search yet — same gap as BetPawa. Start workflows from a SportPesa internal id; extract the SR id from event-detail.
- **Betika**: no SR-id reverse search yet — same gap as BetPawa / SportPesa. Start workflows from a Betika internal `match_id`; the SR id is on `data[0].parent_match_id` in event-detail.

## When `extract_sportradar_id` is not enough

For events fed from non-SportRadar providers (notably **GeniusSport**), no SR id is exposed. These events will not show up in `match_events` results and there is no current workaround in this lib.

## See also

- [docs/markets.md](markets.md) — what to do once you have the per-bookmaker event ids.
- `examples/odds_for_sr_id.py` — single-event compare across all 7.
- `examples/odds_for_betpawa_competition.py` — full-tournament compare via BetPawa as the seed.
