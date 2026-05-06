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


# ---- SportyBet ------------------------------------------------------------

def _kickoff_sportybet(response: dict, _mode: Mode | None) -> datetime | None:
    data = response.get("data") or {}
    ms = data.get("estimateStartTime")
    if not isinstance(ms, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (ValueError, OSError):
        return None


def _participants_sportybet(response: dict, _mode: Mode | None) -> Participants:
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


# ---- Bet9ja ---------------------------------------------------------------

def _bet9ja_is_live(response: dict, mode: Mode | None) -> bool:
    """True if explicit mode says live, or if auto-detect sees D.A.

    Caller passed mode='live' / mode='prematch' wins. Otherwise the response
    shape decides: presence of `D.A` means it's a GetLiveEvent payload.
    """
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


# ---- Betway ---------------------------------------------------------------

def _kickoff_betway(response: dict, _mode: Mode | None) -> datetime | None:
    sport_event = response.get("sportEvent") or {}
    s = sport_event.get("expectedStartEpoch")
    if not isinstance(s, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(s, tz=timezone.utc)
    except (ValueError, OSError):
        return None


def _participants_betway(response: dict, _mode: Mode | None) -> Participants:
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
    # Auto-detect prematch via two independent signals OR'd together:
    #  (a) the `time` key is absent (most common — Betway omits it pre-kick)
    #  (b) `comments == "NotStarted"` (covers the edge case where Betway sends
    #      `time: 0` literally instead of omitting the key).
    # Both must be checked: removing either leaves a hole. The score=['0','0']
    # value reported during prematch is a known artefact and must be suppressed.
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


# ---- MSport ---------------------------------------------------------------

def _kickoff_msport(response: dict, _mode: Mode | None) -> datetime | None:
    data = response.get("data") or {}
    ms = data.get("startTime")
    if not isinstance(ms, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (ValueError, OSError):
        return None


def _participants_msport(response: dict, _mode: Mode | None) -> Participants:
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


# ---- Dispatch tables -------------------------------------------------------

_KICKOFF_DISPATCH: dict[str, Callable[[dict, Mode | None], datetime | None]] = {
    "betpawa": _kickoff_betpawa,
    "sportybet": _kickoff_sportybet,
    "bet9ja": _kickoff_bet9ja,
    "betway": _kickoff_betway,
    "msport": _kickoff_msport,
}

_PARTICIPANTS_DISPATCH: dict[str, Callable[[dict, Mode | None], Participants]] = {
    "betpawa": _participants_betpawa,
    "sportybet": _participants_sportybet,
    "bet9ja": _participants_bet9ja,
    "betway": _participants_betway,
    "msport": _participants_msport,
}

_LIVE_INFO_DISPATCH: dict[str, Callable[[dict, Mode | None], LiveInfo]] = {
    "betpawa": _live_info_betpawa,
    "sportybet": _live_info_sportybet,
    "bet9ja": _live_info_bet9ja,
    "betway": _live_info_betway,
    "msport": _live_info_msport,
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
