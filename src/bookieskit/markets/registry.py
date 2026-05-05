"""Market registry — built-in + user-extensible."""

from bookieskit.markets.builtin_mappings import BUILTIN_MAPPINGS
from bookieskit.markets.types import MarketMapping, OutcomeMapping


class MarketRegistry:
    """Registry of market mappings.

    Ships with 4 built-in markets (1X2, O/U, BTTS, DC).
    Users can add custom mappings at runtime.
    """

    def __init__(self, load_builtins: bool = True):
        """Initialize registry.

        Args:
            load_builtins: Load built-in markets (default: True).
        """
        self._by_canonical: dict[str, MarketMapping] = {}
        self._by_betpawa: dict[str, MarketMapping] = {}
        self._by_sportybet: dict[str, MarketMapping] = {}
        self._by_bet9ja: dict[str, MarketMapping] = {}
        self._by_betway: dict[str, MarketMapping] = {}

        if load_builtins:
            for mapping in BUILTIN_MAPPINGS:
                self._register(mapping)

    def _register(self, mapping: MarketMapping) -> None:
        """Register a mapping in all lookup indices."""
        self._by_canonical[mapping.canonical_id] = mapping
        if mapping.betpawa_id:
            self._by_betpawa[mapping.betpawa_id] = mapping
        if mapping.sportybet_id:
            self._by_sportybet[mapping.sportybet_id] = mapping
        if mapping.bet9ja_key:
            self._by_bet9ja[mapping.bet9ja_key] = mapping
        if mapping.betway_id:
            self._by_betway[mapping.betway_id] = mapping

    def add(
        self,
        canonical_id: str,
        name: str,
        betpawa_id: str | None = None,
        sportybet_id: str | None = None,
        bet9ja_key: str | None = None,
        betway_id: str | None = None,
        outcomes: dict[str, OutcomeMapping] | None = None,
        parameterized: bool = False,
    ) -> None:
        """Register a new market mapping.

        Args:
            canonical_id: Unique ID (e.g., "correct_score_ft")
            name: Human-readable name
            betpawa_id: BetPawa market ID (or None)
            sportybet_id: SportyBet market ID (or None)
            bet9ja_key: Bet9ja key prefix (or None)
            betway_id: Betway market name (or None)
            outcomes: Dict of canonical_name -> OutcomeMapping
            parameterized: True if market has lines (O/U, handicaps)
        """
        mapping = MarketMapping(
            canonical_id=canonical_id,
            name=name,
            betpawa_id=betpawa_id,
            sportybet_id=sportybet_id,
            bet9ja_key=bet9ja_key,
            betway_id=betway_id,
            outcomes=outcomes or {},
            parameterized=parameterized,
        )
        self._register(mapping)

    def get_by_canonical(self, canonical_id: str) -> MarketMapping | None:
        """Look up by canonical ID."""
        return self._by_canonical.get(canonical_id)

    def get_by_platform_id(
        self, platform: str, platform_id: str
    ) -> MarketMapping | None:
        """Look up by platform-specific ID.

        Args:
            platform: "betpawa", "sportybet", or "bet9ja"
            platform_id: Platform-specific market ID or key
        """
        index = {
            "betpawa": self._by_betpawa,
            "sportybet": self._by_sportybet,
            "bet9ja": self._by_bet9ja,
            "betway": self._by_betway,
        }.get(platform, {})
        return index.get(platform_id)

    def list_markets(self) -> list[MarketMapping]:
        """Return all registered mappings."""
        return list(self._by_canonical.values())
