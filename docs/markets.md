# Market Mapping

## Overview

bookieskit normalizes market data from different platforms into a canonical format. Each platform uses different IDs, outcome names, and response structures — the market mapping layer abstracts this away.

## Quick Start

```python
from bookieskit import BetPawa
from bookieskit.markets import MarketRegistry

# Convenience method (fetches + parses)
async with BetPawa(country="ng") as client:
    markets = await client.get_markets(event_id="32299257")

for market in markets:
    print(f"{market.name}:")
    if market.lines:
        for line, outcomes in market.lines.items():
            for o in outcomes:
                print(f"  {line} {o.canonical_name}: {o.odds}")
    else:
        for o in market.outcomes:
            print(f"  {o.canonical_name}: {o.odds}")
```

## Built-in Markets

| Canonical ID | Name | BetPawa | SportyBet | Bet9ja | Parameterized |
|---|---|---|---|---|---|
| `1x2_ft` | 1X2 - Full Time | 3743 | 1 | S_1X2 | No |
| `over_under_ft` | Over/Under - Full Time | 5000 | 18 | S_OU | Yes |
| `btts_ft` | Both Teams To Score | 3795 | 29 | S_GGNG | No |
| `double_chance_ft` | Double Chance | 4693 | 10 | S_DC | No |

## Custom Registry

```python
from bookieskit.markets import MarketRegistry, OutcomeMapping

registry = MarketRegistry()  # includes 4 built-in

# Add your own
registry.add(
    canonical_id="draw_no_bet_ft",
    name="Draw No Bet - Full Time",
    betpawa_id="4703",
    sportybet_id="11",
    bet9ja_key="S_DNB",
    outcomes={
        "home": OutcomeMapping(canonical_name="home", betpawa="1", sportybet="Home", bet9ja="1"),
        "away": OutcomeMapping(canonical_name="away", betpawa="2", sportybet="Away", bet9ja="2"),
    },
)

# Use with client
markets = await client.get_markets(event_id="123", registry=registry)
```

## Using the Parser Directly

```python
from bookieskit.markets import parse_markets, MarketRegistry

# Parse any raw response
raw = await client.get_event_detail(event_id="123")
markets = parse_markets(raw, platform="betpawa")
```

## Contributing New Built-in Markets (PR Guide)

1. Edit `src/bookieskit/markets/builtin_mappings.py`
2. Add a new `MarketMapping` entry to `BUILTIN_MAPPINGS`
3. Include all outcome mappings for each platform (use `None` for platform IDs if the market doesn't exist on that platform)
4. Set `parameterized=True` if the market has lines (Over/Under, handicaps)
5. Add tests in `tests/test_parser_*.py` with fixture data
6. Update the "Built-in Markets" table above
