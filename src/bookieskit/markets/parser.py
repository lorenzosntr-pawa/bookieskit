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
    """Parse SportyBet event detail response."""
    results: list[NormalizedMarket] = []
    data = response.get("data", response)
    markets = data.get("markets", [])

    # Group parameterized markets by ID (multiple entries per line)
    parameterized_groups: dict[str, list[dict]] = {}

    for market_data in markets:
        market_id = str(market_data.get("id", ""))
        mapping = registry.get_by_platform_id("sportybet", market_id)
        if mapping is None:
            continue

        if mapping.parameterized:
            if market_id not in parameterized_groups:
                parameterized_groups[market_id] = []
            parameterized_groups[market_id].append(market_data)
        else:
            results.append(
                _parse_sportybet_simple(market_data, mapping)
            )

    # Process grouped parameterized markets
    for market_id, entries in parameterized_groups.items():
        mapping = registry.get_by_platform_id("sportybet", market_id)
        if mapping:
            results.append(
                _parse_sportybet_parameterized(entries, mapping)
            )

    return results


def _parse_sportybet_simple(
    market_data: dict, mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a simple SportyBet market."""
    outcomes: list[Outcome] = []

    for outcome_data in market_data.get("outcomes", []):
        desc = str(outcome_data.get("desc", ""))
        odds = float(outcome_data.get("odds", 0))
        canonical = _resolve_outcome_sportybet(desc, mapping)
        if canonical:
            outcomes.append(
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=desc,
                )
            )

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=outcomes,
        lines=None,
    )


def _parse_sportybet_parameterized(
    entries: list[dict], mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a parameterized SportyBet market (multiple entries, one per line)."""
    lines: dict[float, list[Outcome]] = {}

    for entry in entries:
        specifier = entry.get("specifier", "") or ""
        line = _extract_line_from_specifier(specifier)
        if line is None:
            continue

        line_outcomes: list[Outcome] = []
        for outcome_data in entry.get("outcomes", []):
            desc = str(outcome_data.get("desc", ""))
            odds = float(outcome_data.get("odds", 0))
            canonical = _resolve_outcome_sportybet(desc, mapping)
            if canonical:
                line_outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=desc,
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


def _extract_line_from_specifier(specifier: str) -> float | None:
    """Extract line value from SportyBet specifier string.

    Examples: "total=2.5" -> 2.5, "hcp=-0.5" -> -0.5
    """
    for part in specifier.split("|"):
        if "=" in part:
            key, value = part.split("=", 1)
            if key in ("total", "hcp"):
                try:
                    return float(value)
                except ValueError:
                    continue
    return None


def _resolve_outcome_sportybet(
    platform_name: str, mapping: MarketMapping
) -> str | None:
    """Find canonical outcome name from SportyBet outcome desc."""
    for om in mapping.outcomes.values():
        if om.sportybet == platform_name:
            return om.canonical_name
    return None


def _parse_bet9ja(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse Bet9ja event detail response."""
    results: list[NormalizedMarket] = []
    data = response.get("D", {})
    odds_dict = data.get("O", {})

    if not odds_dict:
        return []

    # Group odds keys by market key
    # Format: S_{MARKET}_{OUTCOME} or S_{MARKET}@{LINE}_{OUTCOME}
    simple_groups: dict[str, list[tuple[str, float]]] = {}
    parameterized_groups: dict[str, dict[float, list[tuple[str, float]]]] = {}

    for key, value in odds_dict.items():
        if not key.startswith("S_"):
            continue

        odds = float(value)
        parsed = _parse_bet9ja_key(key)
        if parsed is None:
            continue

        market_key, line, outcome_suffix = parsed
        mapping = registry.get_by_platform_id("bet9ja", market_key)
        if mapping is None:
            continue

        if mapping.parameterized and line is not None:
            if market_key not in parameterized_groups:
                parameterized_groups[market_key] = {}
            if line not in parameterized_groups[market_key]:
                parameterized_groups[market_key][line] = []
            parameterized_groups[market_key][line].append(
                (outcome_suffix, odds)
            )
        else:
            if market_key not in simple_groups:
                simple_groups[market_key] = []
            simple_groups[market_key].append((outcome_suffix, odds))

    # Build simple markets
    for market_key, outcomes_data in simple_groups.items():
        mapping = registry.get_by_platform_id("bet9ja", market_key)
        if mapping:
            outcomes = _build_bet9ja_outcomes(outcomes_data, mapping)
            if outcomes:
                results.append(
                    NormalizedMarket(
                        canonical_id=mapping.canonical_id,
                        name=mapping.name,
                        outcomes=outcomes,
                        lines=None,
                    )
                )

    # Build parameterized markets
    for market_key, lines_data in parameterized_groups.items():
        mapping = registry.get_by_platform_id("bet9ja", market_key)
        if mapping:
            lines: dict[float, list[Outcome]] = {}
            for line, outcomes_data in lines_data.items():
                line_outcomes = _build_bet9ja_outcomes(
                    outcomes_data, mapping
                )
                if line_outcomes:
                    lines[line] = line_outcomes
            if lines:
                results.append(
                    NormalizedMarket(
                        canonical_id=mapping.canonical_id,
                        name=mapping.name,
                        outcomes=[],
                        lines=lines,
                    )
                )

    return results


def _parse_bet9ja_key(
    key: str,
) -> tuple[str, float | None, str] | None:
    """Parse a Bet9ja odds key into (market_key, line, outcome_suffix).

    Examples:
        "S_1X2_1" -> ("S_1X2", None, "1")
        "S_OU@2.5_O" -> ("S_OU", 2.5, "O")
        "S_DC_1X" -> ("S_DC", None, "1X")
    """
    # Remove "S_" prefix for parsing
    without_prefix = key[2:]

    # Check for line (@ separator)
    if "@" in without_prefix:
        # Format: MARKET@LINE_OUTCOME
        at_idx = without_prefix.index("@")
        market_part = without_prefix[:at_idx]
        rest = without_prefix[at_idx + 1:]
        # Find last underscore for outcome
        last_us = rest.rfind("_")
        if last_us == -1:
            return None
        try:
            line = float(rest[:last_us])
        except ValueError:
            return None
        outcome = rest[last_us + 1:]
        return (f"S_{market_part}", line, outcome)
    else:
        # Format: MARKET_OUTCOME (find the split point)
        # Market keys: 1X2, OU, GGNG, DC, etc.
        # Try splitting at last underscore
        last_us = without_prefix.rfind("_")
        if last_us == -1:
            return None
        market_part = without_prefix[:last_us]
        outcome = without_prefix[last_us + 1:]
        return (f"S_{market_part}", None, outcome)


def _build_bet9ja_outcomes(
    outcomes_data: list[tuple[str, float]],
    mapping: MarketMapping,
) -> list[Outcome]:
    """Build Outcome list from Bet9ja suffix/odds pairs."""
    outcomes: list[Outcome] = []
    for suffix, odds in outcomes_data:
        canonical = _resolve_outcome_bet9ja(suffix, mapping)
        if canonical:
            outcomes.append(
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=suffix,
                )
            )
    return outcomes


def _resolve_outcome_bet9ja(
    suffix: str, mapping: MarketMapping
) -> str | None:
    """Find canonical outcome name from Bet9ja key suffix."""
    for om in mapping.outcomes.values():
        if om.bet9ja == suffix:
            return om.canonical_name
    return None
