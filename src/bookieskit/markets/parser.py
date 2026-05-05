"""Market parser — transforms raw event responses into NormalizedMarkets."""

from bookieskit.markets.registry import MarketRegistry
from bookieskit.markets.types import (
    MarketMapping,
    NormalizedMarket,
    Outcome,
)


def parse_markets(
    response: dict,
    platform: str,
    registry: MarketRegistry | None = None,
) -> list[NormalizedMarket]:
    """Parse raw event detail response into normalized markets.

    Args:
        response: Raw JSON from get_event_detail()
        platform: "betpawa", "sportybet", or "bet9ja"
        registry: Market registry to use (default: built-in 4 markets)

    Returns:
        List of NormalizedMarket for all recognized markets.
        Markets not in the registry are skipped.
    """
    if registry is None:
        registry = MarketRegistry()

    parsers = {
        "betpawa": _parse_betpawa,
        "sportybet": _parse_sportybet,
        "bet9ja": _parse_bet9ja,
    }
    parser = parsers.get(platform)
    if parser is None:
        return []
    return parser(response, registry)


def _parse_betpawa(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse BetPawa event detail response."""
    results: list[NormalizedMarket] = []
    markets = response.get("markets", [])

    for market_data in markets:
        market_id = str(market_data.get("id", ""))
        mapping = registry.get_by_platform_id("betpawa", market_id)
        if mapping is None:
            continue

        if mapping.parameterized:
            results.append(
                _parse_betpawa_parameterized(market_data, mapping)
            )
        else:
            results.append(_parse_betpawa_simple(market_data, mapping))

    return results


def _parse_betpawa_simple(
    market_data: dict, mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a simple BetPawa market (1X2, BTTS, DC)."""
    outcomes: list[Outcome] = []
    rows = market_data.get("row", [])

    for row in rows:
        for price in row.get("prices", []):
            price_name = str(price.get("name", ""))
            odds = float(price.get("odds", 0))
            canonical = _resolve_outcome_betpawa(
                price_name, mapping
            )
            if canonical:
                outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=price_name,
                    )
                )

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=outcomes,
        lines=None,
    )


def _parse_betpawa_parameterized(
    market_data: dict, mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a parameterized BetPawa market (O/U, handicaps)."""
    lines: dict[float, list[Outcome]] = {}
    rows = market_data.get("row", [])

    for row in rows:
        line = row.get("line")
        if line is None:
            continue
        line = float(line)
        line_outcomes: list[Outcome] = []

        for price in row.get("prices", []):
            price_name = str(price.get("name", ""))
            odds = float(price.get("odds", 0))
            canonical = _resolve_outcome_betpawa(
                price_name, mapping
            )
            if canonical:
                line_outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=price_name,
                    )
                )

        if line_outcomes:
            lines[line] = line_outcomes

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=[],
        lines=lines,
    )


def _resolve_outcome_betpawa(
    platform_name: str, mapping: MarketMapping
) -> str | None:
    """Find canonical outcome name from BetPawa platform name."""
    for om in mapping.outcomes.values():
        if om.betpawa == platform_name:
            return om.canonical_name
    return None


def _parse_sportybet(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse SportyBet event detail response. (Implemented in Task 5)"""
    return []


def _parse_bet9ja(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse Bet9ja event detail response. (Implemented in Task 6)"""
    return []
