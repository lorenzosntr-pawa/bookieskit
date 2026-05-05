"""Market mapping and normalization."""

from bookieskit.markets.parser import parse_markets
from bookieskit.markets.registry import MarketRegistry
from bookieskit.markets.types import (
    MarketMapping,
    NormalizedMarket,
    Outcome,
    OutcomeMapping,
)

__all__ = [
    "MarketRegistry",
    "parse_markets",
    "NormalizedMarket",
    "Outcome",
    "MarketMapping",
    "OutcomeMapping",
]
