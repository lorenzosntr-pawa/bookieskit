# bookieskit

HTTP clients for scraping betting data from BetPawa, SportyBet, Bet9ja, Betway, and MSport.

## Installation

```bash
pip install git+https://github.com/<user>/bookieskit.git
```

## Quick Start

```python
from bookieskit import BetPawa

# Async
async with BetPawa(country="ng") as client:
    sports = await client.get_sports()
    events = await client.get_events(tournament_id="11965")
    detail = await client.get_event_detail(event_id="32299257")

# Sync
with BetPawa(country="ng") as client:
    sports = client.get_sports()
```

## Supported Bookmakers

| Bookmaker | Countries |
|-----------|-----------|
| BetPawa   | ng, gh, ke, ug, tz, zm |
| SportyBet | ng, gh, ke |
| Bet9ja    | ng |
| Betway    | ng, gh, ke, tz, ug, zm |
| MSport    | ng, gh, ke |

## Configuration

```python
from bookieskit import Bet9ja

client = Bet9ja(
    country="ng",
    timeout=15.0,         # seconds (default: 30)
    max_retries=5,        # attempts (default: 3)
    max_concurrent=10,    # parallel requests (default: platform-specific)
)
```
