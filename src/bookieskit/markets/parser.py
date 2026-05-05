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
        platform: "betpawa", "sportybet", "bet9ja", "betway", or "msport"
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
        "betway": _parse_betway,
        "msport": _parse_msport,
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
        # BetPawa nests market ID under marketType.id
        market_type = market_data.get("marketType", {})
        market_id = str(market_type.get("id", market_data.get("id", "")))
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
    if not isinstance(rows, list):
        rows = [rows] if rows else []

    for row in rows:
        for price in row.get("prices", []):
            price_name = str(price.get("name", price.get("displayName", "")))
            # BetPawa uses "price" field (not "odds")
            odds = float(price.get("price", price.get("odds", 0)))
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
    if not isinstance(rows, list):
        rows = [rows] if rows else []

    for row in rows:
        # BetPawa uses "handicap" field (internal value, divide by 4 for actual line)
        # or "formattedHandicap" (display value, already correct)
        formatted = row.get("formattedHandicap")
        if formatted is not None:
            try:
                line = float(formatted)
            except (ValueError, TypeError):
                line = None
        else:
            raw_handicap = row.get("handicap")
            if raw_handicap is not None:
                line = float(raw_handicap) / 4
            else:
                line = row.get("line")
        if line is None:
            continue
        line = float(line)
        line_outcomes: list[Outcome] = []

        for price in row.get("prices", []):
            price_name = str(price.get("name", price.get("displayName", "")))
            odds = float(price.get("price", price.get("odds", 0)))
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
    """Extract line value from a specifier string.

    Shared by SportyBet and MSport — both use the same pipe-delimited
    key=value format (e.g., "total=2.5", "hcp=-0.5").
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
    """Find canonical outcome name from SportyBet outcome desc.

    Handles both exact match ("Over") and prefix match ("Over 2.5")
    for parameterized markets where desc includes the line value.
    """
    for om in mapping.outcomes.values():
        if om.sportybet == platform_name:
            return om.canonical_name
    # Fallback: prefix match for parameterized markets
    # e.g., "Over 2" should match mapping "Over"
    for om in mapping.outcomes.values():
        if platform_name.startswith(om.sportybet):
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
        # Bet9ja prematch keys start with "S_"; live keys start with "LIVES_".
        # Normalize both to "S_..." so the rest of the parser is unchanged.
        if key.startswith("LIVES_"):
            key = "S_" + key[len("LIVES_"):]
        elif not key.startswith("S_"):
            continue

        # Live odds are wrapped as {"v": <float>}; prematch are bare strings.
        if isinstance(value, dict):
            value = value.get("v")
        if value is None:
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


def _parse_betway(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse Betway event markets response.

    Betway returns denormalized data: marketsInGroup[], outcomes[], prices[]
    as separate arrays linked by marketId and outcomeId.
    """
    results: list[NormalizedMarket] = []
    markets_in_group = response.get("marketsInGroup", [])
    all_outcomes = response.get("outcomes", [])
    all_prices = response.get("prices", [])

    # Build price lookup: outcomeId -> priceDecimal
    price_map: dict[str, float] = {}
    for p in all_prices:
        price_map[str(p.get("outcomeId", ""))] = float(
            p.get("priceDecimal", 0)
        )

    # Build outcome lookup: marketId -> list of outcomes
    outcomes_by_market: dict[str, list[dict]] = {}
    for o in all_outcomes:
        mid = str(o.get("marketId", ""))
        if mid not in outcomes_by_market:
            outcomes_by_market[mid] = []
        outcomes_by_market[mid].append(o)

    # Group markets: find parent market name -> collect all variants
    # For parameterized markets (Total Goals), multiple entries share
    # the parent betway_id but have different handicap values
    simple_markets: dict[str, tuple[dict, list[dict]]] = {}
    parameterized_markets: dict[str, list[tuple[dict, list[dict]]]] = {}

    for market in markets_in_group:
        market_name = str(market.get("name", ""))
        market_id = str(market.get("marketId", ""))
        market_outcomes = outcomes_by_market.get(market_id, [])

        # Check if this is a known parent market
        mapping = registry.get_by_platform_id("betway", market_name)
        if mapping is not None:
            if mapping.parameterized:
                if mapping.betway_id not in parameterized_markets:
                    parameterized_markets[mapping.betway_id] = []
                parameterized_markets[mapping.betway_id].append(
                    (market, market_outcomes)
                )
            else:
                simple_markets[market_name] = (
                    market,
                    market_outcomes,
                )
            continue

        # Check if this is a parameterized variant (name="Total")
        # by checking if any registered parameterized market
        # has a matching parent
        for mm in registry.list_markets():
            if not mm.parameterized or not mm.betway_id:
                continue
            # "Total" matches "[Total Goals]" parent
            parent_name = mm.betway_id
            if _is_betway_parameterized_variant(
                market_name, parent_name
            ):
                if parent_name not in parameterized_markets:
                    parameterized_markets[parent_name] = []
                parameterized_markets[parent_name].append(
                    (market, market_outcomes)
                )
                break

    # Build simple markets
    for market_name, (market, outcomes_list) in simple_markets.items():
        mapping = registry.get_by_platform_id("betway", market_name)
        if mapping:
            parsed = _build_betway_simple(
                outcomes_list, mapping, price_map
            )
            if parsed:
                results.append(parsed)

    # Build parameterized markets
    for parent_name, entries in parameterized_markets.items():
        mapping = registry.get_by_platform_id("betway", parent_name)
        if mapping:
            parsed = _build_betway_parameterized(
                entries, mapping, price_map
            )
            if parsed:
                results.append(parsed)

    return results


def _is_betway_parameterized_variant(
    market_name: str, parent_name: str
) -> bool:
    """Check if a market name is a variant of a parameterized parent.

    e.g., "Total" is a variant of "[Total Goals]"
    """
    # Strip brackets from parent: "[Total Goals]" -> "Total Goals"
    clean_parent = parent_name.strip("[]")
    # "Total" matches if it's a prefix of "Total Goals"
    return clean_parent.startswith(market_name)


def _build_betway_simple(
    outcomes_list: list[dict],
    mapping: MarketMapping,
    price_map: dict[str, float],
) -> NormalizedMarket | None:
    """Build a simple NormalizedMarket from Betway outcomes."""
    parsed_outcomes: list[Outcome] = []

    for i, outcome_data in enumerate(outcomes_list):
        oid = str(outcome_data.get("outcomeId", ""))
        name = str(outcome_data.get("name", ""))
        odds = price_map.get(oid, 0)

        canonical = _resolve_outcome_betway(
            name, i, mapping
        )
        if canonical:
            parsed_outcomes.append(
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=name,
                )
            )

    if not parsed_outcomes:
        return None

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=parsed_outcomes,
        lines=None,
    )


def _build_betway_parameterized(
    entries: list[tuple[dict, list[dict]]],
    mapping: MarketMapping,
    price_map: dict[str, float],
) -> NormalizedMarket | None:
    """Build a parameterized NormalizedMarket from Betway entries.

    Betway links all outcomes to the parent market ID, not to individual
    line entries. Outcome IDs contain the line info (e.g., "...total=2.5~12").
    We collect outcomes from the parent (handicap=0) and distribute them
    to lines by matching line entries' marketId against outcome IDs.
    """
    lines: dict[float, list[Outcome]] = {}

    # Collect all outcomes from the parent entry (handicap=0)
    parent_outcomes: list[dict] = []
    line_market_ids: list[tuple[float, str]] = []

    for market, outcomes_list in entries:
        handicap = market.get("handicap")
        market_id = str(market.get("marketId", ""))
        if handicap is None:
            continue
        if handicap == 0:
            parent_outcomes = outcomes_list
        else:
            line_market_ids.append((float(handicap), market_id))

    # If we have parent outcomes, distribute them by line
    if parent_outcomes and line_market_ids:
        for line, line_mid in line_market_ids:
            line_outcomes: list[Outcome] = []
            # Find outcomes whose outcomeId starts with this line's marketId
            for i, outcome_data in enumerate(parent_outcomes):
                oid = str(outcome_data.get("outcomeId", ""))
                if oid.startswith(line_mid):
                    name = str(outcome_data.get("name", ""))
                    odds = price_map.get(oid, 0)
                    canonical = _resolve_outcome_betway(
                        name, i, mapping
                    )
                    if canonical:
                        line_outcomes.append(
                            Outcome(
                                canonical_name=canonical,
                                odds=odds,
                                platform_name=name,
                            )
                        )
            if line_outcomes:
                lines[line] = line_outcomes
    else:
        # Fallback: outcomes directly on line entries
        for market, outcomes_list in entries:
            handicap = market.get("handicap")
            if handicap is None or handicap == 0:
                continue
            line = float(handicap)
            line_outcomes_list: list[Outcome] = []
            for i, outcome_data in enumerate(outcomes_list):
                oid = str(outcome_data.get("outcomeId", ""))
                name = str(outcome_data.get("name", ""))
                odds = price_map.get(oid, 0)
                canonical = _resolve_outcome_betway(
                    name, i, mapping
                )
                if canonical:
                    line_outcomes_list.append(
                        Outcome(
                            canonical_name=canonical,
                            odds=odds,
                            platform_name=name,
                        )
                    )
            if line_outcomes_list:
                lines[line] = line_outcomes_list

    if not lines:
        return None

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=[],
        lines=lines,
    )


def _resolve_outcome_betway(
    platform_name: str,
    index: int,
    mapping: MarketMapping,
) -> str | None:
    """Find canonical outcome name from Betway outcome.

    Uses exact match first, then position-based matching for
    markets that use team names (1X2, DC).
    Sentinel values: __HOME__=pos0, __AWAY__=pos2,
    __POS_1__=pos0, __POS_2__=pos1, __POS_3__=pos2.
    """
    # Exact match first (strip whitespace from platform names)
    clean_name = platform_name.strip()
    for om in mapping.outcomes.values():
        if om.betway == clean_name:
            return om.canonical_name

    # Position-based match for sentinels
    position_sentinels = {
        0: ["__HOME__", "__POS_1__"],
        1: ["__POS_2__"],
        2: ["__AWAY__", "__POS_3__"],
    }
    sentinels_for_index = position_sentinels.get(index, [])
    for om in mapping.outcomes.values():
        if om.betway in sentinels_for_index:
            return om.canonical_name

    return None


def _parse_msport(
    response: dict, registry: MarketRegistry
) -> list[NormalizedMarket]:
    """Parse MSport event detail response.

    MSport's payload mirrors SportyBet's structurally but uses
    `description` instead of `desc` and `specifiers` (plural) instead
    of `specifier`. Market ids are integer-strings; parameterized
    markets repeat the same id once per line, with `specifiers` like
    "total=2.5" or "hcp=-0.5".
    """
    results: list[NormalizedMarket] = []
    data = response.get("data", response)
    markets = data.get("markets", [])

    parameterized_groups: dict[str, list[dict]] = {}

    for market_data in markets:
        market_id = str(market_data.get("id", ""))
        mapping = registry.get_by_platform_id("msport", market_id)
        if mapping is None:
            continue

        if mapping.parameterized:
            parameterized_groups.setdefault(market_id, []).append(market_data)
        else:
            results.append(_parse_msport_simple(market_data, mapping))

    for market_id, entries in parameterized_groups.items():
        mapping = registry.get_by_platform_id("msport", market_id)
        if mapping:
            results.append(_parse_msport_parameterized(entries, mapping))

    return results


def _parse_msport_simple(
    market_data: dict, mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a simple MSport market."""
    outcomes: list[Outcome] = []

    for outcome_data in market_data.get("outcomes", []):
        desc = str(outcome_data.get("description", ""))
        odds = float(outcome_data.get("odds", 0))
        canonical = _resolve_outcome_msport(desc, mapping)
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


def _parse_msport_parameterized(
    entries: list[dict], mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a parameterized MSport market (multiple entries, one per line)."""
    lines: dict[float, list[Outcome]] = {}

    for entry in entries:
        specifiers = entry.get("specifiers", "") or ""
        line = _extract_line_from_specifier(specifiers)
        if line is None:
            continue

        line_outcomes: list[Outcome] = []
        for outcome_data in entry.get("outcomes", []):
            desc = str(outcome_data.get("description", ""))
            odds = float(outcome_data.get("odds", 0))
            canonical = _resolve_outcome_msport(desc, mapping)
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


def _resolve_outcome_msport(
    platform_name: str, mapping: MarketMapping
) -> str | None:
    """Find canonical outcome name from MSport outcome description.

    Exact match first, then prefix match for parameterized payloads
    where the description embeds the line value (e.g. "Over 2.5").
    """
    for om in mapping.outcomes.values():
        if om.msport == platform_name:
            return om.canonical_name
    for om in mapping.outcomes.values():
        if om.msport and platform_name.startswith(om.msport):
            return om.canonical_name
    return None
