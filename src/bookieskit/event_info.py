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


def is_live_now(kickoff: datetime | None) -> bool:
    """True iff `kickoff` is non-None and in the past (UTC now)."""
    if kickoff is None:
        return False
    return datetime.now(timezone.utc) >= kickoff


# ---- BetPawa --------------------------------------------------------------

def _kickoff_betpawa(response: dict, _mode: Mode | None) -> datetime | None:
    s = response.get("startTime")
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _participants_betpawa(response: dict, _mode: Mode | None) -> Participants:
    parts = response.get("participants") or []
    home = (
        parts[0].get("name") if len(parts) > 0 and isinstance(parts[0], dict) else None
    )
    away = (
        parts[1].get("name") if len(parts) > 1 and isinstance(parts[1], dict) else None
    )
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


# ---- Dispatch tables -------------------------------------------------------

_KICKOFF_DISPATCH: dict[str, Callable[[dict, Mode | None], datetime | None]] = {
    "betpawa": _kickoff_betpawa,
}

_PARTICIPANTS_DISPATCH: dict[str, Callable[[dict, Mode | None], Participants]] = {
    "betpawa": _participants_betpawa,
}

_LIVE_INFO_DISPATCH: dict[str, Callable[[dict, Mode | None], LiveInfo]] = {
    "betpawa": _live_info_betpawa,
}


# ---- Public API ------------------------------------------------------------

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
