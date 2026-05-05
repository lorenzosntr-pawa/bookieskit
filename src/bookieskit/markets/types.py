"""Data types for market mapping."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Outcome:
    """A single outcome within a market."""

    canonical_name: str
    odds: float
    platform_name: str


@dataclass(frozen=True)
class NormalizedMarket:
    """A market normalized to canonical format.

    For simple markets (1X2, BTTS, DC): outcomes is populated, lines is None.
    For parameterized markets (O/U, handicaps): lines is populated, outcomes is empty.
    """

    canonical_id: str
    name: str
    outcomes: list[Outcome] = field(default_factory=list)
    lines: dict[float, list[Outcome]] | None = None


@dataclass(frozen=True)
class OutcomeMapping:
    """Maps one outcome across platforms."""

    canonical_name: str
    betpawa: str
    sportybet: str
    bet9ja: str
    betway: str = ""


@dataclass(frozen=True)
class MarketMapping:
    """Defines how one market maps across platforms."""

    canonical_id: str
    name: str
    betpawa_id: str | None
    sportybet_id: str | None
    bet9ja_key: str | None
    betway_id: str | None = None
    outcomes: dict[str, OutcomeMapping] = field(default_factory=dict)
    parameterized: bool = False
