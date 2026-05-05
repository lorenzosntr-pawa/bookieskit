# Bookieskit v2: Market Mapping & Event Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add normalized market parsing (with extensible registry) and cross-platform event matching via SportRadar IDs to the bookieskit library.

**Architecture:** Two standalone modules (`markets/`, `matching/`) with thin convenience wrappers on existing client classes. Registry ships with 4 built-in markets, users can extend at runtime. Event matching uses SportRadar IDs extracted from platform-specific response locations.

**Tech Stack:** Python 3.11+, dataclasses (frozen), existing httpx clients, pytest + respx for testing

---

## File Structure

```
src/bookieskit/
├── markets/
│   ├── __init__.py          # Public exports
│   ├── types.py             # Outcome, NormalizedMarket, OutcomeMapping, MarketMapping
│   ├── builtin_mappings.py  # 4 built-in market definitions (1X2, O/U, BTTS, DC)
│   ├── registry.py          # MarketRegistry class
│   └── parser.py            # parse_markets() with platform-specific logic
├── matching/
│   ├── __init__.py          # Public exports
│   ├── extractor.py         # extract_sportradar_id()
│   └── matcher.py           # MatchedEvent, match_events()
├── base.py                  # (modify) Add PLATFORM_KEY, get_markets(), get_sportradar_id()
├── bookmakers/
│   ├── betpawa.py           # (modify) Add PLATFORM_KEY = "betpawa"
│   ├── sportybet.py         # (modify) Add PLATFORM_KEY = "sportybet"
│   └── bet9ja.py            # (modify) Add PLATFORM_KEY = "bet9ja"
└── __init__.py              # (modify) Re-export new public APIs
tests/
├── test_types.py            # Market types tests
├── test_registry.py         # MarketRegistry tests
├── test_parser_betpawa.py   # BetPawa parser tests
├── test_parser_sportybet.py # SportyBet parser tests
├── test_parser_bet9ja.py    # Bet9ja parser tests
├── test_extractor.py        # SportRadar ID extraction tests
├── test_matcher.py          # Event matcher tests
└── test_convenience.py      # Client convenience method tests
```

---

## Task 1: Market Types

**Files:**
- Create: `src/bookieskit/markets/__init__.py`
- Create: `src/bookieskit/markets/types.py`
- Create: `tests/test_types.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_types.py`:

```python
from bookieskit.markets.types import (
    MarketMapping,
    NormalizedMarket,
    Outcome,
    OutcomeMapping,
)


def test_outcome_is_frozen():
    o = Outcome(canonical_name="home", odds=1.95, platform_name="1")
    assert o.canonical_name == "home"
    assert o.odds == 1.95
    assert o.platform_name == "1"


def test_normalized_market_simple():
    market = NormalizedMarket(
        canonical_id="1x2_ft",
        name="1X2 - Full Time",
        outcomes=[
            Outcome(canonical_name="home", odds=1.95, platform_name="1"),
            Outcome(canonical_name="draw", odds=3.50, platform_name="X"),
            Outcome(canonical_name="away", odds=2.10, platform_name="2"),
        ],
    )
    assert market.canonical_id == "1x2_ft"
    assert len(market.outcomes) == 3
    assert market.lines is None


def test_normalized_market_parameterized():
    market = NormalizedMarket(
        canonical_id="over_under_ft",
        name="Over/Under - Full Time",
        outcomes=[],
        lines={
            2.5: [
                Outcome(canonical_name="over", odds=1.80, platform_name="Over"),
                Outcome(canonical_name="under", odds=2.00, platform_name="Under"),
            ],
        },
    )
    assert market.lines is not None
    assert 2.5 in market.lines
    assert len(market.lines[2.5]) == 2


def test_outcome_mapping():
    om = OutcomeMapping(
        canonical_name="home",
        betpawa="1",
        sportybet="Home",
        bet9ja="1",
    )
    assert om.canonical_name == "home"
    assert om.betpawa == "1"
    assert om.sportybet == "Home"
    assert om.bet9ja == "1"


def test_market_mapping():
    mm = MarketMapping(
        canonical_id="1x2_ft",
        name="1X2 - Full Time",
        betpawa_id="3743",
        sportybet_id="1",
        bet9ja_key="S_1X2",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
            ),
        },
        parameterized=False,
    )
    assert mm.canonical_id == "1x2_ft"
    assert mm.betpawa_id == "3743"
    assert mm.parameterized is False
    assert "home" in mm.outcomes


def test_market_mapping_with_none_platform():
    mm = MarketMapping(
        canonical_id="test_market",
        name="Test",
        betpawa_id="123",
        sportybet_id=None,
        bet9ja_key=None,
        outcomes={},
        parameterized=False,
    )
    assert mm.sportybet_id is None
    assert mm.bet9ja_key is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd c:/Users/loren/Desktop/betpawa/comparison/mvp1/bookieskit && .venv/Scripts/python -m pytest tests/test_types.py -v`
Expected: FAIL (cannot import)

- [ ] **Step 3: Write implementation**

Create `src/bookieskit/markets/__init__.py`:

```python
"""Market mapping and normalization."""
```

Create `src/bookieskit/markets/types.py`:

```python
"""Data types for market mapping."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Outcome:
    """A single outcome within a market."""

    canonical_name: str
    odds: float
    platform_name: str


@dataclass(frozen=True)
class NormalizedMarket:
    """A market normalized to canonical format.

    For simple markets (1X2, BTTS, DC): outcomes is populated, lines is None.
    For parameterized markets (O/U, handicaps): lines is populated, outcomes is empty.
    """

    canonical_id: str
    name: str
    outcomes: list[Outcome] = field(default_factory=list)
    lines: dict[float, list[Outcome]] | None = None


@dataclass(frozen=True)
class OutcomeMapping:
    """Maps one outcome across platforms."""

    canonical_name: str
    betpawa: str
    sportybet: str
    bet9ja: str


@dataclass(frozen=True)
class MarketMapping:
    """Defines how one market maps across platforms."""

    canonical_id: str
    name: str
    betpawa_id: str | None
    sportybet_id: str | None
    bet9ja_key: str | None
    outcomes: dict[str, OutcomeMapping]
    parameterized: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_types.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/ tests/test_types.py
git commit -m "feat: add market mapping data types"
```

---

## Task 2: Built-in Market Mappings

**Files:**
- Create: `src/bookieskit/markets/builtin_mappings.py`

- [ ] **Step 1: Create built-in mappings**

Create `src/bookieskit/markets/builtin_mappings.py`:

```python
"""Built-in market mappings for the 4 main markets."""

from bookieskit.markets.types import MarketMapping, OutcomeMapping

BUILTIN_MAPPINGS: list[MarketMapping] = [
    MarketMapping(
        canonical_id="1x2_ft",
        name="1X2 - Full Time",
        betpawa_id="3743",
        sportybet_id="1",
        bet9ja_key="S_1X2",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
            ),
            "draw": OutcomeMapping(
                canonical_name="draw",
                betpawa="X",
                sportybet="Draw",
                bet9ja="X",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
            ),
        },
        parameterized=False,
    ),
    MarketMapping(
        canonical_id="over_under_ft",
        name="Over/Under - Full Time",
        betpawa_id="5000",
        sportybet_id="18",
        bet9ja_key="S_OU",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="O",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="U",
            ),
        },
        parameterized=True,
    ),
    MarketMapping(
        canonical_id="btts_ft",
        name="Both Teams To Score - Full Time",
        betpawa_id="3795",
        sportybet_id="29",
        bet9ja_key="S_GGNG",
        outcomes={
            "yes": OutcomeMapping(
                canonical_name="yes",
                betpawa="Yes",
                sportybet="Yes",
                bet9ja="Y",
            ),
            "no": OutcomeMapping(
                canonical_name="no",
                betpawa="No",
                sportybet="No",
                bet9ja="N",
            ),
        },
        parameterized=False,
    ),
    MarketMapping(
        canonical_id="double_chance_ft",
        name="Double Chance - Full Time",
        betpawa_id="4693",
        sportybet_id="10",
        bet9ja_key="S_DC",
        outcomes={
            "home_draw": OutcomeMapping(
                canonical_name="home_draw",
                betpawa="1X",
                sportybet="Home or Draw",
                bet9ja="1X",
            ),
            "draw_away": OutcomeMapping(
                canonical_name="draw_away",
                betpawa="X2",
                sportybet="Draw or Away",
                bet9ja="X2",
            ),
            "home_away": OutcomeMapping(
                canonical_name="home_away",
                betpawa="12",
                sportybet="Home or Away",
                bet9ja="12",
            ),
        },
        parameterized=False,
    ),
]
```

- [ ] **Step 2: Verify import works**

Run: `.venv/Scripts/python -c "from bookieskit.markets.builtin_mappings import BUILTIN_MAPPINGS; print(len(BUILTIN_MAPPINGS))"`
Expected: `4`

- [ ] **Step 3: Commit**

```bash
git add src/bookieskit/markets/builtin_mappings.py
git commit -m "feat: add 4 built-in market mappings (1X2, O/U, BTTS, DC)"
```

---

## Task 3: MarketRegistry

**Files:**
- Create: `src/bookieskit/markets/registry.py`
- Create: `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_registry.py`:

```python
import pytest

from bookieskit.markets.registry import MarketRegistry
from bookieskit.markets.types import MarketMapping, OutcomeMapping


def test_registry_loads_builtins_by_default():
    registry = MarketRegistry()
    markets = registry.list_markets()
    assert len(markets) == 4


def test_registry_no_builtins():
    registry = MarketRegistry(load_builtins=False)
    markets = registry.list_markets()
    assert len(markets) == 0


def test_registry_get_by_canonical():
    registry = MarketRegistry()
    mapping = registry.get_by_canonical("1x2_ft")
    assert mapping is not None
    assert mapping.name == "1X2 - Full Time"


def test_registry_get_by_canonical_not_found():
    registry = MarketRegistry()
    assert registry.get_by_canonical("nonexistent") is None


def test_registry_get_by_platform_id_betpawa():
    registry = MarketRegistry()
    mapping = registry.get_by_platform_id("betpawa", "3743")
    assert mapping is not None
    assert mapping.canonical_id == "1x2_ft"


def test_registry_get_by_platform_id_sportybet():
    registry = MarketRegistry()
    mapping = registry.get_by_platform_id("sportybet", "18")
    assert mapping is not None
    assert mapping.canonical_id == "over_under_ft"


def test_registry_get_by_platform_id_bet9ja():
    registry = MarketRegistry()
    mapping = registry.get_by_platform_id("bet9ja", "S_GGNG")
    assert mapping is not None
    assert mapping.canonical_id == "btts_ft"


def test_registry_get_by_platform_id_not_found():
    registry = MarketRegistry()
    assert registry.get_by_platform_id("betpawa", "99999") is None


def test_registry_add_custom_mapping():
    registry = MarketRegistry()
    registry.add(
        canonical_id="draw_no_bet_ft",
        name="Draw No Bet - Full Time",
        betpawa_id="4703",
        sportybet_id="11",
        bet9ja_key="S_DNB",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
            ),
        },
    )
    assert len(registry.list_markets()) == 5
    mapping = registry.get_by_canonical("draw_no_bet_ft")
    assert mapping is not None
    assert mapping.betpawa_id == "4703"


def test_registry_add_parameterized():
    registry = MarketRegistry(load_builtins=False)
    registry.add(
        canonical_id="asian_handicap_ft",
        name="Asian Handicap - Full Time",
        betpawa_id="3774",
        sportybet_id="16",
        bet9ja_key="S_AH",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
            ),
        },
        parameterized=True,
    )
    mapping = registry.get_by_canonical("asian_handicap_ft")
    assert mapping.parameterized is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_registry.py -v`
Expected: FAIL (cannot import MarketRegistry)

- [ ] **Step 3: Write implementation**

Create `src/bookieskit/markets/registry.py`:

```python
"""Market registry — built-in + user-extensible."""

from bookieskit.markets.builtin_mappings import BUILTIN_MAPPINGS
from bookieskit.markets.types import MarketMapping, OutcomeMapping


class MarketRegistry:
    """Registry of market mappings.

    Ships with 4 built-in markets (1X2, O/U, BTTS, DC).
    Users can add custom mappings at runtime.
    """

    def __init__(self, load_builtins: bool = True):
        """Initialize registry.

        Args:
            load_builtins: Load built-in markets (default: True).
        """
        self._by_canonical: dict[str, MarketMapping] = {}
        self._by_betpawa: dict[str, MarketMapping] = {}
        self._by_sportybet: dict[str, MarketMapping] = {}
        self._by_bet9ja: dict[str, MarketMapping] = {}

        if load_builtins:
            for mapping in BUILTIN_MAPPINGS:
                self._register(mapping)

    def _register(self, mapping: MarketMapping) -> None:
        """Register a mapping in all lookup indices."""
        self._by_canonical[mapping.canonical_id] = mapping
        if mapping.betpawa_id:
            self._by_betpawa[mapping.betpawa_id] = mapping
        if mapping.sportybet_id:
            self._by_sportybet[mapping.sportybet_id] = mapping
        if mapping.bet9ja_key:
            self._by_bet9ja[mapping.bet9ja_key] = mapping

    def add(
        self,
        canonical_id: str,
        name: str,
        betpawa_id: str | None = None,
        sportybet_id: str | None = None,
        bet9ja_key: str | None = None,
        outcomes: dict[str, OutcomeMapping] | None = None,
        parameterized: bool = False,
    ) -> None:
        """Register a new market mapping.

        Args:
            canonical_id: Unique ID (e.g., "correct_score_ft")
            name: Human-readable name
            betpawa_id: BetPawa market ID (or None)
            sportybet_id: SportyBet market ID (or None)
            bet9ja_key: Bet9ja key prefix (or None)
            outcomes: Dict of canonical_name -> OutcomeMapping
            parameterized: True if market has lines (O/U, handicaps)
        """
        mapping = MarketMapping(
            canonical_id=canonical_id,
            name=name,
            betpawa_id=betpawa_id,
            sportybet_id=sportybet_id,
            bet9ja_key=bet9ja_key,
            outcomes=outcomes or {},
            parameterized=parameterized,
        )
        self._register(mapping)

    def get_by_canonical(self, canonical_id: str) -> MarketMapping | None:
        """Look up by canonical ID."""
        return self._by_canonical.get(canonical_id)

    def get_by_platform_id(
        self, platform: str, platform_id: str
    ) -> MarketMapping | None:
        """Look up by platform-specific ID.

        Args:
            platform: "betpawa", "sportybet", or "bet9ja"
            platform_id: Platform-specific market ID or key
        """
        index = {
            "betpawa": self._by_betpawa,
            "sportybet": self._by_sportybet,
            "bet9ja": self._by_bet9ja,
        }.get(platform, {})
        return index.get(platform_id)

    def list_markets(self) -> list[MarketMapping]:
        """Return all registered mappings."""
        return list(self._by_canonical.values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_registry.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/registry.py tests/test_registry.py
git commit -m "feat: add MarketRegistry with built-in + user-extensible mappings"
```

---

## Task 4: Market Parser — BetPawa

**Files:**
- Create: `src/bookieskit/markets/parser.py`
- Create: `tests/test_parser_betpawa.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_parser_betpawa.py`:

```python
from bookieskit.markets.parser import parse_markets
from bookieskit.markets.registry import MarketRegistry


BETPAWA_EVENT_RESPONSE = {
    "id": "32299257",
    "homeTeam": "Manchester City",
    "awayTeam": "Liverpool",
    "markets": [
        {
            "id": "3743",
            "name": "1X2 - Full Time",
            "row": [
                {
                    "prices": [
                        {"name": "1", "odds": 1.95},
                        {"name": "X", "odds": 3.50},
                        {"name": "2", "odds": 2.10},
                    ]
                }
            ],
        },
        {
            "id": "5000",
            "name": "Over/Under",
            "row": [
                {
                    "line": 2.5,
                    "prices": [
                        {"name": "Over", "odds": 1.80},
                        {"name": "Under", "odds": 2.00},
                    ],
                },
                {
                    "line": 3.5,
                    "prices": [
                        {"name": "Over", "odds": 2.10},
                        {"name": "Under", "odds": 1.70},
                    ],
                },
            ],
        },
        {
            "id": "3795",
            "name": "Both Teams To Score",
            "row": [
                {
                    "prices": [
                        {"name": "Yes", "odds": 1.75},
                        {"name": "No", "odds": 2.05},
                    ]
                }
            ],
        },
        {
            "id": "4693",
            "name": "Double Chance",
            "row": [
                {
                    "prices": [
                        {"name": "1X", "odds": 1.25},
                        {"name": "X2", "odds": 1.50},
                        {"name": "12", "odds": 1.10},
                    ]
                }
            ],
        },
        {
            "id": "9999",
            "name": "Unknown Market",
            "row": [{"prices": [{"name": "A", "odds": 2.00}]}],
        },
    ],
}


def test_parse_betpawa_1x2():
    markets = parse_markets(BETPAWA_EVENT_RESPONSE, platform="betpawa")
    m1x2 = next(m for m in markets if m.canonical_id == "1x2_ft")
    assert m1x2.name == "1X2 - Full Time"
    assert len(m1x2.outcomes) == 3
    assert m1x2.lines is None
    home = next(o for o in m1x2.outcomes if o.canonical_name == "home")
    assert home.odds == 1.95
    assert home.platform_name == "1"


def test_parse_betpawa_over_under():
    markets = parse_markets(BETPAWA_EVENT_RESPONSE, platform="betpawa")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    assert ou.lines is not None
    assert 2.5 in ou.lines
    assert 3.5 in ou.lines
    assert len(ou.outcomes) == 0
    over_25 = next(
        o for o in ou.lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds == 1.80
    assert over_25.platform_name == "Over"


def test_parse_betpawa_btts():
    markets = parse_markets(BETPAWA_EVENT_RESPONSE, platform="betpawa")
    btts = next(m for m in markets if m.canonical_id == "btts_ft")
    assert len(btts.outcomes) == 2
    yes = next(o for o in btts.outcomes if o.canonical_name == "yes")
    assert yes.odds == 1.75


def test_parse_betpawa_double_chance():
    markets = parse_markets(BETPAWA_EVENT_RESPONSE, platform="betpawa")
    dc = next(m for m in markets if m.canonical_id == "double_chance_ft")
    assert len(dc.outcomes) == 3
    hd = next(o for o in dc.outcomes if o.canonical_name == "home_draw")
    assert hd.odds == 1.25


def test_parse_betpawa_skips_unknown_markets():
    markets = parse_markets(BETPAWA_EVENT_RESPONSE, platform="betpawa")
    ids = [m.canonical_id for m in markets]
    assert len(markets) == 4
    assert "1x2_ft" in ids
    assert "over_under_ft" in ids
    assert "btts_ft" in ids
    assert "double_chance_ft" in ids


def test_parse_betpawa_with_custom_registry():
    registry = MarketRegistry(load_builtins=False)
    markets = parse_markets(
        BETPAWA_EVENT_RESPONSE, platform="betpawa", registry=registry
    )
    assert len(markets) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_parser_betpawa.py -v`
Expected: FAIL (cannot import parse_markets)

- [ ] **Step 3: Write implementation**

Create `src/bookieskit/markets/parser.py`:

```python
"""Market parser — transforms raw event responses into NormalizedMarkets."""

from bookieskit.markets.registry import MarketRegistry
from bookieskit.markets.types import (
    MarketMapping,
    NormalizedMarket,
    Outcome,
)


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
    if registry is None:
        registry = MarketRegistry()

    parsers = {
        "betpawa": _parse_betpawa,
        "sportybet": _parse_sportybet,
        "bet9ja": _parse_bet9ja,
    }
    parser = parsers.get(platform)
    if parser is None:
        return []
    return parser(response, registry)


def _parse_betpawa(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse BetPawa event detail response."""
    results: list[NormalizedMarket] = []
    markets = response.get("markets", [])

    for market_data in markets:
        market_id = str(market_data.get("id", ""))
        mapping = registry.get_by_platform_id("betpawa", market_id)
        if mapping is None:
            continue

        if mapping.parameterized:
            results.append(
                _parse_betpawa_parameterized(market_data, mapping)
            )
        else:
            results.append(_parse_betpawa_simple(market_data, mapping))

    return results


def _parse_betpawa_simple(
    market_data: dict, mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a simple BetPawa market (1X2, BTTS, DC)."""
    outcomes: list[Outcome] = []
    rows = market_data.get("row", [])

    for row in rows:
        for price in row.get("prices", []):
            price_name = str(price.get("name", ""))
            odds = float(price.get("odds", 0))
            canonical = _resolve_outcome_betpawa(
                price_name, mapping
            )
            if canonical:
                outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=price_name,
                    )
                )

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=outcomes,
        lines=None,
    )


def _parse_betpawa_parameterized(
    market_data: dict, mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a parameterized BetPawa market (O/U, handicaps)."""
    lines: dict[float, list[Outcome]] = {}
    rows = market_data.get("row", [])

    for row in rows:
        line = row.get("line")
        if line is None:
            continue
        line = float(line)
        line_outcomes: list[Outcome] = []

        for price in row.get("prices", []):
            price_name = str(price.get("name", ""))
            odds = float(price.get("odds", 0))
            canonical = _resolve_outcome_betpawa(
                price_name, mapping
            )
            if canonical:
                line_outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=price_name,
                    )
                )

        if line_outcomes:
            lines[line] = line_outcomes

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=[],
        lines=lines,
    )


def _resolve_outcome_betpawa(
    platform_name: str, mapping: MarketMapping
) -> str | None:
    """Find canonical outcome name from BetPawa platform name."""
    for om in mapping.outcomes.values():
        if om.betpawa == platform_name:
            return om.canonical_name
    return None


def _parse_sportybet(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse SportyBet event detail response. (Implemented in Task 5)"""
    return []


def _parse_bet9ja(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse Bet9ja event detail response. (Implemented in Task 6)"""
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_parser_betpawa.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_parser_betpawa.py
git commit -m "feat: add market parser with BetPawa support"
```

---

## Task 5: Market Parser — SportyBet

**Files:**
- Modify: `src/bookieskit/markets/parser.py`
- Create: `tests/test_parser_sportybet.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_parser_sportybet.py`:

```python
from bookieskit.markets.parser import parse_markets
from bookieskit.markets.registry import MarketRegistry


SPORTYBET_EVENT_RESPONSE = {
    "bizCode": 10000,
    "data": {
        "eventId": "sr:match:61300947",
        "markets": [
            {
                "id": "1",
                "desc": "1X2 - Full Time",
                "specifier": None,
                "outcomes": [
                    {"id": "1", "desc": "Home", "odds": "1.95"},
                    {"id": "2", "desc": "Draw", "odds": "3.50"},
                    {"id": "3", "desc": "Away", "odds": "2.10"},
                ],
            },
            {
                "id": "18",
                "desc": "Over/Under",
                "specifier": "total=2.5",
                "outcomes": [
                    {"id": "1", "desc": "Over", "odds": "1.80"},
                    {"id": "2", "desc": "Under", "odds": "2.00"},
                ],
            },
            {
                "id": "18",
                "desc": "Over/Under",
                "specifier": "total=3.5",
                "outcomes": [
                    {"id": "1", "desc": "Over", "odds": "2.10"},
                    {"id": "2", "desc": "Under", "odds": "1.70"},
                ],
            },
            {
                "id": "29",
                "desc": "Both Teams To Score",
                "specifier": None,
                "outcomes": [
                    {"id": "1", "desc": "Yes", "odds": "1.75"},
                    {"id": "2", "desc": "No", "odds": "2.05"},
                ],
            },
            {
                "id": "10",
                "desc": "Double Chance",
                "specifier": None,
                "outcomes": [
                    {"id": "1", "desc": "Home or Draw", "odds": "1.25"},
                    {"id": "2", "desc": "Draw or Away", "odds": "1.50"},
                    {"id": "3", "desc": "Home or Away", "odds": "1.10"},
                ],
            },
            {
                "id": "999",
                "desc": "Unknown Market",
                "specifier": None,
                "outcomes": [
                    {"id": "1", "desc": "Option A", "odds": "2.00"},
                ],
            },
        ],
    },
}


def test_parse_sportybet_1x2():
    markets = parse_markets(SPORTYBET_EVENT_RESPONSE, platform="sportybet")
    m1x2 = next(m for m in markets if m.canonical_id == "1x2_ft")
    assert m1x2.name == "1X2 - Full Time"
    assert len(m1x2.outcomes) == 3
    assert m1x2.lines is None
    home = next(o for o in m1x2.outcomes if o.canonical_name == "home")
    assert home.odds == 1.95
    assert home.platform_name == "Home"


def test_parse_sportybet_over_under():
    markets = parse_markets(SPORTYBET_EVENT_RESPONSE, platform="sportybet")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    assert ou.lines is not None
    assert 2.5 in ou.lines
    assert 3.5 in ou.lines
    over_25 = next(
        o for o in ou.lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds == 1.80
    assert over_25.platform_name == "Over"


def test_parse_sportybet_btts():
    markets = parse_markets(SPORTYBET_EVENT_RESPONSE, platform="sportybet")
    btts = next(m for m in markets if m.canonical_id == "btts_ft")
    assert len(btts.outcomes) == 2
    yes = next(o for o in btts.outcomes if o.canonical_name == "yes")
    assert yes.odds == 1.75


def test_parse_sportybet_double_chance():
    markets = parse_markets(SPORTYBET_EVENT_RESPONSE, platform="sportybet")
    dc = next(m for m in markets if m.canonical_id == "double_chance_ft")
    assert len(dc.outcomes) == 3
    hd = next(o for o in dc.outcomes if o.canonical_name == "home_draw")
    assert hd.odds == 1.25
    assert hd.platform_name == "Home or Draw"


def test_parse_sportybet_skips_unknown():
    markets = parse_markets(SPORTYBET_EVENT_RESPONSE, platform="sportybet")
    assert len(markets) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_parser_sportybet.py -v`
Expected: FAIL (parse_markets returns empty for sportybet)

- [ ] **Step 3: Replace `_parse_sportybet` stub in `src/bookieskit/markets/parser.py`**

Replace the `_parse_sportybet` function with:

```python
def _parse_sportybet(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse SportyBet event detail response."""
    results: list[NormalizedMarket] = []
    data = response.get("data", response)
    markets = data.get("markets", [])

    # Group parameterized markets by ID (multiple entries per line)
    parameterized_groups: dict[str, list[dict]] = {}

    for market_data in markets:
        market_id = str(market_data.get("id", ""))
        mapping = registry.get_by_platform_id("sportybet", market_id)
        if mapping is None:
            continue

        if mapping.parameterized:
            if market_id not in parameterized_groups:
                parameterized_groups[market_id] = []
            parameterized_groups[market_id].append(market_data)
        else:
            results.append(
                _parse_sportybet_simple(market_data, mapping)
            )

    # Process grouped parameterized markets
    for market_id, entries in parameterized_groups.items():
        mapping = registry.get_by_platform_id("sportybet", market_id)
        if mapping:
            results.append(
                _parse_sportybet_parameterized(entries, mapping)
            )

    return results


def _parse_sportybet_simple(
    market_data: dict, mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a simple SportyBet market."""
    outcomes: list[Outcome] = []

    for outcome_data in market_data.get("outcomes", []):
        desc = str(outcome_data.get("desc", ""))
        odds = float(outcome_data.get("odds", 0))
        canonical = _resolve_outcome_sportybet(desc, mapping)
        if canonical:
            outcomes.append(
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=desc,
                )
            )

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=outcomes,
        lines=None,
    )


def _parse_sportybet_parameterized(
    entries: list[dict], mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a parameterized SportyBet market (multiple entries, one per line)."""
    lines: dict[float, list[Outcome]] = {}

    for entry in entries:
        specifier = entry.get("specifier", "") or ""
        line = _extract_line_from_specifier(specifier)
        if line is None:
            continue

        line_outcomes: list[Outcome] = []
        for outcome_data in entry.get("outcomes", []):
            desc = str(outcome_data.get("desc", ""))
            odds = float(outcome_data.get("odds", 0))
            canonical = _resolve_outcome_sportybet(desc, mapping)
            if canonical:
                line_outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=desc,
                    )
                )

        if line_outcomes:
            lines[line] = line_outcomes

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=[],
        lines=lines,
    )


def _extract_line_from_specifier(specifier: str) -> float | None:
    """Extract line value from SportyBet specifier string.

    Examples: "total=2.5" -> 2.5, "hcp=-0.5" -> -0.5
    """
    for part in specifier.split("|"):
        if "=" in part:
            key, value = part.split("=", 1)
            if key in ("total", "hcp"):
                try:
                    return float(value)
                except ValueError:
                    continue
    return None


def _resolve_outcome_sportybet(
    platform_name: str, mapping: MarketMapping
) -> str | None:
    """Find canonical outcome name from SportyBet outcome desc."""
    for om in mapping.outcomes.values():
        if om.sportybet == platform_name:
            return om.canonical_name
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_parser_sportybet.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_parser_sportybet.py
git commit -m "feat: add SportyBet market parser with specifier handling"
```

---

## Task 6: Market Parser — Bet9ja

**Files:**
- Modify: `src/bookieskit/markets/parser.py`
- Create: `tests/test_parser_bet9ja.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_parser_bet9ja.py`:

```python
from bookieskit.markets.parser import parse_markets
from bookieskit.markets.registry import MarketRegistry


BET9JA_EVENT_RESPONSE = {
    "R": "D",
    "D": {
        "EXTID": "sr:match:61300947",
        "O": {
            "S_1X2_1": "1.95",
            "S_1X2_X": "3.50",
            "S_1X2_2": "2.10",
            "S_OU@2.5_O": "1.80",
            "S_OU@2.5_U": "2.00",
            "S_OU@3.5_O": "2.10",
            "S_OU@3.5_U": "1.70",
            "S_GGNG_Y": "1.75",
            "S_GGNG_N": "2.05",
            "S_DC_1X": "1.25",
            "S_DC_X2": "1.50",
            "S_DC_12": "1.10",
            "S_UNKNOWN_A": "2.00",
        },
    },
}


def test_parse_bet9ja_1x2():
    markets = parse_markets(BET9JA_EVENT_RESPONSE, platform="bet9ja")
    m1x2 = next(m for m in markets if m.canonical_id == "1x2_ft")
    assert m1x2.name == "1X2 - Full Time"
    assert len(m1x2.outcomes) == 3
    assert m1x2.lines is None
    home = next(o for o in m1x2.outcomes if o.canonical_name == "home")
    assert home.odds == 1.95
    assert home.platform_name == "1"


def test_parse_bet9ja_over_under():
    markets = parse_markets(BET9JA_EVENT_RESPONSE, platform="bet9ja")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    assert ou.lines is not None
    assert 2.5 in ou.lines
    assert 3.5 in ou.lines
    over_25 = next(
        o for o in ou.lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds == 1.80
    assert over_25.platform_name == "O"


def test_parse_bet9ja_btts():
    markets = parse_markets(BET9JA_EVENT_RESPONSE, platform="bet9ja")
    btts = next(m for m in markets if m.canonical_id == "btts_ft")
    assert len(btts.outcomes) == 2
    yes = next(o for o in btts.outcomes if o.canonical_name == "yes")
    assert yes.odds == 1.75
    assert yes.platform_name == "Y"


def test_parse_bet9ja_double_chance():
    markets = parse_markets(BET9JA_EVENT_RESPONSE, platform="bet9ja")
    dc = next(m for m in markets if m.canonical_id == "double_chance_ft")
    assert len(dc.outcomes) == 3
    hd = next(o for o in dc.outcomes if o.canonical_name == "home_draw")
    assert hd.odds == 1.25
    assert hd.platform_name == "1X"


def test_parse_bet9ja_skips_unknown():
    markets = parse_markets(BET9JA_EVENT_RESPONSE, platform="bet9ja")
    assert len(markets) == 4


def test_parse_bet9ja_empty_odds():
    response = {"R": "D", "D": {"O": {}}}
    markets = parse_markets(response, platform="bet9ja")
    assert len(markets) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_parser_bet9ja.py -v`
Expected: FAIL (parse_markets returns empty for bet9ja)

- [ ] **Step 3: Replace `_parse_bet9ja` stub in `src/bookieskit/markets/parser.py`**

Replace the `_parse_bet9ja` function with:

```python
def _parse_bet9ja(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse Bet9ja event detail response."""
    results: list[NormalizedMarket] = []
    data = response.get("D", {})
    odds_dict = data.get("O", {})

    if not odds_dict:
        return []

    # Group odds keys by market key
    # Format: S_{MARKET}_{OUTCOME} or S_{MARKET}@{LINE}_{OUTCOME}
    simple_groups: dict[str, list[tuple[str, float]]] = {}
    parameterized_groups: dict[str, dict[float, list[tuple[str, float]]]] = {}

    for key, value in odds_dict.items():
        if not key.startswith("S_"):
            continue

        odds = float(value)
        parsed = _parse_bet9ja_key(key)
        if parsed is None:
            continue

        market_key, line, outcome_suffix = parsed
        mapping = registry.get_by_platform_id("bet9ja", market_key)
        if mapping is None:
            continue

        if mapping.parameterized and line is not None:
            if market_key not in parameterized_groups:
                parameterized_groups[market_key] = {}
            if line not in parameterized_groups[market_key]:
                parameterized_groups[market_key][line] = []
            parameterized_groups[market_key][line].append(
                (outcome_suffix, odds)
            )
        else:
            if market_key not in simple_groups:
                simple_groups[market_key] = []
            simple_groups[market_key].append((outcome_suffix, odds))

    # Build simple markets
    for market_key, outcomes_data in simple_groups.items():
        mapping = registry.get_by_platform_id("bet9ja", market_key)
        if mapping:
            outcomes = _build_bet9ja_outcomes(outcomes_data, mapping)
            if outcomes:
                results.append(
                    NormalizedMarket(
                        canonical_id=mapping.canonical_id,
                        name=mapping.name,
                        outcomes=outcomes,
                        lines=None,
                    )
                )

    # Build parameterized markets
    for market_key, lines_data in parameterized_groups.items():
        mapping = registry.get_by_platform_id("bet9ja", market_key)
        if mapping:
            lines: dict[float, list[Outcome]] = {}
            for line, outcomes_data in lines_data.items():
                line_outcomes = _build_bet9ja_outcomes(
                    outcomes_data, mapping
                )
                if line_outcomes:
                    lines[line] = line_outcomes
            if lines:
                results.append(
                    NormalizedMarket(
                        canonical_id=mapping.canonical_id,
                        name=mapping.name,
                        outcomes=[],
                        lines=lines,
                    )
                )

    return results


def _parse_bet9ja_key(
    key: str,
) -> tuple[str, float | None, str] | None:
    """Parse a Bet9ja odds key into (market_key, line, outcome_suffix).

    Examples:
        "S_1X2_1" -> ("S_1X2", None, "1")
        "S_OU@2.5_O" -> ("S_OU", 2.5, "O")
        "S_DC_1X" -> ("S_DC", None, "1X")
    """
    # Remove "S_" prefix for parsing
    without_prefix = key[2:]

    # Check for line (@ separator)
    if "@" in without_prefix:
        # Format: MARKET@LINE_OUTCOME
        at_idx = without_prefix.index("@")
        market_part = without_prefix[:at_idx]
        rest = without_prefix[at_idx + 1:]
        # Find last underscore for outcome
        last_us = rest.rfind("_")
        if last_us == -1:
            return None
        try:
            line = float(rest[:last_us])
        except ValueError:
            return None
        outcome = rest[last_us + 1:]
        return (f"S_{market_part}", line, outcome)
    else:
        # Format: MARKET_OUTCOME (find the split point)
        # Market keys: 1X2, OU, GGNG, DC, etc.
        # Try splitting at last underscore
        last_us = without_prefix.rfind("_")
        if last_us == -1:
            return None
        market_part = without_prefix[:last_us]
        outcome = without_prefix[last_us + 1:]
        return (f"S_{market_part}", None, outcome)


def _build_bet9ja_outcomes(
    outcomes_data: list[tuple[str, float]],
    mapping: MarketMapping,
) -> list[Outcome]:
    """Build Outcome list from Bet9ja suffix/odds pairs."""
    outcomes: list[Outcome] = []
    for suffix, odds in outcomes_data:
        canonical = _resolve_outcome_bet9ja(suffix, mapping)
        if canonical:
            outcomes.append(
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=suffix,
                )
            )
    return outcomes


def _resolve_outcome_bet9ja(
    suffix: str, mapping: MarketMapping
) -> str | None:
    """Find canonical outcome name from Bet9ja key suffix."""
    for om in mapping.outcomes.values():
        if om.bet9ja == suffix:
            return om.canonical_name
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_parser_bet9ja.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Run all parser tests together**

Run: `.venv/Scripts/python -m pytest tests/test_parser_betpawa.py tests/test_parser_sportybet.py tests/test_parser_bet9ja.py -v`
Expected: All 17 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_parser_bet9ja.py
git commit -m "feat: add Bet9ja market parser with flat-key parsing"
```

---

## Task 7: SportRadar ID Extractor

**Files:**
- Create: `src/bookieskit/matching/__init__.py`
- Create: `src/bookieskit/matching/extractor.py`
- Create: `tests/test_extractor.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_extractor.py`:

```python
from bookieskit.matching.extractor import extract_sportradar_id


def test_extract_from_betpawa():
    response = {
        "id": "32299257",
        "widgets": [
            {"type": "OTHER", "value": "something"},
            {"type": "SPORTRADAR", "value": "sr:match:61300947"},
        ],
    }
    sr_id = extract_sportradar_id(response, platform="betpawa")
    assert sr_id == "61300947"


def test_extract_from_betpawa_no_widget():
    response = {"id": "32299257", "widgets": []}
    sr_id = extract_sportradar_id(response, platform="betpawa")
    assert sr_id is None


def test_extract_from_betpawa_no_widgets_key():
    response = {"id": "32299257"}
    sr_id = extract_sportradar_id(response, platform="betpawa")
    assert sr_id is None


def test_extract_from_sportybet():
    response = {
        "bizCode": 10000,
        "data": {"eventId": "sr:match:61300947", "markets": []},
    }
    sr_id = extract_sportradar_id(response, platform="sportybet")
    assert sr_id == "61300947"


def test_extract_from_sportybet_no_prefix():
    response = {
        "bizCode": 10000,
        "data": {"eventId": "61300947", "markets": []},
    }
    sr_id = extract_sportradar_id(response, platform="sportybet")
    assert sr_id == "61300947"


def test_extract_from_sportybet_no_event_id():
    response = {"bizCode": 10000, "data": {"markets": []}}
    sr_id = extract_sportradar_id(response, platform="sportybet")
    assert sr_id is None


def test_extract_from_bet9ja():
    response = {
        "R": "D",
        "D": {"EXTID": "sr:match:61300947", "O": {}},
    }
    sr_id = extract_sportradar_id(response, platform="bet9ja")
    assert sr_id == "61300947"


def test_extract_from_bet9ja_numeric_extid():
    response = {"R": "D", "D": {"EXTID": "61300947", "O": {}}}
    sr_id = extract_sportradar_id(response, platform="bet9ja")
    assert sr_id == "61300947"


def test_extract_from_bet9ja_no_extid():
    response = {"R": "D", "D": {"O": {}}}
    sr_id = extract_sportradar_id(response, platform="bet9ja")
    assert sr_id is None


def test_extract_unknown_platform():
    sr_id = extract_sportradar_id({}, platform="unknown")
    assert sr_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_extractor.py -v`
Expected: FAIL (cannot import)

- [ ] **Step 3: Write implementation**

Create `src/bookieskit/matching/__init__.py`:

```python
"""Event matching via SportRadar IDs."""
```

Create `src/bookieskit/matching/extractor.py`:

```python
"""SportRadar ID extraction from platform-specific responses."""


def extract_sportradar_id(
    response: dict, platform: str
) -> str | None:
    """Extract SportRadar ID from a raw event detail response.

    Args:
        response: Raw JSON from get_event_detail()
        platform: "betpawa", "sportybet", or "bet9ja"

    Returns:
        SportRadar ID as numeric string (no prefix), or None if not found.
    """
    extractors = {
        "betpawa": _extract_betpawa,
        "sportybet": _extract_sportybet,
        "bet9ja": _extract_bet9ja,
    }
    extractor = extractors.get(platform)
    if extractor is None:
        return None
    return extractor(response)


def _strip_sr_prefix(value: str) -> str:
    """Strip 'sr:match:' prefix if present."""
    if value.startswith("sr:match:"):
        return value[len("sr:match:"):]
    return value


def _extract_betpawa(response: dict) -> str | None:
    """Extract from BetPawa widgets array."""
    widgets = response.get("widgets", [])
    for widget in widgets:
        if widget.get("type") == "SPORTRADAR":
            value = widget.get("value", "")
            if value:
                return _strip_sr_prefix(value)
    return None


def _extract_sportybet(response: dict) -> str | None:
    """Extract from SportyBet data.eventId field."""
    data = response.get("data", {})
    event_id = data.get("eventId")
    if event_id:
        return _strip_sr_prefix(str(event_id))
    return None


def _extract_bet9ja(response: dict) -> str | None:
    """Extract from Bet9ja D.EXTID field."""
    data = response.get("D", {})
    ext_id = data.get("EXTID")
    if ext_id:
        return _strip_sr_prefix(str(ext_id))
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_extractor.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/matching/ tests/test_extractor.py
git commit -m "feat: add SportRadar ID extraction for all platforms"
```

---

## Task 8: Event Matcher

**Files:**
- Create: `src/bookieskit/matching/matcher.py`
- Create: `tests/test_matcher.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_matcher.py`:

```python
from bookieskit.matching.matcher import MatchedEvent, match_events


def test_match_events_two_platforms():
    bp_events = [
        {
            "id": "111",
            "widgets": [
                {"type": "SPORTRADAR", "value": "sr:match:100"}
            ],
        },
        {
            "id": "222",
            "widgets": [
                {"type": "SPORTRADAR", "value": "sr:match:200"}
            ],
        },
    ]
    sb_events = [
        {"bizCode": 10000, "data": {"eventId": "sr:match:100"}},
        {"bizCode": 10000, "data": {"eventId": "sr:match:300"}},
    ]

    matched = match_events(("betpawa", bp_events), ("sportybet", sb_events))

    assert len(matched) == 3
    # Find the one that matches both
    both = next(m for m in matched if m.betpawa and m.sportybet)
    assert both.sportradar_id == "100"


def test_match_events_three_platforms():
    bp = [
        {
            "id": "1",
            "widgets": [
                {"type": "SPORTRADAR", "value": "sr:match:999"}
            ],
        }
    ]
    sb = [{"bizCode": 10000, "data": {"eventId": "sr:match:999"}}]
    b9 = [{"R": "D", "D": {"EXTID": "999", "O": {}}}]

    matched = match_events(
        ("betpawa", bp), ("sportybet", sb), ("bet9ja", b9)
    )

    assert len(matched) == 1
    assert matched[0].sportradar_id == "999"
    assert matched[0].betpawa is not None
    assert matched[0].sportybet is not None
    assert matched[0].bet9ja is not None


def test_match_events_no_overlap():
    bp = [
        {
            "id": "1",
            "widgets": [
                {"type": "SPORTRADAR", "value": "sr:match:100"}
            ],
        }
    ]
    sb = [{"bizCode": 10000, "data": {"eventId": "sr:match:200"}}]

    matched = match_events(("betpawa", bp), ("sportybet", sb))

    assert len(matched) == 2
    bp_only = next(m for m in matched if m.sportradar_id == "100")
    assert bp_only.betpawa is not None
    assert bp_only.sportybet is None


def test_match_events_empty_input():
    matched = match_events(("betpawa", []), ("sportybet", []))
    assert len(matched) == 0


def test_match_events_skips_events_without_sr_id():
    bp = [{"id": "1", "widgets": []}]  # No SR ID
    sb = [{"bizCode": 10000, "data": {"eventId": "sr:match:100"}}]

    matched = match_events(("betpawa", bp), ("sportybet", sb))

    assert len(matched) == 1
    assert matched[0].sportradar_id == "100"
    assert matched[0].betpawa is None
    assert matched[0].sportybet is not None


def test_matched_event_dataclass():
    me = MatchedEvent(sportradar_id="123")
    assert me.betpawa is None
    assert me.sportybet is None
    assert me.bet9ja is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_matcher.py -v`
Expected: FAIL (cannot import)

- [ ] **Step 3: Write implementation**

Create `src/bookieskit/matching/matcher.py`:

```python
"""Event matching across platforms via SportRadar IDs."""

from dataclasses import dataclass, field

from bookieskit.matching.extractor import extract_sportradar_id


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
    # Build map: sportradar_id -> {platform: event_data}
    groups: dict[str, dict[str, dict]] = {}

    for platform, events in event_lists:
        for event in events:
            sr_id = extract_sportradar_id(event, platform=platform)
            if sr_id is None:
                continue
            if sr_id not in groups:
                groups[sr_id] = {}
            groups[sr_id][platform] = event

    # Convert to MatchedEvent list
    results: list[MatchedEvent] = []
    for sr_id, platforms in groups.items():
        results.append(
            MatchedEvent(
                sportradar_id=sr_id,
                betpawa=platforms.get("betpawa"),
                sportybet=platforms.get("sportybet"),
                bet9ja=platforms.get("bet9ja"),
            )
        )

    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_matcher.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/matching/matcher.py tests/test_matcher.py
git commit -m "feat: add event matcher for cross-platform matching"
```

---

## Task 9: Client Convenience Methods & PLATFORM_KEY

**Files:**
- Modify: `src/bookieskit/base.py`
- Modify: `src/bookieskit/bookmakers/betpawa.py`
- Modify: `src/bookieskit/bookmakers/sportybet.py`
- Modify: `src/bookieskit/bookmakers/bet9ja.py`
- Create: `tests/test_convenience.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_convenience.py`:

```python
import pytest
import respx

from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.sportybet import SportyBet
from bookieskit.bookmakers.bet9ja import Bet9ja


@pytest.mark.asyncio
@respx.mock
async def test_betpawa_get_markets():
    respx.get(
        "https://www.betpawa.ng/api/sportsbook/v3/events/123"
    ).respond(
        json={
            "id": "123",
            "markets": [
                {
                    "id": "3743",
                    "name": "1X2",
                    "row": [
                        {
                            "prices": [
                                {"name": "1", "odds": 1.95},
                                {"name": "X", "odds": 3.50},
                                {"name": "2", "odds": 2.10},
                            ]
                        }
                    ],
                }
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        markets = await client.get_markets(event_id="123")
    assert len(markets) == 1
    assert markets[0].canonical_id == "1x2_ft"


@pytest.mark.asyncio
@respx.mock
async def test_betpawa_get_sportradar_id():
    respx.get(
        "https://www.betpawa.ng/api/sportsbook/v3/events/123"
    ).respond(
        json={
            "id": "123",
            "widgets": [
                {"type": "SPORTRADAR", "value": "sr:match:999"}
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        sr_id = await client.get_sportradar_id(event_id="123")
    assert sr_id == "999"


@pytest.mark.asyncio
@respx.mock
async def test_sportybet_get_markets():
    respx.get(
        "https://www.sportybet.com/api/ng/factsCenter/event"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "eventId": "sr:match:100",
                "markets": [
                    {
                        "id": "29",
                        "desc": "BTTS",
                        "specifier": None,
                        "outcomes": [
                            {"id": "1", "desc": "Yes", "odds": "1.75"},
                            {"id": "2", "desc": "No", "odds": "2.05"},
                        ],
                    }
                ],
            },
        }
    )
    async with SportyBet(country="ng") as client:
        markets = await client.get_markets(event_id="sr:match:100")
    assert len(markets) == 1
    assert markets[0].canonical_id == "btts_ft"


@pytest.mark.asyncio
@respx.mock
async def test_bet9ja_get_sportradar_id():
    respx.get(
        "https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetEvent"
    ).respond(
        json={"R": "D", "D": {"EXTID": "61300947", "O": {}}}
    )
    async with Bet9ja(country="ng") as client:
        sr_id = await client.get_sportradar_id(event_id="707096003")
    assert sr_id == "61300947"


@respx.mock
def test_sync_get_markets():
    respx.get(
        "https://www.betpawa.ng/api/sportsbook/v3/events/123"
    ).respond(
        json={
            "id": "123",
            "markets": [
                {
                    "id": "3795",
                    "name": "BTTS",
                    "row": [
                        {
                            "prices": [
                                {"name": "Yes", "odds": 1.75},
                                {"name": "No", "odds": 2.05},
                            ]
                        }
                    ],
                }
            ],
        }
    )
    with BetPawa(country="ng") as client:
        markets = client.get_markets(event_id="123")
    assert len(markets) == 1
    assert markets[0].canonical_id == "btts_ft"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_convenience.py -v`
Expected: FAIL (no get_markets method)

- [ ] **Step 3: Add PLATFORM_KEY to bookmaker subclasses**

Add `PLATFORM_KEY = "betpawa"` to `src/bookieskit/bookmakers/betpawa.py` class body (after `NAME = "BetPawa"`).

Add `PLATFORM_KEY = "sportybet"` to `src/bookieskit/bookmakers/sportybet.py` class body (after `NAME = "SportyBet"`).

Add `PLATFORM_KEY = "bet9ja"` to `src/bookieskit/bookmakers/bet9ja.py` class body (after `NAME = "Bet9ja"`).

- [ ] **Step 4: Add convenience methods to BaseBookmaker**

Add to `src/bookieskit/base.py`, in the `BaseBookmaker` class (after the `_request` method, before `class _SyncProxy`):

```python
    PLATFORM_KEY: str = ""

    async def get_markets(
        self,
        event_id: str,
        registry=None,
    ):
        """Fetch event detail and return normalized markets.

        Args:
            event_id: Platform-specific event ID
            registry: MarketRegistry (default: built-in 4 markets)

        Returns:
            List of NormalizedMarket for recognized markets.
        """
        from bookieskit.markets.parser import parse_markets

        raw = await self.get_event_detail(event_id=event_id)
        return parse_markets(
            raw, platform=self.PLATFORM_KEY, registry=registry
        )

    async def get_sportradar_id(self, event_id: str) -> str | None:
        """Fetch event detail and extract SportRadar ID.

        Args:
            event_id: Platform-specific event ID

        Returns:
            SportRadar ID string, or None if not available.
        """
        from bookieskit.matching.extractor import extract_sportradar_id

        raw = await self.get_event_detail(event_id=event_id)
        return extract_sportradar_id(
            raw, platform=self.PLATFORM_KEY
        )
```

Note: Imports are inside methods to avoid circular imports (base.py is imported by bookmaker modules, which markets/matching modules may reference).

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_convenience.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/base.py src/bookieskit/bookmakers/betpawa.py src/bookieskit/bookmakers/sportybet.py src/bookieskit/bookmakers/bet9ja.py tests/test_convenience.py
git commit -m "feat: add get_markets() and get_sportradar_id() convenience methods"
```

---

## Task 10: Public Exports

**Files:**
- Modify: `src/bookieskit/markets/__init__.py`
- Modify: `src/bookieskit/matching/__init__.py`
- Modify: `src/bookieskit/__init__.py`

- [ ] **Step 1: Update markets/__init__.py**

```python
"""Market mapping and normalization."""

from bookieskit.markets.parser import parse_markets
from bookieskit.markets.registry import MarketRegistry
from bookieskit.markets.types import (
    MarketMapping,
    NormalizedMarket,
    Outcome,
    OutcomeMapping,
)

__all__ = [
    "MarketRegistry",
    "parse_markets",
    "NormalizedMarket",
    "Outcome",
    "MarketMapping",
    "OutcomeMapping",
]
```

- [ ] **Step 2: Update matching/__init__.py**

```python
"""Event matching via SportRadar IDs."""

from bookieskit.matching.extractor import extract_sportradar_id
from bookieskit.matching.matcher import MatchedEvent, match_events

__all__ = [
    "extract_sportradar_id",
    "match_events",
    "MatchedEvent",
]
```

- [ ] **Step 3: Update package __init__.py**

Add to `src/bookieskit/__init__.py` (keep existing exports, add new ones):

```python
"""Bookieskit — HTTP clients for betting data scraping."""

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.sportybet import SportyBet

__all__ = ["BetPawa", "SportyBet", "Bet9ja"]
__version__ = "0.2.0"
```

- [ ] **Step 4: Verify imports work**

```bash
.venv/Scripts/python -c "from bookieskit.markets import MarketRegistry, parse_markets, NormalizedMarket, Outcome; print('markets OK')"
.venv/Scripts/python -c "from bookieskit.matching import extract_sportradar_id, match_events, MatchedEvent; print('matching OK')"
```

Expected: Both print OK

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/__init__.py src/bookieskit/matching/__init__.py src/bookieskit/__init__.py
git commit -m "feat: update public exports and bump to v0.2.0"
```

---

## Task 11: Documentation

**Files:**
- Create: `docs/markets.md`
- Create: `docs/matching.md`

- [ ] **Step 1: Create docs/markets.md**

Create `docs/markets.md`:

```markdown
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
```

- [ ] **Step 2: Create docs/matching.md**

Create `docs/matching.md`:

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add docs/markets.md docs/matching.md
git commit -m "docs: add market mapping and event matching documentation"
```

---

## Task 12: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

```bash
cd c:/Users/loren/Desktop/betpawa/comparison/mvp1/bookieskit
.venv/Scripts/python -m pytest -v
```

Expected: All tests PASS (v1 tests + new v2 tests)

- [ ] **Step 2: Run linter**

```bash
.venv/Scripts/python -m ruff check src/ tests/
```

Expected: No errors (fix any that appear)

- [ ] **Step 3: Verify all imports work**

```bash
.venv/Scripts/python -c "
from bookieskit import BetPawa, SportyBet, Bet9ja
from bookieskit.markets import MarketRegistry, parse_markets, NormalizedMarket, Outcome, OutcomeMapping
from bookieskit.matching import extract_sportradar_id, match_events, MatchedEvent
print('All imports OK')
print(f'Version: {__import__(\"bookieskit\").__version__}')
"
```

Expected: `All imports OK` and `Version: 0.2.0`

- [ ] **Step 4: Final commit (if any linting fixes)**

```bash
git add -A
git commit -m "chore: linting fixes and final cleanup"
```
