"""Event-info extractors — kickoff, live info, participants — for all 5 bookmakers.

Mirrors the dispatcher pattern in `bookieskit.matching.extractor`. Each public
function takes a `platform` string plus an optional `mode` keyword. Auto-detect
when mode is None; explicit mode (`"prematch"` / `"live"`) overrides.

All functions are total: missing keys, malformed shapes, and unknown platforms
yield None / empty dataclasses — they never raise.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

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
