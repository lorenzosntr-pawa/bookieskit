"""Market parser — transforms raw event responses into NormalizedMarkets."""

import re
from typing import Literal

from bookieskit.bookmakers._betika_shape import betika_first_match
from bookieskit.bookmakers._betpawa_obfuscation import decode_betpawa_probability
from bookieskit.markets.registry import MarketRegistry
from bookieskit.markets.types import (
    MarketMapping,
    NormalizedMarket,
    Outcome,
)

ProbabilityMode = Literal["off", "true", "with_void"]


def _normalised_probability_mode(mode: object) -> ProbabilityMode:
    """Coerce arbitrary user input to a known ProbabilityMode value.

    Invalid mode strings silently become 'off' — matches the total-function
    contract used elsewhere in the lib (e.g. event_info._normalised_mode)."""
    if mode == "true" or mode == "with_void":
        return mode  # type: ignore[return-value]
    return "off"


class _SportScopedRegistry:
    """Thin wrapper that injects a ``sport=`` filter into every
    ``get_by_platform_id`` call without requiring per-parser changes.

    Per-platform parsers issue ``registry.get_by_platform_id(platform,
    id)`` to resolve raw market ids to canonical mappings. For
    sport-scoped ids (SportPesa's "52" is football O/U AND basketball
    O/U), the bare lookup returns the first-registered mapping
    (typically soccer). When parse_markets is invoked with
    ``sport="basketball"``, this wrapper rewrites those lookups to use
    the sport-aware index instead.
    """

    def __init__(self, inner: MarketRegistry, sport: str) -> None:
        self._inner = inner
        self._sport = sport

    def get_by_platform_id(
        self,
        platform: str,
        platform_id: str,
        sport: str | None = None,
    ) -> MarketMapping | None:
        # Prefer caller-supplied sport (composes with outer wrappers
        # like _TeamScopedBetwayRegistry that forward sport=); fall
        # back to the injected sport when caller doesn't specify.
        return self._inner.get_by_platform_id(
            platform, platform_id, sport=sport if sport is not None else self._sport
        )

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


class _TeamScopedBetwayRegistry:
    """Wraps a MarketRegistry to substitute [Home Team] / [Away Team]
    placeholders in Betway mapping keys with the actual team names from
    the current event payload. Used only for the duration of one
    ``_parse_betway`` call.

    Mirrors :class:`_SportScopedRegistry` — re-scope a view of the
    registry without mutating the underlying indexes. The direct
    ``get_by_platform_id`` lookup is unchanged (covers every
    non-team-named market); placeholder substitution only fires when
    the direct lookup misses, and only iterates mappings that actually
    carry a placeholder token.
    """

    _PLACEHOLDER_HOME = "[Home Team]"
    _PLACEHOLDER_AWAY = "[Away Team]"

    def __init__(
        self, inner: MarketRegistry, home_team: str, away_team: str
    ) -> None:
        self._inner = inner
        self._home = home_team
        self._away = away_team

    def get_by_platform_id(
        self,
        platform: str,
        platform_id: str,
        sport: str | None = None,
    ) -> MarketMapping | None:
        result = self._inner.get_by_platform_id(
            platform, platform_id, sport=sport
        )
        if result is not None:
            return result
        if platform != "betway":
            return None
        for mapping in self._inner.list_markets():
            bid = mapping.betway_id
            if not bid or (
                self._PLACEHOLDER_HOME not in bid
                and self._PLACEHOLDER_AWAY not in bid
            ):
                continue
            substituted = bid.replace(
                self._PLACEHOLDER_HOME, self._home
            ).replace(self._PLACEHOLDER_AWAY, self._away)
            if substituted == platform_id:
                return mapping
        return None

    def list_markets(self) -> list[MarketMapping]:
        return self._inner.list_markets()

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


def parse_markets(
    response: dict,
    platform: str,
    registry: MarketRegistry | None = None,
    *,
    probability: ProbabilityMode = "off",
    sport: str | None = None,
) -> list[NormalizedMarket]:
    """Parse raw event detail response into normalized markets.

    Args:
        response: Raw JSON from get_event_detail()
        platform: One of "betpawa", "sportybet", "bet9ja", "betway",
            "msport", "sportpesa", "betika". Unknown values return [].
        registry: Market registry to use (default: built-in markets)
        probability: How much probability data to extract per outcome.
            "off" (default) — no probability parsing; both fields None.
            "true" — populate true_probability where the platform supports it.
            "with_void" — populate true_probability AND void_probability.
            Bet9ja, Betway, SportPesa, and Betika don't expose probability
            on their selections — both fields stay None for them regardless
            of mode.
        sport: Optional sport filter for registry lookups. Pass
            ``"basketball"`` to disambiguate market ids that overlap
            with football on the same bookmaker (notably SportPesa's
            id ``"52"`` is football O/U AND basketball O/U). Defaults
            to ``None``, preserving pre-0.12.0 behaviour (each shared
            id resolves to whichever mapping was registered first,
            typically soccer).

    Returns:
        List of NormalizedMarket for all recognized markets.
        Markets not in the registry are skipped.
    """
    if registry is None:
        registry = MarketRegistry()
    if sport is not None:
        registry = _SportScopedRegistry(registry, sport)  # type: ignore[assignment]
    mode = _normalised_probability_mode(probability)

    parsers = {
        "betpawa": _parse_betpawa,
        "sportybet": _parse_sportybet,
        "bet9ja": _parse_bet9ja,
        "betway": _parse_betway,
        "msport": _parse_msport,
        "sportpesa": _parse_sportpesa,
        "betika": _parse_betika,
    }
    parser = parsers.get(platform)
    if parser is None:
        return []
    return parser(response, registry, mode)


def _parse_betpawa(
    response: dict, registry: MarketRegistry, mode: ProbabilityMode = "off"
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
                _parse_betpawa_parameterized(market_data, mapping, mode)
            )
        else:
            results.append(_parse_betpawa_simple(market_data, mapping, mode))

    return results


def _parse_betpawa_simple(
    market_data: dict, mapping: MarketMapping, mode: ProbabilityMode = "off"
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
                true_p = void_p = None
                if mode != "off":
                    win, refund = decode_betpawa_probability(price.get("probability"))
                    true_p = win
                    if mode == "with_void":
                        void_p = refund
                outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=price_name,
                        true_probability=true_p,
                        void_probability=void_p,
                    )
                )

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=outcomes,
        lines=None,
    )


def _parse_betpawa_parameterized(
    market_data: dict, mapping: MarketMapping, mode: ProbabilityMode = "off"
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
                true_p = void_p = None
                if mode != "off":
                    win, refund = decode_betpawa_probability(price.get("probability"))
                    true_p = win
                    if mode == "with_void":
                        void_p = refund
                line_outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=price_name,
                        true_probability=true_p,
                        void_probability=void_p,
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


def _try_float(v: object) -> float | None:
    """Best-effort float cast; None on failure or empty/invalid string."""
    if v is None:
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _parse_sportybet(
    response: dict, registry: MarketRegistry, mode: ProbabilityMode = "off"
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
                _parse_sportybet_simple(market_data, mapping, mode)
            )

    # Process grouped parameterized markets
    for market_id, entries in parameterized_groups.items():
        mapping = registry.get_by_platform_id("sportybet", market_id)
        if mapping:
            results.append(
                _parse_sportybet_parameterized(entries, mapping, mode)
            )

    return results


def _parse_sportybet_simple(
    market_data: dict, mapping: MarketMapping, mode: ProbabilityMode = "off"
) -> NormalizedMarket:
    """Parse a simple SportyBet market."""
    outcomes: list[Outcome] = []

    for outcome_data in market_data.get("outcomes", []):
        desc = str(outcome_data.get("desc", ""))
        odds = float(outcome_data.get("odds", 0))
        canonical = _resolve_outcome_sportybet(desc, mapping)
        if canonical:
            true_p = void_p = None
            if mode != "off":
                true_p = _try_float(outcome_data.get("probability"))
                if mode == "with_void":
                    void_p = _try_float(outcome_data.get("voidProbability"))
            outcomes.append(
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=desc,
                    true_probability=true_p,
                    void_probability=void_p,
                )
            )

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=outcomes,
        lines=None,
    )


def _parse_sportybet_parameterized(
    entries: list[dict], mapping: MarketMapping, mode: ProbabilityMode = "off"
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
                true_p = void_p = None
                if mode != "off":
                    true_p = _try_float(outcome_data.get("probability"))
                    if mode == "with_void":
                        void_p = _try_float(outcome_data.get("voidProbability"))
                line_outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=desc,
                        true_probability=true_p,
                        void_probability=void_p,
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
    key=value format (e.g., "total=2.5", "hcp=-0.5", "goalnr=1").
    """
    for part in specifier.split("|"):
        if "=" in part:
            key, value = part.split("=", 1)
            if key in ("total", "hcp", "goalnr"):
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
    response: dict, registry: MarketRegistry, _mode: ProbabilityMode = "off"
) -> list[NormalizedMarket]:
    """Parse Bet9ja event detail response."""
    results: list[NormalizedMarket] = []
    data = response.get("D", {})
    odds_dict = data.get("O", {})

    if not odds_dict:
        return []

    # Group odds keys by canonical_id (not market_key) so multiple
    # canonicals sharing the same Bet9ja key (e.g. S_HAOU →
    # home_over_under_ft + away_over_under_ft) each get their own
    # NormalizedMarket.
    # Format: S_{MARKET}_{OUTCOME} or S_{MARKET}@{LINE}_{OUTCOME}
    simple_groups: dict[str, list[tuple[str, float]]] = {}
    parameterized_groups: dict[str, dict[float, list[tuple[str, float]]]] = {}
    canonical_to_mapping: dict[str, MarketMapping] = {}

    for key, value in odds_dict.items():
        # Bet9ja prematch keys are sport-prefixed: "S_" for soccer,
        # "B_" for basketball, "T_" for tennis. Live soccer is "LIVES_"
        # which we normalise to "S_" for the rest of the parser.
        if key.startswith("LIVES_"):
            key = "S_" + key[len("LIVES_"):]
        elif not (
            key.startswith("S_")
            or key.startswith("B_")
            or key.startswith("T_")
        ):
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

        # Find the mapping that (a) shares this Bet9ja key and (b)
        # has an OutcomeMapping claiming this outcome_suffix. This
        # supports one wire market splitting into multiple canonicals
        # (e.g. Bet9ja's S_HAOU contains _OH/_UH outcomes for the home
        # canonical AND _OA/_UA outcomes for the away canonical).
        mapping: MarketMapping | None = None
        for m in registry.list_markets():
            if m.bet9ja_key != market_key:
                continue
            if any(
                om.bet9ja == outcome_suffix for om in m.outcomes.values()
            ):
                mapping = m
                break
        if mapping is None:
            continue
        canonical_to_mapping[mapping.canonical_id] = mapping

        if mapping.parameterized and line is not None:
            parameterized_groups.setdefault(
                mapping.canonical_id, {}
            ).setdefault(line, []).append((outcome_suffix, odds))
        else:
            simple_groups.setdefault(mapping.canonical_id, []).append(
                (outcome_suffix, odds)
            )

    # Build simple markets — keyed by canonical_id
    for canonical_id, outcomes_data in simple_groups.items():
        mapping = canonical_to_mapping[canonical_id]
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

    # Build parameterized markets — keyed by canonical_id
    for canonical_id, lines_data in parameterized_groups.items():
        mapping = canonical_to_mapping[canonical_id]
        lines: dict[float, list[Outcome]] = {}
        for line, outcomes_data in lines_data.items():
            line_outcomes = _build_bet9ja_outcomes(outcomes_data, mapping)
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

    Bet9ja uses a single-letter sport prefix on every key: ``S_`` for
    soccer, ``B_`` for basketball. The rebuilt ``market_key`` preserves
    the original prefix so the registry lookup matches the right
    ``MarketMapping.bet9ja_key``.

    Examples:
        "S_1X2_1"   -> ("S_1X2", None, "1")
        "S_OU@2.5_O" -> ("S_OU", 2.5, "O")
        "S_DC_1X"   -> ("S_DC", None, "1X")
        "B_12_1"    -> ("B_12", None, "1")
        "B_OUN@157.5_O" -> ("B_OUN", 157.5, "O")
        "B_H@-3.5_1" -> ("B_H", -3.5, "1")  (signed line)
    """
    # The prefix is always 2 chars (S_ / B_ / T_) — preserve it on rebuild.
    if not (
        key.startswith("S_")
        or key.startswith("B_")
        or key.startswith("T_")
    ):
        return None
    prefix = key[:2]
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
        return (f"{prefix}{market_part}", line, outcome)
    else:
        # Format: MARKET_OUTCOME (find the split point)
        # Market keys: 1X2, OU, GGNG, DC, 12, OUN, H, etc.
        # Try splitting at last underscore
        last_us = without_prefix.rfind("_")
        if last_us == -1:
            return None
        market_part = without_prefix[:last_us]
        outcome = without_prefix[last_us + 1:]
        return (f"{prefix}{market_part}", None, outcome)


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
    response: dict, registry: MarketRegistry, _mode: ProbabilityMode = "off"
) -> list[NormalizedMarket]:
    """Parse Betway event markets response.

    Betway returns denormalized data: marketsInGroup[], outcomes[], prices[]
    as separate arrays linked by marketId and outcomeId. Per-team markets
    (Home/Away Total Goals) carry the literal team name in the market-name
    field; we wrap the registry with _TeamScopedBetwayRegistry so the
    canonical mappings can register the [Home Team] / [Away Team]
    placeholder form and have it substituted at parse-time.
    """
    sport_event = response.get("sportEvent", {})
    home_team = str(sport_event.get("homeTeam", ""))
    away_team = str(sport_event.get("awayTeam", ""))
    if home_team and away_team:
        registry = _TeamScopedBetwayRegistry(
            registry, home_team, away_team,
        )  # type: ignore[assignment]

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
                outcomes_list, mapping, price_map, _mode
            )
            if parsed:
                results.append(parsed)

    # Build parameterized markets
    for parent_name, entries in parameterized_markets.items():
        mapping = registry.get_by_platform_id("betway", parent_name)
        if mapping:
            parsed = _build_betway_parameterized(
                entries, mapping, price_map, _mode
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
    _mode: ProbabilityMode = "off",
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


_BETWAY_GOALNR_RE = re.compile(r"goalnr=(\d+)")


def _extract_betway_line_from_market_id(market_id: str) -> float | None:
    """Extract the line value from a Betway marketId path segment.

    Betway encodes some parameterized markets' line value in the marketId
    string rather than the `handicap` field. Currently observed: the
    `next_goal_ft` market uses `<prefix>goalnr=N~<suffix>` to specify
    which goal number a market entry covers. The line value is N (1-based).

    Returns None if no recognised marker is present.
    """
    if not market_id:
        return None
    m = _BETWAY_GOALNR_RE.search(market_id)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _build_betway_parameterized(
    entries: list[tuple[dict, list[dict]]],
    mapping: MarketMapping,
    price_map: dict[str, float],
    _mode: ProbabilityMode = "off",
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
    parent_market_id: str = ""

    for market, outcomes_list in entries:
        handicap = market.get("handicap")
        market_id = str(market.get("marketId", ""))
        if handicap is None:
            continue
        if handicap == 0:
            parent_outcomes = outcomes_list
            parent_market_id = market_id
        else:
            line_market_ids.append((float(handicap), market_id))

    # Case 1: parent + per-line entries — distribute parent outcomes by line
    if parent_outcomes and line_market_ids:
        for line, line_mid in line_market_ids:
            # Filter to the per-line outcomes first, THEN enumerate. The
            # position index passed to _resolve_outcome_betway must be the
            # index within this line's outcome group (0 = first outcome of
            # the line) — not the index within the full parent list. Using
            # the parent-list index breaks position sentinels like
            # __POS_2__ for every line whose outcomes don't happen to land
            # at the front of the parent list (e.g. basketball Handicap
            # where only the first line's outcomes were resolved).
            matched = [
                o for o in parent_outcomes
                if str(o.get("outcomeId", "")).startswith(line_mid)
            ]
            line_outcomes: list[Outcome] = []
            for i, outcome_data in enumerate(matched):
                name = str(outcome_data.get("name", ""))
                oid = str(outcome_data.get("outcomeId", ""))
                odds = price_map.get(oid, 0)
                canonical = _resolve_outcome_betway(name, i, mapping)
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
    # Case 2: single parent entry with line encoded in marketId
    # (e.g. next_goal_ft: "<eventId><typeId>goalnr=1~" with handicap=0).
    elif parent_outcomes and not line_market_ids:
        line = _extract_betway_line_from_market_id(parent_market_id)
        if line is not None:
            line_outcomes: list[Outcome] = []
            for i, outcome_data in enumerate(parent_outcomes):
                name = str(outcome_data.get("name", ""))
                oid = str(outcome_data.get("outcomeId", ""))
                odds = price_map.get(oid, 0)
                canonical = _resolve_outcome_betway(name, i, mapping)
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
        # Case 3 (existing fallback): outcomes directly on line entries.
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
    response: dict, registry: MarketRegistry, mode: ProbabilityMode = "off"
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
            results.append(_parse_msport_simple(market_data, mapping, mode))

    for market_id, entries in parameterized_groups.items():
        mapping = registry.get_by_platform_id("msport", market_id)
        if mapping:
            results.append(_parse_msport_parameterized(entries, mapping, mode))

    return results


def _parse_msport_simple(
    market_data: dict, mapping: MarketMapping, mode: ProbabilityMode = "off"
) -> NormalizedMarket:
    """Parse a simple MSport market."""
    outcomes: list[Outcome] = []

    for outcome_data in market_data.get("outcomes", []):
        desc = str(outcome_data.get("description", ""))
        odds = float(outcome_data.get("odds", 0))
        canonical = _resolve_outcome_msport(desc, mapping)
        if canonical:
            true_p = None
            if mode != "off":
                true_p = _try_float(outcome_data.get("probability"))
            # MSport doesn't expose voidProbability — leave void_probability as None
            # even when mode == "with_void".
            outcomes.append(
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=desc,
                    true_probability=true_p,
                )
            )

    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=outcomes,
        lines=None,
    )


def _parse_msport_parameterized(
    entries: list[dict], mapping: MarketMapping, mode: ProbabilityMode = "off"
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
                true_p = None
                if mode != "off":
                    true_p = _try_float(outcome_data.get("probability"))
                # MSport doesn't expose voidProbability — leave void_probability as None
                # even when mode == "with_void".
                line_outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=desc,
                        true_probability=true_p,
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


def _parse_sportpesa(
    response, registry: MarketRegistry, _mode: ProbabilityMode = "off"
) -> list[NormalizedMarket]:
    """Parse a SportPesa ``/api/games/markets`` payload.

    Response shape: ``{<game_id>: [<market>, ...]}``. Each market has
    ``id``, ``name``, ``specValue``, ``selections``. Parameterized
    markets (e.g. Total Goals Over/Under) repeat the same ``id`` once
    per line, each entry's ``specValue`` carrying the line value.

    SportPesa does not expose ``probability`` / ``void_probability``
    on selections — ``_mode`` is accepted for symmetry but both
    Outcome probability fields stay ``None``.
    """
    if not isinstance(response, dict) or not response:
        return []
    # The payload is keyed by game id; take the first (callers pass a
    # single-game response from get_event_markets).
    first_value = next(iter(response.values()), None)
    if not isinstance(first_value, list):
        return []
    markets = first_value

    results: list[NormalizedMarket] = []
    parameterized_groups: dict[str, list[dict]] = {}

    for md in markets:
        if not isinstance(md, dict):
            continue
        market_id = str(md.get("id", ""))
        mapping = registry.get_by_platform_id("sportpesa", market_id)
        if mapping is None:
            continue
        if mapping.parameterized:
            parameterized_groups.setdefault(market_id, []).append(md)
        else:
            results.append(_parse_sportpesa_simple(md, mapping))

    for market_id, entries in parameterized_groups.items():
        mapping = registry.get_by_platform_id("sportpesa", market_id)
        if mapping:
            results.append(_parse_sportpesa_parameterized(entries, mapping))

    return results


def _parse_sportpesa_simple(
    market_data: dict, mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a simple SportPesa market (1X2, BTTS, DC)."""
    outcomes: list[Outcome] = []
    for sel in market_data.get("selections", []):
        if not isinstance(sel, dict):
            continue
        short = str(sel.get("shortName", ""))
        try:
            odds = float(sel.get("odds", 0))
        except (TypeError, ValueError):
            continue
        canonical = _resolve_outcome_sportpesa(short, mapping)
        if canonical:
            outcomes.append(
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=short,
                )
            )
    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=outcomes,
        lines=None,
    )


def _parse_sportpesa_parameterized(
    entries: list[dict], mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a parameterized SportPesa market (Over/Under, handicaps).

    Each entry is one (market_id, specValue) pair with its selections.
    """
    lines: dict[float, list[Outcome]] = {}
    for entry in entries:
        try:
            line = float(entry.get("specValue"))
        except (TypeError, ValueError):
            continue
        line_outcomes: list[Outcome] = []
        for sel in entry.get("selections", []):
            if not isinstance(sel, dict):
                continue
            short = str(sel.get("shortName", ""))
            try:
                odds = float(sel.get("odds", 0))
            except (TypeError, ValueError):
                continue
            canonical = _resolve_outcome_sportpesa(short, mapping)
            if canonical:
                line_outcomes.append(
                    Outcome(
                        canonical_name=canonical,
                        odds=odds,
                        platform_name=short,
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


def _resolve_outcome_sportpesa(
    short_name: str, mapping: MarketMapping
) -> str | None:
    """Find canonical outcome name from a SportPesa selection ``shortName``.

    Exact match — SportPesa's ``shortName`` is a discrete token (``1``,
    ``X``, ``OV``, ``UN``, ``Yes``, ``1X``, ...) with no embedded line
    value, so no prefix-match fallback is required.
    """
    for om in mapping.outcomes.values():
        if om.sportpesa and om.sportpesa == short_name:
            return om.canonical_name
    return None


# ---- Betika ---------------------------------------------------------------

_BETIKA_NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_betika(
    response, registry: MarketRegistry, _mode: ProbabilityMode = "off"
) -> list[NormalizedMarket]:
    """Parse a Betika ``/v1/uo/matches`` payload.

    Response shape: ``{"data": [<match>], "meta": {...}}`` where
    ``<match>.odds`` is a list of market groups. Each group has
    ``sub_type_id`` (canonical market key), ``name``, and an ``odds`` list
    of selections (each with ``display``, ``odd_value``,
    ``special_bet_value``).

    Betika does not expose ``probability`` on selections — ``_mode`` is
    accepted for symmetry but both Outcome probability fields stay None.
    """
    m = betika_first_match(response)
    if m is None:
        return []
    groups = m.get("odds") or []
    if not isinstance(groups, list):
        return []

    results: list[NormalizedMarket] = []
    for grp in groups:
        if not isinstance(grp, dict):
            continue
        sub_type_id = str(grp.get("sub_type_id", ""))
        mapping = registry.get_by_platform_id("betika", sub_type_id)
        if mapping is None:
            continue
        selections = grp.get("odds") or []
        if not isinstance(selections, list):
            continue
        if mapping.parameterized:
            results.append(_parse_betika_parameterized(selections, mapping))
        else:
            results.append(_parse_betika_simple(selections, mapping))
    return results


def _parse_betika_simple(
    selections: list, mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a simple Betika market (1X2, BTTS, DC)."""
    outcomes: list[Outcome] = []
    for sel in selections:
        if not isinstance(sel, dict):
            continue
        display = str(sel.get("display", ""))
        try:
            odds = float(sel.get("odd_value", 0))
        except (TypeError, ValueError):
            continue
        canonical = _resolve_outcome_betika(display, mapping)
        if canonical:
            outcomes.append(
                Outcome(
                    canonical_name=canonical,
                    odds=odds,
                    platform_name=display,
                )
            )
    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=outcomes,
        lines=None,
    )


def _parse_betika_parameterized(
    selections: list, mapping: MarketMapping
) -> NormalizedMarket:
    """Parse a parameterized Betika market (Over/Under).

    All selections live in one market group; the line is read from
    ``special_bet_value`` when present and otherwise extracted from the
    ``display`` label (e.g. ``"OVER 2.5"`` → 2.5).
    """
    lines: dict[float, list[Outcome]] = {}
    for sel in selections:
        if not isinstance(sel, dict):
            continue
        line = _parse_betika_line(sel)
        if line is None:
            continue
        display = str(sel.get("display", ""))
        try:
            odds = float(sel.get("odd_value", 0))
        except (TypeError, ValueError):
            continue
        canonical = _resolve_outcome_betika(display, mapping)
        if canonical is None:
            continue
        lines.setdefault(line, []).append(
            Outcome(
                canonical_name=canonical,
                odds=odds,
                platform_name=display,
            )
        )
    return NormalizedMarket(
        canonical_id=mapping.canonical_id,
        name=mapping.name,
        outcomes=[],
        lines=lines,
    )


def _parse_betika_line(sel: dict) -> float | None:
    """Extract the line value for a parameterized Betika selection.

    ``special_bet_value`` shape varies: bare numeric string (``"2.5"``),
    key=value (``"total=2.5"``), or empty. Falls back to the first number
    found in ``display`` (e.g. ``"OVER 2.5"`` → 2.5) when no numeric
    candidate is present in ``special_bet_value``.
    """
    sbv = sel.get("special_bet_value")
    if isinstance(sbv, (int, float)):
        return float(sbv)
    if isinstance(sbv, str) and sbv:
        try:
            return float(sbv)
        except ValueError:
            m = _BETIKA_NUMERIC_RE.search(sbv)
            if m:
                try:
                    return float(m.group(0))
                except ValueError:
                    pass
    display = sel.get("display")
    if isinstance(display, str):
        m = _BETIKA_NUMERIC_RE.search(display)
        if m:
            try:
                return float(m.group(0))
            except ValueError:
                return None
    return None


def _resolve_outcome_betika(
    display: str, mapping: MarketMapping
) -> str | None:
    """Resolve a Betika selection ``display`` label to a canonical name.

    Case-insensitive. Accepts both exact tokens (``"1"``, ``"X"``,
    ``"Yes"``, ``"1/X"``) and labels with an embedded line (``"OVER 2.5"``
    — first whitespace-delimited token compared).
    """
    if not isinstance(display, str) or not display:
        return None
    target = display.strip().lower()
    if not target:
        return None
    first = target.split()[0]
    for om in mapping.outcomes.values():
        if not om.betika:
            continue
        ref = om.betika.lower()
        if target == ref or first == ref:
            return om.canonical_name
    return None
