# MSport Bookmaker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MSport as the fifth bookmaker in `bookieskit`, including HTTP client (prematch + live), market parser, SportRadar ID extractor, registry/builtins extension, exports, and documentation.

**Architecture:** New `MSport` subclass of `BaseBookmaker` with three-country support (`ng`/`gh`/`ke`) on a single domain (`https://www.msport.com`) differentiated by path prefix. Add `msport_id` to `MarketMapping`, `msport` field to `OutcomeMapping`, an `_by_msport` index on `MarketRegistry`, and platform-specific `_parse_msport` / `_extract_msport` mirroring the SportyBet implementation but reading `description` (not `desc`) and `specifiers` (not `specifier`).

**Tech Stack:** Python 3.11+, httpx (async), pytest + pytest-asyncio + respx (test mocks)

**Source spec:** `docs/specs/2026-05-05-msport-bookmaker-design.md`

---

## File Structure

```
Modified:
  src/bookieskit/markets/types.py             — add msport field to OutcomeMapping, msport_id to MarketMapping
  src/bookieskit/markets/registry.py          — add _by_msport index + dispatch + add() kwarg
  src/bookieskit/markets/builtin_mappings.py  — add msport values to all 4 builtins
  src/bookieskit/markets/parser.py            — add _parse_msport + _resolve_outcome_msport + dispatcher entry
  src/bookieskit/matching/extractor.py        — add _extract_msport + dispatcher entry
  src/bookieskit/config.py                    — add MSPORT_MAX_CONCURRENT, MSPORT_REQUEST_DELAY
  src/bookieskit/bookmakers/__init__.py       — export MSport
  src/bookieskit/__init__.py                  — export MSport, bump version 0.3.0 -> 0.4.0
  tests/test_extractor.py                     — add MSport cases
  tests/test_registry.py                      — add msport platform-id round-trip case
  tests/test_types.py                         — verify new fields default correctly
  README.md                                   — bump bookmaker count 4 -> 5

Created:
  src/bookieskit/bookmakers/msport.py         — MSport client class
  tests/test_msport.py                        — client tests (respx-mocked)
  tests/test_parser_msport.py                 — parser tests
  docs/msport.md                              — client reference
```

---

## Task 1: Add `msport` field to types

**Files:**
- Modify: `src/bookieskit/markets/types.py`
- Modify: `tests/test_types.py`

- [ ] **Step 1: Write failing test for new fields**

Add to `tests/test_types.py`:

```python
def test_outcome_mapping_with_msport():
    om = OutcomeMapping(
        canonical_name="home",
        betpawa="1",
        sportybet="Home",
        bet9ja="1",
        betway="__HOME__",
        msport="Home",
    )
    assert om.msport == "Home"


def test_outcome_mapping_msport_defaults_empty():
    om = OutcomeMapping(
        canonical_name="home",
        betpawa="1",
        sportybet="Home",
        bet9ja="1",
    )
    assert om.msport == ""


def test_market_mapping_with_msport_id():
    mm = MarketMapping(
        canonical_id="1x2_ft",
        name="1X2 - Full Time",
        betpawa_id="3743",
        sportybet_id="1",
        bet9ja_key="S_1X2",
        betway_id="[Win/Draw/Win]",
        msport_id="1",
        outcomes={},
        parameterized=False,
    )
    assert mm.msport_id == "1"


def test_market_mapping_msport_id_defaults_none():
    mm = MarketMapping(
        canonical_id="x",
        name="X",
        betpawa_id=None,
        sportybet_id=None,
        bet9ja_key=None,
        outcomes={},
    )
    assert mm.msport_id is None
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_types.py -v -k msport`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'msport'` (and similarly `msport_id`).

- [ ] **Step 3: Add fields to `types.py`**

Modify `src/bookieskit/markets/types.py` so `OutcomeMapping` and `MarketMapping` end up exactly as below:

```python
@dataclass(frozen=True)
class OutcomeMapping:
    """Maps one outcome across platforms."""

    canonical_name: str
    betpawa: str
    sportybet: str
    bet9ja: str
    betway: str = ""
    msport: str = ""


@dataclass(frozen=True)
class MarketMapping:
    """Defines how one market maps across platforms."""

    canonical_id: str
    name: str
    betpawa_id: str | None
    sportybet_id: str | None
    bet9ja_key: str | None
    betway_id: str | None = None
    msport_id: str | None = None
    outcomes: dict[str, OutcomeMapping] = field(default_factory=dict)
    parameterized: bool = False
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `pytest tests/test_types.py -v`
Expected: PASS for all tests in the file (existing + 4 new).

- [ ] **Step 5: Run full suite to confirm no regressions**

Run: `pytest tests/ -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/types.py tests/test_types.py
git commit -m "feat(types): add msport_id and msport fields to mapping types"
```

---

## Task 2: Add `msport` index to MarketRegistry

**Files:**
- Modify: `src/bookieskit/markets/registry.py`
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Write failing test for msport platform-id lookup**

Add to `tests/test_registry.py`:

```python
def test_registry_get_by_platform_id_msport():
    registry = MarketRegistry()
    mapping = registry.get_by_platform_id("msport", "1")
    assert mapping is not None
    assert mapping.canonical_id == "1x2_ft"


def test_registry_add_with_msport_id():
    registry = MarketRegistry(load_builtins=False)
    registry.add(
        canonical_id="custom",
        name="Custom",
        msport_id="42",
        outcomes={},
    )
    mapping = registry.get_by_platform_id("msport", "42")
    assert mapping is not None
    assert mapping.canonical_id == "custom"
```

Note: the first test will only pass once builtins are updated (Task 3). For now we expect Step 2's run to fail it because the registry has no `_by_msport` map. The `add()`-with-`msport_id` test confirms the registry-side wiring independently of builtins.

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_registry.py -v -k msport`
Expected: FAIL — `add()` rejects `msport_id` kwarg AND `get_by_platform_id("msport", ...)` returns `None`.

- [ ] **Step 3: Update `registry.py`**

Apply these three changes to `src/bookieskit/markets/registry.py`:

(a) In `__init__`, add the new index:

```python
def __init__(self, load_builtins: bool = True):
    self._by_canonical: dict[str, MarketMapping] = {}
    self._by_betpawa: dict[str, MarketMapping] = {}
    self._by_sportybet: dict[str, MarketMapping] = {}
    self._by_bet9ja: dict[str, MarketMapping] = {}
    self._by_betway: dict[str, MarketMapping] = {}
    self._by_msport: dict[str, MarketMapping] = {}

    if load_builtins:
        for mapping in BUILTIN_MAPPINGS:
            self._register(mapping)
```

(b) In `_register`, add the indexing line:

```python
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
    if mapping.msport_id:
        self._by_msport[mapping.msport_id] = mapping
```

(c) In `add(...)`, accept the new kwarg:

```python
def add(
    self,
    canonical_id: str,
    name: str,
    betpawa_id: str | None = None,
    sportybet_id: str | None = None,
    bet9ja_key: str | None = None,
    betway_id: str | None = None,
    msport_id: str | None = None,
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
        msport_id=msport_id,
        outcomes=outcomes or {},
        parameterized=parameterized,
    )
    self._register(mapping)
```

(d) In `get_by_platform_id`, extend the dispatch dict:

```python
def get_by_platform_id(
    self, platform: str, platform_id: str
) -> MarketMapping | None:
    index = {
        "betpawa": self._by_betpawa,
        "sportybet": self._by_sportybet,
        "bet9ja": self._by_bet9ja,
        "betway": self._by_betway,
        "msport": self._by_msport,
    }.get(platform, {})
    return index.get(platform_id)
```

- [ ] **Step 4: Run only the `add()` test (builtins still don't have msport_id)**

Run: `pytest tests/test_registry.py::test_registry_add_with_msport_id -v`
Expected: PASS.

- [ ] **Step 5: Confirm full registry test file still passes (the `get_by_platform_id_msport` for builtins will still fail until Task 3)**

Run: `pytest tests/test_registry.py -v`
Expected: all PASS except `test_registry_get_by_platform_id_msport` which still fails — that's expected and gets fixed in Task 3.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/registry.py tests/test_registry.py
git commit -m "feat(registry): index mappings by msport_id"
```

---

## Task 3: Add MSport values to built-in mappings

**Files:**
- Modify: `src/bookieskit/markets/builtin_mappings.py`

- [ ] **Step 1: Update `builtin_mappings.py`**

Replace the file contents with:

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
        msport_id="1",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
                betway="__HOME__",
                msport="Home",
            ),
            "draw": OutcomeMapping(
                canonical_name="draw",
                betpawa="X",
                sportybet="Draw",
                bet9ja="X",
                betway="Draw",
                msport="Draw",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__AWAY__",
                msport="Away",
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
        msport_id="18",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="O",
                betway="Over",
                msport="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="U",
                betway="Under",
                msport="Under",
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
        msport_id="29",
        outcomes={
            "yes": OutcomeMapping(
                canonical_name="yes",
                betpawa="Yes",
                sportybet="Yes",
                bet9ja="Y",
                betway="Yes",
                msport="Yes",
            ),
            "no": OutcomeMapping(
                canonical_name="no",
                betpawa="No",
                sportybet="No",
                bet9ja="N",
                betway="No",
                msport="No",
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
        msport_id="10",
        outcomes={
            "home_draw": OutcomeMapping(
                canonical_name="home_draw",
                betpawa="1X",
                sportybet="Home or Draw",
                bet9ja="1X",
                betway="__POS_1__",
                msport="Home or Draw",
            ),
            "draw_away": OutcomeMapping(
                canonical_name="draw_away",
                betpawa="X2",
                sportybet="Draw or Away",
                bet9ja="X2",
                betway="__POS_2__",
                msport="Draw or Away",
            ),
            "home_away": OutcomeMapping(
                canonical_name="home_away",
                betpawa="12",
                sportybet="Home or Away",
                bet9ja="12",
                betway="__POS_3__",
                msport="Home or Away",
            ),
        },
        parameterized=False,
    ),
]
```

- [ ] **Step 2: Run the registry msport-builtin test**

Run: `pytest tests/test_registry.py::test_registry_get_by_platform_id_msport -v`
Expected: PASS.

- [ ] **Step 3: Run the full registry suite**

Run: `pytest tests/test_registry.py -v`
Expected: all PASS.

- [ ] **Step 4: Run the full suite**

Run: `pytest tests/ -q`
Expected: all existing tests still pass (the builtins change is additive).

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/builtin_mappings.py
git commit -m "feat(markets): add MSport identifiers to built-in mappings"
```

---

## Task 4: Add MSport rate-limit constants

**Files:**
- Modify: `src/bookieskit/config.py`

- [ ] **Step 1: Update `config.py`**

Append the MSport block before `RETRYABLE_STATUS_CODES`:

```python
"""Default configuration constants for bookieskit."""

# HTTP client defaults
DEFAULT_TIMEOUT = 30.0  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 1.0  # exponential: 1s, 2s, 4s

# Connection pooling
DEFAULT_MAX_CONNECTIONS = 200
DEFAULT_MAX_KEEPALIVE = 100

# Platform-specific rate limits
BETPAWA_MAX_CONCURRENT = 50
BETPAWA_REQUEST_DELAY = 0.0

SPORTYBET_MAX_CONCURRENT = 50
SPORTYBET_REQUEST_DELAY = 0.0

BET9JA_MAX_CONCURRENT = 15
BET9JA_REQUEST_DELAY = 0.025  # 25ms

MSPORT_MAX_CONCURRENT = 50
MSPORT_REQUEST_DELAY = 0.0

# Retry-eligible HTTP status codes
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
```

- [ ] **Step 2: Quick smoke check**

Run: `python -c "from bookieskit.config import MSPORT_MAX_CONCURRENT, MSPORT_REQUEST_DELAY; print(MSPORT_MAX_CONCURRENT, MSPORT_REQUEST_DELAY)"`
Expected output: `50 0.0`

- [ ] **Step 3: Commit**

```bash
git add src/bookieskit/config.py
git commit -m "feat(config): add MSport rate-limit constants"
```

---

## Task 5: Build MSport HTTP client

**Files:**
- Create: `src/bookieskit/bookmakers/msport.py`
- Create: `tests/test_msport.py`

- [ ] **Step 1: Create `tests/test_msport.py` with all happy-path + setup tests**

```python
import pytest
import respx

from bookieskit.bookmakers.msport import MSport


def test_msport_country_ng_resolves_domain():
    client = MSport(country="ng")
    assert client.base_url == "https://www.msport.com"


def test_msport_country_gh_resolves_domain():
    client = MSport(country="gh")
    assert client.base_url == "https://www.msport.com"


def test_msport_country_ke_resolves_domain():
    client = MSport(country="ke")
    assert client.base_url == "https://www.msport.com"


def test_msport_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        MSport(country="xx")


@pytest.mark.asyncio
@respx.mock
async def test_msport_headers():
    route = respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/sports"
    ).respond(json={"bizCode": 10000, "data": {"sports": []}})
    async with MSport(country="ng") as client:
        await client.get_sports()
    headers = route.calls[0].request.headers
    assert headers["clientid"] == "web"
    assert headers["operid"] == "2"
    assert headers["platform"] == "web"


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/sports"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "sports": [
                    {"sportId": "sr:sport:1", "sportName": "Soccer", "count": 0},
                    {"sportId": "sr:sport:2", "sportName": "Basketball", "count": 0},
                ]
            },
        }
    )
    async with MSport(country="ng") as client:
        result = await client.get_sports()
    assert result["data"]["sports"][0]["sportName"] == "Soccer"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/sports-matches-list"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "tournaments": [
                    {
                        "category": "England",
                        "tournament": "Premier League",
                        "tournamentId": "sr:tournament:17",
                        "events": [
                            {
                                "eventId": "sr:match:61301233",
                                "homeTeam": "Liverpool",
                                "awayTeam": "Chelsea",
                            }
                        ],
                    }
                ]
            },
        }
    )
    async with MSport(country="ng") as client:
        result = await client.get_events(sport_id="sr:sport:1")
    tournaments = result["data"]["tournaments"]
    assert tournaments[0]["events"][0]["homeTeam"] == "Liverpool"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail():
    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/match/detail"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "eventId": "sr:match:61301231",
                "homeTeam": "Fulham",
                "awayTeam": "Bournemouth",
                "markets": [
                    {
                        "id": 1,
                        "description": "1x2",
                        "name": "1x2",
                        "specifiers": None,
                        "outcomes": [
                            {"description": "Home", "id": "1", "odds": "2.76"},
                        ],
                    }
                ],
            },
        }
    )
    async with MSport(country="ng") as client:
        result = await client.get_event_detail(event_id="sr:match:61301231")
    assert result["data"]["markets"][0]["description"] == "1x2"


@pytest.mark.asyncio
@respx.mock
async def test_get_live_sports():
    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/live-matches/sports"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "sports": [
                    {"sportId": "sr:sport:1", "sportName": "Soccer", "count": 30},
                ]
            },
        }
    )
    async with MSport(country="ng") as client:
        result = await client.get_live_sports()
    assert result["data"]["sports"][0]["count"] == 30


@pytest.mark.asyncio
@respx.mock
async def test_get_live_events():
    respx.get(
        "https://www.msport.com/api/ng/facts-center/query/frontend/live-matches/list"
    ).respond(
        json={
            "bizCode": 10000,
            "data": {
                "tournaments": [],
                "events": [{"eventId": "sr:match:61301233"}],
                "comingSoons": [],
            },
        }
    )
    async with MSport(country="ng") as client:
        result = await client.get_live_events(sport_id="sr:sport:1")
    assert result["data"]["events"][0]["eventId"] == "sr:match:61301233"


@pytest.mark.asyncio
@respx.mock
async def test_msport_gh_uses_gh_path():
    respx.get(
        "https://www.msport.com/api/gh/facts-center/query/frontend/sports"
    ).respond(json={"bizCode": 10000, "data": {"sports": []}})
    async with MSport(country="gh") as client:
        result = await client.get_sports()
    assert result["bizCode"] == 10000


@pytest.mark.asyncio
@respx.mock
async def test_msport_ke_uses_ke_path():
    respx.get(
        "https://www.msport.com/api/ke/facts-center/query/frontend/sports"
    ).respond(json={"bizCode": 10000, "data": {"sports": []}})
    async with MSport(country="ke") as client:
        result = await client.get_sports()
    assert result["bizCode"] == 10000
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_msport.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bookieskit.bookmakers.msport'`.

- [ ] **Step 3: Create `src/bookieskit/bookmakers/msport.py`**

```python
"""MSport client — supports ng, gh, ke."""

from typing import Any

from bookieskit.base import BaseBookmaker
from bookieskit.config import MSPORT_MAX_CONCURRENT, MSPORT_REQUEST_DELAY


class MSport(BaseBookmaker):
    """HTTP client for MSport API.

    MSport uses the same base domain for all countries but differentiates
    via the API path (e.g., /api/ng/... vs /api/gh/...). The MSport API
    returns prematch matches grouped by tournament in a single call per
    sport — there is no per-tournament fetch.

    Args:
        country: Country code (ng, gh, ke)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 50)
        request_delay: Delay between requests in seconds (default: 0)
    """

    DOMAINS = {
        "ng": "https://www.msport.com",
        "gh": "https://www.msport.com",
        "ke": "https://www.msport.com",
    }
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "en",
        "clientid": "web",
        "operid": "2",
        "platform": "web",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",  # noqa: E501
    }
    MAX_CONCURRENT = MSPORT_MAX_CONCURRENT
    REQUEST_DELAY = MSPORT_REQUEST_DELAY
    NAME = "MSport"
    PLATFORM_KEY = "msport"

    @property
    def _api_prefix(self) -> str:
        """Country-specific API path prefix."""
        return f"/api/{self._country}/facts-center/query/frontend"

    async def get_sports(self) -> dict[str, Any]:
        """Get all available prematch sports.

        Returns:
            Raw JSON with data.sports list — each entry has sportId,
            sportName, count.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/sports",
        )

    async def get_events(
        self, sport_id: str = "sr:sport:1"
    ) -> dict[str, Any]:
        """Get all prematch events for a sport, grouped by tournament.

        MSport bundles the entire sport's match list per call — there is
        no per-tournament endpoint.

        Args:
            sport_id: SportRadar sport ID (default: "sr:sport:1" for Soccer)

        Returns:
            Raw JSON with data.tournaments list — each tournament has
            category, tournament, tournamentId, and events.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/sports-matches-list",
            params={"sportId": sport_id},
        )

    async def get_event_detail(self, event_id: str) -> dict[str, Any]:
        """Get full event details including all markets.

        Args:
            event_id: SportRadar match ID (e.g., "sr:match:61301231")

        Returns:
            Raw JSON with data containing eventId, homeTeam, awayTeam,
            and markets list.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/match/detail",
            params={"eventId": event_id, "productId": "3"},
        )

    async def get_live_sports(self) -> dict[str, Any]:
        """Get all sports that currently have live events.

        Returns:
            Raw JSON with data.sports list — each entry has sportId,
            sportName, and a non-zero count.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/live-matches/sports",
        )

    async def get_live_events(
        self, sport_id: str = "sr:sport:1"
    ) -> dict[str, Any]:
        """Get live events for a sport, grouped by tournament.

        Uses the richer /live-matches/list endpoint, which returns
        tournaments, events, and comingSoons in one call.

        Args:
            sport_id: SportRadar sport ID (default: "sr:sport:1" for Soccer)

        Returns:
            Raw JSON with data.tournaments, data.events, data.comingSoons.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/live-matches/list",
            params={"sportId": sport_id},
        )
```

- [ ] **Step 4: Run client tests, confirm they pass**

Run: `pytest tests/test_msport.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/bookmakers/msport.py tests/test_msport.py
git commit -m "feat(msport): add HTTP client for prematch and live"
```

---

## Task 6: Add MSport market parser

**Files:**
- Modify: `src/bookieskit/markets/parser.py`
- Create: `tests/test_parser_msport.py`

- [ ] **Step 1: Create `tests/test_parser_msport.py`**

```python
from bookieskit.markets.parser import parse_markets

MSPORT_EVENT_RESPONSE = {
    "bizCode": 10000,
    "data": {
        "eventId": "sr:match:61301231",
        "markets": [
            {
                "id": "1",
                "description": "1x2",
                "name": "1x2",
                "specifiers": None,
                "outcomes": [
                    {"id": "1", "description": "Home", "odds": "2.76"},
                    {"id": "2", "description": "Draw", "odds": "3.77"},
                    {"id": "3", "description": "Away", "odds": "2.39"},
                ],
            },
            {
                "id": "18",
                "description": "Over/Under",
                "name": "Over/Under",
                "specifiers": "total=2.5",
                "outcomes": [
                    {"id": "12", "description": "Over", "odds": "1.80"},
                    {"id": "13", "description": "Under", "odds": "2.00"},
                ],
            },
            {
                "id": "18",
                "description": "Over/Under",
                "name": "Over/Under",
                "specifiers": "total=3.5",
                "outcomes": [
                    {"id": "12", "description": "Over", "odds": "2.10"},
                    {"id": "13", "description": "Under", "odds": "1.70"},
                ],
            },
            {
                "id": "29",
                "description": "Both Teams To Score",
                "name": "Both Teams To Score",
                "specifiers": None,
                "outcomes": [
                    {"id": "74", "description": "Yes", "odds": "1.75"},
                    {"id": "76", "description": "No", "odds": "2.05"},
                ],
            },
            {
                "id": "10",
                "description": "Double Chance",
                "name": "Double Chance",
                "specifiers": None,
                "outcomes": [
                    {"id": "9", "description": "Home or Draw", "odds": "1.25"},
                    {"id": "11", "description": "Draw or Away", "odds": "1.50"},
                    {"id": "10", "description": "Home or Away", "odds": "1.10"},
                ],
            },
            {
                "id": "999",
                "description": "Unknown Market",
                "name": "Unknown",
                "specifiers": None,
                "outcomes": [
                    {"id": "1", "description": "Option A", "odds": "2.00"},
                ],
            },
        ],
    },
}


def test_parse_msport_1x2():
    markets = parse_markets(MSPORT_EVENT_RESPONSE, platform="msport")
    m = next(m for m in markets if m.canonical_id == "1x2_ft")
    assert len(m.outcomes) == 3
    assert m.lines is None
    home = next(o for o in m.outcomes if o.canonical_name == "home")
    assert home.odds == 2.76
    assert home.platform_name == "Home"


def test_parse_msport_over_under():
    markets = parse_markets(MSPORT_EVENT_RESPONSE, platform="msport")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    assert ou.lines is not None
    assert 2.5 in ou.lines
    assert 3.5 in ou.lines
    over_25 = next(
        o for o in ou.lines[2.5] if o.canonical_name == "over"
    )
    assert over_25.odds == 1.80


def test_parse_msport_btts():
    markets = parse_markets(MSPORT_EVENT_RESPONSE, platform="msport")
    btts = next(m for m in markets if m.canonical_id == "btts_ft")
    assert len(btts.outcomes) == 2
    yes = next(o for o in btts.outcomes if o.canonical_name == "yes")
    assert yes.odds == 1.75


def test_parse_msport_double_chance():
    markets = parse_markets(MSPORT_EVENT_RESPONSE, platform="msport")
    dc = next(m for m in markets if m.canonical_id == "double_chance_ft")
    assert len(dc.outcomes) == 3
    home_draw = next(
        o for o in dc.outcomes if o.canonical_name == "home_draw"
    )
    assert home_draw.platform_name == "Home or Draw"


def test_parse_msport_skips_unknown_market():
    markets = parse_markets(MSPORT_EVENT_RESPONSE, platform="msport")
    canonical_ids = {m.canonical_id for m in markets}
    assert "999" not in canonical_ids
    assert len(markets) == 4


def test_parse_msport_outcome_prefix_fallback():
    """Parameterized markets sometimes embed the line in the description
    (e.g. 'Over 2.5'). The resolver should match by prefix."""
    response = {
        "bizCode": 10000,
        "data": {
            "markets": [
                {
                    "id": "18",
                    "description": "Over/Under",
                    "specifiers": "total=2.5",
                    "outcomes": [
                        {"id": "12", "description": "Over 2.5", "odds": "1.80"},
                        {"id": "13", "description": "Under 2.5", "odds": "2.00"},
                    ],
                }
            ]
        },
    }
    markets = parse_markets(response, platform="msport")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    over = next(o for o in ou.lines[2.5] if o.canonical_name == "over")
    assert over.platform_name == "Over 2.5"
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_parser_msport.py -v`
Expected: FAIL — `parse_markets(..., platform="msport")` returns `[]` because the dispatcher has no `"msport"` entry, so all assertions miss.

- [ ] **Step 3: Add `_parse_msport` and `_resolve_outcome_msport` to `parser.py`**

In `src/bookieskit/markets/parser.py`, add `"msport": _parse_msport` to the `parsers` dict in `parse_markets`:

```python
def parse_markets(
    response: dict,
    platform: str,
    registry: MarketRegistry | None = None,
) -> list[NormalizedMarket]:
    if registry is None:
        registry = MarketRegistry()

    parsers = {
        "betpawa": _parse_betpawa,
        "sportybet": _parse_sportybet,
        "bet9ja": _parse_bet9ja,
        "betway": _parse_betway,
        "msport": _parse_msport,
    }
    parser = parsers.get(platform)
    if parser is None:
        return []
    return parser(response, registry)
```

Then add the MSport-specific functions at the bottom of the file (after the Betway block):

```python
def _parse_msport(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse MSport event detail response.

    MSport's payload mirrors SportyBet's structurally but uses
    `description` instead of `desc` and `specifiers` (plural) instead
    of `specifier`. Market ids are integer-strings; parameterized
    markets repeat the same id once per line, with `specifiers` like
    "total=2.5" or "hcp=-0.5".
    """
    results: list[NormalizedMarket] = []
    data = response.get("data", response)
    markets = data.get("markets", [])

    parameterized_groups: dict[str, list[dict]] = {}

    for market_data in markets:
        market_id = str(market_data.get("id", ""))
        mapping = registry.get_by_platform_id("msport", market_id)
        if mapping is None:
            continue

        if mapping.parameterized:
            parameterized_groups.setdefault(market_id, []).append(market_data)
        else:
            results.append(_parse_msport_simple(market_data, mapping))

    for market_id, entries in parameterized_groups.items():
        mapping = registry.get_by_platform_id("msport", market_id)
        if mapping:
            results.append(_parse_msport_parameterized(entries, mapping))

    return results


def _parse_msport_simple(
    market_data: dict, mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a simple MSport market."""
    outcomes: list[Outcome] = []

    for outcome_data in market_data.get("outcomes", []):
        desc = str(outcome_data.get("description", ""))
        odds = float(outcome_data.get("odds", 0))
        canonical = _resolve_outcome_msport(desc, mapping)
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


def _parse_msport_parameterized(
    entries: list[dict], mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a parameterized MSport market (multiple entries, one per line)."""
    lines: dict[float, list[Outcome]] = {}

    for entry in entries:
        specifiers = entry.get("specifiers", "") or ""
        line = _extract_line_from_specifier(specifiers)
        if line is None:
            continue

        line_outcomes: list[Outcome] = []
        for outcome_data in entry.get("outcomes", []):
            desc = str(outcome_data.get("description", ""))
            odds = float(outcome_data.get("odds", 0))
            canonical = _resolve_outcome_msport(desc, mapping)
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


def _resolve_outcome_msport(
    platform_name: str, mapping: MarketMapping
) -> str | None:
    """Find canonical outcome name from MSport outcome description.

    Exact match first, then prefix match for parameterized payloads
    where the description embeds the line value (e.g. "Over 2.5").
    """
    for om in mapping.outcomes.values():
        if om.msport == platform_name:
            return om.canonical_name
    for om in mapping.outcomes.values():
        if om.msport and platform_name.startswith(om.msport):
            return om.canonical_name
    return None
```

The helper `_extract_line_from_specifier` already exists in the file (used by SportyBet) and takes the same `total=...|hcp=...` format — no changes needed.

- [ ] **Step 4: Run parser tests, confirm they pass**

Run: `pytest tests/test_parser_msport.py -v`
Expected: all PASS.

- [ ] **Step 5: Run full suite, confirm no regressions**

Run: `pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_parser_msport.py
git commit -m "feat(parser): add MSport market parser"
```

---

## Task 7: Add MSport SportRadar ID extractor

**Files:**
- Modify: `src/bookieskit/matching/extractor.py`
- Modify: `tests/test_extractor.py`

- [ ] **Step 1: Add failing extractor tests**

Append to `tests/test_extractor.py`:

```python
def test_extract_from_msport():
    response = {
        "bizCode": 10000,
        "data": {"eventId": "sr:match:61301231", "markets": []},
    }
    sr_id = extract_sportradar_id(response, platform="msport")
    assert sr_id == "61301231"


def test_extract_from_msport_no_prefix():
    response = {
        "bizCode": 10000,
        "data": {"eventId": "61301231", "markets": []},
    }
    sr_id = extract_sportradar_id(response, platform="msport")
    assert sr_id == "61301231"


def test_extract_from_msport_no_event_id():
    response = {"bizCode": 10000, "data": {"markets": []}}
    sr_id = extract_sportradar_id(response, platform="msport")
    assert sr_id is None


def test_extract_from_msport_no_data():
    sr_id = extract_sportradar_id({"bizCode": 10000}, platform="msport")
    assert sr_id is None
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `pytest tests/test_extractor.py -v -k msport`
Expected: FAIL — `extract_sportradar_id(..., platform="msport")` returns `None` for the happy-path test (no dispatcher entry yet).

- [ ] **Step 3: Add `_extract_msport` to `extractor.py`**

In `src/bookieskit/matching/extractor.py`, add `"msport": _extract_msport` to the `extractors` dict:

```python
def extract_sportradar_id(
    response: dict, platform: str
) -> str | None:
    extractors = {
        "betpawa": _extract_betpawa,
        "sportybet": _extract_sportybet,
        "bet9ja": _extract_bet9ja,
        "betway": _extract_betway,
        "msport": _extract_msport,
    }
    extractor = extractors.get(platform)
    if extractor is None:
        return None
    return extractor(response)
```

Add the helper at the bottom of the file:

```python
def _extract_msport(response: dict) -> str | None:
    """Extract from MSport data.eventId field.

    MSport returns the eventId at the top level of the `data` object,
    same shape as SportyBet — typically prefixed with `sr:match:`.
    """
    data = response.get("data", {})
    event_id = data.get("eventId")
    if event_id:
        return _strip_sr_prefix(str(event_id))
    return None
```

- [ ] **Step 4: Run extractor tests, confirm they pass**

Run: `pytest tests/test_extractor.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/matching/extractor.py tests/test_extractor.py
git commit -m "feat(extractor): add MSport SportRadar ID extraction"
```

---

## Task 8: Wire up exports + bump version

**Files:**
- Modify: `src/bookieskit/bookmakers/__init__.py`
- Modify: `src/bookieskit/__init__.py`

- [ ] **Step 1: Update `bookmakers/__init__.py`**

Replace contents:

```python
"""Bookmaker client implementations."""

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.betway import Betway
from bookieskit.bookmakers.msport import MSport
from bookieskit.bookmakers.sportybet import SportyBet

__all__ = ["BetPawa", "SportyBet", "Bet9ja", "Betway", "MSport"]
```

- [ ] **Step 2: Update `bookieskit/__init__.py`**

Replace contents:

```python
"""Bookieskit — HTTP clients for betting data scraping."""

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.betway import Betway
from bookieskit.bookmakers.msport import MSport
from bookieskit.bookmakers.sportybet import SportyBet

__all__ = ["BetPawa", "SportyBet", "Bet9ja", "Betway", "MSport"]
__version__ = "0.4.0"
```

- [ ] **Step 3: Smoke check the public surface**

Run: `python -c "from bookieskit import MSport; print(MSport.NAME, MSport.PLATFORM_KEY)"`
Expected output: `MSport msport`

Run: `python -c "import bookieskit; print(bookieskit.__version__)"`
Expected output: `0.4.0`

- [ ] **Step 4: Run full suite**

Run: `pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/__init__.py src/bookieskit/bookmakers/__init__.py
git commit -m "feat: expose MSport in public API, bump version to 0.4.0"
```

---

## Task 9: Documentation

**Files:**
- Create: `docs/msport.md`
- Modify: `README.md`

- [ ] **Step 1: Create `docs/msport.md`**

```markdown
# MSport Client

`MSport` is the HTTP client for MSport's sportsbook API.

## Countries

| Code | Domain |
|------|-----------------------|
| `ng` | https://www.msport.com |
| `gh` | https://www.msport.com |
| `ke` | https://www.msport.com |

All countries share the same domain; the country segment lives in the
URL path (`/api/{country}/facts-center/query/frontend/...`).

## Methods

| Method | HTTP | Path |
|--------|------|------|
| `get_sports()` | GET | `/sports` |
| `get_events(sport_id="sr:sport:1")` | GET | `/sports-matches-list?sportId=...` |
| `get_event_detail(event_id)` | GET | `/match/detail?eventId=...&productId=3` |
| `get_live_sports()` | GET | `/live-matches/sports` |
| `get_live_events(sport_id="sr:sport:1")` | GET | `/live-matches/list?sportId=...` |

## Quirks

- Outcome name field is `description` (not `desc` like SportyBet).
- Specifier field is `specifiers` plural (not `specifier`).
- Prematch matches are returned grouped by tournament for the entire
  sport in one call — there is no per-tournament endpoint.
- Live events use the richer `/live-matches/list` endpoint, which
  includes `tournaments`, `events`, and `comingSoons`.

## Example

```python
import asyncio
from bookieskit import MSport

async def main():
    async with MSport(country="ng") as client:
        sports = await client.get_sports()
        events = await client.get_events(sport_id="sr:sport:1")
        markets = await client.get_markets(
            event_id=events["data"]["tournaments"][0]["events"][0]["eventId"]
        )
        for m in markets:
            print(m.canonical_id, m.name)

asyncio.run(main())
```

## Headers

```
operid: 2
clientid: web
platform: web
```

(Identical to SportyBet — both rely on the same SportRadar-fed feed
infrastructure under the hood.)

## Underlying research

`docs/specs/msport-api-research.md` documents the full API survey —
endpoints, response shapes, market IDs, comparison with SportyBet.
```

- [ ] **Step 2: Update `README.md`**

The README currently has two places that enumerate bookmakers:

(a) The tagline (line 3) reads:
```
HTTP clients for scraping betting data from BetPawa, SportyBet, and Bet9ja.
```
Replace with:
```
HTTP clients for scraping betting data from BetPawa, SportyBet, Bet9ja, Betway, and MSport.
```

(b) The "Supported Bookmakers" table currently lists three rows. Replace the table with:

```markdown
## Supported Bookmakers

| Bookmaker | Countries |
|-----------|-----------|
| BetPawa   | ng, gh, ke, ug, tz, zm |
| SportyBet | ng, gh, ke |
| Bet9ja    | ng |
| Betway    | ng, gh, ke, tz, ug, zm |
| MSport    | ng, gh, ke |
```

(The Betway row is added here too — it's missing from the current README despite Betway already being part of the library. This is a small drive-by fix; if you'd rather keep the change MSport-only, drop the Betway row and submit it as a follow-up.)

- [ ] **Step 3: Commit**

```bash
git add docs/msport.md README.md
git commit -m "docs: add MSport client reference"
```

---

## Task 10: Final verification

**Files:** none (verification-only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all PASS, including the new MSport tests (estimated +15 tests).

- [ ] **Step 2: Run lint / typecheck if configured**

Run: `python -m ruff check src/ tests/ 2>/dev/null || echo "ruff not configured"`
Run: `python -m mypy src/ 2>/dev/null || echo "mypy not configured"`

If either is configured and reports errors, fix them before proceeding. If neither is configured, that's fine — skip.

- [ ] **Step 3: Smoke-test the public import surface**

Run:
```bash
python -c "
from bookieskit import MSport, BetPawa, SportyBet, Bet9ja, Betway
import bookieskit
assert bookieskit.__version__ == '0.4.0'
assert MSport.PLATFORM_KEY == 'msport'
assert MSport.DOMAINS.keys() == {'ng', 'gh', 'ke'}
print('OK')
"
```
Expected output: `OK`

- [ ] **Step 4: Confirm no stray uncommitted changes**

Run: `git status`
Expected: working tree clean.

- [ ] **Step 5: Print commit log for the feature**

Run: `git log --oneline -n 10`
Expected: 9 new commits from this plan (one per task) on top of the previous tip.

---

## Self-Review Checklist

(For the plan author — already completed.)

- ✅ Spec coverage — every section of `docs/specs/2026-05-05-msport-bookmaker-design.md` maps to a task: types (Task 1), registry (Task 2), builtins (Task 3), config (Task 4), client + 5 methods (Task 5), parser (Task 6), extractor (Task 7), exports + version (Task 8), docs (Task 9), verification (Task 10).
- ✅ No placeholders — every code step has full code; every command has expected output.
- ✅ Type consistency — `msport_id` and `msport` field names used uniformly across types, registry, builtins, parser. `PLATFORM_KEY = "msport"` matches the dispatcher entries in parser and extractor. Method signatures in client match the test expectations.
- ✅ Out-of-scope items from the spec (5-bookie audit example, live-flow demo, additional market mappings) are deliberately not present in any task — risk acknowledged in the spec's "Risk and follow-ups" section.
