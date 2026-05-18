"""Market registry — built-in + user-extensible."""

from bookieskit.markets.builtin_mappings import BUILTIN_MAPPINGS
from bookieskit.markets.types import MarketMapping, OutcomeMapping


class MarketRegistry:
    """Registry of market mappings.

    Ships with 6 built-in markets (1X2, O/U, BTTS, DC, 1X2 1Up, 1X2 2Up).
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
        self._by_msport: dict[str, MarketMapping] = {}
        self._by_sportpesa: dict[str, MarketMapping] = {}
        self._by_betika: dict[str, MarketMapping] = {}
        # Sport-scoped index: (platform, sport, market_id) -> mapping.
        # Used to disambiguate market ids that are shared across sports
        # on the same platform (e.g. SportPesa's id "52" is football
        # Over/Under AND basketball Over/Under).
        self._by_platform_sport_id: dict[
            tuple[str, str, str], MarketMapping
        ] = {}

        if load_builtins:
            for mapping in BUILTIN_MAPPINGS:
                self._register(mapping)

    def _register(self, mapping: MarketMapping) -> None:
        """Register a mapping in all lookup indices.

        The flat per-platform indexes use first-registered-wins so a
        bare ``get_by_platform_id(platform, id)`` call returns the
        same mapping a pre-0.12.0 caller would have got (typically the
        soccer mapping, since soccer entries are loaded first by
        :data:`BUILTIN_MAPPINGS`). Sport disambiguation requires the
        explicit ``sport=`` argument on the lookup method.
        """
        self._by_canonical[mapping.canonical_id] = mapping

        def _add_to(index: dict[str, MarketMapping], key: str | None) -> None:
            if key and key not in index:
                index[key] = mapping

        _add_to(self._by_betpawa, mapping.betpawa_id)
        _add_to(self._by_sportybet, mapping.sportybet_id)
        _add_to(self._by_bet9ja, mapping.bet9ja_key)
        _add_to(self._by_betway, mapping.betway_id)
        _add_to(self._by_msport, mapping.msport_id)
        _add_to(self._by_sportpesa, mapping.sportpesa_id)
        _add_to(self._by_betika, mapping.betika_id)

        # Always populate the sport-scoped index — (platform, sport, id)
        # is unique so we don't need first-wins guarding.
        for platform, market_id in (
            ("betpawa", mapping.betpawa_id),
            ("sportybet", mapping.sportybet_id),
            ("bet9ja", mapping.bet9ja_key),
            ("betway", mapping.betway_id),
            ("msport", mapping.msport_id),
            ("sportpesa", mapping.sportpesa_id),
            ("betika", mapping.betika_id),
        ):
            if market_id:
                self._by_platform_sport_id[
                    (platform, mapping.sport, market_id)
                ] = mapping

    def add(
        self,
        canonical_id: str,
        name: str,
        betpawa_id: str | None = None,
        sportybet_id: str | None = None,
        bet9ja_key: str | None = None,
        betway_id: str | None = None,
        msport_id: str | None = None,
        sportpesa_id: str | None = None,
        betika_id: str | None = None,
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
            msport_id: MSport market ID (or None)
            sportpesa_id: SportPesa market ID (or None)
            betika_id: Betika sub_type_id (or None)
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
            msport_id=msport_id,
            sportpesa_id=sportpesa_id,
            betika_id=betika_id,
            outcomes=outcomes or {},
            parameterized=parameterized,
        )
        self._register(mapping)

    def get_by_canonical(self, canonical_id: str) -> MarketMapping | None:
        """Return the MarketMapping for a canonical ID, or None if not registered.

        Args:
            canonical_id: Canonical market identifier (e.g., "1x2_ft").

        Returns:
            Matching MarketMapping, or None.
        """
        return self._by_canonical.get(canonical_id)

    def get_by_platform_id(
        self,
        platform: str,
        platform_id: str,
        sport: str | None = None,
    ) -> MarketMapping | None:
        """Return the MarketMapping for a platform-specific ID.

        Args:
            platform: One of "betpawa", "sportybet", "bet9ja", "betway",
                "msport", "sportpesa", or "betika".
            platform_id: Platform-specific market ID or key.
            sport: Optional sport filter. Pass ``"basketball"`` to
                disambiguate IDs that overlap across sports (e.g.
                SportPesa's id ``"52"`` is football O/U AND basketball
                O/U). Omitting it falls back to the first-registered
                mapping for that id — typically soccer.

        Returns:
            Matching MarketMapping, or None if the platform or ID is unrecognised.
        """
        if sport is not None:
            return self._by_platform_sport_id.get(
                (platform, sport, platform_id)
            )
        index = {
            "betpawa": self._by_betpawa,
            "sportybet": self._by_sportybet,
            "bet9ja": self._by_bet9ja,
            "betway": self._by_betway,
            "msport": self._by_msport,
            "sportpesa": self._by_sportpesa,
            "betika": self._by_betika,
        }.get(platform, {})
        return index.get(platform_id)

    def list_markets(self) -> list[MarketMapping]:
        """Return all registered market mappings in insertion order.

        Returns:
            List of all MarketMapping objects currently registered.
        """
        return list(self._by_canonical.values())
