"""Data types for market mapping."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Outcome:
    """A single outcome within a market.

    `true_probability` is the bookmaker's fair (pre-margin) probability
    estimate — across mutually exclusive outcomes of one market, these
    sum to ≈1, NOT to 1 + margin like 1/odds would. Populated only when
    the platform exposes it (SportyBet, MSport, BetPawa) AND the caller
    passes `probability="true"` or `probability="with_void"` to
    parse_markets.

    `void_probability` is the bookmaker's estimate of the bet being
    voided/refunded (e.g. event abandoned). Populated only when the
    platform exposes it (SportyBet, BetPawa) AND the caller passes
    `probability="with_void"`. Always None on MSport/Betway/Bet9ja.
    """

    canonical_name: str
    odds: float
    platform_name: str
    true_probability: float | None = None
    void_probability: float | None = None


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
    msport: str = ""
    sportpesa: str = ""
    betika: str = ""


@dataclass(frozen=True)
class MarketMapping:
    """Defines how one market maps across platforms."""

    canonical_id: str
    name: str
    betpawa_id: str | None
    sportybet_id: str | None
    bet9ja_key: str | None
    betway_id: str | None = None
    msport_id: str | None = None
    sportpesa_id: str | None = None
    betika_id: str | None = None
    outcomes: dict[str, OutcomeMapping] = field(default_factory=dict)
    parameterized: bool = False
