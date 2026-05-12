"""SportPesa client — supports ke, tz."""

from typing import Any

from bookieskit.base import BaseBookmaker
from bookieskit.config import SPORTPESA_MAX_CONCURRENT, SPORTPESA_REQUEST_DELAY


class SportPesa(BaseBookmaker):
    """HTTP client for SportPesa sportsbook API.

    SportPesa uses country-specific subdomains (www.ke.sportpesa.com,
    www.tz.sportpesa.com). Country also drives the `x-app-timezone`
    request header.

    The API is gated by Akamai Bot Manager. This client does NOT solve the
    challenge — callers must supply warmed cookies (e.g. by injecting
    `Cookie:` into `self._http_client.headers` after `__aenter__`).

    Event IDs are SportPesa-internal integers (e.g. "8868005"), NOT
    SportRadar ids. `get_sportradar_id` fetches event-detail and pulls the
    SR id from the response.

    Args:
        country: Country code (ke, tz)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 15)
        request_delay: Delay between requests in seconds (default: 0.05)
    """

    DOMAINS = {
        "ke": "https://www.ke.sportpesa.com",
        "tz": "https://www.tz.sportpesa.com",
    }
    DEFAULT_HEADERS = {
        "accept": "application/json, text/plain, */*",
        "x-requested-with": "XMLHttpRequest",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/144.0.0.0 Safari/537.36"
        ),
    }
    MAX_CONCURRENT = SPORTPESA_MAX_CONCURRENT
    REQUEST_DELAY = SPORTPESA_REQUEST_DELAY
    NAME = "SportPesa"
    PLATFORM_KEY = "sportpesa"

    _TIMEZONE_PER_COUNTRY = {
        "ke": "Africa/Nairobi",
        "tz": "Africa/Dar_es_Salaam",
    }

    def _build_headers(self) -> dict[str, str]:
        headers = dict(self.DEFAULT_HEADERS)
        headers["x-app-timezone"] = self._TIMEZONE_PER_COUNTRY.get(
            self._country, "Africa/Nairobi"
        )
        return headers

    async def get_event_detail(
        self, event_id: str, live: bool = False
    ) -> dict[str, Any]:
        """Get event detail (metadata + SR id, NOT full markets).

        Args:
            event_id: SportPesa internal game id (e.g., "8868005")
            live: If True, query the live endpoint family.

        Returns:
            Raw JSON. SR id lives at <RESOLVED.md path>.
        """
        path = "/api/live/games" if live else "/api/upcoming/games"
        return await self._request(
            "GET",
            path,
            params={
                "gameId": event_id,
                "sportId": "1",
                "section": "markets",
                "pag_count": "1",
            },
        )

    async def get_event_markets(self, event_id: str) -> dict[str, Any]:
        """Get the full markets payload for one event.

        Args:
            event_id: SportPesa internal game id

        Returns:
            Raw JSON with data[0].markets[].
        """
        return await self._request(
            "GET",
            "/api/games/markets",
            params={
                "games": event_id,
                "markets": "all",
            },
        )

    async def get_markets(self, event_id: str, registry: Any = None) -> list:
        """Fetch markets and return normalized markets.

        Overrides the base because SportPesa uses a separate markets
        endpoint, same pattern as Betway.

        Args:
            event_id: SportPesa internal game id
            registry: MarketRegistry (default: built-in)

        Returns:
            List of NormalizedMarket for recognized markets.
        """
        from bookieskit.markets.parser import parse_markets

        raw = await self.get_event_markets(event_id=event_id)
        return parse_markets(raw, platform=self.PLATFORM_KEY, registry=registry)

    async def get_sports(self, live: bool = False) -> dict[str, Any]:
        """Get all available sports.

        Args:
            live: If True, fetch the live-sports endpoint.

        Returns:
            Raw JSON.
        """
        # fixture-resolve: confirm exact path per RESOLVED.md
        path = "/api/live/sports" if live else "/api/sports"
        return await self._request("GET", path)

    async def get_countries(
        self, sport_id: str = "1", live: bool = False
    ) -> dict[str, Any]:
        """Get countries/categories for a sport.

        Args:
            sport_id: SportPesa sport id (default "1" for Football)
            live: If True, query the live endpoint family.

        Returns:
            Raw JSON.
        """
        # fixture-resolve: confirm exact path per RESOLVED.md
        path = "/api/live/categories" if live else "/api/upcoming/categories"
        return await self._request("GET", path, params={"sportId": sport_id})

    async def get_tournaments(
        self,
        sport_id: str = "1",
        category_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Get tournaments/competitions for a sport.

        Args:
            sport_id: SportPesa sport id (default "1" for Football)
            category_id: Optional country/category id filter
            live: If True, query the live endpoint family.

        Returns:
            Raw JSON.
        """
        # fixture-resolve: confirm exact path per RESOLVED.md
        path = "/api/live/competitions" if live else "/api/upcoming/competitions"
        params: dict[str, Any] = {"sportId": sport_id}
        if category_id:
            params["categoryId"] = category_id
        return await self._request("GET", path, params=params)

    async def get_events(
        self,
        sport_id: str = "1",
        competition_id: str | None = None,
        live: bool = False,
        page: int = 0,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """Get events for a sport / competition.

        Args:
            sport_id: SportPesa sport id (default "1" for Football)
            competition_id: Optional competition id filter
            live: If True, query the live endpoint family.
            page: Pagination page (default 0)
            per_page: Page size (default 50)

        Returns:
            Raw JSON.
        """
        # fixture-resolve: confirm exact path + param names per RESOLVED.md
        path = "/api/live/games" if live else "/api/upcoming/games"
        params: dict[str, Any] = {
            "sportId": sport_id,
            "page": str(page),
            "per_page": str(per_page),
        }
        if competition_id:
            params["competitionId"] = competition_id
        return await self._request("GET", path, params=params)
