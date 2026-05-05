"""MSport client — supports ng, gh, ke."""

from typing import Any

from bookieskit.base import BaseBookmaker
from bookieskit.config import MSPORT_MAX_CONCURRENT, MSPORT_REQUEST_DELAY


class MSport(BaseBookmaker):
    """HTTP client for MSport API.

    MSport uses the same base domain for all countries but differentiates
    via the API path (e.g., /api/ng/... vs /api/gh/...). The MSport API
    returns prematch matches grouped by tournament in a single call per
    sport — there is no per-tournament fetch.

    Args:
        country: Country code (ng, gh, ke)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 50)
        request_delay: Delay between requests in seconds (default: 0)
    """

    DOMAINS = {
        "ng": "https://www.msport.com",
        "gh": "https://www.msport.com",
        "ke": "https://www.msport.com",
    }
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "en",
        "clientid": "web",
        "operid": "2",
        "platform": "web",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",  # noqa: E501
    }
    MAX_CONCURRENT = MSPORT_MAX_CONCURRENT
    REQUEST_DELAY = MSPORT_REQUEST_DELAY
    NAME = "MSport"
    PLATFORM_KEY = "msport"

    @property
    def _api_prefix(self) -> str:
        """Country-specific API path prefix."""
        return f"/api/{self._country}/facts-center/query/frontend"

    async def get_sports(self) -> dict[str, Any]:
        """Get all available prematch sports.

        Returns:
            Raw JSON with data.sports list — each entry has sportId,
            sportName, count.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/sports",
        )

    async def get_events(
        self, sport_id: str = "sr:sport:1"
    ) -> dict[str, Any]:
        """Get all prematch events for a sport, grouped by tournament.

        MSport bundles the entire sport's match list per call — there is
        no per-tournament endpoint.

        Args:
            sport_id: SportRadar sport ID (default: "sr:sport:1" for Soccer)

        Returns:
            Raw JSON with data.tournaments list — each tournament has
            category, tournament, tournamentId, and events.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/sports-matches-list",
            params={"sportId": sport_id},
        )

    async def get_event_detail(
        self, event_id: str, live: bool = False
    ) -> dict[str, Any]:
        """Get full event details including all markets.

        Args:
            event_id: SportRadar match ID (e.g., "sr:match:61301231")
            live: If True, request the live market set (productId=1).
                  Default False uses productId=3 (prematch). For live
                  events, productId=3 returns only a partial subset;
                  productId=1 returns the full live market book.

        Returns:
            Raw JSON with data containing eventId, homeTeam, awayTeam,
            and markets list.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/match/detail",
            params={
                "eventId": event_id,
                "productId": "1" if live else "3",
            },
        )

    async def get_live_sports(self) -> dict[str, Any]:
        """Get all sports that currently have live events.

        Returns:
            Raw JSON with data.sports list — each entry has sportId,
            sportName, and a non-zero count.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/live-matches/sports",
        )

    async def get_live_events(
        self, sport_id: str = "sr:sport:1"
    ) -> dict[str, Any]:
        """Get live events for a sport, grouped by tournament.

        Uses the richer /live-matches/list endpoint, which returns
        tournaments, events, and comingSoons in one call.

        Args:
            sport_id: SportRadar sport ID (default: "sr:sport:1" for Soccer)

        Returns:
            Raw JSON with data.tournaments, data.events, data.comingSoons.
        """
        return await self._request(
            "GET",
            f"{self._api_prefix}/live-matches/list",
            params={"sportId": sport_id},
        )
