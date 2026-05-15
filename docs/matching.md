# Matching — provider-id extraction and cross-bookmaker pairing

The `bookieskit.matching` package finds the same real-world event across multiple bookmakers using **two providers**: SportRadar (universal) and BetGenius / Genius Sports (BetPawa, SportyBet, Bet9ja-live). The matcher unions events that share **any** provider id, so a BetPawa row carrying both SR and Genius widgets bridges a Betway row (SR only) with a SportyBet Genius event (Genius only).

## `EventIds`

Frozen dataclass returned by `extract_event_ids`:

```python
@dataclass(frozen=True)
class EventIds:
    sportradar: str | None = None
    genius: str | None = None
    def keys(self) -> tuple[str, ...]: ...  # ('sr:NNN', 'genius:MMM') in stable order
```

## `extract_event_ids(response, platform)`

New unified entry point. Returns an `EventIds` with whichever provider ids the payload carries. Where each bookmaker stores each kind of id:

| Platform | SR id field | Genius id field |
|---|---|---|
| `betpawa` | widget `type=SPORTRADAR`, `.id` | widget `type=GENIUSSPORTS`, `.id` |
| `sportybet` | `data.eventSource.{preMatchSource,liveSource}.sourceId` when `sourceType=BET_RADAR` (7-ones prefix stripped); fallback to `data.eventId` (always carries the SR id) | `data.eventSource.{preMatchSource,liveSource}.sourceId` when `sourceType=BET_GENIUS` (7-ones prefix stripped to yield the bare 8-digit Genius id matching BetPawa's widget id) |
| `bet9ja` (prematch) | `D.EXTID` | — |
| `bet9ja` (live) | `D.A.BRMATCHID` | *deferred — needs Genius-event fixture* |
| `betway` | `sportEvent.eventId` | — |
| `msport` | `data.eventId` | — |
| `sportpesa` | `data[0].betradarId` | — |
| `betika` | `data[0].parent_match_id` | — |

### SportyBet's `1111111` source-id prefix

SportyBet's `eventSource.sourceId` is namespaced with seven leading `1`s on some rows: BET_GENIUS sourceIds always carry the prefix (e.g. `"111111113899686"` for Genius id `13899686`); BET_RADAR `preMatchSource.sourceId` rows usually carry it too (`"111111171127902"` strips to SR id `71127902`), while `liveSource.sourceId` for BET_RADAR ships the bare id. The extractor strips the prefix unconditionally so the resulting bare id matches BetPawa's `GENIUSSPORTS` widget id (8 digits, typically starting with `13...`).

Note: `data.eventId` **always** carries the SportRadar id (`"sr:match:<sr_id>"`), regardless of provider — a SportyBet BetGenius event still has an SR id for the same physical match. So an event with sourceType=BET_GENIUS produces an `EventIds` with BOTH `sportradar` and `genius` populated. If the SR id parsed from `eventId` disagrees with the SR id from an `eventSource` BET_RADAR row, a `WARNING` is logged and `eventSource` wins. (Earlier 0.9.0 docs incorrectly claimed a `sr:match:11111111<gid>` synthetic encoding on `eventId`; that form never appears in real responses.)

## `extract_sportradar_id(response, platform)` — back-compat

Equivalent to `extract_event_ids(response, platform).sportradar`. Pre-0.9.0 callers that only care about SR ids keep working without code changes; pick up Genius matching by switching to `extract_event_ids`.

Unknown platforms return `None`.

## `match_events(*event_lists)`

Groups events from multiple bookmakers by **any** shared provider id (SR or Genius) using a small union-find. Each argument is a tuple `(platform, [event_response, ...])`. Returns a list of `MatchedEvent` records, one per group.

The union-find matters when one bookmaker bridges two others: BetPawa carries both SR (`widgets[type=SPORTRADAR]`) and Genius (`widgets[type=GENIUSSPORTS]`), so it links a Betway row that only knows the SR id to a SportyBet row that only knows the Genius id.

```python
@dataclass
class MatchedEvent:
    sportradar_id: str | None = None  # may be None on Genius-only matches
    genius_id: str | None = None      # may be None on SR-only matches
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
    print(f"{len(matched)} unique events, {overlap} present on all 3 bookmakers")
    genius_only = sum(1 for m in matched if m.sportradar_id is None and m.genius_id)
    print(f"  of which {genius_only} matched only via BetGenius")

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
