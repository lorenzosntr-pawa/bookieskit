"""Dataclasses for the market-add harness."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Handle:
    """Per-bookmaker identifier(s) needed to fetch markets for the event."""

    platform: str
    event_id: str | None  # SR-prefixed, numeric, or internal id to fetch with
    extra: dict[str, Any] = field(default_factory=dict)  # e.g. betika comp id


@dataclass
class ResolvedEvent:
    """The outcome of resolving one seed across the requested bookmakers."""

    seed: str
    sport: str
    sr_numeric: str | None
    home: str
    away: str
    handles: dict[str, Handle]  # platform -> handle (present only where resolved)
    skipped: dict[str, str]  # platform -> human reason (cookie/not found/error)


@dataclass
class Candidate:
    """One candidate market discovered on a bookmaker payload."""

    platform: str
    market_id: str | None  # id / key / marketId / sub_type_id, per platform
    name: str
    specifier: str | None
    outcomes: list[str]


@dataclass
class VerifyResult:
    """Per-platform parse_markets result."""

    platform: str
    resolved: dict[str, Any]  # canonical_id -> {lines/outcomes with odds}
    missing: list[str]  # requested canonical_ids that did NOT parse
