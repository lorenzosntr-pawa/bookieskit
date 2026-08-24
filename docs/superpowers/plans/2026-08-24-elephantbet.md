# ElephantBet Bookmaker Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ElephantBet (Mozambique) as the eighth bookmaker in `bookieskit`, with core soccer markets normalised and cross-book matching via SportRadar ids.

**Architecture:** A `BaseBookmaker` subclass hitting the BtoBet REST API at `sports-core.elephantbet.com`, following the existing seven-book pattern exactly. Markets flow through the existing `MarketRegistry` via a new `_parse_elephantbet` dispatch arm. No changes to `BaseBookmaker`.

**Tech Stack:** Python 3.11+, httpx, respx (test mocks), pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-08-24-elephantbet-design.md`

## Global Constraints

- `src/` stays 100% ruff-clean (`ruff check .`).
- Run tests with `.venv/Scripts/python.exe -m pytest`.
- Market ids and outcome labels come from captured payloads, never guessed.
- Fixtures are committed in the same PR as the code that reads them.
- Any `src/bookieskit/**` change needs a doc surface change in the same PR (CI `docs-sync` job).
- Conventional-commit messages; frequent commits.
- Country code is `mz` only. `ao`/`sl`/`mw` are out of scope (WAF 403).

## Verified API facts

All confirmed live on 2026-08-24. These are the values the tasks below use.

| Fact | Value |
|---|---|
| Base URL | `https://sports-core.elephantbet.com` |
| Sports | `GET /rest/FEWFixture/Sports?culture=pt` |
| Fixtures tree | `GET /rest/FEWFixture/FixturesMenu?Culture=pt` |
| Events | `GET /rest/FEMobile/GetGroupedMatches?TournamentData[]=<tid>&Culture=pt&Limit=<n>` |
| Event detail | `GET /rest/FEWMatches/MatchOdds?MatchID=<mid>&Culture=pt` |
| Auth | none |
| `Culture` | mandatory; omitting it returns HTTP 400 |

Match-level fields (from `GetGroupedMatches`):

```
mid   5998731        match id
brid  "72221172"     SportRadar id  (verified: Betway event 72221172 = "Fulham FC vs. Chelsea FC")
ht    "Fulham FC"    home team
at    "Chelsea FC"   away team
d     "2026-08-24 19:00"   kickoff, naive local string
sid   1              sport id (1 = soccer)
tid   1428062        tournament id (Premier League)
```

Market ids (from `MatchOdds`, 153 distinct markets on one fixture):

| Canonical | id | `n` | Outcomes (`id`, `n`) | Line |
|---|---|---|---|---|
| `1x2_ft` | `3` | `1X2` | 615 `1`, 616 `X`, 617 `2` | — |
| `over_under_ft` | `29` | `Acima / Abaixo` | `Acima` / `Abaixo` | `sbv` e.g. `"2.5"` |
| `btts_ft` | `7` | `Ambas as equipas a marcar` | 626 `Sim`, 627 `Não` | — |
| `double_chance_ft` | `17` | `HIPÓTESE DUPLA` | 662 `1X`, 663 `12`, 664 `X2` | — |

Odds are **strings** (`"3.96"`). Outcome `eon` carries team-name placeholders `{{HomeTeam}}` / `{{AwayTeam}}` (analogous to Betway's `__HOME__`).

Event-detail shape: `{"s": null, "t": [{"id": 19, "n": "Principal", "o": [<market>, ...]}]}` — markets live under tabs in `t[].o[]`.

---

### Task 1: Client skeleton and `get_sports`

**Files:**
- Create: `src/bookieskit/bookmakers/elephantbet.py`
- Modify: `src/bookieskit/config.py`, `src/bookieskit/bookmakers/__init__.py`, `src/bookieskit/__init__.py`
- Test: `tests/test_elephantbet.py`

**Interfaces:**
- Consumes: `BaseBookmaker` from `bookieskit.base`.
- Produces: `ElephantBet` class with `DOMAINS`, `NAME = "ElephantBet"`, `PLATFORM_KEY = "elephantbet"`, `async get_sports() -> dict`.

- [ ] **Step 1: Write the failing test**

```python
import pytest
import respx
from httpx import Response

from bookieskit import ElephantBet


def test_elephantbet_country_mz_resolves_domain():
    client = ElephantBet(country="mz")
    assert client.base_url == "https://sports-core.elephantbet.com"


def test_elephantbet_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError
    with pytest.raises(UnsupportedCountryError):
        ElephantBet(country="ao")


@pytest.mark.asyncio
@respx.mock
async def test_get_sports_sends_culture():
    route = respx.get(
        "https://sports-core.elephantbet.com/rest/FEWFixture/Sports"
    ).mock(return_value=Response(200, json=[{"id": 1, "n": "Futebol", "c": "soccer"}]))
    async with ElephantBet(country="mz") as client:
        data = await client.get_sports()
    assert data[0]["c"] == "soccer"
    # Culture is mandatory upstream: omitting it returns HTTP 400.
    assert route.calls.last.request.url.params["culture"] == "pt"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_elephantbet.py -v`
Expected: FAIL — `ImportError: cannot import name 'ElephantBet'`

- [ ] **Step 3: Add config constants**

In `src/bookieskit/config.py`, next to the other per-platform constants:

```python
ELEPHANTBET_MAX_CONCURRENT = 50
ELEPHANTBET_REQUEST_DELAY = 0.0
```

- [ ] **Step 4: Write the client**

Create `src/bookieskit/bookmakers/elephantbet.py`:

```python
"""HTTP client for ElephantBet (BtoBet platform).

ElephantBet runs BtoBet ``Sb.WebApi`` v8.2.0.29, which publishes an OpenAPI
spec at ``/swagger/v1/swagger.json``. The endpoints used here are the ones
the brand's own SPA calls, not the superficially-similar alternatives in the
spec: ``FEMobile/GetGroupedMatches`` and ``FEWMatches/MatchOdds`` return
data, while ``FEWFixture/TournamentMatchOdds`` and ``FEMobile/GetMatchOdds``
answer ``204 No Content`` for the same arguments.

Only Mozambique is supported. ElephantBet also has Angola, Sierra Leone and
Malawi brands, but their hosts sit behind a WAF that returns 403 to
non-browser clients, so they cannot be verified and are not listed.
"""

from typing import Any

from bookieskit.base import BaseBookmaker
from bookieskit.config import (
    ELEPHANTBET_MAX_CONCURRENT,
    ELEPHANTBET_REQUEST_DELAY,
)

# Country -> BtoBet `Culture` value. The API rejects requests without it.
_CULTURE_PER_COUNTRY = {"mz": "pt"}


class ElephantBet(BaseBookmaker):
    """HTTP client for the ElephantBet sportsbook API.

    Args:
        country: Country code (only "mz" supported)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 50)
        request_delay: Delay between requests in seconds (default: 0)
    """

    DOMAINS = {
        "mz": "https://sports-core.elephantbet.com",
    }
    DEFAULT_HEADERS = {
        "accept": "application/json",
        "accept-language": "pt-PT,pt;q=0.9,en;q=0.8",
        "origin": "https://www.elephantbet.co.mz",
        "referer": "https://www.elephantbet.co.mz/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",  # noqa: E501
    }
    MAX_CONCURRENT = ELEPHANTBET_MAX_CONCURRENT
    REQUEST_DELAY = ELEPHANTBET_REQUEST_DELAY
    NAME = "ElephantBet"
    PLATFORM_KEY = "elephantbet"

    @property
    def _culture(self) -> str:
        """BtoBet culture code for this country."""
        return _CULTURE_PER_COUNTRY.get(self._country, "pt")

    async def get_sports(self) -> dict[str, Any]:
        """Get all available sports.

        Returns:
            Raw JSON list; each entry has ``id``, ``n`` (localised name) and
            ``c`` (stable slug, e.g. ``"soccer"``). The catalogue includes
            virtual and Zoom products, so filter on ``c``, not on position.
        """
        return await self._request(
            "GET",
            "/rest/FEWFixture/Sports",
            params={"culture": self._culture},
        )
```

- [ ] **Step 5: Export the client**

In `src/bookieskit/bookmakers/__init__.py` add the import and `__all__` entry; in `src/bookieskit/__init__.py` add the same, keeping both lists in sync.

```python
from bookieskit.bookmakers.elephantbet import ElephantBet
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_elephantbet.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add src/bookieskit/bookmakers/elephantbet.py src/bookieskit/config.py src/bookieskit/bookmakers/__init__.py src/bookieskit/__init__.py tests/test_elephantbet.py
git commit -m "feat(elephantbet): client skeleton with get_sports"
```

---

### Task 2: Catalogue and event methods

**Files:**
- Modify: `src/bookieskit/bookmakers/elephantbet.py`
- Test: `tests/test_elephantbet.py`

**Interfaces:**
- Consumes: `ElephantBet` from Task 1.
- Produces: `get_countries(sport_id)`, `get_tournaments(sport_id)`, `get_events(tournament_id, limit)`, `get_event_detail(event_id)` — all `async`, all returning raw JSON.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
@respx.mock
async def test_get_events_uses_grouped_matches():
    route = respx.get(
        "https://sports-core.elephantbet.com/rest/FEMobile/GetGroupedMatches"
    ).mock(return_value=Response(200, json=[{"id": 1, "t": []}]))
    async with ElephantBet(country="mz") as client:
        await client.get_events(tournament_id="1428062", limit=5)
    params = route.calls.last.request.url.params
    assert params["TournamentData[]"] == "1428062"
    assert params["Culture"] == "pt"
    assert params["Limit"] == "5"


@pytest.mark.asyncio
@respx.mock
async def test_get_event_detail_uses_fewmatches():
    route = respx.get(
        "https://sports-core.elephantbet.com/rest/FEWMatches/MatchOdds"
    ).mock(return_value=Response(200, json={"s": None, "t": []}))
    async with ElephantBet(country="mz") as client:
        await client.get_event_detail("5998731")
    assert route.calls.last.request.url.params["MatchID"] == "5998731"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_elephantbet.py -v`
Expected: FAIL — `AttributeError: 'ElephantBet' object has no attribute 'get_events'`

- [ ] **Step 3: Implement the methods**

Append to `ElephantBet`:

```python
    async def get_countries(self, sport_id: str = "1") -> dict[str, Any]:
        """Get the full sport -> category -> tournament tree.

        BtoBet returns the whole menu in one call rather than per-sport, so
        ``sport_id`` is accepted for interface symmetry with the other
        clients and callers filter the ``s[]`` list themselves.

        Returns:
            Raw JSON with ``s[]`` (sports), each carrying ``i[]``
            (categories), each carrying ``i[]`` (tournaments).
        """
        return await self._request(
            "GET",
            "/rest/FEWFixture/FixturesMenu",
            params={"Culture": self._culture},
        )

    async def get_tournaments(self, sport_id: str = "1") -> dict[str, Any]:
        """Alias of :meth:`get_countries` — same endpoint, same payload."""
        return await self.get_countries(sport_id)

    async def get_events(
        self, tournament_id: str, limit: int = 50
    ) -> dict[str, Any]:
        """Get events for a tournament, with their main markets.

        Args:
            tournament_id: BtoBet tournament id (e.g. "1428062").
            limit: Page size.

        Returns:
            Raw JSON list of sports, each with ``t[]`` tournaments, each
            with ``m[]`` matches. Match fields include ``mid`` (match id),
            ``brid`` (SportRadar id), ``ht``/``at`` and ``d`` (kickoff).
        """
        return await self._request(
            "GET",
            "/rest/FEMobile/GetGroupedMatches",
            params={
                "TournamentData[]": tournament_id,
                "Culture": self._culture,
                "Limit": str(limit),
            },
        )

    async def get_event_detail(self, event_id: str) -> dict[str, Any]:
        """Get full markets and odds for one match.

        Args:
            event_id: BtoBet match id (``mid``, e.g. "5998731").

        Returns:
            Raw JSON shaped ``{"s": ..., "t": [{"o": [<market>, ...]}]}`` —
            markets are nested under display tabs in ``t[].o[]``.
        """
        return await self._request(
            "GET",
            "/rest/FEWMatches/MatchOdds",
            params={"MatchID": event_id, "Culture": self._culture},
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_elephantbet.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/bookmakers/elephantbet.py tests/test_elephantbet.py
git commit -m "feat(elephantbet): catalogue, events and event-detail methods"
```

---

### Task 3: Capture fixtures

**Files:**
- Create: `tests/fixtures/event_info/elephantbet/prematch.json`
- Create: `tests/fixtures/event_info/elephantbet/events.json`

**Interfaces:**
- Consumes: `ElephantBet` from Task 2.
- Produces: two committed fixtures every later task reads.

This task is **in-region only** (see the in-region constraint in `CLAUDE.md`).

- [ ] **Step 1: Capture both payloads**

```python
# scratch script, not committed
import asyncio, json, pathlib, sys
sys.path.insert(0, "src")
from bookieskit import ElephantBet

async def main():
    out = pathlib.Path("tests/fixtures/event_info/elephantbet")
    out.mkdir(parents=True, exist_ok=True)
    async with ElephantBet(country="mz") as c:
        events = await c.get_events(tournament_id="1428062", limit=5)
        (out / "events.json").write_text(
            json.dumps(events, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        # first match id in the payload
        mid = str(events[0]["t"][0]["m"][0]["mid"])
        detail = await c.get_event_detail(mid)
        (out / "prematch.json").write_text(
            json.dumps(detail, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        print("captured mid", mid, "markets", len(detail["t"][0]["o"]))

asyncio.run(main())
```

- [ ] **Step 2: Verify the fixtures contain the four core markets**

Run:

```bash
.venv/Scripts/python.exe -c "
import json
d=json.load(open('tests/fixtures/event_info/elephantbet/prematch.json',encoding='utf-8'))
ids={m['id'] for tab in d['t'] for m in tab['o']}
print('has 1X2(3):',3 in ids,'O/U(29):',29 in ids,'BTTS(7):',7 in ids,'DC(17):',17 in ids)
"
```

Expected: all four `True`. If any is `False`, capture a different fixture — do not proceed with a partial fixture.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/event_info/elephantbet/
git commit -m "test(elephantbet): commit captured prematch and events fixtures"
```

---

### Task 4: Registry fields and market mappings

**Files:**
- Modify: `src/bookieskit/markets/types.py`
- Modify: `src/bookieskit/markets/builtin_mappings.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `MarketMapping.elephantbet_id: str | None` and `OutcomeMapping.elephantbet: str`, plus ids on the four core soccer mappings.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_registry.py`:

```python
def test_elephantbet_core_soccer_mappings():
    """Ids and labels lifted from the captured prematch fixture."""
    from bookieskit.markets.registry import MarketRegistry

    r = MarketRegistry()
    assert r.get_by_canonical("1x2_ft").elephantbet_id == "3"
    assert r.get_by_canonical("over_under_ft").elephantbet_id == "29"
    assert r.get_by_canonical("btts_ft").elephantbet_id == "7"
    assert r.get_by_canonical("double_chance_ft").elephantbet_id == "17"

    dc = r.get_by_canonical("double_chance_ft").outcomes
    assert dc["home_draw"].elephantbet == "1X"
    assert dc["home_away"].elephantbet == "12"
    assert dc["draw_away"].elephantbet == "X2"

    btts = r.get_by_canonical("btts_ft").outcomes
    assert btts["yes"].elephantbet == "Sim"
    assert btts["no"].elephantbet == "Não"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_registry.py::test_elephantbet_core_soccer_mappings -v`
Expected: FAIL — `TypeError: MarketMapping.__init__() got an unexpected keyword argument` or `AttributeError: elephantbet_id`

- [ ] **Step 3: Add the dataclass fields**

In `src/bookieskit/markets/types.py`, add to `OutcomeMapping` after `betika`:

```python
    elephantbet: str = ""
```

and to `MarketMapping` after `betika_id`:

```python
    elephantbet_id: str | None = None
```

Both default, so existing literals stay valid and no unrelated mapping needs editing.

- [ ] **Step 4: Add the four mappings**

In `src/bookieskit/markets/builtin_mappings.py`, set `elephantbet_id` and the
`elephantbet` outcome labels on exactly these four entries. Values are taken
verbatim from the captured fixture:

- `1x2_ft`: `elephantbet_id="3"`; outcomes `home="1"`, `draw="X"`, `away="2"`
- `over_under_ft`: `elephantbet_id="29"`; outcomes `over="Acima"`, `under="Abaixo"`
- `btts_ft`: `elephantbet_id="7"`; outcomes `yes="Sim"`, `no="Não"`
- `double_chance_ft`: `elephantbet_id="17"`; outcomes `home_draw="1X"`, `home_away="12"`, `draw_away="X2"`

Add this comment above the `1x2_ft` entry:

```python
    # ElephantBet (BtoBet) market ids come from a captured MatchOdds payload;
    # its outcome labels are Portuguese ("Sim"/"Não", "Acima"/"Abaixo").
    # Over/Under carries its line in the outcome's `sbv` field, not the
    # market id, so one market id covers every line.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_registry.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/types.py src/bookieskit/markets/builtin_mappings.py tests/test_registry.py
git commit -m "feat(markets): add elephantbet fields and core soccer mappings"
```

---

### Task 5: Parser arm

**Files:**
- Modify: `src/bookieskit/markets/parser.py`
- Test: `tests/test_parser_elephantbet.py`

**Interfaces:**
- Consumes: fixtures from Task 3, mappings from Task 4.
- Produces: `_parse_elephantbet(response, registry, mode) -> list[NormalizedMarket]`, registered in the platform dispatch so `parse_markets(payload, platform="elephantbet")` works.

- [ ] **Step 1: Write the failing test**

Create `tests/test_parser_elephantbet.py`:

```python
"""Parser tests for ElephantBet core soccer markets.

Ids and labels lifted from the captured fixture, never guessed:
  1X2 = 3, Over/Under = 29, BTTS = 7, Double Chance = 17.
Over/Under is parameterized by the outcome's `sbv` field, so a single
market id carries every line.
"""

import json
from pathlib import Path

from bookieskit.markets.parser import parse_markets

_FIXTURES = Path(__file__).parent / "fixtures" / "event_info"


def _markets(fixture: str = "prematch.json"):
    payload = json.loads(
        (_FIXTURES / "elephantbet" / fixture).read_text(encoding="utf-8")
    )
    return parse_markets(payload, platform="elephantbet")


def test_elephantbet_1x2_ft():
    m = next(m for m in _markets() if m.canonical_id == "1x2_ft")
    assert m.lines is None
    assert {o.canonical_name for o in m.outcomes} == {"home", "draw", "away"}
    assert all(isinstance(o.odds, float) for o in m.outcomes)


def test_elephantbet_double_chance_ft():
    m = next(m for m in _markets() if m.canonical_id == "double_chance_ft")
    assert {o.canonical_name for o in m.outcomes} == {
        "home_draw", "home_away", "draw_away",
    }


def test_elephantbet_btts_ft():
    m = next(m for m in _markets() if m.canonical_id == "btts_ft")
    assert {o.canonical_name for o in m.outcomes} == {"yes", "no"}


def test_elephantbet_over_under_ft_is_parameterized_by_sbv():
    m = next(m for m in _markets() if m.canonical_id == "over_under_ft")
    assert m.lines is not None
    assert 2.5 in m.lines
    names = {o.canonical_name for o in m.lines[2.5]}
    assert names == {"over", "under"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_parser_elephantbet.py -v`
Expected: FAIL — `StopIteration` (no markets returned; platform not dispatched)

- [ ] **Step 3: Implement the parser arm**

Add to `src/bookieskit/markets/parser.py`:

```python
def _parse_elephantbet(
    response: dict, registry: MarketRegistry, mode: ProbabilityMode = "off"
) -> list[NormalizedMarket]:
    """Parse an ElephantBet (BtoBet) MatchOdds response.

    Markets are nested under display tabs: ``t[].o[]``. Odds arrive as
    strings. Over/Under-style markets repeat one market id across lines and
    carry the line in each outcome's ``sbv`` field, so grouping is by
    ``(market_id, sbv)`` rather than by market id alone.
    """
    results: list[NormalizedMarket] = []
    simple: dict[str, list[dict]] = {}
    parameterized: dict[str, dict[float, list[dict]]] = {}
    mappings: dict[str, MarketMapping] = {}

    for tab in response.get("t") or []:
        for market in tab.get("o") or []:
            market_id = str(market.get("id", ""))
            mapping = registry.get_by_platform_id("elephantbet", market_id)
            if mapping is None:
                continue
            mappings[market_id] = mapping
            for outcome in market.get("m") or []:
                if mapping.parameterized:
                    line = _try_float(outcome.get("sbv"))
                    if line is None:
                        continue
                    parameterized.setdefault(market_id, {}).setdefault(
                        line, []
                    ).append(outcome)
                else:
                    simple.setdefault(market_id, []).append(outcome)

    for market_id, outcomes in simple.items():
        mapping = mappings[market_id]
        parsed = [
            Outcome(
                canonical_name=canonical,
                odds=odds,
                platform_name=str(o.get("n", "")),
            )
            for o in outcomes
            if (odds := _try_float(o.get("o"))) is not None
            and (
                canonical := _resolve_outcome_elephantbet(
                    str(o.get("n", "")), mapping
                )
            )
        ]
        if parsed:
            results.append(
                NormalizedMarket(
                    canonical_id=mapping.canonical_id,
                    name=mapping.name,
                    outcomes=parsed,
                    lines=None,
                )
            )

    for market_id, by_line in parameterized.items():
        mapping = mappings[market_id]
        lines: dict[float, list[Outcome]] = {}
        for line, outcomes in by_line.items():
            parsed = [
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=str(o.get("n", "")),
                )
                for o in outcomes
                if (odds := _try_float(o.get("o"))) is not None
                and (
                    canonical := _resolve_outcome_elephantbet(
                        str(o.get("n", "")), mapping
                    )
                )
            ]
            if parsed:
                lines[line] = parsed
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


def _resolve_outcome_elephantbet(
    label: str, mapping: MarketMapping
) -> str | None:
    """Map an ElephantBet outcome label to its canonical name."""
    target = label.strip().casefold()
    for canonical, outcome in mapping.outcomes.items():
        if outcome.elephantbet and outcome.elephantbet.casefold() == target:
            return canonical
    return None
```

Register it in the platform dispatch table alongside the other seven, keyed
`"elephantbet"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_parser_elephantbet.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass except `tests/devtools/test_coverage.py::test_coverage_matrix_golden_snapshot`, which Task 6 updates.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_parser_elephantbet.py
git commit -m "feat(markets): parse ElephantBet core soccer markets"
```

---

### Task 6: Event info, matching, harness wiring, docs

**Files:**
- Modify: `src/bookieskit/event_info.py`, `src/bookieskit/matching/extractor.py`
- Modify: `src/bookieskit/devtools/sports.py`, `src/bookieskit/devtools/adapters.py`, `src/bookieskit/devtools/resolver.py`
- Modify: `tests/devtools/test_coverage.py`, `docs/coverage.md`, `docs/elephantbet.md`, `README.md`, `CHANGELOG.md`
- Test: `tests/test_event_info.py`, `tests/test_extractor.py`

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: `elephantbet` participating in `extract_event_ids`, `extract_kickoff`, `extract_participants`, the coverage matrix and the audit harness.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_extractor.py
def test_extract_event_ids_elephantbet():
    """`brid` is the SportRadar id — verified against Betway event 72221172,
    which resolves to the same fixture ("Fulham FC vs. Chelsea FC")."""
    from bookieskit.matching import extract_event_ids

    match = {"mid": 5998731, "brid": "72221172", "ht": "Fulham FC",
             "at": "Chelsea FC", "d": "2026-08-24 19:00"}
    ids = extract_event_ids(match, platform="elephantbet")
    assert ids.sportradar_id == "72221172"


# tests/test_event_info.py
def test_extract_participants_elephantbet():
    from bookieskit import extract_participants

    match = {"mid": 5998731, "ht": "Fulham FC", "at": "Chelsea FC"}
    p = extract_participants(match, platform="elephantbet")
    assert p.home == "Fulham FC"
    assert p.away == "Chelsea FC"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_extractor.py tests/test_event_info.py -v`
Expected: FAIL — extractors return empty for the unknown platform.

- [ ] **Step 3: Implement extractors and wiring**

- `matching/extractor.py`: add an `elephantbet` entry reading `brid` as the SportRadar id (string, no `sr:match:` prefix).
- `event_info.py`: add `_kickoff_elephantbet` parsing `d` (`"%Y-%m-%d %H:%M"`, naive), `_participants_elephantbet` reading `ht`/`at`, and `_live_info_elephantbet` returning the empty `LiveInfo` with a comment that live state is not yet mapped. Register all three in their dispatch tables.
- `devtools/sports.py`: add the `elephantbet` column — `soccer="1"`, `basketball=None`, `tennis=None` (only soccer is verified this increment).
- `devtools/adapters.py` and `devtools/resolver.py`: add an ElephantBet adapter following the existing shape so the harness and audit can reach it.

- [ ] **Step 4: Update the coverage golden snapshot**

In `tests/devtools/test_coverage.py`, add `"elephantbet"` to every row of `EXPECTED_MATRIX`: `True` for `1x2_ft`, `over_under_ft`, `btts_ft`, `double_chance_ft`; `False` for all others.

- [ ] **Step 5: Regenerate the coverage doc**

```bash
.venv/Scripts/python.exe -m bookieskit.devtools coverage > docs/coverage.md
```

- [ ] **Step 6: Write the docs**

Create `docs/elephantbet.md` following `docs/betpawa.md` in structure: supported countries (mz only, with the ao/sl/mw WAF finding), methods table, response shapes, and a Quirks section covering: `Culture` is mandatory (400 without it); the SPA's endpoints differ from the similarly-named ones in the Swagger spec; odds are strings; Over/Under carries its line in `sbv`; `eon` holds `{{HomeTeam}}`/`{{AwayTeam}}` placeholders; `brid` is the SportRadar id.

Add the ElephantBet row to the README bookmaker table (`mz`) and a `CHANGELOG.md` `[Unreleased]` entry.

- [ ] **Step 7: Verify everything**

```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m bookieskit.devtools coverage | diff - docs/coverage.md
.venv/Scripts/python.exe -m bookieskit.devtools check-docs-sync --base origin/main
```

Expected: all tests pass, ruff clean, no diff, docs-sync OK.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(elephantbet): event info, SR-id matching, harness wiring and docs"
```

---

## Self-review

**Spec coverage.** Client → Task 1-2. Registry fields and ids → Task 4. Parser arm → Task 5. Event info, matching, harness, docs → Task 6. Fixtures → Task 3. The spec's #1 risk (provider ids) is resolved: `brid` is the SportRadar id, verified against Betway, so Task 6 wires real cross-book matching rather than the standalone fallback.

**Placeholders.** None. Every market id, outcome label, endpoint and field name is a captured value.

**Type consistency.** `PLATFORM_KEY`, the registry key, the parser dispatch key, the sports-table column and the coverage column are all the literal string `"elephantbet"`. `elephantbet_id` (mapping) and `elephantbet` (outcome) are used consistently across Tasks 4, 5 and 6.

**Deviation from the spec, deliberate:** the spec named `FEWFixture/TournamentMatchOdds` and `FEMobile/GetMatchOdds`. Both return `204 No Content`. The endpoints above are the ones the brand's own SPA calls and are verified to return data.
