"""Betway client — supports ng, gh, ke, tz, ug, zm."""

from typing import Any

import httpx

from bookieskit.base import BaseBookmaker
from bookieskit.config import DEFAULT_TIMEOUT

# Country code mapping (lowercase -> API format)
_COUNTRY_CODES = {
    "ng": "NG",
    "gh": "GH",
    "ke": "KE",
    "tz": "TZ",
    "ug": "UG",
    "zm": "ZM",
}

# Config domain (sports list only)
_CONFIG_BASE_URL = "https://config.betwayafrica.com"


class Betway(BaseBookmaker):
    """HTTP client for Betway sportsbook API.

    Betway uses two API domains:
    - config.betwayafrica.com for sports configuration
    - feeds-roa2.betwayafrica.com for data (events, markets, odds)

    The country is passed via countryCode query parameter.
    Event IDs are SportRadar IDs natively.

    Args:
        country: Country code (ng, gh, ke, tz, ug, zm)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 50)
        request_delay: Delay between requests in seconds (default: 0)
    """

    DOMAINS = {
        "ng": "https://feeds-roa2.betwayafrica.com",
        "gh": "https://feeds-roa2.betwayafrica.com",
        "ke": "https://feeds-roa2.betwayafrica.com",
        "tz": "https://feeds-roa2.betwayafrica.com",
        "ug": "https://feeds-roa2.betwayafrica.com",
        "zm": "https://feeds-roa2.betwayafrica.com",
    }
    DEFAULT_HEADERS = {
        "accept": "application/json",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/144.0.0.0 Safari/537.36"
        ),
    }
    MAX_CONCURRENT = 50
    REQUEST_DELAY = 0.0
    NAME = "Betway"
    PLATFORM_KEY = "betway"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._country_code = _COUNTRY_CODES.get(
            self._country, self._country.upper()
        )

    async def get_sports(self) -> dict[str, Any]:
        """Get all available sports.

        Uses the config domain (separate from data domain).

        Returns:
            Raw JSON with sports[] array.
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT)
        ) as config_client:
            url = (
                f"{_CONFIG_BASE_URL}/cron/sports"
                f"/{self._country_code}/en-US"
            )
            response = await config_client.get(
                url, headers=self._build_headers()
            )
            response.raise_for_status()
            return response.json()

    async def get_countries(
        self, sport_id: str = "soccer"
    ) -> dict[str, Any]:
        """Get regions/countries and leagues for a sport.

        Args:
            sport_id: Sport slug (e.g., "soccer", "tennis")

        Returns:
            Raw JSON with regions[].leagues[] structure.
        """
        return await self._request(
            "GET",
            f"/br/_apis/sport/v1/Feeds/RegionsAndLeagues/{sport_id}",
            params={"countryCode": self._country_code},
        )

    async def get_tournaments(
        self, sport_id: str = "soccer"
    ) -> dict[str, Any]:
        """Get tournaments (same as get_countries — leagues are tournaments).

        Args:
            sport_id: Sport slug (e.g., "soccer")

        Returns:
            Raw JSON with regions[].leagues[] structure.
        """
        return await self.get_countries(sport_id=sport_id)

    async def get_events(
        self,
        region_id: str | None = None,
        league_id: str | None = None,
        sport_id: str = "soccer",
        skip: int = 0,
        take: int = 50,
        market_types: str = "[Win/Draw/Win]",
    ) -> dict[str, Any]:
        """Get events for a league.

        Args:
            region_id: Region slug (e.g., "international-clubs", "england").
                       Required together with league_id for filtered results.
            league_id: League slug (e.g., "uefa-champions-league",
                       "premier-league"). Required together with region_id.
            sport_id: Sport slug (default: "soccer")
            skip: Pagination offset (default: 0)
            take: Page size (default: 50)
            market_types: Market types to include (default: "[Win/Draw/Win]")

        Returns:
            Raw JSON with events[], markets[], outcomes[], prices[].
        """
        params: dict[str, Any] = {
            "countryCode": self._country_code,
            "sportId": sport_id,
            "Skip": str(skip),
            "Take": str(take),
            "cultureCode": "en-US",
            "isEsport": "false",
            "boostedOnly": "false",
            "marketTypes": market_types,
        }
        if region_id and league_id:
            params["SortOrder"] = "League"
            params["RegionAndLeagueIds[0].regionId"] = region_id
            params["RegionAndLeagueIds[0].leagueId"] = league_id
            endpoint = "/br/_apis/sport/v1/BetBook/Filtered/"
        else:
            endpoint = "/br/_apis/sport/v1/BetBook/Highlights/"
        return await self._request("GET", endpoint, params=params)

    async def get_event_detail(
        self, event_id: str
    ) -> dict[str, Any]:
        """Get event detail (basic info + game state).

        Args:
            event_id: Betway event ID (= SportRadar ID)

        Returns:
            Raw JSON with sportEvent object.
        """
        return await self._request(
            "GET",
            "/br/_apis/sport/v3/Feeds/Events/EventAndGameState",
            params={
                "eventId": event_id,
                "countryCode": self._country_code,
            },
        )

    async def get_event_markets(
        self,
        event_id: str,
        skip: int = 0,
        take: int = 100,
    ) -> dict[str, Any]:
        """Get all markets for an event.

        Args:
            event_id: Betway event ID (= SportRadar ID)
            skip: Pagination offset (default: 0)
            take: Page size (default: 100)

        Returns:
            Raw JSON with marketsInGroup[], outcomes[], prices[].
        """
        return await self._request(
            "GET",
            "/br/_apis/sport/v1/MarketGroupings"
            "/MarketGroupNamesAndMarketsForEvent",
            params={
                "eventId": event_id,
                "marketGroupId": " ",
                "countryCode": self._country_code,
                "cultureCode": "en-US",
                "skip": str(skip),
                "take": str(take),
                "isBuildABetOnly": "false",
                "searchQuery": "",
            },
        )

    async def get_markets(self, event_id: str, registry=None):
        """Fetch event markets and return normalized markets.

        Overrides base because Betway uses a separate markets endpoint.

        Args:
            event_id: Betway event ID (= SportRadar ID)
            registry: MarketRegistry (default: built-in)

        Returns:
            List of NormalizedMarket for recognized markets.
        """
        from bookieskit.markets.parser import parse_markets

        raw = await self.get_event_markets(event_id=event_id)
        return parse_markets(
            raw, platform=self.PLATFORM_KEY, registry=registry
        )

    async def get_sportradar_id(
        self, event_id: str
    ) -> str | None:
        """Return the event ID directly (it IS the SportRadar ID).

        Overrides base to avoid an unnecessary API call.

        Args:
            event_id: Betway event ID

        Returns:
            The event ID as string (same value).
        """
        return str(event_id)
