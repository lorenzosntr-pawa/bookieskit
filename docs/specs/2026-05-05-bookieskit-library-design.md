# Bookieskit — Betting Scraper Library Design

## Overview

**bookieskit** is a standalone Python library that provides HTTP clients for scraping betting data from multiple bookmakers (BetPawa, SportyBet, Bet9ja). It exposes a clean, unified API for fetching sports, countries, tournaments, events, and full event detail (markets/odds) from each platform.

**Key principles:**
- Each data level is independently callable (no forced hierarchy traversal)
- Multi-country support — same bookmaker, different domains
- Async core with sync wrapper — one class, two modes
- Built-in retries and rate limiting with sensible defaults
- v1 returns raw JSON responses; parsing/mapping are future layers

## Audience

Internal use — reusable across projects (bots, data pipelines, different frontends) without importing the full MVP1 application.

## Project Structure

```
bookieskit/
├── src/
│   └── bookieskit/
│       ├── __init__.py          # Public exports: BetPawa, SportyBet, Bet9ja
│       ├── base.py              # BaseBookmaker (HTTP, retries, rate-limiting)
│       ├── config.py            # Timeout, retry, concurrency defaults
│       ├── exceptions.py        # Exception hierarchy
│       ├── _sync.py             # Sync wrapper utility
│       └── bookmakers/
│           ├── __init__.py
│           ├── betpawa.py       # BetPawa client
│           ├── sportybet.py     # SportyBet client
│           └── bet9ja.py        # Bet9ja client
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── test_betpawa.py
│   ├── test_sportybet.py
│   └── test_bet9ja.py
├── docs/
│   ├── betpawa.md               # BetPawa endpoints & response shapes
│   ├── sportybet.md             # SportyBet endpoints & response shapes
│   └── bet9ja.md                # Bet9ja endpoints & response shapes
├── pyproject.toml
├── README.md
└── .gitignore
```

## Architecture

### Shared Base + Bookmaker Subclasses

A `BaseBookmaker` class handles all shared concerns. Each bookmaker subclass defines only what's unique to that platform.

**BaseBookmaker provides:**
- `httpx.AsyncClient` lifecycle (connection pooling, headers)
- Retry logic (configurable attempts, exponential backoff)
- Rate limiting (configurable delay, max concurrent requests)
- Timeout handling
- Context manager support (`with` / `async with`)
- Country-to-domain resolution

**Each bookmaker subclass defines:**
- `DOMAINS` mapping (country code → base URL)
- Default headers specific to the platform
- Endpoint paths for each data level
- Platform-specific rate-limit defaults

### Consumer API

All five data levels, independently callable:

```python
from bookieskit import BetPawa

# Async usage
async with BetPawa(country="ng") as client:
    sports = await client.get_sports()
    countries = await client.get_countries(sport_id="1")
    tournaments = await client.get_tournaments(country_id="5")
    events = await client.get_events(tournament_id="123")
    detail = await client.get_event_detail(event_id="456")

# Sync usage (identical interface, no await)
with BetPawa(country="ng") as client:
    sports = client.get_sports()
    detail = client.get_event_detail(event_id="456")
```

### Configuration

```python
client = Bet9ja(
    country="ng",
    timeout=15.0,         # seconds (default: 30)
    max_retries=5,        # attempts (default: 3)
    backoff_factor=2.0,   # exponential base (default: 1.0)
    max_concurrent=10,    # parallel requests (default: platform-specific)
    request_delay=0.05,   # seconds between requests (default: platform-specific)
)
```

### Return Values (v1)

Raw dictionaries — the JSON response from the bookmaker API, unmodified. Structure varies per platform. No parsing, no dataclasses — that's a future layer.

```python
sports = await client.get_sports()
# Returns: {"data": [{"id": "1", "name": "Football", ...}, ...]}
```

## Multi-Country & Domain Resolution

Each bookmaker has a `DOMAINS` mapping. The `country` parameter (required, no implicit default) resolves to the correct base URL.

### Domain Mappings

**BetPawa:**
| Country | Domain |
|---------|--------|
| ng | `https://www.betpawa.ng` |
| gh | `https://www.betpawa.com.gh` |
| ke | `https://www.betpawa.co.ke` |
| ug | `https://www.betpawa.co.ug` |
| tz | `https://www.betpawa.co.tz` |
| zm | `https://www.betpawa.co.zm` |

**SportyBet:**
| Country | Domain | Note |
|---------|--------|------|
| ng | `https://www.sportybet.com` | Uses `/api/ng/...` path |
| gh | `https://www.sportybet.com` | Uses `/api/gh/...` path |
| ke | `https://www.sportybet.com` | Uses `/api/ke/...` path |

**Bet9ja:**
| Country | Domain |
|---------|--------|
| ng | `https://sports.bet9ja.com` |

### Error on Invalid Country

```python
client = Bet9ja(country="gh")
# raises: UnsupportedCountryError("Bet9ja does not support 'gh'. Available: ['ng']")
```

### Country-Dependent Headers

Headers that vary by country (e.g., `x-pawa-brand: betpawa-nigeria` vs `betpawa-ghana`) are auto-resolved from the `country` parameter.

## Error Handling

### Exception Hierarchy

```python
from bookieskit.exceptions import (
    BookiesKitError,          # Base — catch-all for any library error
    RequestError,             # HTTP request failed (network, DNS, etc.)
    TimeoutError,             # Request exceeded timeout
    RateLimitError,           # Platform returned 429 or known rate-limit signal
    UnsupportedCountryError,  # Invalid country for bookmaker
    ResponseError,            # Got a response but it indicates failure
)
```

### Behavior

- Retries are attempted for: network errors, 5xx responses, 429 responses
- After all retries exhausted: raises the appropriate exception (no silent failures)
- Exceptions include context: URL attempted, status code, retry count

```python
try:
    detail = await client.get_event_detail(event_id="456")
except TimeoutError as e:
    print(f"Failed after {e.retries} retries: {e.url}")
except RateLimitError as e:
    print(f"Rate limited by {e.bookmaker}: retry after {e.retry_after}s")
```

## Resilience Defaults

### Retry Configuration

| Setting | Default | Configurable |
|---------|---------|-------------|
| `max_retries` | 3 | Yes |
| `backoff_factor` | 1.0 (delays: 1s, 2s, 4s) | Yes |
| `retry_on` | Network errors, 5xx, 429 | No (fixed set) |
| `timeout` | 30s | Yes |

### Rate Limiting (per-client instance)

| Bookmaker | `max_concurrent` | `request_delay` |
|-----------|-------------------|-----------------|
| BetPawa | 50 | 0ms |
| SportyBet | 50 | 0ms |
| Bet9ja | 15 | 25ms |

## Sync/Async Implementation

### Strategy

One codebase — async is the real implementation, sync is a thin wrapper using `asyncio.run()`.

### Single Class, Two Modes

The bookmaker class supports both context managers. The mode is determined by which one you use:

```python
# Async mode
async with BetPawa(country="ng") as client:
    data = await client.get_sports()

# Sync mode
with BetPawa(country="ng") as client:
    data = client.get_sports()
```

No separate `AsyncBetPawa` vs `BetPawa` — one import, one class.

## Packaging & Dependencies

### Runtime Dependencies

- `httpx>=0.27` — the only runtime dependency

### Dev Dependencies

- `pytest>=8.0`
- `pytest-asyncio>=0.23`
- `respx>=0.21` (httpx mocking)
- `ruff>=0.5` (linting + formatting)

### Python Version

- 3.11+ (for modern asyncio features, `TaskGroup`, etc.)

### Installation

```bash
pip install git+https://github.com/<user>/bookieskit.git
```

## Testing Strategy

### Unit Tests (mocked HTTP)

Using `respx` to mock each bookmaker's API responses with real response fixtures captured from MVP1:

```python
@respx.mock
async def test_betpawa_get_sports(betpawa_client):
    respx.get("https://www.betpawa.ng/api/sportsbook/v3/sports").respond(
        json={"data": [{"id": "1", "name": "Football"}]}
    )
    result = await betpawa_client.get_sports()
    assert result["data"][0]["name"] == "Football"
```

### Integration Tests

Marked `@pytest.mark.integration`, skipped by default. Hit real APIs to verify endpoints haven't changed.

### Coverage

Test per data level (`get_sports`, `get_countries`, `get_tournaments`, `get_events`, `get_event_detail`) for each bookmaker, in both sync and async modes.

## Documentation

### README.md

Quick start, installation instructions, usage examples for each bookmaker and data level, configuration options.

### docs/ Folder

One page per bookmaker documenting:
- Available countries/domains
- API endpoints the client calls
- Response shapes (example JSON for each data level)
- Platform-specific quirks or limitations

### Docstrings

All public methods have docstrings with parameter descriptions and return type hints, visible in IDE autocomplete.

## Future Layers (Not in v1)

These are explicitly out of scope for v1 but designed to slot in cleanly:

1. **Parsing layer** — transform raw JSON into typed dataclasses/Pydantic models
2. **Market mapping** — normalize market IDs across platforms (128 mappings from MVP1)
3. **Event matching** — cross-platform event linking via SportRadar IDs
4. **Batch orchestration** — priority queues, parallel batch scraping
5. **Additional bookmakers** — 1xbet, nairabet, etc. (just add a subclass)

## Reference

This library extracts and generalizes the scraping logic from the [MVP1 odds comparison project](../../../). The following MVP1 modules serve as reference implementations:

- `src/scraping/` — Event coordinator, platform-specific fetchers
- `src/market_mapping/` — Market ID mappings (future layer)
- `src/matching/` — SportRadar ID matching (future layer)
