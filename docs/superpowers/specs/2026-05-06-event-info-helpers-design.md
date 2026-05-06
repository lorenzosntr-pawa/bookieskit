# Event-info helpers in bookieskit — design

## 1. Goal

Promote the kickoff / live-info / participants extraction logic that today
lives inside `examples/monitor_competitions.py` into a first-class library
module, and wire it for **all five bookmakers** (BetPawa, SportyBet, Bet9ja,
Betway, MSport), mirroring the existing `extract_sportradar_id` dispatcher
pattern in `bookieskit.matching.extractor`.

This unblocks live-monitoring projects: callers can compute "is this match
live yet?" from a prematch fetch, and read minute / score / period from a
live fetch, without re-implementing per-platform JSON spelunking.

## 2. Public surface

New module: `src/bookieskit/event_info.py`. Re-exported from
`bookieskit/__init__.py` so users can:

```python
from bookieskit import (
    extract_kickoff,
    extract_live_info,
    extract_participants,
    is_live_now,
    LiveInfo,
    Participants,
    Mode,  # Literal["prematch", "live"]
)
```

Functions:

- `extract_kickoff(response: dict, platform: str, *, mode: Mode | None = None) -> datetime | None`
  Returns a tz-aware UTC `datetime`, or `None`.
- `extract_live_info(response: dict, platform: str, *, mode: Mode | None = None) -> LiveInfo`
  Always returns a `LiveInfo`; fields that are not present become `None`.
- `extract_participants(response: dict, platform: str, *, mode: Mode | None = None) -> Participants`
  Always returns a `Participants`; fields not present become `None`.
- `is_live_now(kickoff: datetime | None) -> bool`
  Returns `False` if `kickoff is None`, else `datetime.now(timezone.utc) >= kickoff`.

Where `Mode = Literal["prematch", "live"]`.

`mode` is an optional keyword-only hint:

- **`mode=None` (default)** — auto-detect from response shape. For most
  platforms this is unambiguous (e.g. BetPawa: `results is None` ⇒
  prematch; Bet9ja: `D.A` present ⇒ live). Recommended default.
- **`mode="prematch"` / `mode="live"`** — explicit. Caller asserts which
  endpoint they used. The extractor takes the corresponding branch
  without probing. Most useful for Bet9ja (whose two endpoints return
  genuinely different shapes) and for forcing Betway to ignore its
  prematch `score=["0","0"]` artefact. For BetPawa / SportyBet / MSport
  the explicit mode and the auto-detected mode agree on healthy
  responses — passing it is documentation but has no behavioral effect.

The dispatcher signature itself remains symmetric across all platforms,
matching `extract_sportradar_id(response, platform)`.

Dataclasses (frozen):

```python
@dataclass(frozen=True)
class LiveInfo:
    minute: int | None
    period: str | None
    score_home: int | None
    score_away: int | None

@dataclass(frozen=True)
class Participants:
    home: str | None
    away: str | None
```

`None` (not `""`, not `0`) for missing fields — distinguishes "prematch /
unknown" from a real 0-0 at minute 0.

## 3. Field paths per platform

Captured fixtures live under `tests/fixtures/event_info/{platform}/{prematch|live}.json`
and bind the unit tests to real shapes.

### 3.1 BetPawa

Endpoint: `BetPawa.get_event_detail(event_id)` — same response for prematch
and live; live fields are populated only after kickoff.

| Field | JSON path | Notes |
|---|---|---|
| kickoff | `startTime` | ISO 8601 with `Z` (UTC). Normalise `Z` → `+00:00` then `datetime.fromisoformat`. |
| home | `participants[0].name` | |
| away | `participants[1].name` | |
| minute | `results.display.minute` | String, cast to int. `results` is `None` during prematch — return `None`. |
| period | `results.display.currentPeriod.name` | e.g. `"Second Half"`. |
| score_home | walk `results.participantPeriodResults[]` for `participant.type == "HOME"`, find `periodResults[].period.slug == "FULL_TIME_EXCLUDING_OVERTIME"`, take `result` and cast to int. | |
| score_away | same as above with `participant.type == "AWAY"`. | |

### 3.2 SportyBet

Endpoint: `SportyBet.get_event_detail(event_id, live=<bool>)`. Two call modes
returning the same `data.*` envelope; live-only fields are `None` when
`live=False` or when the match has not started.

| Field | JSON path | Notes |
|---|---|---|
| kickoff | `data.estimateStartTime` | Epoch milliseconds (UTC). `datetime.fromtimestamp(v/1000, tz=timezone.utc)`. |
| home | `data.homeTeamName` | |
| away | `data.awayTeamName` | |
| minute | `data.playedSeconds` | Format `"MM:SS"` (e.g. `"90:00"`). Parse minutes part as int. `None` during prematch. |
| period | `data.matchStatus` | Human-readable, e.g. `"H1"`, `"H2"`, `"HT"`, `"Not start"`. Map `"Not start"` → `None`. |
| score_home / score_away | `data.setScore` | Format `"H:A"` (e.g. `"0:3"`). Split on `:`. `None` during prematch. |

### 3.3 Bet9ja

Bet9ja uses **different shapes** for prematch and live event detail.
Branch selection rule:

- If caller passed `mode="prematch"` or `mode="live"`, take that branch.
- Else (auto-detect): if `D.A` is present in the response, treat as
  live; otherwise treat as prematch.

If the explicit `mode` and the response shape disagree (e.g. user passed
`mode="live"` but `D.A` is absent), follow the explicit mode and let the
field reads resolve to `None` — never raise.

#### 3.3.1 Prematch — `Bet9ja.get_event_detail(event_id)`

| Field | JSON path | Notes |
|---|---|---|
| kickoff | `D.STARTDATE` | Naive string `"YYYY-MM-DD HH:MM:SS"`. Empirically UTC (cross-checked vs BetPawa `startTime` Z-suffixed value). Parse with `datetime.strptime(...)` then `.replace(tzinfo=timezone.utc)`. |
| home | `D.DS` | Format `"Home - Away"`. Split on `" - "` (with spaces). |
| away | `D.DS` | Same; second segment. |
| minute / period / scores | n/a | Prematch response has no live block — all `None`. |

#### 3.3.2 Live — `Bet9ja.get_live_event_detail(event_id)`

| Field | JSON path | Notes |
|---|---|---|
| kickoff | n/a | Live response does not carry kickoff — return `None`. |
| home / away | n/a | Live response does not carry team names — return `None`/`None`. Callers can resolve via the prematch endpoint or `get_live_events`. |
| minute | `D.A.T` | Integer (e.g. `91`). |
| period | `D.A.ES` | e.g. `"2nd Half"`. |
| score_home / score_away | `D.A.R.S` | Format `"H:A"`. Split on `:`. |

### 3.4 Betway

Endpoint: `Betway.get_event_detail(event_id)` — same response for both phases.
Field shape under `sportEvent.gameStateTimeScore` differs by phase
(`comments == "NotStarted"` for prematch, `"RegularPeriod"` for live).

| Field | JSON path | Notes |
|---|---|---|
| kickoff | `sportEvent.expectedStartEpoch` | Epoch **seconds** (UTC). `datetime.fromtimestamp(v, tz=timezone.utc)`. |
| home | `sportEvent.homeTeam` | |
| away | `sportEvent.awayTeam` | |
| minute | `sportEvent.gameStateTimeScore.time` | Integer. **Caveat:** sibling `timePeriod` says `"seconds"` but observed value (`90` at full time) is minutes; trust the value. Key is absent in prematch (`comments == "NotStarted"`) — return `None`. |
| period | `sportEvent.gameStateTimeScore.state` | e.g. `"2nd half"`. Key is absent in prematch — return `None`. |
| score_home / score_away | `sportEvent.gameStateTimeScore.score` | List of two strings (e.g. `["0", "3"]`). Cast each to int. **Empirically present even during prematch with `["0","0"]`** — gate on either: (a) explicit `mode="prematch"` ⇒ return `None`/`None`; (b) auto-detect via the presence of the `time` key (or `comments != "NotStarted"`). Avoids emitting fake 0-0 scores. |

### 3.5 MSport

Endpoint: `MSport.get_event_detail(event_id, live=<bool>)`. Same `data.*`
envelope; live fields populated only when the match is in progress.

| Field | JSON path | Notes |
|---|---|---|
| kickoff | `data.startTime` | Epoch milliseconds (UTC). |
| home | `data.homeTeam` | |
| away | `data.awayTeam` | |
| minute | `data.playedTime` | Format `"M'SS\""` (e.g. `"90'00\""`). Parse the minutes portion (digits before `'`). |
| period | `data.statusDescription` | `None` in observed live fixture; may carry e.g. `"H1"`/`"H2"` in other states. Extractor returns the value as-is, or `None`. |
| score_home / score_away | `data.scoreOfWholeMatch` | Format `"H:A"`. `None` during prematch. |

## 4. Error handling

All extractors are **total**: any missing key, wrong type, or per-field
parse error becomes `None` in that field — never raises. Rationale: these
run inside live-monitoring fetch loops where one weird payload must not
kill the loop.

- Unknown `platform` value → `None` (kickoff), all-`None` `LiveInfo`,
  all-`None` `Participants`. Matches the existing `extract_sportradar_id`
  behavior (`return None` on unknown platform).
- Per-field cast errors (e.g. `int("?")`) are caught at field granularity
  and yield `None` only for that field.
- Invalid `mode` values (anything not in `{None, "prematch", "live"}`) are
  treated as `None` — fall back to auto-detect, never raise.

## 5. Testing

Unit tests in `tests/test_event_info.py`. Pure-data tests bound to the
captured fixtures under `tests/fixtures/event_info/`.

Per platform, per phase:
- `extract_kickoff` returns the expected `datetime` (UTC, tz-aware).
- `extract_participants` returns the expected `home`/`away` (with the known
  Bet9ja-live exception of both being `None`).
- `extract_live_info` returns expected fields during live, all-`None`
  during prematch (with the Betway carve-out: `score=["0","0"]` during
  prematch maps to `None`, not 0).

Plus generic tests:
- `extract_*(empty_dict, platform)` does not raise; returns the empty
  shape.
- `extract_*(<fixture>, "no-such-platform")` returns the empty shape.
- `is_live_now`: `None` → False; future → False; past → True.

Mode-hint tests:
- For each platform, `extract_*` with `mode=None` (auto-detect) and with
  the matching explicit `mode` agree on healthy fixtures.
- Bet9ja: passing `mode="live"` to a prematch fixture (and vice-versa)
  does not raise — it follows the explicit mode and yields `None`s where
  the requested fields are absent.
- Betway prematch fixture: `mode="prematch"` → score `None`/`None`
  (overrides the `["0","0"]` artefact); `mode=None` → same outcome via
  auto-detect.
- Invalid `mode` (e.g. `"foo"`) is silently treated as `None` — no
  exception.

Cross-platform consistency check (one parametrised test per extractor):
the kickoffs returned across the five fixtures for a single phase agree
within a small tolerance (e.g. ≤ 5 minutes), and `home`/`away` team names
are case-insensitive substrings of each other in some direction (e.g.
`"Wuhan Three Towns"` ⊆ `"Wuhan Three Towns FC"`). Bet9ja-live is excepted
from the participants check because its live response carries no team
names. This guards against shape drift over time.

## 6. Migration of `examples/monitor_competitions.py`

Replace inline `_parse_kickoff`, `_extract_live_info`, `_empty_live_info`
with imports from `bookieskit.event_info`. The CSV row builder switches
from "stringified-from-the-start" to converting at write time:

```python
"minute": "" if li.minute is None else str(li.minute),
"score_home": "" if li.score_home is None else str(li.score_home),
# ...etc
```

Same one-tick output shape — the script's CSV is unchanged.

## 7. Out of scope

- No client-side convenience methods (no `bp.get_event_snapshot`).
- No `event_phase("ended")` lifecycle helper — the "ended" boundary
  varies by bookmaker (settled vs scrubbed vs FT-but-not-settled) and we
  don't have evidence yet for a clean rule.
- Bet9ja-live `extract_participants` returns `(None, None)`; the design
  notes the workaround (resolve via prematch endpoint or live-events
  list) but does not paper over it inside the extractor.
- No coverage of the live-events *list* response shapes — only event
  *detail* responses are mapped. The list endpoints are a separate
  concern.

## 8. Repository layout

```
src/bookieskit/event_info.py          # new module
tests/test_event_info.py              # new tests
tests/fixtures/event_info/
  betpawa/{prematch,live}.json
  sportybet/{prematch,live}.json
  bet9ja/{prematch,live}.json
  betway/{prematch,live}.json
  msport/{prematch,live}.json
scripts/capture_event_info_fixtures.py # already exists; keep for re-capture
```

`bookieskit/__init__.py` adds the six re-exports listed in §2.
