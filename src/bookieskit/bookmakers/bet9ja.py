"""Bet9ja client — supports ng only."""

from typing import Any

from bookieskit.base import BaseBookmaker
from bookieskit.config import BET9JA_MAX_CONCURRENT, BET9JA_REQUEST_DELAY

# Cache version used in Bet9ja API requests
_CACHE_VERSION = "1.301.2.225"


class Bet9ja(BaseBookmaker):
    """HTTP client for Bet9ja sportsbook API.

    Bet9ja has stricter rate limits (15 concurrent, 25ms delay) which are
    enforced by default.

    Args:
        country: Country code (only "ng" supported)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 15)
        request_delay: Delay between requests in seconds (default: 0.025)
    """

    DOMAINS = {
        "ng": "https://sports.bet9ja.com",
    }
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",  # noqa: E501
    }
    MAX_CONCURRENT = BET9JA_MAX_CONCURRENT
    REQUEST_DELAY = BET9JA_REQUEST_DELAY
    NAME = "Bet9ja"
    PLATFORM_KEY = "bet9ja"

    async def get_sports(self) -> dict[str, Any]:
        """Get all available sports with their category hierarchy.

        Returns:
            Raw JSON with R (status) and D (data) containing PAL hierarchy.
        """
        return await self._request(
            "GET",
            "/desktop/feapi/PalimpsestAjax/GetSports",
            params={"DISP": "0", "v_cache_version": _CACHE_VERSION},
        )

    async def get_countries(self) -> dict[str, Any]:
        """Get countries/categories (included in sports hierarchy).

        Returns:
            Same as get_sports — Bet9ja returns full hierarchy in one call.
        """
        return await self.get_sports()

    async def get_tournaments(self) -> dict[str, Any]:
        """Get tournaments (included in sports hierarchy).

        Returns:
            Same as get_sports — Bet9ja returns full hierarchy in one call.
        """
        return await self.get_sports()

    async def get_events(
        self,
        tournament_id: str,
        market_id: str = "1",
    ) -> dict[str, Any]:
        """Get events for a tournament/group.

        Args:
            tournament_id: Bet9ja group ID (e.g., "170880")
            market_id: Market group ID to include (default: "1" for 1X2)

        Returns:
            Raw JSON with R (status) and D.E (events array).
        """
        return await self._request(
            "GET",
            "/desktop/feapi/PalimpsestAjax/GetEventsInGroupV2",
            params={
                "GROUPID": tournament_id,
                "DISP": "0",
                "GROUPMARKETID": market_id,
                "v_cache_version": _CACHE_VERSION,
            },
        )

    async def get_event_detail(self, event_id: str) -> dict[str, Any]:
        """Get full event details with all odds.

        Args:
            event_id: Bet9ja event ID (e.g., "707096003")

        Returns:
            Raw JSON with R (status), D.O (flat odds dict), D.EXTID (SportRadar ID).
        """
        return await self._request(
            "GET",
            "/desktop/feapi/PalimpsestAjax/GetEvent",
            params={"EVENTID": event_id, "v_cache_version": _CACHE_VERSION},
        )
