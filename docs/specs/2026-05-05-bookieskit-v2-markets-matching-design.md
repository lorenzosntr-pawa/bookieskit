# Bookieskit v2 — Market Mapping & Event Matching Design

## Overview

v2 adds two layers on top of the existing v1 HTTP clients:

1. **Market mapping** — Normalize platform-specific market data into canonical format using an extensible registry
2. **Event matching** — Cross-reference events across bookmakers via SportRadar IDs

Both are implemented as standalone modules with convenience methods on the client classes. v1 API is 100% backwards compatible.

## Architecture

**Approach: Separate Modules + Client Convenience Wrappers**

- `bookieskit.markets` — standalone market parsing and registry
- `bookieskit.matching` — standalone SportRadar ID extraction and event matching
- Client classes get thin wrapper methods (`get_markets()`, `get_sportradar_id()`)
- Power users can use modules directly for custom workflows

## File Structure (New Files)

```
src/bookieskit/
├── ... (existing v1 files unchanged)
├── markets/
│   ├── __init__.py          # Public: MarketRegistry, parse_markets, NormalizedMarket, Outcome
│   ├── registry.py          # MarketRegistry class (built-in + user-extensible)
│   ├── parser.py            # parse_markets() — platform-specific parsing logic
│   ├── types.py             # NormalizedMarket, Outcome, MarketMapping, OutcomeMapping
│   └── builtin_mappings.py  # The 4 built-in market definitions
├── matching/
│   ├── __init__.py          # Public: extract_sportradar_id, match_events, MatchedEvent
│   ├── extractor.py         # Platform-specific SportRadar ID extraction
│   └── matcher.py           # match_events() grouping logic
docs/
├── ... (existing)
├── markets.md               # How market mapping works + contribution guide
└── matching.md              # How event matching works
```

## Modified Files

- `src/bookieskit/base.py` — Add `PLATFORM_KEY` class var, `get_markets()` and `get_sportradar_id()` convenience methods
- `src/bookieskit/bookmakers/betpawa.py` — Add `PLATFORM_KEY = "betpawa"`
- `src/bookieskit/bookmakers/sportybet.py` — Add `PLATFORM_KEY = "sportybet"`
- `src/bookieskit/bookmakers/bet9ja.py` — Add `PLATFORM_KEY = "bet9ja"`
- `src/bookieskit/__init__.py` — Re-export new public APIs

## Data Types

### Core Types (`markets/types.py`)

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Outcome:
    """A single outcome within a market."""
    canonical_name: str   # e.g., "home", "draw", "away", "over", "under"
    odds: float
    platform_name: str    # original name from platform (e.g., "1", "X", "2")


@dataclass(frozen=True)
class NormalizedMarket:
    """A market normalized to canonical format."""
    canonical_id: str     # e.g., "1x2_ft", "over_under_ft"
    name: str             # e.g., "1X2 - Full Time"
    outcomes: list[Outcome] = field(default_factory=list)  # For simple markets
    lines: dict[float, list[Outcome]] | None = None        # For parameterized markets


@dataclass(frozen=True)
class OutcomeMapping:
    """Maps one outcome across platforms."""
    canonical_name: str   # e.g., "home"
    betpawa: str          # e.g., "1"
    sportybet: str        # e.g., "Home"
    bet9ja: str           # e.g., "1"


@dataclass(frozen=True)
class MarketMapping:
    """Defines how one market maps across platforms."""
    canonical_id: str
    name: str
    betpawa_id: str | None
    sportybet_id: str | None
    bet9ja_key: str | None
    outcomes: dict[str, OutcomeMapping]  # canonical_name -> platform mappings
    parameterized: bool = False          # True for O/U, handicaps (have lines)
```

### Design Choices

- Frozen dataclasses (immutable, hashable, safe to cache)
- Simple markets: `outcomes` populated, `lines` is None
- Parameterized markets: `lines` populated (grouped by line value), `outcomes` is empty list
- `None` allowed for platform IDs (some markets don't exist on all platforms)

## MarketRegistry

### API

```python
class MarketRegistry:
    """Registry of market mappings — built-in + user-extensible."""

    def __init__(self, load_builtins: bool = True):
        """Initialize. Set load_builtins=False for a blank registry."""
        ...

    def add(
        self,
        canonical_id: str,
        name: str,
        betpawa_id: str | None = None,
        sportybet_id: str | None = None,
        bet9ja_key: str | None = None,
        outcomes: dict[str, OutcomeMapping] = ...,
        parameterized: bool = False,
    ) -> None:
        """Register a new market mapping."""
        ...

    def get_by_canonical(self, canonical_id: str) -> MarketMapping | None:
        """Look up by canonical ID."""
        ...

    def get_by_platform_id(self, platform: str, platform_id: str) -> MarketMapping | None:
        """Look up by platform-specific ID."""
        ...

    def list_markets(self) -> list[MarketMapping]:
        """Return all registered mappings."""
        ...
```

### Usage

```python
from bookieskit.markets import MarketRegistry, OutcomeMapping

# Default — 4 built-in markets ready
registry = MarketRegistry()

# Add custom mapping
registry.add(
    canonical_id="correct_score_ft",
    name="Correct Score - Full Time",
    betpawa_id="4429",
    sportybet_id="45",
    bet9ja_key="S_CSFT",
    outcomes={
        "0-0": OutcomeMapping(canonical_name="0-0", betpawa="0-0", sportybet="0:0", bet9ja="0-0"),
        "1-0": OutcomeMapping(canonical_name="1-0", betpawa="1-0", sportybet="1:0", bet9ja="1-0"),
    },
    parameterized=False,
)

# Look up by platform ID
mapping = registry.get_by_platform_id("sportybet", "18")
# Returns the Over/Under mapping
```

## Built-in Market Mappings

### 1X2 - Full Time

| | BetPawa | SportyBet | Bet9ja |
|---|---|---|---|
| Market ID | `3743` | `1` | `S_1X2` |
| Home | `1` | `Home` | `1` |
| Draw | `X` | `Draw` | `X` |
| Away | `2` | `Away` | `2` |

### Over/Under - Full Time (parameterized)

| | BetPawa | SportyBet | Bet9ja |
|---|---|---|---|
| Market ID | `5000` | `18` | `S_OU` |
| Over | `Over` | `Over` | `O` |
| Under | `Under` | `Under` | `U` |

Lines extracted from: BetPawa `row[].line`, SportyBet specifier `"total=2.5"`, Bet9ja key `S_OU@2.5_O`

### Both Teams To Score - Full Time

| | BetPawa | SportyBet | Bet9ja |
|---|---|---|---|
| Market ID | `3795` | `29` | `S_GGNG` |
| Yes | `Yes` | `Yes` | `Y` |
| No | `No` | `No` | `N` |

### Double Chance - Full Time

| | BetPawa | SportyBet | Bet9ja |
|---|---|---|---|
| Market ID | `4693` | `10` | `S_DC` |
| Home/Draw | `1X` | `Home or Draw` | `1X` |
| Draw/Away | `X2` | `Draw or Away` | `X2` |
| Home/Away | `12` | `Home or Away` | `12` |

## Market Parser

### API

```python
def parse_markets(
    response: dict,
    platform: str,
    registry: MarketRegistry | None = None,
) -> list[NormalizedMarket]:
    """Parse raw event detail response into normalized markets.

    Args:
        response: Raw JSON from get_event_detail()
        platform: "betpawa", "sportybet", or "bet9ja"
        registry: Market registry to use (default: built-in 4 markets)

    Returns:
        List of NormalizedMarket for all recognized markets.
        Markets not in the registry are skipped.
    """
```

### Platform-Specific Parsing

**BetPawa:**
- Iterates `markets[]` array
- Matches `market.id` (string) against registry's `betpawa_id`
- Extracts odds from `row[].prices[]`
- For parameterized markets: groups by `row[].line` value into `lines` dict

**SportyBet:**
- Iterates `data.markets[]` array
- Matches `market.id` (string) against registry's `sportybet_id`
- Parses specifier string (e.g., `"total=2.5"`) to extract line value
- Maps `outcome.id`/`outcome.desc` to canonical names via OutcomeMapping

**Bet9ja:**
- Iterates the flat `D.O` dict (key-value pairs)
- Matches key prefix against registry's `bet9ja_key` (e.g., keys starting with `S_OU`)
- Extracts line from `@` separator (e.g., `S_OU@2.5_O` → line=2.5)
- Maps key suffix to canonical outcome name (e.g., `_O` → "over")

### Output Examples

**Simple market (1X2):**

```python
NormalizedMarket(
    canonical_id="1x2_ft",
    name="1X2 - Full Time",
    outcomes=[
        Outcome(canonical_name="home", odds=1.95, platform_name="1"),
        Outcome(canonical_name="draw", odds=3.50, platform_name="X"),
        Outcome(canonical_name="away", odds=2.10, platform_name="2"),
    ],
    lines=None,
)
```

**Parameterized market (O/U):**

```python
NormalizedMarket(
    canonical_id="over_under_ft",
    name="Over/Under - Full Time",
    outcomes=[],
    lines={
        2.5: [
            Outcome(canonical_name="over", odds=1.80, platform_name="Over"),
            Outcome(canonical_name="under", odds=2.00, platform_name="Under"),
        ],
        3.5: [
            Outcome(canonical_name="over", odds=2.10, platform_name="Over"),
            Outcome(canonical_name="under", odds=1.70, platform_name="Under"),
        ],
    },
)
```

## Event Matching

### SportRadar ID Extraction

```python
def extract_sportradar_id(response: dict, platform: str) -> str | None:
    """Extract SportRadar ID from a raw event detail response.

    Args:
        response: Raw JSON from get_event_detail()
        platform: "betpawa", "sportybet", or "bet9ja"

    Returns:
        SportRadar ID as string (numeric only, no prefix), or None if not found.
    """
```

**Platform-specific extraction:**
- **BetPawa**: Searches `widgets[]` for object with `type="SPORTRADAR"`, returns `value`
- **SportyBet**: Takes `data.eventId` field, strips `"sr:match:"` prefix
- **Bet9ja**: Takes `D.EXTID` field directly

All return a normalized numeric string (no prefixes) for consistent matching.

### Event Matcher

```python
@dataclass
class MatchedEvent:
    """An event matched across multiple platforms."""
    sportradar_id: str
    betpawa: dict | None = None
    sportybet: dict | None = None
    bet9ja: dict | None = None


def match_events(
    *event_lists: tuple[str, list[dict]],
) -> list[MatchedEvent]:
    """Match events across platforms by SportRadar ID.

    Args:
        event_lists: Tuples of (platform, events) where events
                     are raw event detail responses.

    Returns:
        List of MatchedEvent grouped by shared SportRadar ID.
    """
```

### Usage

```python
from bookieskit import BetPawa, SportyBet
from bookieskit.matching import extract_sportradar_id, match_events

# Low-level: single event
async with BetPawa(country="ng") as client:
    detail = await client.get_event_detail(event_id="32299257")
    sr_id = extract_sportradar_id(detail, platform="betpawa")
    # Returns: "61300947"

# High-level: match across platforms
matched = match_events(
    ("betpawa", bp_details),
    ("sportybet", sb_details),
    ("bet9ja", b9_details),
)
# Returns: [MatchedEvent(sportradar_id="61300947", betpawa={...}, sportybet={...}, bet9ja={...})]
```

## Client Convenience Methods

Added to `BaseBookmaker` (inherited by all clients):

```python
class BaseBookmaker:
    PLATFORM_KEY: str = ""  # Overridden by subclasses

    async def get_markets(
        self,
        event_id: str,
        registry: MarketRegistry | None = None,
    ) -> list[NormalizedMarket]:
        """Fetch event detail and return normalized markets.

        Args:
            event_id: Platform-specific event ID
            registry: Market registry (default: built-in 4 markets)

        Returns:
            List of NormalizedMarket for recognized markets.
        """
        raw = await self.get_event_detail(event_id=event_id)
        return parse_markets(raw, platform=self.PLATFORM_KEY, registry=registry)

    async def get_sportradar_id(self, event_id: str) -> str | None:
        """Fetch event detail and extract SportRadar ID.

        Args:
            event_id: Platform-specific event ID

        Returns:
            SportRadar ID string, or None if not available.
        """
        raw = await self.get_event_detail(event_id=event_id)
        return extract_sportradar_id(raw, platform=self.PLATFORM_KEY)
```

Platform keys:
- `BetPawa.PLATFORM_KEY = "betpawa"`
- `SportyBet.PLATFORM_KEY = "sportybet"`
- `Bet9ja.PLATFORM_KEY = "bet9ja"`

Sync mode works automatically via the existing `_SyncProxy`.

## Documentation

### docs/markets.md

Contents:
1. How market mapping works (registry, parsing, canonical IDs)
2. Built-in markets reference table
3. Usage examples (get_markets, custom registry, filtering)
4. **Contributing new markets via PR:**
   - Add mapping entry to `builtin_mappings.py`
   - Add outcome mappings for all 3 platforms (None if not available)
   - Add test with real response fixtures
   - Update reference table in docs
   - Set `parameterized=True` if market has lines (O/U, handicaps)

### docs/matching.md

Contents:
1. How SportRadar IDs work per platform
2. Usage examples (extraction, matching)
3. Limitations (BetPawa/Bet9ja need event detail fetch for SR ID)

## Backwards Compatibility

- All v1 methods unchanged (`get_sports`, `get_countries`, `get_tournaments`, `get_events`, `get_event_detail`)
- New methods are additive (`get_markets`, `get_sportradar_id`)
- New modules are opt-in imports (`from bookieskit.markets import ...`)
- No breaking changes to existing consumer code

## Testing Strategy

- Unit tests for each parser (BetPawa, SportyBet, Bet9ja) with fixture responses
- Unit tests for MarketRegistry (add, lookup, builtins)
- Unit tests for SportRadar ID extraction per platform
- Unit tests for match_events grouping logic
- Integration tests for convenience methods (get_markets, get_sportradar_id)
- Sync wrapper tests for new convenience methods
