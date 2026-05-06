# Event-info Helpers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the kickoff / live-info / participants extraction logic from `examples/monitor_competitions.py` into a first-class library module `bookieskit.event_info`, wired for all 5 bookmakers, with a dual auto-detect / explicit-mode API.

**Architecture:** New top-level module `src/bookieskit/event_info.py` mirroring the dispatcher pattern in `bookieskit.matching.extractor`. Each public function takes `(response, platform, *, mode=None)`. All functions are total: missing keys, malformed shapes, unknown platforms yield `None` / empty dataclasses — never raise. Tests are pure-data, bound to fixtures already captured under `tests/fixtures/event_info/{platform}/{prematch,live}.json`.

**Tech Stack:** Python 3.11, stdlib only (dataclasses, datetime, typing.Literal). Tests via pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-06-event-info-helpers-design.md`

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/bookieskit/event_info.py` | create | Module: dataclasses, `Mode` type, four public functions, five private platform impls per extractor. |
| `src/bookieskit/__init__.py` | modify | Re-export `extract_kickoff`, `extract_live_info`, `extract_participants`, `is_live_now`, `LiveInfo`, `Participants`, `Mode`. |
| `tests/test_event_info.py` | create | Unit tests bound to fixtures. |
| `tests/fixtures/event_info/{platform}/{phase}.json` | already exists (10 files) | Captured real responses. Do not modify. |
| `examples/monitor_competitions.py` | modify | Replace inline `_parse_kickoff`/`_extract_live_info` with imports from `bookieskit.event_info`; convert `int|None` → CSV strings at write time. |
| `scripts/capture_event_info_fixtures.py` | already exists | Keep for re-capture when shapes drift. No changes. |

Each task ends with a commit so the work integrates incrementally.

---

## Task 1: Module skeleton with types and stub functions

**Files:**
- Create: `src/bookieskit/event_info.py`
- Test: `tests/test_event_info.py`

- [ ] **Step 1: Write the failing test for imports and types**

Create `tests/test_event_info.py`:

```python
"""Unit tests for bookieskit.event_info — pure-data, bound to captured fixtures."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bookieskit.event_info import (
    LiveInfo,
    Mode,
    Participants,
    extract_kickoff,
    extract_live_info,
    extract_participants,
    is_live_now,
)

FIXTURES = Path(__file__).parent / "fixtures" / "event_info"


def _load(platform: str, phase: str) -> dict:
    with open(FIXTURES / platform / f"{phase}.json", encoding="utf-8") as f:
        return json.load(f)


def test_dataclasses_construct_with_all_none():
    li = LiveInfo()
    assert li.minute is None
    assert li.period is None
    assert li.score_home is None
    assert li.score_away is None
    p = Participants()
    assert p.home is None
    assert p.away is None


def test_dataclasses_are_frozen():
    li = LiveInfo()
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        li.minute = 5  # type: ignore[misc]


def test_mode_alias_is_literal():
    # Mode is Literal["prematch","live"] — runtime check is type-only,
    # but the symbol must exist and be importable.
    assert Mode is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_event_info.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bookieskit.event_info'`

- [ ] **Step 3: Write the minimal module to make tests pass**

Create `src/bookieskit/event_info.py`:

```python
"""Event-info extractors — kickoff, live info, participants — for all 5 bookmakers.

Mirrors the dispatcher pattern in `bookieskit.matching.extractor`. Each public
function takes a `platform` string plus an optional `mode` keyword. Auto-detect
when mode is None; explicit mode (`"prematch"` / `"live"`) overrides.

All functions are total: missing keys, malformed shapes, and unknown platforms
yield None / empty dataclasses — they never raise.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Literal


Mode = Literal["prematch", "live"]


@dataclass(frozen=True)
class LiveInfo:
    minute: int | None = None
    period: str | None = None
    score_home: int | None = None
    score_away: int | None = None


@dataclass(frozen=True)
class Participants:
    home: str | None = None
    away: str | None = None


_EMPTY_LIVE_INFO = LiveInfo()
_EMPTY_PARTICIPANTS = Participants()


def _normalised_mode(mode: object) -> Mode | None:
    """Coerce arbitrary user input to a known Mode value or None.

    Invalid mode strings silently become None — matches the total-function
    contract (never raise on bad input)."""
    if mode == "prematch" or mode == "live":
        return mode  # type: ignore[return-value]
    return None


def is_live_now(kickoff: datetime | None) -> bool:
    """True iff `kickoff` is non-None and in the past (UTC now)."""
    if kickoff is None:
        return False
    return datetime.now(timezone.utc) >= kickoff


def extract_kickoff(
    response: dict, platform: str, *, mode: Mode | None = None
) -> datetime | None:
    """Return the event kickoff as a tz-aware UTC datetime, or None."""
    return None  # filled in per platform in later tasks


def extract_participants(
    response: dict, platform: str, *, mode: Mode | None = None
) -> Participants:
    """Return home/away participant names. Missing fields are None."""
    return _EMPTY_PARTICIPANTS  # filled in per platform in later tasks


def extract_live_info(
    response: dict, platform: str, *, mode: Mode | None = None
) -> LiveInfo:
    """Return live-match info (minute/period/scores). Missing fields are None."""
    return _EMPTY_LIVE_INFO  # filled in per platform in later tasks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_event_info.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/event_info.py tests/test_event_info.py
git commit -m "feat(event_info): module skeleton with dataclasses, Mode, and stubs"
```

---

## Task 2: is_live_now helper

**Files:**
- Modify: `tests/test_event_info.py` (append tests)
- (no module change — already implemented in Task 1)

- [ ] **Step 1: Append failing tests for is_live_now**

Append to `tests/test_event_info.py`:

```python
from datetime import timedelta


def test_is_live_now_none_returns_false():
    assert is_live_now(None) is False


def test_is_live_now_past_kickoff_returns_true():
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert is_live_now(past) is True


def test_is_live_now_future_kickoff_returns_false():
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert is_live_now(future) is False


def test_is_live_now_exactly_now_returns_true():
    # `>=` boundary — at the exact kickoff instant, treat as live.
    now = datetime.now(timezone.utc)
    assert is_live_now(now) is True
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_event_info.py -v -k is_live_now`
Expected: 4 passed (already implemented in Task 1).

- [ ] **Step 3: Commit**

```bash
git add tests/test_event_info.py
git commit -m "test(event_info): is_live_now coverage"
```

---

## Task 3: BetPawa extractors

**Files:**
- Modify: `src/bookieskit/event_info.py`
- Modify: `tests/test_event_info.py`

Fixture facts (verified from `tests/fixtures/event_info/betpawa/*.json`):
- prematch event 33289995: `startTime="2026-05-06T11:00:00Z"`, names `["Wuhan Three Towns FC", "Qingdao Hainiu FC"]`, `results=None`.
- live event 33247830: `startTime="2026-05-06T06:00:00Z"`, names `["FC Tokyo", "JEF United Chiba"]`, minute `"96"`, period `"Second Half"`, scores `0-3` via `FULL_TIME_EXCLUDING_OVERTIME`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_event_info.py`:

```python
def test_betpawa_kickoff_prematch():
    d = _load("betpawa", "prematch")
    k = extract_kickoff(d, "betpawa")
    assert k == datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_betpawa_kickoff_live():
    d = _load("betpawa", "live")
    k = extract_kickoff(d, "betpawa")
    assert k == datetime(2026, 5, 6, 6, 0, 0, tzinfo=timezone.utc)


def test_betpawa_participants_prematch():
    d = _load("betpawa", "prematch")
    p = extract_participants(d, "betpawa")
    assert p.home == "Wuhan Three Towns FC"
    assert p.away == "Qingdao Hainiu FC"


def test_betpawa_participants_live():
    d = _load("betpawa", "live")
    p = extract_participants(d, "betpawa")
    assert p.home == "FC Tokyo"
    assert p.away == "JEF United Chiba"


def test_betpawa_live_info_prematch_all_none():
    d = _load("betpawa", "prematch")
    li = extract_live_info(d, "betpawa")
    assert li == LiveInfo()


def test_betpawa_live_info_live():
    d = _load("betpawa", "live")
    li = extract_live_info(d, "betpawa")
    assert li.minute == 96
    assert li.period == "Second Half"
    assert li.score_home == 0
    assert li.score_away == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_event_info.py -v -k betpawa`
Expected: 6 failed (stubs return empty / None).

- [ ] **Step 3: Implement BetPawa branches**

Replace the stub bodies of `extract_kickoff`, `extract_participants`, `extract_live_info` and add the BetPawa private functions. Edit `src/bookieskit/event_info.py`:

Replace the three stub functions with dispatcher versions, and add private impls. Final code added/changed:

```python
# Add after _normalised_mode:

def _try_int(v: object) -> int | None:
    """Best-effort int cast — returns None on failure."""
    try:
        return int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _split_score(s: object) -> tuple[int | None, int | None]:
    """Split 'H:A' string into (home, away) ints; (None, None) on bad input."""
    if not isinstance(s, str) or ":" not in s:
        return None, None
    h, _, a = s.partition(":")
    return _try_int(h), _try_int(a)


# ---- BetPawa --------------------------------------------------------------

def _kickoff_betpawa(response: dict, mode: Mode | None) -> datetime | None:
    s = response.get("startTime")
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _participants_betpawa(response: dict, mode: Mode | None) -> Participants:
    parts = response.get("participants") or []
    home = parts[0].get("name") if len(parts) > 0 and isinstance(parts[0], dict) else None
    away = parts[1].get("name") if len(parts) > 1 and isinstance(parts[1], dict) else None
    return Participants(home=home, away=away)


def _live_info_betpawa(response: dict, mode: Mode | None) -> LiveInfo:
    if mode == "prematch":
        return _EMPTY_LIVE_INFO
    results = response.get("results")
    if not isinstance(results, dict):
        return _EMPTY_LIVE_INFO
    display = results.get("display") or {}
    minute = _try_int(display.get("minute"))
    current_period = display.get("currentPeriod") or {}
    period = current_period.get("name") or None
    score_home = score_away = None
    for block in results.get("participantPeriodResults") or []:
        participant = block.get("participant") or {}
        ptype = participant.get("type")
        if ptype not in ("HOME", "AWAY"):
            continue
        for pr in block.get("periodResults") or []:
            slug = (pr.get("period") or {}).get("slug")
            if slug == "FULL_TIME_EXCLUDING_OVERTIME":
                v = _try_int(pr.get("result"))
                if ptype == "HOME":
                    score_home = v
                else:
                    score_away = v
                break
    return LiveInfo(
        minute=minute, period=period,
        score_home=score_home, score_away=score_away,
    )


# ---- Dispatcher tables ----------------------------------------------------

_KICKOFF_DISPATCH: dict[str, Callable[[dict, Mode | None], datetime | None]] = {
    "betpawa": _kickoff_betpawa,
}

_PARTICIPANTS_DISPATCH: dict[str, Callable[[dict, Mode | None], Participants]] = {
    "betpawa": _participants_betpawa,
}

_LIVE_INFO_DISPATCH: dict[str, Callable[[dict, Mode | None], LiveInfo]] = {
    "betpawa": _live_info_betpawa,
}
```

Then replace the three public stubs with dispatchers:

```python
def extract_kickoff(
    response: dict, platform: str, *, mode: Mode | None = None
) -> datetime | None:
    """Return the event kickoff as a tz-aware UTC datetime, or None."""
    impl = _KICKOFF_DISPATCH.get(platform)
    if impl is None:
        return None
    return impl(response, _normalised_mode(mode))


def extract_participants(
    response: dict, platform: str, *, mode: Mode | None = None
) -> Participants:
    """Return home/away participant names. Missing fields are None."""
    impl = _PARTICIPANTS_DISPATCH.get(platform)
    if impl is None:
        return _EMPTY_PARTICIPANTS
    return impl(response, _normalised_mode(mode))


def extract_live_info(
    response: dict, platform: str, *, mode: Mode | None = None
) -> LiveInfo:
    """Return live-match info (minute/period/scores). Missing fields are None."""
    impl = _LIVE_INFO_DISPATCH.get(platform)
    if impl is None:
        return _EMPTY_LIVE_INFO
    return impl(response, _normalised_mode(mode))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_event_info.py -v -k betpawa`
Expected: 6 passed.

- [ ] **Step 5: Run all event_info tests**

Run: `pytest tests/test_event_info.py -v`
Expected: 13 passed (3 from Task 1 + 4 from Task 2 + 6 here).

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/event_info.py tests/test_event_info.py
git commit -m "feat(event_info): BetPawa kickoff/participants/live_info extractors"
```

---

## Task 4: SportyBet extractors

**Files:**
- Modify: `src/bookieskit/event_info.py`
- Modify: `tests/test_event_info.py`

Fixture facts (`tests/fixtures/event_info/sportybet/*.json`):
- prematch: `data.estimateStartTime=1778065200000` (= `2026-05-06T11:00:00Z`), `data.homeTeamName="Wuhan Three Towns FC"`, `data.awayTeamName="Qingdao Hainiu FC"`, `data.matchStatus="Not start"`, `data.setScore=None`.
- live: `data.estimateStartTime=1778047200000` (= `2026-05-06T06:00:00Z`), names `FC Tokyo` / `JEF United Chiba`, `data.playedSeconds="90:00"`, `data.matchStatus="H2"`, `data.setScore="0:3"`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_event_info.py`:

```python
def test_sportybet_kickoff_prematch():
    d = _load("sportybet", "prematch")
    k = extract_kickoff(d, "sportybet")
    assert k == datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_sportybet_kickoff_live():
    d = _load("sportybet", "live")
    k = extract_kickoff(d, "sportybet")
    assert k == datetime(2026, 5, 6, 6, 0, 0, tzinfo=timezone.utc)


def test_sportybet_participants_prematch():
    d = _load("sportybet", "prematch")
    p = extract_participants(d, "sportybet")
    assert p.home == "Wuhan Three Towns FC"
    assert p.away == "Qingdao Hainiu FC"


def test_sportybet_participants_live():
    d = _load("sportybet", "live")
    p = extract_participants(d, "sportybet")
    assert p.home == "FC Tokyo"
    assert p.away == "JEF United Chiba"


def test_sportybet_live_info_prematch_all_none():
    d = _load("sportybet", "prematch")
    li = extract_live_info(d, "sportybet")
    assert li == LiveInfo()


def test_sportybet_live_info_live():
    d = _load("sportybet", "live")
    li = extract_live_info(d, "sportybet")
    assert li.minute == 90
    assert li.period == "H2"
    assert li.score_home == 0
    assert li.score_away == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_event_info.py -v -k sportybet`
Expected: 6 failed.

- [ ] **Step 3: Implement SportyBet branches**

Add to `src/bookieskit/event_info.py` (after the BetPawa private functions):

```python
# ---- SportyBet ------------------------------------------------------------

def _kickoff_sportybet(response: dict, mode: Mode | None) -> datetime | None:
    data = response.get("data") or {}
    ms = data.get("estimateStartTime")
    if not isinstance(ms, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (ValueError, OSError):
        return None


def _participants_sportybet(response: dict, mode: Mode | None) -> Participants:
    data = response.get("data") or {}
    return Participants(
        home=data.get("homeTeamName") or None,
        away=data.get("awayTeamName") or None,
    )


def _live_info_sportybet(response: dict, mode: Mode | None) -> LiveInfo:
    if mode == "prematch":
        return _EMPTY_LIVE_INFO
    data = response.get("data") or {}
    played_seconds = data.get("playedSeconds")
    minute = None
    if isinstance(played_seconds, str) and ":" in played_seconds:
        minute = _try_int(played_seconds.split(":", 1)[0])
    match_status = data.get("matchStatus")
    period = match_status if match_status not in ("Not start", None, "") else None
    score_home, score_away = _split_score(data.get("setScore"))
    return LiveInfo(
        minute=minute, period=period,
        score_home=score_home, score_away=score_away,
    )
```

Add to each dispatcher table:

```python
_KICKOFF_DISPATCH["sportybet"] = _kickoff_sportybet
_PARTICIPANTS_DISPATCH["sportybet"] = _participants_sportybet
_LIVE_INFO_DISPATCH["sportybet"] = _live_info_sportybet
```

(Or include the entry directly in the dict literal if you re-write the table.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_event_info.py -v -k sportybet`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/event_info.py tests/test_event_info.py
git commit -m "feat(event_info): SportyBet kickoff/participants/live_info extractors"
```

---

## Task 5: Bet9ja extractors with mode-hint logic

**Files:**
- Modify: `src/bookieskit/event_info.py`
- Modify: `tests/test_event_info.py`

Fixture facts (`tests/fixtures/event_info/bet9ja/*.json`):
- prematch: `D.STARTDATE="2026-05-06 11:00:00"`, `D.DS="Wuhan Three Towns - Qingdao Hainiu FC"`, no `D.A`.
- live: `D.A.T=91`, `D.A.ES="2nd Half"`, `D.A.R.S="0:3"`, no `D.STARTDATE`, no `D.DS`.

Branch rule: if `mode` is explicit, follow it; else auto-detect via `D.A` presence.

- [ ] **Step 1: Write failing tests (auto-detect)**

Append to `tests/test_event_info.py`:

```python
def test_bet9ja_kickoff_prematch_auto():
    d = _load("bet9ja", "prematch")
    k = extract_kickoff(d, "bet9ja")
    assert k == datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_bet9ja_kickoff_live_auto_returns_none():
    d = _load("bet9ja", "live")
    assert extract_kickoff(d, "bet9ja") is None


def test_bet9ja_participants_prematch_auto():
    d = _load("bet9ja", "prematch")
    p = extract_participants(d, "bet9ja")
    assert p.home == "Wuhan Three Towns"
    assert p.away == "Qingdao Hainiu FC"


def test_bet9ja_participants_live_auto_returns_none():
    d = _load("bet9ja", "live")
    p = extract_participants(d, "bet9ja")
    assert p == Participants()


def test_bet9ja_live_info_prematch_auto_all_none():
    d = _load("bet9ja", "prematch")
    li = extract_live_info(d, "bet9ja")
    assert li == LiveInfo()


def test_bet9ja_live_info_live_auto():
    d = _load("bet9ja", "live")
    li = extract_live_info(d, "bet9ja")
    assert li.minute == 91
    assert li.period == "2nd Half"
    assert li.score_home == 0
    assert li.score_away == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_event_info.py -v -k bet9ja`
Expected: 6 failed.

- [ ] **Step 3: Implement Bet9ja branches**

Add to `src/bookieskit/event_info.py`:

```python
# ---- Bet9ja ---------------------------------------------------------------

def _bet9ja_is_live(response: dict, mode: Mode | None) -> bool:
    """True if explicit mode says live, or if auto-detect sees D.A."""
    if mode == "live":
        return True
    if mode == "prematch":
        return False
    # auto-detect
    D = response.get("D") or {}
    return "A" in D


def _kickoff_bet9ja(response: dict, mode: Mode | None) -> datetime | None:
    if _bet9ja_is_live(response, mode):
        return None  # live response carries no kickoff
    D = response.get("D") or {}
    s = D.get("STARTDATE")
    if not isinstance(s, str):
        return None
    try:
        # "YYYY-MM-DD HH:MM:SS" — empirically UTC.
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _participants_bet9ja(response: dict, mode: Mode | None) -> Participants:
    if _bet9ja_is_live(response, mode):
        return _EMPTY_PARTICIPANTS  # live response carries no team names
    D = response.get("D") or {}
    ds = D.get("DS")
    if not isinstance(ds, str) or " - " not in ds:
        return _EMPTY_PARTICIPANTS
    home, away = ds.split(" - ", 1)
    return Participants(home=home or None, away=away or None)


def _live_info_bet9ja(response: dict, mode: Mode | None) -> LiveInfo:
    if not _bet9ja_is_live(response, mode):
        return _EMPTY_LIVE_INFO
    A = (response.get("D") or {}).get("A") or {}
    minute = _try_int(A.get("T"))
    period = A.get("ES") or None
    R = A.get("R") or {}
    score_home, score_away = _split_score(R.get("S"))
    return LiveInfo(
        minute=minute, period=period,
        score_home=score_home, score_away=score_away,
    )


_KICKOFF_DISPATCH["bet9ja"] = _kickoff_bet9ja
_PARTICIPANTS_DISPATCH["bet9ja"] = _participants_bet9ja
_LIVE_INFO_DISPATCH["bet9ja"] = _live_info_bet9ja
```

- [ ] **Step 4: Run tests to verify auto-detect tests pass**

Run: `pytest tests/test_event_info.py -v -k bet9ja`
Expected: 6 passed.

- [ ] **Step 5: Write failing tests for explicit mode hint**

Append to `tests/test_event_info.py`:

```python
def test_bet9ja_explicit_mode_live_on_prematch_fixture_yields_nones():
    """User asserts live, but fixture is prematch shape — follow the mode,
    yield Nones where the live fields are absent. Must not raise."""
    d = _load("bet9ja", "prematch")
    assert extract_kickoff(d, "bet9ja", mode="live") is None
    assert extract_participants(d, "bet9ja", mode="live") == Participants()
    assert extract_live_info(d, "bet9ja", mode="live") == LiveInfo()


def test_bet9ja_explicit_mode_prematch_on_live_fixture_yields_nones():
    """User asserts prematch, but fixture is live shape — follow the mode,
    yield Nones where the prematch fields are absent. Must not raise."""
    d = _load("bet9ja", "live")
    assert extract_kickoff(d, "bet9ja", mode="prematch") is None
    assert extract_participants(d, "bet9ja", mode="prematch") == Participants()
    assert extract_live_info(d, "bet9ja", mode="prematch") == LiveInfo()


def test_bet9ja_explicit_mode_matches_auto_on_correct_fixture():
    d_pm = _load("bet9ja", "prematch")
    d_lv = _load("bet9ja", "live")
    assert extract_kickoff(d_pm, "bet9ja", mode="prematch") == \
           extract_kickoff(d_pm, "bet9ja")
    assert extract_live_info(d_lv, "bet9ja", mode="live") == \
           extract_live_info(d_lv, "bet9ja")
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_event_info.py -v -k bet9ja`
Expected: 9 passed (6 auto + 3 explicit-mode).

- [ ] **Step 7: Commit**

```bash
git add src/bookieskit/event_info.py tests/test_event_info.py
git commit -m "feat(event_info): Bet9ja extractors with auto-detect + mode hint"
```

---

## Task 6: Betway extractors with score-gating

**Files:**
- Modify: `src/bookieskit/event_info.py`
- Modify: `tests/test_event_info.py`

Fixture facts (`tests/fixtures/event_info/betway/*.json`):
- prematch: `sportEvent.expectedStartEpoch=1778065200`, names `Wuhan Three Towns FC` / `Qingdao Hainiu FC`, `gameStateTimeScore.comments="NotStarted"`, `gameStateTimeScore.score=["0","0"]` (artefact — must NOT be reported), no `time`/`state` keys.
- live: `expectedStartEpoch=1778047200`, names `FC Tokyo` / `JEF United Chiba`, `gameStateTimeScore.time=90`, `state="2nd half"`, `score=["0","3"]`, `comments="RegularPeriod"`.

Gating rule: if `mode == "prematch"`, force live fields to None. Else auto-detect: `time` key absent (or `comments == "NotStarted"`) ⇒ prematch.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_event_info.py`:

```python
def test_betway_kickoff_prematch():
    d = _load("betway", "prematch")
    assert extract_kickoff(d, "betway") == \
           datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_betway_kickoff_live():
    d = _load("betway", "live")
    assert extract_kickoff(d, "betway") == \
           datetime(2026, 5, 6, 6, 0, 0, tzinfo=timezone.utc)


def test_betway_participants_prematch():
    p = extract_participants(_load("betway", "prematch"), "betway")
    assert p.home == "Wuhan Three Towns FC"
    assert p.away == "Qingdao Hainiu FC"


def test_betway_participants_live():
    p = extract_participants(_load("betway", "live"), "betway")
    assert p.home == "FC Tokyo"
    assert p.away == "JEF United Chiba"


def test_betway_live_info_prematch_auto_all_none_despite_zero_score_artefact():
    """Betway prematch carries score=['0','0'] but no time/state — must
    NOT emit fake 0-0; auto-detect via time-key absence."""
    d = _load("betway", "prematch")
    li = extract_live_info(d, "betway")
    assert li == LiveInfo()


def test_betway_live_info_live_auto():
    d = _load("betway", "live")
    li = extract_live_info(d, "betway")
    assert li.minute == 90
    assert li.period == "2nd half"
    assert li.score_home == 0
    assert li.score_away == 3


def test_betway_live_info_explicit_prematch_mode_overrides_anything():
    """mode='prematch' forces all live fields to None, even on a live fixture."""
    d = _load("betway", "live")
    li = extract_live_info(d, "betway", mode="prematch")
    assert li == LiveInfo()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_event_info.py -v -k betway`
Expected: 7 failed.

- [ ] **Step 3: Implement Betway branches**

Add to `src/bookieskit/event_info.py`:

```python
# ---- Betway ---------------------------------------------------------------

def _kickoff_betway(response: dict, mode: Mode | None) -> datetime | None:
    sport_event = response.get("sportEvent") or {}
    s = sport_event.get("expectedStartEpoch")
    if not isinstance(s, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(s, tz=timezone.utc)
    except (ValueError, OSError):
        return None


def _participants_betway(response: dict, mode: Mode | None) -> Participants:
    sport_event = response.get("sportEvent") or {}
    return Participants(
        home=sport_event.get("homeTeam") or None,
        away=sport_event.get("awayTeam") or None,
    )


def _live_info_betway(response: dict, mode: Mode | None) -> LiveInfo:
    if mode == "prematch":
        return _EMPTY_LIVE_INFO
    sport_event = response.get("sportEvent") or {}
    g = sport_event.get("gameStateTimeScore") or {}
    # Auto-detect: prematch responses lack the `time` key (and have
    # comments=='NotStarted'). Their score=['0','0'] is an artefact.
    if mode is None and ("time" not in g or g.get("comments") == "NotStarted"):
        return _EMPTY_LIVE_INFO
    minute = _try_int(g.get("time"))
    period = g.get("state") or None
    score = g.get("score") or []
    if isinstance(score, list) and len(score) >= 2:
        score_home = _try_int(score[0])
        score_away = _try_int(score[1])
    else:
        score_home = score_away = None
    return LiveInfo(
        minute=minute, period=period,
        score_home=score_home, score_away=score_away,
    )


_KICKOFF_DISPATCH["betway"] = _kickoff_betway
_PARTICIPANTS_DISPATCH["betway"] = _participants_betway
_LIVE_INFO_DISPATCH["betway"] = _live_info_betway
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_event_info.py -v -k betway`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/event_info.py tests/test_event_info.py
git commit -m "feat(event_info): Betway extractors with score-artefact gating"
```

---

## Task 7: MSport extractors

**Files:**
- Modify: `src/bookieskit/event_info.py`
- Modify: `tests/test_event_info.py`

Fixture facts (`tests/fixtures/event_info/msport/*.json`):
- prematch: `data.startTime=1778065200000`, `data.homeTeam="Wuhan Three Towns"`, `data.awayTeam="Qingdao Hainiu FC"`, `data.playedTime=None`, `data.scoreOfWholeMatch=None`, `data.statusDescription=None`.
- live: `data.startTime=1778047200000`, `data.homeTeam="Tokyo"`, `data.awayTeam="Ichihara Chiba"`, `data.playedTime="90'00\""`, `data.scoreOfWholeMatch="0:3"`, `data.statusDescription=None`.

Note: MSport's period field (`statusDescription`) is `None` in the live fixture; the extractor should pass it through as None rather than fabricate one.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_event_info.py`:

```python
def test_msport_kickoff_prematch():
    d = _load("msport", "prematch")
    assert extract_kickoff(d, "msport") == \
           datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_msport_kickoff_live():
    d = _load("msport", "live")
    assert extract_kickoff(d, "msport") == \
           datetime(2026, 5, 6, 6, 0, 0, tzinfo=timezone.utc)


def test_msport_participants_prematch():
    p = extract_participants(_load("msport", "prematch"), "msport")
    assert p.home == "Wuhan Three Towns"
    assert p.away == "Qingdao Hainiu FC"


def test_msport_participants_live():
    p = extract_participants(_load("msport", "live"), "msport")
    assert p.home == "Tokyo"
    assert p.away == "Ichihara Chiba"


def test_msport_live_info_prematch_all_none():
    li = extract_live_info(_load("msport", "prematch"), "msport")
    assert li == LiveInfo()


def test_msport_live_info_live():
    li = extract_live_info(_load("msport", "live"), "msport")
    assert li.minute == 90
    assert li.period is None  # statusDescription is None in this fixture
    assert li.score_home == 0
    assert li.score_away == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_event_info.py -v -k msport`
Expected: 6 failed.

- [ ] **Step 3: Implement MSport branches**

Add to `src/bookieskit/event_info.py`:

```python
# ---- MSport ---------------------------------------------------------------

def _kickoff_msport(response: dict, mode: Mode | None) -> datetime | None:
    data = response.get("data") or {}
    ms = data.get("startTime")
    if not isinstance(ms, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (ValueError, OSError):
        return None


def _participants_msport(response: dict, mode: Mode | None) -> Participants:
    data = response.get("data") or {}
    return Participants(
        home=data.get("homeTeam") or None,
        away=data.get("awayTeam") or None,
    )


def _live_info_msport(response: dict, mode: Mode | None) -> LiveInfo:
    if mode == "prematch":
        return _EMPTY_LIVE_INFO
    data = response.get("data") or {}
    played = data.get("playedTime")
    minute = None
    if isinstance(played, str) and "'" in played:
        # "90'00\"" → "90"
        minute = _try_int(played.split("'", 1)[0])
    period = data.get("statusDescription") or None
    score_home, score_away = _split_score(data.get("scoreOfWholeMatch"))
    return LiveInfo(
        minute=minute, period=period,
        score_home=score_home, score_away=score_away,
    )


_KICKOFF_DISPATCH["msport"] = _kickoff_msport
_PARTICIPANTS_DISPATCH["msport"] = _participants_msport
_LIVE_INFO_DISPATCH["msport"] = _live_info_msport
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_event_info.py -v -k msport`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/event_info.py tests/test_event_info.py
git commit -m "feat(event_info): MSport extractors"
```

---

## Task 8: Generic dispatcher and total-function tests

**Files:**
- Modify: `tests/test_event_info.py`

Cover unknown-platform, empty-dict, and invalid-mode behavior. No code changes — these exercise behavior that's already implied by the design.

- [ ] **Step 1: Write tests**

Append to `tests/test_event_info.py`:

```python
@pytest.mark.parametrize("platform", ["betpawa", "sportybet", "bet9ja", "betway", "msport"])
def test_empty_dict_does_not_raise(platform):
    assert extract_kickoff({}, platform) is None
    assert extract_participants({}, platform) == Participants()
    assert extract_live_info({}, platform) == LiveInfo()


def test_unknown_platform_returns_empty():
    fixture = _load("betpawa", "live")
    assert extract_kickoff(fixture, "no-such-platform") is None
    assert extract_participants(fixture, "no-such-platform") == Participants()
    assert extract_live_info(fixture, "no-such-platform") == LiveInfo()


def test_invalid_mode_silently_treated_as_none():
    """Unknown mode strings must not raise; behavior matches mode=None."""
    d = _load("betpawa", "live")
    li_invalid = extract_live_info(d, "betpawa", mode="garbage")  # type: ignore[arg-type]
    li_default = extract_live_info(d, "betpawa")
    assert li_invalid == li_default


def test_invalid_mode_on_betway_does_not_force_prematch():
    """Specifically: a bogus mode should NOT silently become 'prematch'
    (which would zero out live data on Betway)."""
    d = _load("betway", "live")
    li = extract_live_info(d, "betway", mode="LIVE")  # type: ignore[arg-type]
    # 'LIVE' is not in the Mode literal → fall back to auto-detect → live data.
    assert li.minute == 90
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_event_info.py -v -k "empty_dict or unknown_platform or invalid_mode"`
Expected: 7 passed (5 parametrised + 3 dedicated).

- [ ] **Step 3: Commit**

```bash
git add tests/test_event_info.py
git commit -m "test(event_info): unknown platform, empty dict, invalid mode"
```

---

## Task 9: Cross-platform consistency check

**Files:**
- Modify: `tests/test_event_info.py`

Same SR id across the 5 fixtures of one phase ⇒ kickoffs agree within 5 minutes (small tolerance for any clock skew between providers). Skip Bet9ja in the live phase because it carries no kickoff there.

- [ ] **Step 1: Write tests**

Append to `tests/test_event_info.py`:

```python
ALL_PLATFORMS = ["betpawa", "sportybet", "bet9ja", "betway", "msport"]


def _kickoffs_for(phase: str) -> dict[str, datetime | None]:
    return {p: extract_kickoff(_load(p, phase), p) for p in ALL_PLATFORMS}


def test_kickoffs_agree_across_platforms_prematch():
    kicks = _kickoffs_for("prematch")
    assert all(k is not None for k in kicks.values()), kicks
    base = kicks["betpawa"]
    for platform, k in kicks.items():
        assert k is not None
        delta = abs((k - base).total_seconds())
        assert delta <= 300, f"{platform} kickoff drifts {delta}s vs betpawa"


def test_kickoffs_agree_across_platforms_live_except_bet9ja():
    kicks = _kickoffs_for("live")
    # Bet9ja's live response has no kickoff.
    assert kicks["bet9ja"] is None
    base = kicks["betpawa"]
    for platform, k in kicks.items():
        if platform == "bet9ja":
            continue
        assert k is not None, platform
        delta = abs((k - base).total_seconds())
        assert delta <= 300, f"{platform} kickoff drifts {delta}s vs betpawa"


def test_participants_present_for_all_except_bet9ja_live():
    """Sanity: every fixture except bet9ja-live yields non-None home/away."""
    for phase in ("prematch", "live"):
        for platform in ALL_PLATFORMS:
            p = extract_participants(_load(platform, phase), platform)
            if platform == "bet9ja" and phase == "live":
                assert p == Participants(), platform
            else:
                assert p.home and p.away, f"{platform}/{phase}"
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_event_info.py -v -k "kickoffs_agree or participants_present"`
Expected: 3 passed.

- [ ] **Step 3: Run the full event_info test suite**

Run: `pytest tests/test_event_info.py -v`
Expected: ~50 passed (1 + 4 + 6 + 6 + 9 + 7 + 6 + 8 + 3 ≈ 50).

- [ ] **Step 4: Commit**

```bash
git add tests/test_event_info.py
git commit -m "test(event_info): cross-platform kickoff/participants consistency"
```

---

## Task 10: Re-export public surface from bookieskit/__init__.py

**Files:**
- Modify: `src/bookieskit/__init__.py`
- Modify: `tests/test_event_info.py` (one extra import test)

- [ ] **Step 1: Write failing test**

Append to `tests/test_event_info.py`:

```python
def test_top_level_reexports():
    """Public surface must be importable from `bookieskit` directly."""
    import bookieskit

    for name in (
        "extract_kickoff",
        "extract_live_info",
        "extract_participants",
        "is_live_now",
        "LiveInfo",
        "Participants",
        "Mode",
    ):
        assert hasattr(bookieskit, name), name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_event_info.py::test_top_level_reexports -v`
Expected: FAIL — `extract_kickoff` not on `bookieskit`.

- [ ] **Step 3: Add re-exports**

Replace `src/bookieskit/__init__.py` with:

```python
"""Bookieskit — HTTP clients for betting data scraping."""

from bookieskit.bookmakers.bet9ja import Bet9ja
from bookieskit.bookmakers.betpawa import BetPawa
from bookieskit.bookmakers.betway import Betway
from bookieskit.bookmakers.msport import MSport
from bookieskit.bookmakers.sportybet import SportyBet
from bookieskit.event_info import (
    LiveInfo,
    Mode,
    Participants,
    extract_kickoff,
    extract_live_info,
    extract_participants,
    is_live_now,
)

__version__ = "0.4.0"
__all__ = [
    "BetPawa",
    "SportyBet",
    "Bet9ja",
    "Betway",
    "MSport",
    "LiveInfo",
    "Mode",
    "Participants",
    "extract_kickoff",
    "extract_live_info",
    "extract_participants",
    "is_live_now",
    "__version__",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_event_info.py::test_top_level_reexports -v`
Expected: PASS.

- [ ] **Step 5: Run the full test suite to make sure nothing else broke**

Run: `pytest -q`
Expected: all tests pass (existing tests + new event_info tests).

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/__init__.py tests/test_event_info.py
git commit -m "feat(event_info): re-export public surface from top-level package"
```

---

## Task 11: Migrate `examples/monitor_competitions.py`

**Files:**
- Modify: `examples/monitor_competitions.py`

Replace inline `_parse_kickoff`, `_extract_live_info`, `_empty_live_info` with imports from `bookieskit.event_info`. Adapt the CSV row builder to convert `int|None` to strings at write time.

- [ ] **Step 1: Update imports**

In `examples/monitor_competitions.py`, change the imports block:

```python
# Public surface of the library — only what we need.
from bookieskit import (
    Bet9ja,
    BetPawa,
    Betway,
    LiveInfo,
    SportyBet,
    extract_kickoff,
    extract_live_info,
    extract_participants,
    is_live_now,
)
from bookieskit.markets import parse_markets
from bookieskit.matching import extract_sportradar_id
```

- [ ] **Step 2: Replace `resolve_event` to use the new helpers**

Replace the `resolve_event` function:

```python
async def resolve_event(bp: BetPawa, betpawa_id: str) -> dict | None:
    """One-shot resolve of static event metadata. Returns None on failure."""
    if betpawa_id in EVENT_CACHE:
        return EVENT_CACHE[betpawa_id]
    try:
        detail = await bp.get_event_detail(event_id=betpawa_id)
    except Exception as e:
        print(f"  resolve {betpawa_id}: ERROR {e}")
        return None
    parts = extract_participants(detail, platform="betpawa")
    sr_numeric = extract_sportradar_id(detail, platform="betpawa")
    kickoff = extract_kickoff(detail, platform="betpawa")
    EVENT_CACHE[betpawa_id] = {
        "sr_numeric": sr_numeric,
        "home": parts.home or "?",
        "away": parts.away or "?",
        "kickoff_utc": kickoff,
    }
    return EVENT_CACHE[betpawa_id]
```

Delete the now-unused `_parse_kickoff` function entirely.

- [ ] **Step 3: Delete `is_live_now` local helper**

The local `def is_live_now(...)` in the example is now identical to the library's. Delete the local definition; the import already provides the name.

- [ ] **Step 4: Replace `fetch_betpawa_tick` to use the library extractor**

Replace the `fetch_betpawa_tick` function and delete `_empty_live_info` and `_extract_live_info`:

```python
async def fetch_betpawa_tick(bp: BetPawa, betpawa_id: str) -> dict:
    """Fetch fresh BetPawa data for one tick. Returns {markets, live_info}."""
    try:
        detail = await bp.get_event_detail(event_id=betpawa_id)
    except Exception:
        return {"markets": [], "live_info": LiveInfo()}
    markets = parse_markets(detail, platform="betpawa")
    live_info = extract_live_info(detail, platform="betpawa")
    return {"markets": markets, "live_info": live_info}
```

Remove `_empty_live_info` and `_extract_live_info` definitions.

- [ ] **Step 5: Update the dict-keyed call sites to use dataclass attributes**

Inside `run_tick`, the live-info fields are now on a dataclass. Replace usages of `live_info["minute"]` etc. with the converted form. Find and replace the relevant block:

```python
            live_info = bp_result["live_info"] if live else LiveInfo()

            counts = " ".join(
                f"{short[name]}={len(per_bookmaker[name])}" for name in BOOKMAKERS
            )
            extra = ""
            if live and live_info.minute is not None:
                extra = (f"  [{live_info.period or ''} {live_info.minute}'  "
                         f"{live_info.score_home}-{live_info.score_away}]")
            print(f"    [{mode}] {entry['home']} vs {entry['away']}: {counts}{extra}")
```

- [ ] **Step 6: Update `event_rows` to take a LiveInfo and stringify at write time**

Replace `event_rows`:

```python
def event_rows(
    timestamp: str,
    event_meta: dict,
    sr_numeric: str,
    mode: str,
    live_info: LiveInfo,
    per_bookmaker: dict[str, list],
) -> list[dict]:
    """Build CSV rows for one event."""
    grid: dict[tuple, dict[str, float]] = defaultdict(dict)

    for bookie, markets in per_bookmaker.items():
        for m in markets:
            for line, outcome, odds in _outcomes_to_emit(m):
                key = (m.canonical_id, m.name, line, outcome)
                grid[key][bookie] = odds

    def sort_key(item):
        _cid, name, line, outcome = item[0]
        line_key = (1, float(line)) if line != "" else (0, 0.0)
        return (name, line_key, outcome)

    def _s(v: object) -> str:
        return "" if v is None else str(v)

    rows: list[dict] = []
    for (_cid, name, line, outcome), per_bookie in sorted(grid.items(), key=sort_key):
        rows.append({
            "timestamp": timestamp,
            "mode": mode,
            "betpawa_id": event_meta["betpawa_id"],
            "sr_id": sr_numeric,
            "home": event_meta["home"],
            "away": event_meta["away"],
            "minute": _s(live_info.minute),
            "period": _s(live_info.period),
            "score_home": _s(live_info.score_home),
            "score_away": _s(live_info.score_away),
            "market": name,
            "line": line,
            "outcome": outcome,
            **{b: per_bookie.get(b, "") for b in BOOKMAKERS},
        })
    return rows
```

- [ ] **Step 7: Run a single tick to verify the migration**

Delete `monitor_odds.csv` first (or use `--csv` flag) so a fresh run produces a header row for inspection:

```bash
python examples/monitor_competitions.py --once --csv /tmp/event_info_smoke.csv
```

Expected: prints `tick start ... tick end — 2 events, ~80 rows appended`. The CSV columns and content match what `monitor_odds.csv` produces today (one row per outcome, blanks in live-info columns during prematch).

- [ ] **Step 8: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add examples/monitor_competitions.py
git commit -m "refactor(examples): monitor_competitions uses bookieskit.event_info"
```

---

## Final Verification

- [ ] Run the full test suite end-to-end: `pytest -q`
- [ ] Run ruff: `ruff check src/bookieskit/event_info.py tests/test_event_info.py examples/monitor_competitions.py`
- [ ] Smoke test: `python examples/monitor_competitions.py --once`
- [ ] Sanity check public API: `python -c "from bookieskit import extract_kickoff, extract_live_info, extract_participants, is_live_now, LiveInfo, Participants, Mode; print('ok')"`
