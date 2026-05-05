"""BetPawa client — supports ng, gh, ke, ug, tz, zm."""

import json
from typing import Any
from urllib.parse import quote

from bookieskit.base import BaseBookmaker
from bookieskit.config import BETPAWA_MAX_CONCURRENT, BETPAWA_REQUEST_DELAY

# Country code to x-pawa-brand header value
_BRAND_MAP = {
    "ng": "betpawa-nigeria",
    "gh": "betpawa-ghana",
    "ke": "betpawa-kenya",
    "ug": "betpawa-uganda",
    "tz": "betpawa-tanzania",
    "zm": "betpawa-zambia",
}


class BetPawa(BaseBookmaker):
    """HTTP client for BetPawa sportsbook API.

    Args:
        country: Country code (ng, gh, ke, ug, tz, zm)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 50)
        request_delay: Delay between requests in seconds (default: 0)
    """

    DOMAINS = {
        "ng": "https://www.betpawa.ng",
        "gh": "https://www.betpawa.com.gh",
        "ke": "https://www.betpawa.co.ke",
        "ug": "https://www.betpawa.co.ug",
        "tz": "https://www.betpawa.co.tz",
        "zm": "https://www.betpawa.co.zm",
    }
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "devicetype": "web",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",  # noqa: E501
    }
    MAX_CONCURRENT = BETPAWA_MAX_CONCURRENT
    REQUEST_DELAY = BETPAWA_REQUEST_DELAY
    NAME = "BetPawa"

    def _build_headers(self) -> dict[str, str]:
        headers = dict(self.DEFAULT_HEADERS)
        headers["x-pawa-brand"] = _BRAND_MAP.get(
            self._country, f"betpawa-{self._country}"
        )
        return headers

    async def get_sports(self) -> dict[str, Any]:
        """Get all available sports/categories.

        Returns:
            Raw JSON with categories list.
        """
        return await self._request("GET", "/api/sportsbook/v3/categories/list/all")

    async def get_countries(self, sport_id: str) -> dict[str, Any]:
        """Get countries/regions for a sport.

        Args:
            sport_id: Sport category ID (e.g., "2" for Football)

        Returns:
            Raw JSON with regions and their competitions.
        """
        return await self._request(
            "GET", f"/api/sportsbook/v3/categories/list/{sport_id}"
        )

    async def get_tournaments(
        self, sport_id: str, country_id: str | None = None
    ) -> dict[str, Any]:
        """Get tournaments/competitions for a sport (optionally filtered by country).

        Args:
            sport_id: Sport category ID (e.g., "2" for Football)
            country_id: Optional region ID to filter by

        Returns:
            Raw JSON with regions containing competitions.
        """
        return await self._request(
            "GET", f"/api/sportsbook/v3/categories/list/{sport_id}"
        )

    async def get_events(
        self,
        tournament_id: str,
        sport_id: str = "2",
        event_type: str = "UPCOMING",
        skip: int = 0,
        take: int = 100,
    ) -> dict[str, Any]:
        """Get events for a tournament/competition.

        Args:
            tournament_id: Competition ID (e.g., "11965")
            sport_id: Sport category ID (default: "2" for Football)
            event_type: "UPCOMING" or "LIVE" (default: "UPCOMING")
            skip: Pagination offset (default: 0)
            take: Page size (default: 100)

        Returns:
            Raw JSON with results array and totalCount.
        """
        query_payload = {
            "queries": [
                {
                    "query": {
                        "eventType": event_type,
                        "categories": [sport_id],
                        "zones": {"competitions": [tournament_id]},
                        "hasOdds": True,
                    },
                    "view": {},
                    "skip": skip,
                    "take": take,
                }
            ]
        }
        q_param = quote(json.dumps(query_payload, separators=(",", ":")))
        return await self._request(
            "GET", "/api/sportsbook/v3/events/lists/by-queries", params={"q": q_param}
        )

    async def get_event_detail(self, event_id: str) -> dict[str, Any]:
        """Get full event details including all markets and odds.

        Args:
            event_id: BetPawa event ID (e.g., "32299257")

        Returns:
            Raw JSON with event info, markets, and odds.
        """
        return await self._request("GET", f"/api/sportsbook/v3/events/{event_id}")
