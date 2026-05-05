# Betway Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Betway as the 4th bookmaker in bookieskit, including client, market parser, SR ID extractor, and outcome mappings.

**Architecture:** New `Betway` subclass of `BaseBookmaker` with dual-domain support (config domain for sports, feeds domain for data). Add `betway` field to `OutcomeMapping` and `betway_id` to `MarketMapping`. Update registry, parser, extractor, and exports.

**Tech Stack:** Python 3.11+, httpx, existing bookieskit patterns

---

## File Structure

```
Modified:
  src/bookieskit/markets/types.py         — add betway field to OutcomeMapping, betway_id to MarketMapping
  src/bookieskit/markets/builtin_mappings.py — add betway values to all 4 mappings
  src/bookieskit/markets/registry.py      — add betway index
  src/bookieskit/markets/parser.py        — add _parse_betway
  src/bookieskit/matching/extractor.py    — add _extract_betway
  src/bookieskit/bookmakers/__init__.py   — add Betway export
  src/bookieskit/__init__.py              — add Betway export

Created:
  src/bookieskit/bookmakers/betway.py     — Betway client class
  tests/test_betway.py                    — client tests
  tests/test_parser_betway.py             — parser tests
  docs/betway.md                          — API documentation
```

---

## Task 1: Add `betway` field to types and update mappings

**Files:**
- Modify: `src/bookieskit/markets/types.py`
- Modify: `src/bookieskit/markets/builtin_mappings.py`
- Modify: `src/bookieskit/markets/registry.py`

- [ ] **Step 1: Update OutcomeMapping in types.py**

Add `betway: str = ""` field after `bet9ja`:

```python
@dataclass(frozen=True)
class OutcomeMapping:
    """Maps one outcome across platforms."""

    canonical_name: str
    betpawa: str
    sportybet: str
    bet9ja: str
    betway: str = ""
```

Add `betway_id: str | None` field to `MarketMapping` after `bet9ja_key`:

```python
@dataclass(frozen=True)
class MarketMapping:
    """Defines how one market maps across platforms."""

    canonical_id: str
    name: str
    betpawa_id: str | None
    sportybet_id: str | None
    bet9ja_key: str | None
    betway_id: str | None = None
    outcomes: dict[str, OutcomeMapping]
    parameterized: bool = False
```

Note: `betway_id` must come before `outcomes` because `outcomes` has no default and `betway_id` has `None` default. Actually, since `outcomes` has no default and comes after fields with defaults, we need to reorder. Put `betway_id` right after `bet9ja_key` (before `outcomes`):

```python
@dataclass(frozen=True)
class MarketMapping:
    """Defines how one market maps across platforms."""

    canonical_id: str
    name: str
    betpawa_id: str | None
    sportybet_id: str | None
    bet9ja_key: str | None
    betway_id: str | None
    outcomes: dict[str, OutcomeMapping]
    parameterized: bool = False
```

- [ ] **Step 2: Update builtin_mappings.py**

Add `betway` to all OutcomeMappings and `betway_id` to all MarketMappings:

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
        betway_id="[Win/Draw/Win]",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
                betway="__HOME__",
            ),
            "draw": OutcomeMapping(
                canonical_name="draw",
                betpawa="X",
                sportybet="Draw",
                bet9ja="X",
                betway="Draw",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__AWAY__",
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
        betway_id="[Total Goals]",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="O",
                betway="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="U",
                betway="Under",
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
        betway_id="[Both Teams To Score]",
        outcomes={
            "yes": OutcomeMapping(
                canonical_name="yes",
                betpawa="Yes",
                sportybet="Yes",
                bet9ja="Y",
                betway="Yes",
            ),
            "no": OutcomeMapping(
                canonical_name="no",
                betpawa="No",
                sportybet="No",
                bet9ja="N",
                betway="No",
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
        betway_id="[Double Chance]",
        outcomes={
            "home_draw": OutcomeMapping(
                canonical_name="home_draw",
                betpawa="1X",
                sportybet="Home or Draw",
                bet9ja="1X",
                betway="__POS_1__",
            ),
            "draw_away": OutcomeMapping(
                canonical_name="draw_away",
                betpawa="X2",
                sportybet="Draw or Away",
                bet9ja="X2",
                betway="__POS_2__",
            ),
            "home_away": OutcomeMapping(
                canonical_name="home_away",
                betpawa="12",
                sportybet="Home or Away",
                bet9ja="12",
                betway="__POS_3__",
            ),
        },
        parameterized=False,
    ),
]
```

Note: `__HOME__`, `__AWAY__`, `__POS_1__`, `__POS_2__`, `__POS_3__` are sentinel values. The Betway parser uses position-based matching for 1X2 and DC (outcomes use team names, not fixed strings). The parser will match by index for these sentinels.

- [ ] **Step 3: Update registry.py**

Add `_by_betway` index and support for `betway_id` and `betway` platform in `get_by_platform_id`:

```python
class MarketRegistry:
    def __init__(self, load_builtins: bool = True):
        self._by_canonical: dict[str, MarketMapping] = {}
        self._by_betpawa: dict[str, MarketMapping] = {}
        self._by_sportybet: dict[str, MarketMapping] = {}
        self._by_bet9ja: dict[str, MarketMapping] = {}
        self._by_betway: dict[str, MarketMapping] = {}

        if load_builtins:
            for mapping in BUILTIN_MAPPINGS:
                self._register(mapping)

    def _register(self, mapping: MarketMapping) -> None:
        self._by_canonical[mapping.canonical_id] = mapping
        if mapping.betpawa_id:
            self._by_betpawa[mapping.betpawa_id] = mapping
        if mapping.sportybet_id:
            self._by_sportybet[mapping.sportybet_id] = mapping
        if mapping.bet9ja_key:
            self._by_bet9ja[mapping.bet9ja_key] = mapping
        if mapping.betway_id:
            self._by_betway[mapping.betway_id] = mapping

    def add(
        self,
        canonical_id: str,
        name: str,
        betpawa_id: str | None = None,
        sportybet_id: str | None = None,
        bet9ja_key: str | None = None,
        betway_id: str | None = None,
        outcomes: dict[str, OutcomeMapping] | None = None,
        parameterized: bool = False,
    ) -> None:
        mapping = MarketMapping(
            canonical_id=canonical_id,
            name=name,
            betpawa_id=betpawa_id,
            sportybet_id=sportybet_id,
            bet9ja_key=bet9ja_key,
            betway_id=betway_id,
            outcomes=outcomes or {},
            parameterized=parameterized,
        )
        self._register(mapping)

    def get_by_platform_id(
        self, platform: str, platform_id: str
    ) -> MarketMapping | None:
        index = {
            "betpawa": self._by_betpawa,
            "sportybet": self._by_sportybet,
            "bet9ja": self._by_bet9ja,
            "betway": self._by_betway,
        }.get(platform, {})
        return index.get(platform_id)
```

- [ ] **Step 4: Run existing tests to verify nothing broke**

Run: `cd c:/Users/loren/Desktop/betpawa/comparison/mvp1/bookieskit && .venv/Scripts/python -m pytest -v`
Expected: All 99 tests PASS (the new `betway` field has a default value so existing code works)

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/types.py src/bookieskit/markets/builtin_mappings.py src/bookieskit/markets/registry.py
git commit -m "feat: add betway field to OutcomeMapping, MarketMapping, and registry"
```

---

## Task 2: Betway Client

**Files:**
- Create: `src/bookieskit/bookmakers/betway.py`
- Create: `tests/test_betway.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_betway.py`:

```python
import pytest
import respx

from bookieskit.bookmakers.betway import Betway


def test_betway_country_ng_resolves_domain():
    client = Betway(country="ng")
    assert client.base_url == "https://feeds-roa2.betwayafrica.com"


def test_betway_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        Betway(country="xx")


def test_betway_country_code_mapping():
    client = Betway(country="ng")
    assert client._country_code == "NG"
    client_gh = Betway(country="gh")
    assert client_gh._country_code == "GH"


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get(
        "https://config.betwayafrica.com/cron/sports/NG/en-US"
    ).respond(
        json={
            "sports": [
                {
                    "sportId": "soccer",
                    "name": "Soccer",
                    "liveInPlayCount": 5,
                    "hasUpcomingEvents": True,
                }
            ]
        }
    )
    async with Betway(country="ng") as client:
        result = await client.get_sports()
    assert result["sports"][0]["name"] == "Soccer"


@pytest.mark.asyncio
@respx.mock
async def test_get_countries():
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/Feeds/RegionsAndLeagues/soccer"
    ).respond(
        json={
            "regions": [
                {
                    "regionId": "england",
                    "name": "England",
                    "leagues": [
                        {
                            "leagueId": "premier-league",
                            "name": "Premier League",
                        }
                    ],
                }
            ]
        }
    )
    async with Betway(country="ng") as client:
        result = await client.get_countries(sport_id="soccer")
    assert result["regions"][0]["name"] == "England"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/BetBook/Highlights/"
    ).respond(
        json={
            "events": [
                {
                    "eventId": 69339436,
                    "name": "Arsenal FC vs. Atletico Madrid",
                    "homeTeam": "Arsenal FC",
                    "awayTeam": "Atletico Madrid",
                }
            ],
            "markets": [],
            "outcomes": [],
            "prices": [],
        }
    )
    async with Betway(country="ng") as client:
        result = await client.get_events(
            league_id="international-clubs_uefa-champions-league"
        )
    assert result["events"][0]["homeTeam"] == "Arsenal FC"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail():
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v3/Feeds/Events/EventAndGameState"
    ).respond(
        json={
            "sportEvent": {
                "eventId": 69339436,
                "name": "Arsenal FC vs. Atletico Madrid",
                "homeTeam": "Arsenal FC",
                "awayTeam": "Atletico Madrid",
            }
        }
    )
    async with Betway(country="ng") as client:
        result = await client.get_event_detail(event_id="69339436")
    assert result["sportEvent"]["eventId"] == 69339436


@pytest.mark.asyncio
@respx.mock
async def test_get_event_markets():
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/MarketGroupings/MarketGroupNamesAndMarketsForEvent"
    ).respond(
        json={
            "marketGroupNames": ["Main"],
            "marketsInGroup": [
                {
                    "marketId": "693394361",
                    "name": "[Win/Draw/Win]",
                    "handicap": 0,
                }
            ],
            "outcomes": [
                {
                    "outcomeId": "6933943611",
                    "marketId": "693394361",
                    "name": "Arsenal FC",
                }
            ],
            "prices": [
                {
                    "outcomeId": "6933943611",
                    "priceDecimal": 1.63,
                }
            ],
        }
    )
    async with Betway(country="ng") as client:
        result = await client.get_event_markets(event_id="69339436")
    assert len(result["marketsInGroup"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_betway.py -v`
Expected: FAIL (cannot import Betway)

- [ ] **Step 3: Write implementation**

Create `src/bookieskit/bookmakers/betway.py`:

```python
"""Betway client — supports ng, gh, ke, tz, ug, zm."""

from typing import Any

import httpx

from bookieskit.base import BaseBookmaker
from bookieskit.config import DEFAULT_TIMEOUT

# Country code mapping (lowercase -> API format)
_COUNTRY_CODES = {
    "ng": "NG",
    "gh": "GH",
    "ke": "KE",
    "tz": "TZ",
    "ug": "UG",
    "zm": "ZM",
}

# Config domain (sports list only)
_CONFIG_BASE_URL = "https://config.betwayafrica.com"


class Betway(BaseBookmaker):
    """HTTP client for Betway sportsbook API.

    Betway uses two API domains:
    - config.betwayafrica.com for sports configuration
    - feeds-roa2.betwayafrica.com for data (events, markets, odds)

    The country is passed via countryCode query parameter.
    Event IDs are SportRadar IDs natively.

    Args:
        country: Country code (ng, gh, ke, tz, ug, zm)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 50)
        request_delay: Delay between requests in seconds (default: 0)
    """

    DOMAINS = {
        "ng": "https://feeds-roa2.betwayafrica.com",
        "gh": "https://feeds-roa2.betwayafrica.com",
        "ke": "https://feeds-roa2.betwayafrica.com",
        "tz": "https://feeds-roa2.betwayafrica.com",
        "ug": "https://feeds-roa2.betwayafrica.com",
        "zm": "https://feeds-roa2.betwayafrica.com",
    }
    DEFAULT_HEADERS = {
        "accept": "application/json",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/144.0.0.0 Safari/537.36"
        ),
    }
    MAX_CONCURRENT = 50
    REQUEST_DELAY = 0.0
    NAME = "Betway"
    PLATFORM_KEY = "betway"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._country_code = _COUNTRY_CODES.get(
            self._country, self._country.upper()
        )

    async def get_sports(self) -> dict[str, Any]:
        """Get all available sports.

        Uses the config domain (separate from data domain).

        Returns:
            Raw JSON with sports[] array.
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT)
        ) as config_client:
            url = (
                f"{_CONFIG_BASE_URL}/cron/sports"
                f"/{self._country_code}/en-US"
            )
            response = await config_client.get(
                url, headers=self._build_headers()
            )
            response.raise_for_status()
            return response.json()

    async def get_countries(
        self, sport_id: str = "soccer"
    ) -> dict[str, Any]:
        """Get regions/countries and leagues for a sport.

        Args:
            sport_id: Sport slug (e.g., "soccer", "tennis")

        Returns:
            Raw JSON with regions[].leagues[] structure.
        """
        return await self._request(
            "GET",
            f"/br/_apis/sport/v1/Feeds/RegionsAndLeagues/{sport_id}",
            params={"countryCode": self._country_code},
        )

    async def get_tournaments(
        self, sport_id: str = "soccer"
    ) -> dict[str, Any]:
        """Get tournaments (same as get_countries — leagues are tournaments).

        Args:
            sport_id: Sport slug (e.g., "soccer")

        Returns:
            Raw JSON with regions[].leagues[] structure.
        """
        return await self.get_countries(sport_id=sport_id)

    async def get_events(
        self,
        league_id: str | None = None,
        sport_id: str = "soccer",
        skip: int = 0,
        take: int = 50,
        market_types: str = "[Win/Draw/Win]",
    ) -> dict[str, Any]:
        """Get events for a league.

        Args:
            league_id: League ID slug (e.g., "international-clubs_uefa-champions-league").
                       Format: "{regionId}_{leagueId}". None for all.
            sport_id: Sport slug (default: "soccer")
            skip: Pagination offset (default: 0)
            take: Page size (default: 50)
            market_types: Market types to include (default: "[Win/Draw/Win]")

        Returns:
            Raw JSON with events[], markets[], outcomes[], prices[].
        """
        params: dict[str, Any] = {
            "countryCode": self._country_code,
            "sportId": sport_id,
            "Skip": str(skip),
            "Take": str(take),
            "cultureCode": "en-US",
            "isEsport": "false",
            "boostedOnly": "false",
            "marketTypes": market_types,
        }
        if league_id:
            params["leagueIds"] = league_id
        return await self._request(
            "GET",
            "/br/_apis/sport/v1/BetBook/Highlights/",
            params=params,
        )

    async def get_event_detail(
        self, event_id: str
    ) -> dict[str, Any]:
        """Get event detail (basic info + game state).

        Args:
            event_id: Betway event ID (= SportRadar ID)

        Returns:
            Raw JSON with sportEvent object.
        """
        return await self._request(
            "GET",
            "/br/_apis/sport/v3/Feeds/Events/EventAndGameState",
            params={
                "eventId": event_id,
                "countryCode": self._country_code,
            },
        )

    async def get_event_markets(
        self,
        event_id: str,
        skip: int = 0,
        take: int = 100,
    ) -> dict[str, Any]:
        """Get all markets for an event.

        Args:
            event_id: Betway event ID (= SportRadar ID)
            skip: Pagination offset (default: 0)
            take: Page size (default: 100)

        Returns:
            Raw JSON with marketsInGroup[], outcomes[], prices[].
        """
        return await self._request(
            "GET",
            "/br/_apis/sport/v1/MarketGroupings"
            "/MarketGroupNamesAndMarketsForEvent",
            params={
                "eventId": event_id,
                "marketGroupId": " ",
                "countryCode": self._country_code,
                "cultureCode": "en-US",
                "skip": str(skip),
                "take": str(take),
                "isBuildABetOnly": "false",
                "searchQuery": "",
            },
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_betway.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/bookmakers/betway.py tests/test_betway.py
git commit -m "feat: add Betway client with all data levels"
```

---

## Task 3: SportRadar ID Extractor for Betway

**Files:**
- Modify: `src/bookieskit/matching/extractor.py`

- [ ] **Step 1: Add `_extract_betway` and register it**

Add to `extractor.py`:

In the `extract_sportradar_id` function, add `"betway": _extract_betway` to the extractors dict.

Add the extraction function:

```python
def _extract_betway(response: dict) -> str | None:
    """Extract from Betway sportEvent.eventId (IS the SR ID)."""
    sport_event = response.get("sportEvent", {})
    event_id = sport_event.get("eventId")
    if event_id:
        return _strip_sr_prefix(str(event_id))
    return None
```

- [ ] **Step 2: Add test to tests/test_extractor.py**

Append to existing `tests/test_extractor.py`:

```python
def test_extract_from_betway():
    response = {
        "sportEvent": {
            "eventId": 69339436,
            "name": "Arsenal FC vs. Atletico Madrid",
        }
    }
    sr_id = extract_sportradar_id(response, platform="betway")
    assert sr_id == "69339436"


def test_extract_from_betway_no_event():
    response = {"sportEvent": {}}
    sr_id = extract_sportradar_id(response, platform="betway")
    assert sr_id is None
```

- [ ] **Step 3: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_extractor.py -v`
Expected: All 12 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/bookieskit/matching/extractor.py tests/test_extractor.py
git commit -m "feat: add Betway SportRadar ID extractor"
```

---

## Task 4: Betway Market Parser

**Files:**
- Modify: `src/bookieskit/markets/parser.py`
- Create: `tests/test_parser_betway.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_parser_betway.py`:

```python
from bookieskit.markets.parser import parse_markets


BETWAY_MARKETS_RESPONSE = {
    "marketGroupNames": ["Main", "Totals"],
    "marketsInGroup": [
        {
            "marketId": "693394361",
            "name": "[Win/Draw/Win]",
            "displayName": "1X2",
            "handicap": 0,
        },
        {
            "marketId": "6933943610",
            "name": "[Double Chance]",
            "displayName": "Double Chance",
            "handicap": 0,
        },
        {
            "marketId": "69339436btts",
            "name": "[Both Teams To Score]",
            "displayName": "Both Teams To Score",
            "handicap": 0,
        },
        {
            "marketId": "6933943618total=2.5~",
            "name": "Total",
            "displayName": "Total (2.5)",
            "handicap": 2.5,
        },
        {
            "marketId": "6933943618total=3.5~",
            "name": "Total",
            "displayName": "Total (3.5)",
            "handicap": 3.5,
        },
        {
            "marketId": "999unknown",
            "name": "[Unknown Market]",
            "displayName": "Unknown",
            "handicap": 0,
        },
    ],
    "outcomes": [
        {"outcomeId": "o1", "marketId": "693394361", "name": "Arsenal FC"},
        {"outcomeId": "o2", "marketId": "693394361", "name": "Draw"},
        {"outcomeId": "o3", "marketId": "693394361", "name": "Atletico Madrid"},
        {"outcomeId": "o4", "marketId": "6933943610", "name": "Arsenal FC or Draw"},
        {"outcomeId": "o5", "marketId": "6933943610", "name": "Draw or Atletico Madrid"},
        {"outcomeId": "o6", "marketId": "6933943610", "name": "Arsenal FC or Atletico Madrid"},
        {"outcomeId": "o7", "marketId": "69339436btts", "name": "Yes"},
        {"outcomeId": "o8", "marketId": "69339436btts", "name": "No"},
        {"outcomeId": "o9", "marketId": "6933943618total=2.5~", "name": "Over"},
        {"outcomeId": "o10", "marketId": "6933943618total=2.5~", "name": "Under"},
        {"outcomeId": "o11", "marketId": "6933943618total=3.5~", "name": "Over"},
        {"outcomeId": "o12", "marketId": "6933943618total=3.5~", "name": "Under"},
        {"outcomeId": "o99", "marketId": "999unknown", "name": "Opt A"},
    ],
    "prices": [
        {"outcomeId": "o1", "priceDecimal": 1.63},
        {"outcomeId": "o2", "priceDecimal": 4.0},
        {"outcomeId": "o3", "priceDecimal": 4.6},
        {"outcomeId": "o4", "priceDecimal": 1.2},
        {"outcomeId": "o5", "priceDecimal": 1.9},
        {"outcomeId": "o6", "priceDecimal": 1.25},
        {"outcomeId": "o7", "priceDecimal": 1.7},
        {"outcomeId": "o8", "priceDecimal": 2.1},
        {"outcomeId": "o9", "priceDecimal": 1.8},
        {"outcomeId": "o10", "priceDecimal": 2.0},
        {"outcomeId": "o11", "priceDecimal": 2.3},
        {"outcomeId": "o12", "priceDecimal": 1.6},
        {"outcomeId": "o99", "priceDecimal": 3.0},
    ],
}


def test_parse_betway_1x2():
    markets = parse_markets(
        BETWAY_MARKETS_RESPONSE, platform="betway"
    )
    m1x2 = next(m for m in markets if m.canonical_id == "1x2_ft")
    assert m1x2.name == "1X2 - Full Time"
    assert len(m1x2.outcomes) == 3
    assert m1x2.lines is None
    home = next(
        o for o in m1x2.outcomes if o.canonical_name == "home"
    )
    assert home.odds == 1.63


def test_parse_betway_double_chance():
    markets = parse_markets(
        BETWAY_MARKETS_RESPONSE, platform="betway"
    )
    dc = next(
        m for m in markets if m.canonical_id == "double_chance_ft"
    )
    assert len(dc.outcomes) == 3
    hd = next(
        o for o in dc.outcomes if o.canonical_name == "home_draw"
    )
    assert hd.odds == 1.2


def test_parse_betway_btts():
    markets = parse_markets(
        BETWAY_MARKETS_RESPONSE, platform="betway"
    )
    btts = next(
        m for m in markets if m.canonical_id == "btts_ft"
    )
    assert len(btts.outcomes) == 2
    yes = next(
        o for o in btts.outcomes if o.canonical_name == "yes"
    )
    assert yes.odds == 1.7


def test_parse_betway_over_under():
    markets = parse_markets(
        BETWAY_MARKETS_RESPONSE, platform="betway"
    )
    ou = next(
        m for m in markets if m.canonical_id == "over_under_ft"
    )
    assert ou.lines is not None
    assert 2.5 in ou.lines
    assert 3.5 in ou.lines
    over_25 = next(
        o for o in ou.lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds == 1.8


def test_parse_betway_skips_unknown():
    markets = parse_markets(
        BETWAY_MARKETS_RESPONSE, platform="betway"
    )
    assert len(markets) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_parser_betway.py -v`
Expected: FAIL (returns empty for betway)

- [ ] **Step 3: Add `_parse_betway` to parser.py**

Add `"betway": _parse_betway` to the `parsers` dict in `parse_markets`.

Add the parser functions at the end of `parser.py`:

```python
def _parse_betway(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse Betway event markets response.

    Betway returns denormalized data: marketsInGroup[], outcomes[], prices[]
    as separate arrays linked by marketId and outcomeId.
    """
    results: list[NormalizedMarket] = []
    markets_in_group = response.get("marketsInGroup", [])
    all_outcomes = response.get("outcomes", [])
    all_prices = response.get("prices", [])

    # Build price lookup: outcomeId -> priceDecimal
    price_map: dict[str, float] = {}
    for p in all_prices:
        price_map[str(p.get("outcomeId", ""))] = float(
            p.get("priceDecimal", 0)
        )

    # Build outcome lookup: marketId -> list of outcomes
    outcomes_by_market: dict[str, list[dict]] = {}
    for o in all_outcomes:
        mid = str(o.get("marketId", ""))
        if mid not in outcomes_by_market:
            outcomes_by_market[mid] = []
        outcomes_by_market[mid].append(o)

    # Group markets: find parent market name -> collect all variants
    # For parameterized markets (Total Goals), multiple entries share
    # the parent betway_id but have different handicap values
    simple_markets: dict[str, tuple[dict, list[dict]]] = {}
    parameterized_markets: dict[str, list[tuple[dict, list[dict]]]] = {}

    for market in markets_in_group:
        market_name = str(market.get("name", ""))
        market_id = str(market.get("marketId", ""))
        handicap = market.get("handicap", 0)
        market_outcomes = outcomes_by_market.get(market_id, [])

        # Check if this is a known parent market
        mapping = registry.get_by_platform_id("betway", market_name)
        if mapping is not None:
            if mapping.parameterized:
                if mapping.betway_id not in parameterized_markets:
                    parameterized_markets[mapping.betway_id] = []
                parameterized_markets[mapping.betway_id].append(
                    (market, market_outcomes)
                )
            else:
                simple_markets[market_name] = (
                    market,
                    market_outcomes,
                )
            continue

        # Check if this is a parameterized variant (name="Total")
        # by checking if any registered parameterized market
        # has a matching parent
        for mm in registry.list_markets():
            if not mm.parameterized or not mm.betway_id:
                continue
            # "Total" matches "[Total Goals]" parent
            parent_name = mm.betway_id
            if _is_betway_parameterized_variant(
                market_name, parent_name
            ):
                if parent_name not in parameterized_markets:
                    parameterized_markets[parent_name] = []
                parameterized_markets[parent_name].append(
                    (market, market_outcomes)
                )
                break

    # Build simple markets
    for market_name, (market, outcomes_list) in simple_markets.items():
        mapping = registry.get_by_platform_id("betway", market_name)
        if mapping:
            parsed = _build_betway_simple(
                outcomes_list, mapping, price_map
            )
            if parsed:
                results.append(parsed)

    # Build parameterized markets
    for parent_name, entries in parameterized_markets.items():
        mapping = registry.get_by_platform_id("betway", parent_name)
        if mapping:
            parsed = _build_betway_parameterized(
                entries, mapping, price_map
            )
            if parsed:
                results.append(parsed)

    return results


def _is_betway_parameterized_variant(
    market_name: str, parent_name: str
) -> bool:
    """Check if a market name is a variant of a parameterized parent.

    e.g., "Total" is a variant of "[Total Goals]"
    """
    # Strip brackets from parent: "[Total Goals]" -> "Total Goals"
    clean_parent = parent_name.strip("[]")
    # "Total" matches if it's a prefix of "Total Goals"
    return clean_parent.startswith(market_name)


def _build_betway_simple(
    outcomes_list: list[dict],
    mapping: MarketMapping,
    price_map: dict[str, float],
) -> NormalizedMarket | None:
    """Build a simple NormalizedMarket from Betway outcomes."""
    parsed_outcomes: list[Outcome] = []

    for i, outcome_data in enumerate(outcomes_list):
        oid = str(outcome_data.get("outcomeId", ""))
        name = str(outcome_data.get("name", ""))
        odds = price_map.get(oid, 0)

        canonical = _resolve_outcome_betway(
            name, i, mapping
        )
        if canonical:
            parsed_outcomes.append(
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=name,
                )
            )

    if not parsed_outcomes:
        return None

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=parsed_outcomes,
        lines=None,
    )


def _build_betway_parameterized(
    entries: list[tuple[dict, list[dict]]],
    mapping: MarketMapping,
    price_map: dict[str, float],
) -> NormalizedMarket | None:
    """Build a parameterized NormalizedMarket from Betway entries."""
    lines: dict[float, list[Outcome]] = {}

    for market, outcomes_list in entries:
        handicap = market.get("handicap")
        if handicap is None:
            continue
        line = float(handicap)
        line_outcomes: list[Outcome] = []

        for i, outcome_data in enumerate(outcomes_list):
            oid = str(outcome_data.get("outcomeId", ""))
            name = str(outcome_data.get("name", ""))
            odds = price_map.get(oid, 0)

            canonical = _resolve_outcome_betway(
                name, i, mapping
            )
            if canonical:
                line_outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=name,
                    )
                )

        if line_outcomes:
            lines[line] = line_outcomes

    if not lines:
        return None

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=[],
        lines=lines,
    )


def _resolve_outcome_betway(
    platform_name: str,
    index: int,
    mapping: MarketMapping,
) -> str | None:
    """Find canonical outcome name from Betway outcome.

    Uses exact match first, then position-based matching for
    markets that use team names (1X2, DC).
    Sentinel values: __HOME__=pos0, __AWAY__=pos2,
    __POS_1__=pos0, __POS_2__=pos1, __POS_3__=pos2.
    """
    # Exact match first
    for om in mapping.outcomes.values():
        if om.betway == platform_name:
            return om.canonical_name

    # Position-based match for sentinels
    position_sentinels = {
        0: ["__HOME__", "__POS_1__"],
        1: ["__POS_2__"],
        2: ["__AWAY__", "__POS_3__"],
    }
    sentinels_for_index = position_sentinels.get(index, [])
    for om in mapping.outcomes.values():
        if om.betway in sentinels_for_index:
            return om.canonical_name

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_parser_betway.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Run all tests**

Run: `.venv/Scripts/python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_parser_betway.py
git commit -m "feat: add Betway market parser with position-based outcome matching"
```

---

## Task 5: Convenience methods override for Betway

**Files:**
- Modify: `src/bookieskit/bookmakers/betway.py`

- [ ] **Step 1: Override get_markets on Betway**

Betway needs a custom `get_markets` because it uses `get_event_markets` (not `get_event_detail`) for market data. Add to the `Betway` class:

```python
    async def get_markets(self, event_id: str, registry=None):
        """Fetch event markets and return normalized markets.

        Overrides base because Betway uses a separate markets endpoint.

        Args:
            event_id: Betway event ID (= SportRadar ID)
            registry: MarketRegistry (default: built-in)

        Returns:
            List of NormalizedMarket for recognized markets.
        """
        from bookieskit.markets.parser import parse_markets

        raw = await self.get_event_markets(event_id=event_id)
        return parse_markets(
            raw, platform=self.PLATFORM_KEY, registry=registry
        )

    async def get_sportradar_id(
        self, event_id: str
    ) -> str | None:
        """Return the event ID directly (it IS the SportRadar ID).

        Overrides base to avoid an unnecessary API call.

        Args:
            event_id: Betway event ID

        Returns:
            The event ID as string (same value).
        """
        return str(event_id)
```

- [ ] **Step 2: Add convenience tests**

Add to `tests/test_betway.py`:

```python
@pytest.mark.asyncio
@respx.mock
async def test_get_markets_convenience():
    respx.get(
        "https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/MarketGroupings/MarketGroupNamesAndMarketsForEvent"
    ).respond(
        json={
            "marketsInGroup": [
                {
                    "marketId": "1",
                    "name": "[Both Teams To Score]",
                    "handicap": 0,
                }
            ],
            "outcomes": [
                {"outcomeId": "a", "marketId": "1", "name": "Yes"},
                {"outcomeId": "b", "marketId": "1", "name": "No"},
            ],
            "prices": [
                {"outcomeId": "a", "priceDecimal": 1.7},
                {"outcomeId": "b", "priceDecimal": 2.1},
            ],
        }
    )
    async with Betway(country="ng") as client:
        markets = await client.get_markets(event_id="123")
    assert len(markets) == 1
    assert markets[0].canonical_id == "btts_ft"


@pytest.mark.asyncio
async def test_get_sportradar_id_no_api_call():
    """Betway event IDs ARE SR IDs — no API call needed."""
    client = Betway(country="ng")
    sr_id = await client.get_sportradar_id(event_id="69339436")
    assert sr_id == "69339436"
```

- [ ] **Step 3: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_betway.py -v`
Expected: All 10 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/bookieskit/bookmakers/betway.py tests/test_betway.py
git commit -m "feat: add Betway convenience methods (get_markets, get_sportradar_id)"
```

---

## Task 6: Public Exports and Version Bump

**Files:**
- Modify: `src/bookieskit/__init__.py`
- Modify: `src/bookieskit/bookmakers/__init__.py`

- [ ] **Step 1: Update bookmakers __init__.py**

```python
"""Bookmaker client implementations."""

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.betway import Betway
from bookieskit.bookmakers.sportybet import SportyBet

__all__ = ["BetPawa", "SportyBet", "Bet9ja", "Betway"]
```

- [ ] **Step 2: Update package __init__.py**

```python
"""Bookieskit — HTTP clients for betting data scraping."""

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.betway import Betway
from bookieskit.bookmakers.sportybet import SportyBet

__all__ = ["BetPawa", "SportyBet", "Bet9ja", "Betway"]
__version__ = "0.3.0"
```

- [ ] **Step 3: Update pyproject.toml version**

Change `version = "0.2.0"` to `version = "0.3.0"`.

- [ ] **Step 4: Verify imports**

```bash
.venv/Scripts/python -c "from bookieskit import BetPawa, SportyBet, Bet9ja, Betway; print('OK')"
.venv/Scripts/python -c "import bookieskit; print(f'v{bookieskit.__version__}')"
```

Expected: `OK` and `v0.3.0`

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/__init__.py src/bookieskit/bookmakers/__init__.py pyproject.toml
git commit -m "feat: export Betway and bump to v0.3.0"
```

---

## Task 7: Documentation

**Files:**
- Create: `docs/betway.md`

- [ ] **Step 1: Create docs/betway.md**

```markdown
# Betway

## Supported Countries

| Code | Country |
|------|---------|
| ng | Nigeria |
| gh | Ghana |
| ke | Kenya |
| tz | Tanzania |
| ug | Uganda |
| zm | Zambia |

All countries use the same API domain — differentiated by `countryCode` parameter.

## SportRadar ID

Betway event IDs ARE SportRadar IDs natively. No extraction needed — `get_sportradar_id()` returns the event ID directly without an API call.

## Methods

### `get_sports()`

Returns all available sports with live/upcoming counts.

**Endpoint:** `GET https://config.betwayafrica.com/cron/sports/{countryCode}/en-US`

**Response:**
```json
{
  "sports": [
    {
      "sportId": "soccer",
      "name": "Soccer",
      "liveInPlayCount": 29,
      "hasUpcomingEvents": true
    }
  ]
}
```

### `get_countries(sport_id="soccer")`

Returns regions and leagues for a sport.

**Endpoint:** `GET /br/_apis/sport/v1/Feeds/RegionsAndLeagues/{sportId}?countryCode={cc}`

**Response:**
```json
{
  "regions": [
    {
      "regionId": "england",
      "name": "England",
      "leagues": [
        {"leagueId": "premier-league", "name": "Premier League"}
      ]
    }
  ]
}
```

### `get_events(league_id, sport_id="soccer")`

Returns events with inline markets, outcomes, and prices.

**Endpoint:** `GET /br/_apis/sport/v1/BetBook/Highlights/?countryCode={cc}&sportId={sport}&leagueIds={league}`

League ID format: `"{regionId}_{leagueId}"` (e.g., `"international-clubs_uefa-champions-league"`)

**Response:**
```json
{
  "events": [
    {
      "eventId": 69339436,
      "homeTeam": "Arsenal FC",
      "awayTeam": "Atletico Madrid",
      "isLive": false,
      "expectedStartEpoch": 1778007600
    }
  ],
  "markets": [...],
  "outcomes": [...],
  "prices": [{"outcomeId": "...", "priceDecimal": 1.63}]
}
```

### `get_event_detail(event_id)`

Returns event info and game state.

**Endpoint:** `GET /br/_apis/sport/v3/Feeds/Events/EventAndGameState?eventId={id}&countryCode={cc}`

### `get_event_markets(event_id)`

Returns all markets for an event (denormalized).

**Endpoint:** `GET /br/_apis/sport/v1/MarketGroupings/MarketGroupNamesAndMarketsForEvent?eventId={id}&countryCode={cc}`

**Response:**
```json
{
  "marketGroupNames": ["Main", "Totals", "Goals"],
  "marketsInGroup": [
    {"marketId": "693394361", "name": "[Win/Draw/Win]", "displayName": "1X2", "handicap": 0}
  ],
  "outcomes": [
    {"outcomeId": "6933943611", "marketId": "693394361", "name": "Arsenal FC"}
  ],
  "prices": [
    {"outcomeId": "6933943611", "priceDecimal": 1.63}
  ]
}
```

## Notes

- Uses **string-based sport IDs** (slugs: "soccer", "tennis", "basketball")
- **Denormalized responses** — events, markets, outcomes, prices in separate arrays linked by IDs
- **Position-based outcome matching** for 1X2 and Double Chance (outcomes use team names, not "1"/"X"/"2")
- `get_sportradar_id()` does NOT make an API call — returns the event ID directly
```

- [ ] **Step 2: Commit**

```bash
git add docs/betway.md
git commit -m "docs: add Betway API documentation"
```

---

## Task 8: Final Verification

- [ ] **Step 1: Run full test suite**

```bash
.venv/Scripts/python -m pytest -v
```

Expected: All tests PASS

- [ ] **Step 2: Run linter**

```bash
.venv/Scripts/python -m ruff check src/ tests/
```

Expected: No errors (fix any that appear)

- [ ] **Step 3: Verify all imports**

```bash
.venv/Scripts/python -c "
from bookieskit import BetPawa, SportyBet, Bet9ja, Betway
from bookieskit.markets import MarketRegistry, parse_markets
from bookieskit.matching import extract_sportradar_id, match_events
print('All imports OK')
print(f'Version: {__import__(\"bookieskit\").__version__}')
"
```

Expected: `All imports OK` and `Version: 0.3.0`

- [ ] **Step 4: Fix linting issues if any, commit**

```bash
git add -A
git commit -m "chore: linting fixes and final cleanup"
```
