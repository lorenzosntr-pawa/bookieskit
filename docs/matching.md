# Event Matching

## Overview

bookieskit matches events across platforms using SportRadar IDs — a universal identifier that all three bookmakers embed in their responses (in different locations).

## Quick Start

```python
from bookieskit import BetPawa
from bookieskit.matching import extract_sportradar_id, match_events

# Extract SportRadar ID from a single event
async with BetPawa(country="ng") as client:
    sr_id = await client.get_sportradar_id(event_id="32299257")
    # Returns: "61300947"
```

## Where SportRadar IDs Live

| Platform | Location | Example |
|---|---|---|
| BetPawa | `widgets[]` array, `type="SPORTRADAR"` | `{"type": "SPORTRADAR", "value": "sr:match:61300947"}` |
| SportyBet | `data.eventId` field (native) | `"sr:match:61300947"` |
| Bet9ja | `D.EXTID` field | `"61300947"` |

All IDs are normalized to numeric-only format (no `sr:match:` prefix).

## Matching Across Platforms

```python
from bookieskit import BetPawa, SportyBet, Bet9ja
from bookieskit.matching import match_events

# Fetch event details from each platform
async with BetPawa(country="ng") as bp, SportyBet(country="ng") as sb:
    bp_details = [await bp.get_event_detail(id) for id in bp_event_ids]
    sb_details = [await sb.get_event_detail(id) for id in sb_event_ids]

# Match by SportRadar ID
matched = match_events(
    ("betpawa", bp_details),
    ("sportybet", sb_details),
)

for event in matched:
    print(f"SR ID: {event.sportradar_id}")
    if event.betpawa:
        print(f"  BetPawa: {event.betpawa['id']}")
    if event.sportybet:
        print(f"  SportyBet: {event.sportybet['data']['eventId']}")
```

## Low-Level Extraction

```python
from bookieskit.matching import extract_sportradar_id

# Works with raw responses from any platform
raw = await client.get_event_detail(event_id="123")
sr_id = extract_sportradar_id(raw, platform="betpawa")
```

## Limitations

- **BetPawa and Bet9ja** require fetching the full event detail to get the SportRadar ID (it's not in the events list response)
- **SportyBet** has the ID natively in event list responses (`eventId` field)
- Events without a SportRadar ID are skipped during matching
