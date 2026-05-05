"""SportyBet client — supports ng, gh, ke."""

import time
from typing import Any

from bookieskit.base import BaseBookmaker
from bookieskit.config import SPORTYBET_MAX_CONCURRENT, SPORTYBET_REQUEST_DELAY


class SportyBet(BaseBookmaker):
    """HTTP client for SportyBet API.

    SportyBet uses the same base domain for all countries but differentiates
    via the API path (e.g., /api/ng/... vs /api/gh/...).

    Args:
        country: Country code (ng, gh, ke)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 50)
        request_delay: Delay between requests in seconds (default: 0)
    """

    DOMAINS = {
        "ng": "https://www.sportybet.com",
        "gh": "https://www.sportybet.com",
        "ke": "https://www.sportybet.com",
    }
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "en",
        "clientid": "web",
        "operid": "2",
        "platform": "web",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",  # noqa: E501
    }
    MAX_CONCURRENT = SPORTYBET_MAX_CONCURRENT
    REQUEST_DELAY = SPORTYBET_REQUEST_DELAY
    NAME = "SportyBet"
    PLATFORM_KEY = "sportybet"

    @property
    def _api_prefix(self) -> str:
        """Country-specific API path prefix."""
        return f"/api/{self._country}"

    def _timestamp(self) -> str:
        """Current timestamp in milliseconds for cache busting."""
        return str(int(time.time() * 1000))

    async def get_sports(self, live: bool = False) -> dict[str, Any]:
        """Get all available sports.

        Args:
            live: If True, return live sports only (default: False for prematch)

        Returns:
            Raw JSON with data.sportList containing all sports.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/factsCenter/popularAndSportList",
            params={
                "timeline": "",
                "productId": "1" if live else "3",
                "_t": self._timestamp(),
            },
        )

    async def get_countries(
        self, sport_id: str = "sr:sport:1", live: bool = False
    ) -> dict[str, Any]:
        """Get countries/categories for a sport.

        Args:
            sport_id: SportRadar sport ID (default: "sr:sport:1" for Football)
            live: If True, return live data only (default: False)

        Returns:
            Raw JSON — categories are nested under sportList[].categories.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/factsCenter/popularAndSportList",
            params={
                "sportId": sport_id,
                "timeline": "",
                "productId": "1" if live else "3",
                "_t": self._timestamp(),
            },
        )

    async def get_tournaments(
        self, sport_id: str = "sr:sport:1", live: bool = False
    ) -> dict[str, Any]:
        """Get tournaments for a sport (nested under categories).

        Returns the same payload as get_countries — SportyBet's
        popularAndSportList endpoint returns categories and tournaments
        in a single response.

        Args:
            sport_id: SportRadar sport ID (default: "sr:sport:1" for Football)
            live: If True, return live data only (default: False)

        Returns:
            Raw JSON — tournaments nested under sportList[].categories[].tournaments.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/factsCenter/popularAndSportList",
            params={
                "sportId": sport_id,
                "timeline": "",
                "productId": "1" if live else "3",
                "_t": self._timestamp(),
            },
        )

    async def get_events(
        self,
        tournament_id: str,
        sport_id: str = "sr:sport:1",
        market_ids: str = "1,18,10,29,11,26,36,14",
    ) -> dict[str, Any]:
        """Get events for a tournament.

        Args:
            tournament_id: SportRadar tournament ID (e.g., "sr:tournament:17")
            sport_id: SportRadar sport ID (default: "sr:sport:1")
            market_ids: Comma-separated market IDs to include (default: main markets)

        Returns:
            Raw JSON with events array containing markets and odds.
        """
        body = [
            {
                "sportId": sport_id,
                "marketId": market_ids,
                "tournamentId": [[tournament_id]],
            }
        ]
        return await self._request(
            "POST",
            f"{self._api_prefix}/factsCenter/pcEvents",
            json=body,
        )

    async def get_event_detail(
        self, event_id: str, live: bool = False
    ) -> dict[str, Any]:
        """Get full event details including all markets.

        Args:
            event_id: SportRadar match ID (e.g., "sr:match:61300947")
            live: If True, request the live market set (productId=1).
                  Default False uses productId=3 (prematch). For live
                  events, productId=3 returns only player-prop markets;
                  the main 1X2/OU/BTTS/DC live markets live under
                  productId=1.

        Returns:
            Raw JSON with full event info and all available markets.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/factsCenter/event",
            params={
                "eventId": event_id,
                "productId": "1" if live else "3",
                "_t": self._timestamp(),
            },
        )
