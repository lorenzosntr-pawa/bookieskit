# Bookieskit v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Python library (`bookieskit`) that provides async+sync HTTP clients for scraping BetPawa, SportyBet, and Bet9ja betting data across all hierarchy levels (sports, countries, tournaments, events, event detail).

**Architecture:** Shared `BaseBookmaker` class handles HTTP lifecycle, retries, rate limiting, and country-to-domain resolution. Each bookmaker is a subclass that defines endpoints, headers, and platform-specific defaults. Sync interface wraps async core via `asyncio.run()`.

**Tech Stack:** Python 3.11+, httpx (async HTTP), pytest + pytest-asyncio + respx (testing), ruff (linting)

---

## File Structure

```
bookieskit/
├── src/
│   └── bookieskit/
│       ├── __init__.py          # Public exports: BetPawa, SportyBet, Bet9ja
│       ├── base.py              # BaseBookmaker: HTTP, retries, rate-limiting, sync/async
│       ├── config.py            # Default constants (timeout, retries, backoff)
│       ├── exceptions.py        # Exception hierarchy
│       ├── _sync.py             # Sync wrapper mixin
│       └── bookmakers/
│           ├── __init__.py      # Re-exports bookmaker classes
│           ├── betpawa.py       # BetPawa client
│           ├── sportybet.py     # SportyBet client
│           └── bet9ja.py        # Bet9ja client
├── tests/
│   ├── conftest.py              # Shared fixtures (mock clients)
│   ├── test_base.py             # BaseBookmaker tests (retries, rate-limiting)
│   ├── test_exceptions.py       # Exception hierarchy tests
│   ├── test_betpawa.py          # BetPawa endpoint tests
│   ├── test_sportybet.py        # SportyBet endpoint tests
│   ├── test_bet9ja.py           # Bet9ja endpoint tests
│   └── test_sync.py             # Sync wrapper tests
├── pyproject.toml               # Package config, dependencies
├── README.md                    # Usage docs
└── .gitignore                   # Python .gitignore
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/bookieskit/__init__.py`
- Create: `README.md`

- [ ] **Step 1: Initialize git repo**

```bash
cd c:/Users/loren/Desktop/betpawa/comparison/mvp1/bookieskit
git init
```

- [ ] **Step 2: Create pyproject.toml**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "bookieskit"
version = "0.1.0"
description = "HTTP clients for scraping betting data from BetPawa, SportyBet, and Bet9ja"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
    "ruff>=0.5",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I"]
```

- [ ] **Step 3: Create .gitignore**

Create `.gitignore`:

```
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.eggs/
*.egg
.venv/
venv/
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 4: Create package init**

Create `src/bookieskit/__init__.py`:

```python
"""Bookieskit — HTTP clients for betting data scraping."""

__version__ = "0.1.0"
```

- [ ] **Step 5: Create README.md**

Create `README.md`:

```markdown
# bookieskit

HTTP clients for scraping betting data from BetPawa, SportyBet, and Bet9ja.

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
```

- [ ] **Step 6: Create bookmakers subpackage init**

Create `src/bookieskit/bookmakers/__init__.py`:

```python
"""Bookmaker client implementations."""
```

- [ ] **Step 7: Install in dev mode and verify**

```bash
cd c:/Users/loren/Desktop/betpawa/comparison/mvp1/bookieskit
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
python -c "import bookieskit; print(bookieskit.__version__)"
```

Expected: `0.1.0`

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "feat: initial project scaffolding with pyproject.toml"
```

---

## Task 2: Exception Hierarchy

**Files:**
- Create: `src/bookieskit/exceptions.py`
- Create: `tests/test_exceptions.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_exceptions.py`:

```python
from bookieskit.exceptions import (
    BookiesKitError,
    RequestError,
    TimeoutError,
    RateLimitError,
    ResponseError,
    UnsupportedCountryError,
)


def test_exception_hierarchy():
    """All exceptions inherit from BookiesKitError."""
    assert issubclass(RequestError, BookiesKitError)
    assert issubclass(TimeoutError, BookiesKitError)
    assert issubclass(RateLimitError, BookiesKitError)
    assert issubclass(ResponseError, BookiesKitError)
    assert issubclass(UnsupportedCountryError, BookiesKitError)


def test_request_error_contains_context():
    err = RequestError(url="https://example.com/api", retries=3, message="Connection failed")
    assert err.url == "https://example.com/api"
    assert err.retries == 3
    assert "Connection failed" in str(err)


def test_timeout_error_contains_context():
    err = TimeoutError(url="https://example.com/api", retries=3, timeout=30.0)
    assert err.url == "https://example.com/api"
    assert err.retries == 3
    assert err.timeout == 30.0


def test_rate_limit_error_contains_context():
    err = RateLimitError(bookmaker="bet9ja", url="https://sports.bet9ja.com/api", retry_after=5.0)
    assert err.bookmaker == "bet9ja"
    assert err.retry_after == 5.0


def test_response_error_contains_status():
    err = ResponseError(url="https://example.com/api", status_code=500, body="Internal error")
    assert err.status_code == 500
    assert err.body == "Internal error"


def test_unsupported_country_error():
    err = UnsupportedCountryError(bookmaker="Bet9ja", country="gh", available=["ng"])
    assert "gh" in str(err)
    assert "ng" in str(err)
    assert "Bet9ja" in str(err)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_exceptions.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Write implementation**

Create `src/bookieskit/exceptions.py`:

```python
"""Exception hierarchy for bookieskit."""


class BookiesKitError(Exception):
    """Base exception for all bookieskit errors."""


class RequestError(BookiesKitError):
    """HTTP request failed after all retries (network, DNS, etc.)."""

    def __init__(self, url: str, retries: int, message: str):
        self.url = url
        self.retries = retries
        super().__init__(f"Request to {url} failed after {retries} retries: {message}")


class TimeoutError(BookiesKitError):
    """Request exceeded configured timeout."""

    def __init__(self, url: str, retries: int, timeout: float):
        self.url = url
        self.retries = retries
        self.timeout = timeout
        super().__init__(f"Request to {url} timed out after {timeout}s ({retries} retries)")


class RateLimitError(BookiesKitError):
    """Platform returned rate-limit signal (429 or equivalent)."""

    def __init__(self, bookmaker: str, url: str, retry_after: float | None = None):
        self.bookmaker = bookmaker
        self.url = url
        self.retry_after = retry_after
        msg = f"Rate limited by {bookmaker} at {url}"
        if retry_after:
            msg += f" (retry after {retry_after}s)"
        super().__init__(msg)


class ResponseError(BookiesKitError):
    """Got a response but it indicates failure."""

    def __init__(self, url: str, status_code: int, body: str = ""):
        self.url = url
        self.status_code = status_code
        self.body = body
        super().__init__(f"Response error {status_code} from {url}: {body}")


class UnsupportedCountryError(BookiesKitError):
    """Invalid country code for this bookmaker."""

    def __init__(self, bookmaker: str, country: str, available: list[str]):
        self.bookmaker = bookmaker
        self.country = country
        self.available = available
        super().__init__(
            f"{bookmaker} does not support '{country}'. Available: {available}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_exceptions.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/exceptions.py tests/test_exceptions.py
git commit -m "feat: add exception hierarchy"
```

---

## Task 3: Config Constants

**Files:**
- Create: `src/bookieskit/config.py`

- [ ] **Step 1: Create config module**

Create `src/bookieskit/config.py`:

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

# Retry-eligible HTTP status codes
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
```

- [ ] **Step 2: Commit**

```bash
git add src/bookieskit/config.py
git commit -m "feat: add default configuration constants"
```

---

## Task 4: BaseBookmaker (Async Core)

**Files:**
- Create: `src/bookieskit/base.py`
- Create: `tests/test_base.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write failing tests for BaseBookmaker**

Create `tests/conftest.py`:

```python
"""Shared test fixtures."""

import pytest

from bookieskit.base import BaseBookmaker


class MockBookmaker(BaseBookmaker):
    """Concrete subclass for testing base functionality."""

    DOMAINS = {
        "ng": "https://mock.example.com",
        "gh": "https://mock-gh.example.com",
    }
    DEFAULT_HEADERS = {"x-mock": "true"}
    MAX_CONCURRENT = 50
    REQUEST_DELAY = 0.0
    NAME = "MockBookmaker"


@pytest.fixture
def mock_bookmaker():
    return MockBookmaker(country="ng")
```

Create `tests/test_base.py`:

```python
import httpx
import pytest
import respx

from bookieskit.base import BaseBookmaker
from bookieskit.exceptions import (
    RateLimitError,
    RequestError,
    TimeoutError,
    UnsupportedCountryError,
)

from conftest import MockBookmaker


def test_unsupported_country_raises():
    with pytest.raises(UnsupportedCountryError) as exc_info:
        MockBookmaker(country="ke")
    assert "ke" in str(exc_info.value)
    assert "ng" in str(exc_info.value)


def test_base_url_resolved_from_country():
    client = MockBookmaker(country="ng")
    assert client.base_url == "https://mock.example.com"

    client_gh = MockBookmaker(country="gh")
    assert client_gh.base_url == "https://mock-gh.example.com"


@pytest.mark.asyncio
@respx.mock
async def test_async_context_manager():
    async with MockBookmaker(country="ng") as client:
        assert client._http_client is not None
    assert client._http_client.is_closed


@pytest.mark.asyncio
@respx.mock
async def test_successful_request():
    respx.get("https://mock.example.com/api/test").respond(
        json={"result": "ok"}
    )
    async with MockBookmaker(country="ng") as client:
        result = await client._request("GET", "/api/test")
    assert result == {"result": "ok"}


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_server_error():
    route = respx.get("https://mock.example.com/api/test")
    route.side_effect = [
        httpx.Response(500, json={"error": "internal"}),
        httpx.Response(500, json={"error": "internal"}),
        httpx.Response(200, json={"result": "ok"}),
    ]
    async with MockBookmaker(country="ng", backoff_factor=0.01) as client:
        result = await client._request("GET", "/api/test")
    assert result == {"result": "ok"}
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_raises_request_error_after_max_retries():
    respx.get("https://mock.example.com/api/test").respond(500)
    async with MockBookmaker(country="ng", max_retries=2, backoff_factor=0.01) as client:
        with pytest.raises(RequestError) as exc_info:
            await client._request("GET", "/api/test")
    assert exc_info.value.retries == 2


@pytest.mark.asyncio
@respx.mock
async def test_raises_rate_limit_error_on_429():
    respx.get("https://mock.example.com/api/test").respond(
        429, headers={"Retry-After": "5"}
    )
    async with MockBookmaker(country="ng", max_retries=1, backoff_factor=0.01) as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client._request("GET", "/api/test")
    assert exc_info.value.bookmaker == "MockBookmaker"


@pytest.mark.asyncio
@respx.mock
async def test_timeout_raises_timeout_error():
    respx.get("https://mock.example.com/api/test").mock(
        side_effect=httpx.ReadTimeout("timed out")
    )
    async with MockBookmaker(country="ng", max_retries=1, backoff_factor=0.01) as client:
        with pytest.raises(TimeoutError) as exc_info:
            await client._request("GET", "/api/test")
    assert exc_info.value.timeout == 30.0


@pytest.mark.asyncio
@respx.mock
async def test_custom_config_overrides_defaults():
    respx.get("https://mock.example.com/api/test").respond(json={"ok": True})
    async with MockBookmaker(
        country="ng", timeout=10.0, max_retries=5, max_concurrent=20
    ) as client:
        assert client._timeout == 10.0
        assert client._max_retries == 5
        assert client._max_concurrent == 20
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_base.py -v
```

Expected: FAIL (cannot import BaseBookmaker)

- [ ] **Step 3: Write BaseBookmaker implementation**

Create `src/bookieskit/base.py`:

```python
"""Base bookmaker client with shared HTTP, retry, and rate-limiting logic."""

import asyncio
from typing import Any

import httpx

from bookieskit.config import (
    DEFAULT_BACKOFF_FACTOR,
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_MAX_KEEPALIVE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    RETRYABLE_STATUS_CODES,
)
from bookieskit.exceptions import (
    RateLimitError,
    RequestError,
    TimeoutError,
    UnsupportedCountryError,
)


class BaseBookmaker:
    """Base class for all bookmaker HTTP clients.

    Subclasses must define:
        DOMAINS: dict[str, str] — country code to base URL mapping
        DEFAULT_HEADERS: dict[str, str] — platform-specific headers
        MAX_CONCURRENT: int — default max concurrent requests
        REQUEST_DELAY: float — default delay between requests (seconds)
        NAME: str — bookmaker display name
    """

    DOMAINS: dict[str, str] = {}
    DEFAULT_HEADERS: dict[str, str] = {}
    MAX_CONCURRENT: int = 50
    REQUEST_DELAY: float = 0.0
    NAME: str = "BaseBookmaker"

    def __init__(
        self,
        country: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        max_concurrent: int | None = None,
        request_delay: float | None = None,
    ):
        if country not in self.DOMAINS:
            raise UnsupportedCountryError(
                bookmaker=self.NAME,
                country=country,
                available=list(self.DOMAINS.keys()),
            )

        self._country = country
        self.base_url = self.DOMAINS[country]
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._max_concurrent = max_concurrent or self.MAX_CONCURRENT
        self._request_delay = request_delay if request_delay is not None else self.REQUEST_DELAY
        self._http_client: httpx.AsyncClient | None = None
        self._semaphore: asyncio.Semaphore | None = None

    def _build_headers(self) -> dict[str, str]:
        """Build request headers. Override in subclass for country-specific headers."""
        return dict(self.DEFAULT_HEADERS)

    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._build_headers(),
            timeout=httpx.Timeout(self._timeout),
            limits=httpx.Limits(
                max_connections=DEFAULT_MAX_CONNECTIONS,
                max_keepalive_connections=DEFAULT_MAX_KEEPALIVE,
            ),
        )
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        return self

    async def __aexit__(self, *args):
        if self._http_client:
            await self._http_client.aclose()

    def __enter__(self):
        """Sync context manager — creates event loop and async client."""
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self.__aenter__())
        return self

    def __exit__(self, *args):
        """Sync context manager cleanup."""
        self._loop.run_until_complete(self.__aexit__(*args))
        self._loop.close()
        self._loop = None

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with retry and rate-limiting.

        Args:
            method: HTTP method (GET, POST)
            path: URL path (appended to base_url)
            params: Query parameters
            json: JSON body (for POST)

        Returns:
            Parsed JSON response as dict

        Raises:
            TimeoutError: Request timed out after all retries
            RateLimitError: Platform returned 429
            RequestError: Request failed after all retries
        """
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            if attempt > 0:
                delay = self._backoff_factor * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

            try:
                async with self._semaphore:
                    if self._request_delay > 0:
                        await asyncio.sleep(self._request_delay)

                    response = await self._http_client.request(
                        method, path, params=params, json=json
                    )

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    last_error = RateLimitError(
                        bookmaker=self.NAME,
                        url=url,
                        retry_after=float(retry_after) if retry_after else None,
                    )
                    continue

                if response.status_code in RETRYABLE_STATUS_CODES:
                    last_error = RequestError(
                        url=url,
                        retries=attempt + 1,
                        message=f"HTTP {response.status_code}",
                    )
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException:
                last_error = TimeoutError(
                    url=url, retries=attempt + 1, timeout=self._timeout
                )
            except httpx.ConnectError as e:
                last_error = RequestError(
                    url=url, retries=attempt + 1, message=str(e)
                )

        raise last_error
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_base.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/base.py tests/conftest.py tests/test_base.py
git commit -m "feat: add BaseBookmaker with retry, rate-limiting, and dual context managers"
```

---

## Task 5: BetPawa Client

**Files:**
- Create: `src/bookieskit/bookmakers/betpawa.py`
- Create: `tests/test_betpawa.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_betpawa.py`:

```python
import pytest
import respx
from httpx import Response

from bookieskit.bookmakers.betpawa import BetPawa


def test_betpawa_country_ng_resolves_domain():
    client = BetPawa(country="ng")
    assert client.base_url == "https://www.betpawa.ng"


def test_betpawa_country_gh_resolves_domain():
    client = BetPawa(country="gh")
    assert client.base_url == "https://www.betpawa.com.gh"


def test_betpawa_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        BetPawa(country="xx")


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/categories/list/all").respond(
        json={
            "categories": [
                {"id": "2", "name": "Football"},
                {"id": "3", "name": "Basketball"},
            ]
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_sports()
    assert result["categories"][0]["name"] == "Football"


@pytest.mark.asyncio
@respx.mock
async def test_get_countries():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/categories/list/2").respond(
        json={
            "id": "2",
            "name": "Football",
            "regions": [
                {"id": "1", "name": "England", "competitions": []},
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_countries(sport_id="2")
    assert result["regions"][0]["name"] == "England"


@pytest.mark.asyncio
@respx.mock
async def test_get_tournaments():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/categories/list/2").respond(
        json={
            "id": "2",
            "name": "Football",
            "regions": [
                {
                    "id": "1",
                    "name": "England",
                    "competitions": [
                        {"id": "11965", "name": "Premier League"},
                    ],
                },
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_tournaments(sport_id="2", country_id="1")
    assert result["regions"][0]["competitions"][0]["name"] == "Premier League"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/events/lists/by-queries").respond(
        json={
            "results": [
                {
                    "id": "32299257",
                    "homeTeam": "Manchester City",
                    "awayTeam": "Liverpool",
                }
            ],
            "totalCount": 1,
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_events(tournament_id="11965")
    assert result["results"][0]["homeTeam"] == "Manchester City"


@pytest.mark.asyncio
@respx.mock
async def test_get_events_with_sport_id():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/events/lists/by-queries").respond(
        json={"results": [], "totalCount": 0}
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_events(tournament_id="11965", sport_id="3")
    assert result["totalCount"] == 0


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/events/32299257").respond(
        json={
            "id": "32299257",
            "homeTeam": "Manchester City",
            "awayTeam": "Liverpool",
            "markets": [
                {
                    "id": "3743",
                    "name": "1X2 - Full Time",
                    "row": [{"prices": [{"name": "1", "odds": 1.95}]}],
                }
            ],
        }
    )
    async with BetPawa(country="ng") as client:
        result = await client.get_event_detail(event_id="32299257")
    assert result["markets"][0]["name"] == "1X2 - Full Time"


@pytest.mark.asyncio
@respx.mock
async def test_betpawa_headers_include_brand():
    route = respx.get("https://www.betpawa.ng/api/sportsbook/v3/categories/list/all").respond(
        json={"categories": []}
    )
    async with BetPawa(country="ng") as client:
        await client.get_sports()
    assert route.calls[0].request.headers["x-pawa-brand"] == "betpawa-nigeria"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_betpawa.py -v
```

Expected: FAIL (cannot import BetPawa)

- [ ] **Step 3: Write BetPawa implementation**

Create `src/bookieskit/bookmakers/betpawa.py`:

```python
"""BetPawa client — supports ng, gh, ke, ug, tz, zm."""

import json
from typing import Any
from urllib.parse import quote

from bookieskit.base import BaseBookmaker
from bookieskit.config import BETPAWA_MAX_CONCURRENT, BETPAWA_REQUEST_DELAY


# Country code to x-pawa-brand header value
_BRAND_MAP = {
    "ng": "betpawa-nigeria",
    "gh": "betpawa-ghana",
    "ke": "betpawa-kenya",
    "ug": "betpawa-uganda",
    "tz": "betpawa-tanzania",
    "zm": "betpawa-zambia",
}


class BetPawa(BaseBookmaker):
    """HTTP client for BetPawa sportsbook API.

    Args:
        country: Country code (ng, gh, ke, ug, tz, zm)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 50)
        request_delay: Delay between requests in seconds (default: 0)
    """

    DOMAINS = {
        "ng": "https://www.betpawa.ng",
        "gh": "https://www.betpawa.com.gh",
        "ke": "https://www.betpawa.co.ke",
        "ug": "https://www.betpawa.co.ug",
        "tz": "https://www.betpawa.co.tz",
        "zm": "https://www.betpawa.co.zm",
    }
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "devicetype": "web",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    }
    MAX_CONCURRENT = BETPAWA_MAX_CONCURRENT
    REQUEST_DELAY = BETPAWA_REQUEST_DELAY
    NAME = "BetPawa"

    def _build_headers(self) -> dict[str, str]:
        headers = dict(self.DEFAULT_HEADERS)
        headers["x-pawa-brand"] = _BRAND_MAP.get(self._country, f"betpawa-{self._country}")
        return headers

    async def get_sports(self) -> dict[str, Any]:
        """Get all available sports/categories.

        Returns:
            Raw JSON with categories list.
        """
        return await self._request("GET", "/api/sportsbook/v3/categories/list/all")

    async def get_countries(self, sport_id: str) -> dict[str, Any]:
        """Get countries/regions for a sport.

        Args:
            sport_id: Sport category ID (e.g., "2" for Football)

        Returns:
            Raw JSON with regions and their competitions.
        """
        return await self._request("GET", f"/api/sportsbook/v3/categories/list/{sport_id}")

    async def get_tournaments(self, sport_id: str, country_id: str | None = None) -> dict[str, Any]:
        """Get tournaments/competitions for a sport (optionally filtered by country).

        Args:
            sport_id: Sport category ID (e.g., "2" for Football)
            country_id: Optional region ID to filter by

        Returns:
            Raw JSON with regions containing competitions.
        """
        return await self._request("GET", f"/api/sportsbook/v3/categories/list/{sport_id}")

    async def get_events(
        self,
        tournament_id: str,
        sport_id: str = "2",
        event_type: str = "UPCOMING",
        skip: int = 0,
        take: int = 100,
    ) -> dict[str, Any]:
        """Get events for a tournament/competition.

        Args:
            tournament_id: Competition ID (e.g., "11965")
            sport_id: Sport category ID (default: "2" for Football)
            event_type: "UPCOMING" or "LIVE" (default: "UPCOMING")
            skip: Pagination offset (default: 0)
            take: Page size (default: 100)

        Returns:
            Raw JSON with results array and totalCount.
        """
        query_payload = {
            "queries": [
                {
                    "query": {
                        "eventType": event_type,
                        "categories": [sport_id],
                        "zones": {"competitions": [tournament_id]},
                        "hasOdds": True,
                    },
                    "view": {},
                    "skip": skip,
                    "take": take,
                }
            ]
        }
        q_param = quote(json.dumps(query_payload, separators=(",", ":")))
        return await self._request(
            "GET", "/api/sportsbook/v3/events/lists/by-queries", params={"q": q_param}
        )

    async def get_event_detail(self, event_id: str) -> dict[str, Any]:
        """Get full event details including all markets and odds.

        Args:
            event_id: BetPawa event ID (e.g., "32299257")

        Returns:
            Raw JSON with event info, markets, and odds.
        """
        return await self._request("GET", f"/api/sportsbook/v3/events/{event_id}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_betpawa.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/bookmakers/betpawa.py tests/test_betpawa.py
git commit -m "feat: add BetPawa client with all data levels"
```

---

## Task 6: SportyBet Client

**Files:**
- Create: `src/bookieskit/bookmakers/sportybet.py`
- Create: `tests/test_sportybet.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sportybet.py`:

```python
import pytest
import respx
from httpx import Response

from bookieskit.bookmakers.sportybet import SportyBet


def test_sportybet_country_ng_resolves_domain():
    client = SportyBet(country="ng")
    assert client.base_url == "https://www.sportybet.com"


def test_sportybet_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        SportyBet(country="xx")


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/popularAndSportList").respond(
        json={
            "bizCode": 10000,
            "data": {
                "sportList": [
                    {"id": "sr:sport:1", "name": "Football"},
                    {"id": "sr:sport:2", "name": "Basketball"},
                ]
            },
        }
    )
    async with SportyBet(country="ng") as client:
        result = await client.get_sports()
    assert result["data"]["sportList"][0]["name"] == "Football"


@pytest.mark.asyncio
@respx.mock
async def test_get_countries():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/popularAndSportList").respond(
        json={
            "bizCode": 10000,
            "data": {
                "sportList": [
                    {
                        "id": "sr:sport:1",
                        "name": "Football",
                        "categories": [
                            {"id": "sr:category:1", "name": "England"},
                        ],
                    }
                ]
            },
        }
    )
    async with SportyBet(country="ng") as client:
        result = await client.get_countries(sport_id="sr:sport:1")
    assert result["data"]["sportList"][0]["categories"][0]["name"] == "England"


@pytest.mark.asyncio
@respx.mock
async def test_get_tournaments():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/popularAndSportList").respond(
        json={
            "bizCode": 10000,
            "data": {
                "sportList": [
                    {
                        "id": "sr:sport:1",
                        "categories": [
                            {
                                "id": "sr:category:1",
                                "name": "England",
                                "tournaments": [
                                    {"id": "sr:tournament:17", "name": "Premier League"},
                                ],
                            }
                        ],
                    }
                ]
            },
        }
    )
    async with SportyBet(country="ng") as client:
        result = await client.get_tournaments(sport_id="sr:sport:1")
    tournaments = result["data"]["sportList"][0]["categories"][0]["tournaments"]
    assert tournaments[0]["name"] == "Premier League"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.post("https://www.sportybet.com/api/ng/factsCenter/pcEvents").respond(
        json={
            "bizCode": 10000,
            "data": [
                {
                    "events": [
                        {
                            "eventId": "sr:match:61300947",
                            "homeTeamName": "Manchester City",
                            "awayTeamName": "Liverpool",
                        }
                    ]
                }
            ],
        }
    )
    async with SportyBet(country="ng") as client:
        result = await client.get_events(tournament_id="sr:tournament:17")
    assert result["data"][0]["events"][0]["homeTeamName"] == "Manchester City"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/event").respond(
        json={
            "bizCode": 10000,
            "data": {
                "eventId": "sr:match:61300947",
                "markets": [
                    {
                        "id": "1",
                        "desc": "1X2 - Full Time",
                        "outcomes": [
                            {"id": "1", "desc": "Home", "odds": "1.95"},
                        ],
                    }
                ],
            },
        }
    )
    async with SportyBet(country="ng") as client:
        result = await client.get_event_detail(event_id="sr:match:61300947")
    assert result["data"]["markets"][0]["desc"] == "1X2 - Full Time"


@pytest.mark.asyncio
@respx.mock
async def test_sportybet_headers():
    route = respx.get("https://www.sportybet.com/api/ng/factsCenter/popularAndSportList").respond(
        json={"bizCode": 10000, "data": {"sportList": []}}
    )
    async with SportyBet(country="ng") as client:
        await client.get_sports()
    assert route.calls[0].request.headers["clientid"] == "web"
    assert route.calls[0].request.headers["operid"] == "2"


@pytest.mark.asyncio
@respx.mock
async def test_sportybet_gh_uses_gh_path():
    respx.get("https://www.sportybet.com/api/gh/factsCenter/popularAndSportList").respond(
        json={"bizCode": 10000, "data": {"sportList": []}}
    )
    async with SportyBet(country="gh") as client:
        result = await client.get_sports()
    assert result["bizCode"] == 10000
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sportybet.py -v
```

Expected: FAIL (cannot import SportyBet)

- [ ] **Step 3: Write SportyBet implementation**

Create `src/bookieskit/bookmakers/sportybet.py`:

```python
"""SportyBet client — supports ng, gh, ke."""

import time
from typing import Any

from bookieskit.base import BaseBookmaker
from bookieskit.config import SPORTYBET_MAX_CONCURRENT, SPORTYBET_REQUEST_DELAY


class SportyBet(BaseBookmaker):
    """HTTP client for SportyBet API.

    SportyBet uses the same base domain for all countries but differentiates
    via the API path (e.g., /api/ng/... vs /api/gh/...).

    Args:
        country: Country code (ng, gh, ke)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 50)
        request_delay: Delay between requests in seconds (default: 0)
    """

    DOMAINS = {
        "ng": "https://www.sportybet.com",
        "gh": "https://www.sportybet.com",
        "ke": "https://www.sportybet.com",
    }
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "en",
        "clientid": "web",
        "operid": "2",
        "platform": "web",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    }
    MAX_CONCURRENT = SPORTYBET_MAX_CONCURRENT
    REQUEST_DELAY = SPORTYBET_REQUEST_DELAY
    NAME = "SportyBet"

    @property
    def _api_prefix(self) -> str:
        """Country-specific API path prefix."""
        return f"/api/{self._country}"

    def _timestamp(self) -> str:
        """Current timestamp in milliseconds for cache busting."""
        return str(int(time.time() * 1000))

    async def get_sports(self) -> dict[str, Any]:
        """Get all available sports with their category/tournament hierarchy.

        Returns:
            Raw JSON with sportList containing categories and tournaments.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/factsCenter/popularAndSportList",
            params={"sportId": "sr:sport:1", "timeline": "", "productId": "3", "_t": self._timestamp()},
        )

    async def get_countries(self, sport_id: str = "sr:sport:1") -> dict[str, Any]:
        """Get countries/categories for a sport.

        Args:
            sport_id: SportRadar sport ID (default: "sr:sport:1" for Football)

        Returns:
            Raw JSON — categories are nested under sportList[].categories.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/factsCenter/popularAndSportList",
            params={"sportId": sport_id, "timeline": "", "productId": "3", "_t": self._timestamp()},
        )

    async def get_tournaments(self, sport_id: str = "sr:sport:1") -> dict[str, Any]:
        """Get tournaments for a sport (nested under categories).

        Args:
            sport_id: SportRadar sport ID (default: "sr:sport:1" for Football)

        Returns:
            Raw JSON — tournaments nested under sportList[].categories[].tournaments.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/factsCenter/popularAndSportList",
            params={"sportId": sport_id, "timeline": "", "productId": "3", "_t": self._timestamp()},
        )

    async def get_events(
        self,
        tournament_id: str,
        sport_id: str = "sr:sport:1",
        market_ids: str = "1,18,10,29,11,26,36,14",
    ) -> dict[str, Any]:
        """Get events for a tournament.

        Args:
            tournament_id: SportRadar tournament ID (e.g., "sr:tournament:17")
            sport_id: SportRadar sport ID (default: "sr:sport:1")
            market_ids: Comma-separated market IDs to include (default: main markets)

        Returns:
            Raw JSON with events array containing markets and odds.
        """
        body = [
            {
                "sportId": sport_id,
                "marketId": market_ids,
                "tournamentId": [[tournament_id]],
            }
        ]
        return await self._request(
            "POST",
            f"{self._api_prefix}/factsCenter/pcEvents",
            json=body,
        )

    async def get_event_detail(self, event_id: str) -> dict[str, Any]:
        """Get full event details including all markets.

        Args:
            event_id: SportRadar match ID (e.g., "sr:match:61300947")

        Returns:
            Raw JSON with full event info and all available markets.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/factsCenter/event",
            params={"eventId": event_id, "productId": "3", "_t": self._timestamp()},
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_sportybet.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/bookmakers/sportybet.py tests/test_sportybet.py
git commit -m "feat: add SportyBet client with all data levels"
```

---

## Task 7: Bet9ja Client

**Files:**
- Create: `src/bookieskit/bookmakers/bet9ja.py`
- Create: `tests/test_bet9ja.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_bet9ja.py`:

```python
import pytest
import respx
from httpx import Response

from bookieskit.bookmakers.bet9ja import Bet9ja


def test_bet9ja_country_ng_resolves_domain():
    client = Bet9ja(country="ng")
    assert client.base_url == "https://sports.bet9ja.com"


def test_bet9ja_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError

    with pytest.raises(UnsupportedCountryError):
        Bet9ja(country="gh")


def test_bet9ja_default_rate_limits():
    client = Bet9ja(country="ng")
    assert client._max_concurrent == 15
    assert client._request_delay == 0.025


@pytest.mark.asyncio
@respx.mock
async def test_get_sports():
    respx.get("https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetSports").respond(
        json={
            "R": "OK",
            "D": {
                "PAL": {"sports": [{"id": "1", "name": "Football"}]}
            },
        }
    )
    async with Bet9ja(country="ng") as client:
        result = await client.get_sports()
    assert result["R"] == "OK"


@pytest.mark.asyncio
@respx.mock
async def test_get_events():
    respx.get("https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetEventsInGroupV2").respond(
        json={
            "R": "OK",
            "D": {
                "E": [
                    {"id": "707096003", "name": "Man City vs Liverpool"}
                ]
            },
        }
    )
    async with Bet9ja(country="ng") as client:
        result = await client.get_events(tournament_id="170880")
    assert result["D"]["E"][0]["name"] == "Man City vs Liverpool"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail():
    respx.get("https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetEvent").respond(
        json={
            "R": "D",
            "D": {
                "EXTID": "sr:match:61300947",
                "O": {
                    "S_1X2_1": "1.50",
                    "S_1X2_X": "3.20",
                    "S_1X2_2": "2.10",
                },
            },
        }
    )
    async with Bet9ja(country="ng") as client:
        result = await client.get_event_detail(event_id="707096003")
    assert result["D"]["O"]["S_1X2_1"] == "1.50"
    assert result["D"]["EXTID"] == "sr:match:61300947"


@pytest.mark.asyncio
@respx.mock
async def test_bet9ja_headers():
    route = respx.get("https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetSports").respond(
        json={"R": "OK", "D": {}}
    )
    async with Bet9ja(country="ng") as client:
        await client.get_sports()
    headers = route.calls[0].request.headers
    assert "Mozilla" in headers["user-agent"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_bet9ja.py -v
```

Expected: FAIL (cannot import Bet9ja)

- [ ] **Step 3: Write Bet9ja implementation**

Create `src/bookieskit/bookmakers/bet9ja.py`:

```python
"""Bet9ja client — supports ng only."""

from typing import Any

from bookieskit.base import BaseBookmaker
from bookieskit.config import BET9JA_MAX_CONCURRENT, BET9JA_REQUEST_DELAY

# Cache version used in Bet9ja API requests
_CACHE_VERSION = "1.301.2.225"


class Bet9ja(BaseBookmaker):
    """HTTP client for Bet9ja sportsbook API.

    Bet9ja has stricter rate limits (15 concurrent, 25ms delay) which are
    enforced by default.

    Args:
        country: Country code (only "ng" supported)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 15)
        request_delay: Delay between requests in seconds (default: 0.025)
    """

    DOMAINS = {
        "ng": "https://sports.bet9ja.com",
    }
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    }
    MAX_CONCURRENT = BET9JA_MAX_CONCURRENT
    REQUEST_DELAY = BET9JA_REQUEST_DELAY
    NAME = "Bet9ja"

    async def get_sports(self) -> dict[str, Any]:
        """Get all available sports with their category hierarchy.

        Returns:
            Raw JSON with R (status) and D (data) containing PAL hierarchy.
        """
        return await self._request(
            "GET",
            "/desktop/feapi/PalimpsestAjax/GetSports",
            params={"DISP": "0", "v_cache_version": _CACHE_VERSION},
        )

    async def get_countries(self) -> dict[str, Any]:
        """Get countries/categories (included in sports hierarchy).

        Returns:
            Same as get_sports — Bet9ja returns full hierarchy in one call.
        """
        return await self.get_sports()

    async def get_tournaments(self) -> dict[str, Any]:
        """Get tournaments (included in sports hierarchy).

        Returns:
            Same as get_sports — Bet9ja returns full hierarchy in one call.
        """
        return await self.get_sports()

    async def get_events(
        self,
        tournament_id: str,
        market_id: str = "1",
    ) -> dict[str, Any]:
        """Get events for a tournament/group.

        Args:
            tournament_id: Bet9ja group ID (e.g., "170880")
            market_id: Market group ID to include (default: "1" for 1X2)

        Returns:
            Raw JSON with R (status) and D.E (events array).
        """
        return await self._request(
            "GET",
            "/desktop/feapi/PalimpsestAjax/GetEventsInGroupV2",
            params={
                "GROUPID": tournament_id,
                "DISP": "0",
                "GROUPMARKETID": market_id,
                "v_cache_version": _CACHE_VERSION,
            },
        )

    async def get_event_detail(self, event_id: str) -> dict[str, Any]:
        """Get full event details with all odds.

        Args:
            event_id: Bet9ja event ID (e.g., "707096003")

        Returns:
            Raw JSON with R (status), D.O (flat odds dict), D.EXTID (SportRadar ID).
        """
        return await self._request(
            "GET",
            "/desktop/feapi/PalimpsestAjax/GetEvent",
            params={"EVENTID": event_id, "v_cache_version": _CACHE_VERSION},
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_bet9ja.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/bookmakers/bet9ja.py tests/test_bet9ja.py
git commit -m "feat: add Bet9ja client with all data levels"
```

---

## Task 8: Sync Wrapper Tests

**Files:**
- Create: `tests/test_sync.py`

- [ ] **Step 1: Write sync wrapper tests**

Create `tests/test_sync.py`:

```python
import respx

from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.sportybet import SportyBet
from bookieskit.bookmakers.bet9ja import Bet9ja


@respx.mock
def test_betpawa_sync_get_sports():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/categories/list/all").respond(
        json={"categories": [{"id": "2", "name": "Football"}]}
    )
    with BetPawa(country="ng") as client:
        result = client.get_sports()
    assert result["categories"][0]["name"] == "Football"


@respx.mock
def test_betpawa_sync_get_event_detail():
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/events/32299257").respond(
        json={"id": "32299257", "markets": []}
    )
    with BetPawa(country="ng") as client:
        result = client.get_event_detail(event_id="32299257")
    assert result["id"] == "32299257"


@respx.mock
def test_sportybet_sync_get_sports():
    respx.get("https://www.sportybet.com/api/ng/factsCenter/popularAndSportList").respond(
        json={"bizCode": 10000, "data": {"sportList": []}}
    )
    with SportyBet(country="ng") as client:
        result = client.get_sports()
    assert result["bizCode"] == 10000


@respx.mock
def test_bet9ja_sync_get_event_detail():
    respx.get("https://sports.bet9ja.com/desktop/feapi/PalimpsestAjax/GetEvent").respond(
        json={"R": "D", "D": {"O": {"S_1X2_1": "2.00"}}}
    )
    with Bet9ja(country="ng") as client:
        result = client.get_event_detail(event_id="123")
    assert result["D"]["O"]["S_1X2_1"] == "2.00"
```

- [ ] **Step 2: Run tests to verify they pass**

The sync wrapper is already implemented in `BaseBookmaker.__enter__`/`__exit__`. The sync methods need a small addition — we need sync method wrappers on each bookmaker method. Let me update the base class.

```bash
pytest tests/test_sync.py -v
```

If tests fail because sync methods don't exist (calling `client.get_sports()` without await returns a coroutine), we need to add the sync dispatch. Update `src/bookieskit/base.py` — add `__getattr__` to detect sync calls:

- [ ] **Step 3: Add sync method dispatch to BaseBookmaker**

Add this to the end of the `BaseBookmaker` class in `src/bookieskit/base.py`:

```python
    def __getattr__(self, name: str):
        """Dispatch sync calls to async methods when in sync mode."""
        attr = object.__getattribute__(self, name)
        if callable(attr) and hasattr(attr, "__func__"):
            # Check if we're in sync mode (have a _loop)
            loop = object.__getattribute__(self, "__dict__").get("_loop")
            if loop is not None:
                import asyncio
                import functools

                @functools.wraps(attr)
                def sync_wrapper(*args, **kwargs):
                    return loop.run_until_complete(attr(*args, **kwargs))

                return sync_wrapper
        return attr
```

Actually, a cleaner approach — override `__enter__` to return a sync proxy:

Replace the `__enter__`/`__exit__` in `src/bookieskit/base.py` with:

```python
    def __enter__(self):
        """Sync context manager — returns a SyncProxy that wraps async methods."""
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self.__aenter__())
        return _SyncProxy(self, self._loop)

    def __exit__(self, *args):
        """Sync context manager cleanup."""
        self._loop.run_until_complete(self.__aexit__(*args))
        self._loop.close()
        self._loop = None
```

And add the `_SyncProxy` class at the bottom of `src/bookieskit/base.py`:

```python
class _SyncProxy:
    """Proxy that wraps async methods as sync calls."""

    def __init__(self, instance: BaseBookmaker, loop: asyncio.AbstractEventLoop):
        self._instance = instance
        self._loop = loop

    def __getattr__(self, name: str):
        attr = getattr(self._instance, name)
        if callable(attr) and asyncio.iscoroutinefunction(attr):
            def sync_wrapper(*args, **kwargs):
                return self._loop.run_until_complete(attr(*args, **kwargs))
            sync_wrapper.__name__ = name
            sync_wrapper.__doc__ = attr.__doc__
            return sync_wrapper
        return attr
```

- [ ] **Step 4: Run all sync tests to verify they pass**

```bash
pytest tests/test_sync.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/base.py tests/test_sync.py
git commit -m "feat: add sync proxy for sync context manager usage"
```

---

## Task 9: Public Exports & Package Init

**Files:**
- Modify: `src/bookieskit/__init__.py`
- Modify: `src/bookieskit/bookmakers/__init__.py`

- [ ] **Step 1: Update bookmakers __init__.py**

Update `src/bookieskit/bookmakers/__init__.py`:

```python
"""Bookmaker client implementations."""

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.sportybet import SportyBet

__all__ = ["BetPawa", "SportyBet", "Bet9ja"]
```

- [ ] **Step 2: Update package __init__.py**

Update `src/bookieskit/__init__.py`:

```python
"""Bookieskit — HTTP clients for betting data scraping."""

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.sportybet import SportyBet

__all__ = ["BetPawa", "SportyBet", "Bet9ja"]
__version__ = "0.1.0"
```

- [ ] **Step 3: Verify top-level imports work**

```bash
python -c "from bookieskit import BetPawa, SportyBet, Bet9ja; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/bookieskit/__init__.py src/bookieskit/bookmakers/__init__.py
git commit -m "feat: expose BetPawa, SportyBet, Bet9ja from package root"
```

---

## Task 10: Documentation

**Files:**
- Create: `docs/betpawa.md`
- Create: `docs/sportybet.md`
- Create: `docs/bet9ja.md`

- [ ] **Step 1: Create BetPawa docs**

Create `docs/betpawa.md`:

```markdown
# BetPawa

## Supported Countries

| Code | Domain |
|------|--------|
| ng | betpawa.ng |
| gh | betpawa.com.gh |
| ke | betpawa.co.ke |
| ug | betpawa.co.ug |
| tz | betpawa.co.tz |
| zm | betpawa.co.zm |

## Methods

### `get_sports()`

Returns all sport categories.

**Endpoint:** `GET /api/sportsbook/v3/categories/list/all`

**Response:**
```json
{
  "categories": [
    {"id": "2", "name": "Football"},
    {"id": "3", "name": "Basketball"}
  ]
}
```

### `get_countries(sport_id)`

Returns regions/countries for a sport.

**Endpoint:** `GET /api/sportsbook/v3/categories/list/{sport_id}`

**Response:**
```json
{
  "id": "2",
  "name": "Football",
  "regions": [
    {
      "id": "1",
      "name": "England",
      "competitions": [{"id": "11965", "name": "Premier League"}]
    }
  ]
}
```

### `get_tournaments(sport_id, country_id=None)`

Same endpoint as `get_countries` — tournaments are nested under regions.

### `get_events(tournament_id, sport_id="2", event_type="UPCOMING", skip=0, take=100)`

Returns events for a competition.

**Endpoint:** `GET /api/sportsbook/v3/events/lists/by-queries?q={encoded_json}`

**Response:**
```json
{
  "results": [
    {
      "id": "32299257",
      "homeTeam": "Manchester City",
      "awayTeam": "Liverpool",
      "kickoffTime": 1704067200000,
      "markets": [...]
    }
  ],
  "totalCount": 50
}
```

### `get_event_detail(event_id)`

Returns full event with all markets and odds.

**Endpoint:** `GET /api/sportsbook/v3/events/{event_id}`

**Response:**
```json
{
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
            {"name": "2", "odds": 2.10}
          ]
        }
      ]
    }
  ],
  "widgets": [
    {"type": "SPORTRADAR", "value": "sr:match:61300947"}
  ]
}
```
```

- [ ] **Step 2: Create SportyBet docs**

Create `docs/sportybet.md`:

```markdown
# SportyBet

## Supported Countries

| Code | Domain | API Path |
|------|--------|----------|
| ng | sportybet.com | /api/ng/... |
| gh | sportybet.com | /api/gh/... |
| ke | sportybet.com | /api/ke/... |

SportyBet uses the same domain for all countries — the country is in the API path.

## Methods

### `get_sports()`

Returns sports with full category/tournament hierarchy.

**Endpoint:** `GET /api/{country}/factsCenter/popularAndSportList`

**Response:**
```json
{
  "bizCode": 10000,
  "data": {
    "sportList": [
      {
        "id": "sr:sport:1",
        "name": "Football",
        "categories": [
          {
            "id": "sr:category:1",
            "name": "England",
            "tournaments": [
              {"id": "sr:tournament:17", "name": "Premier League"}
            ]
          }
        ]
      }
    ]
  }
}
```

### `get_countries(sport_id="sr:sport:1")`

Same endpoint as `get_sports` — categories are nested under each sport.

### `get_tournaments(sport_id="sr:sport:1")`

Same endpoint — tournaments nested under categories.

### `get_events(tournament_id, sport_id="sr:sport:1", market_ids="1,18,10,29,11,26,36,14")`

Returns events with selected markets via POST.

**Endpoint:** `POST /api/{country}/factsCenter/pcEvents`

**Market IDs:** 1=1X2, 18=O/U, 10=DC, 29=BTTS, 11=DNB, 26=HT/FT, 36=CS, 14=HT 1X2

**Response:**
```json
{
  "bizCode": 10000,
  "data": [
    {
      "events": [
        {
          "eventId": "sr:match:61300947",
          "homeTeamName": "Manchester City",
          "awayTeamName": "Liverpool",
          "markets": [
            {
              "id": "1",
              "desc": "1X2 - Full Time",
              "outcomes": [
                {"id": "1", "desc": "Home", "odds": "1.95"}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### `get_event_detail(event_id)`

Returns full event with all available markets.

**Endpoint:** `GET /api/{country}/factsCenter/event?eventId={id}&productId=3`

**Response:**
```json
{
  "bizCode": 10000,
  "data": {
    "eventId": "sr:match:61300947",
    "markets": [
      {
        "id": "1",
        "desc": "1X2 - Full Time",
        "specifier": null,
        "outcomes": [
          {"id": "1", "desc": "Home", "odds": "1.95", "isActive": 1}
        ]
      },
      {
        "id": "18",
        "desc": "Over/Under",
        "specifier": "total=2.5",
        "outcomes": [
          {"id": "1", "desc": "Over", "odds": "1.80"}
        ]
      }
    ]
  }
}
```

## Notes

- All IDs are SportRadar format (e.g., `sr:match:61300947`, `sr:tournament:17`)
- `bizCode: 10000` means success
- Specifier format for parameterized markets: `key=value` (e.g., `total=2.5`, `hcp=-0.5`)
```

- [ ] **Step 3: Create Bet9ja docs**

Create `docs/bet9ja.md`:

```markdown
# Bet9ja

## Supported Countries

| Code | Domain |
|------|--------|
| ng | sports.bet9ja.com |

## Rate Limiting

Bet9ja is rate-limit sensitive. Defaults:
- Max concurrent: 15
- Request delay: 25ms

## Methods

### `get_sports()`

Returns full sport/category/tournament hierarchy in one call.

**Endpoint:** `GET /desktop/feapi/PalimpsestAjax/GetSports?DISP=0&v_cache_version=1.301.2.225`

**Response:**
```json
{
  "R": "OK",
  "D": {
    "PAL": {
      "sports": [{"id": "1", "name": "Football"}]
    }
  }
}
```

### `get_countries()` / `get_tournaments()`

Same as `get_sports()` — Bet9ja returns the full hierarchy in one call.

### `get_events(tournament_id, market_id="1")`

Returns events for a tournament group.

**Endpoint:** `GET /desktop/feapi/PalimpsestAjax/GetEventsInGroupV2`

**Response:**
```json
{
  "R": "OK",
  "D": {
    "E": [
      {"id": "707096003", "name": "Man City vs Liverpool"}
    ]
  }
}
```

### `get_event_detail(event_id)`

Returns full event with flat odds structure.

**Endpoint:** `GET /desktop/feapi/PalimpsestAjax/GetEvent?EVENTID={id}`

**Response:**
```json
{
  "R": "D",
  "D": {
    "EXTID": "sr:match:61300947",
    "O": {
      "S_1X2_1": "1.50",
      "S_1X2_X": "3.20",
      "S_1X2_2": "2.10",
      "S_OU@2.5_O": "1.80",
      "S_OU@2.5_U": "2.00"
    }
  }
}
```

## Response Codes

- `"R": "OK"` or `"R": "D"` = success
- `"R": "E"` = not found / error

## Odds Key Format

```
S_{MARKET}[@{PARAM}]_{OUTCOME}

Examples:
  S_1X2_1          → 1X2 Home
  S_1X2_X          → 1X2 Draw
  S_OU@2.5_O       → Over 2.5
  S_AH@-0.5_1      → Asian Handicap -0.5 Home
  S_GGNG_Y         → BTTS Yes
```
```

- [ ] **Step 4: Commit**

```bash
git add docs/
git commit -m "docs: add per-bookmaker API documentation"
```

---

## Task 11: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

```bash
pytest -v
```

Expected: All tests PASS

- [ ] **Step 2: Run linter**

```bash
ruff check src/ tests/
```

Expected: No errors

- [ ] **Step 3: Verify package installs cleanly**

```bash
pip install -e ".[dev]"
python -c "from bookieskit import BetPawa, SportyBet, Bet9ja; print('All imports OK')"
```

Expected: `All imports OK`

- [ ] **Step 4: Test a quick integration script (optional, real API)**

```python
# integration_test.py (run manually, not in CI)
import asyncio
from bookieskit import BetPawa

async def main():
    async with BetPawa(country="ng") as client:
        sports = await client.get_sports()
        print(f"Found {len(sports.get('categories', []))} sports")

asyncio.run(main())
```

- [ ] **Step 5: Final commit (if any linting fixes)**

```bash
git add -A
git commit -m "chore: linting fixes and final cleanup"
```
