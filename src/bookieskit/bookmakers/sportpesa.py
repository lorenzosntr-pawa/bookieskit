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
        """Get event detail (metadata + SR id + a subset of markets).

        SportPesa serves the same `/api/upcoming/games?gameId=...` endpoint
        for both prematch and in-play events — `state` is empty in both
        cases and there is no separate `/api/live/games?gameId=...` route.
        The ``live`` argument is accepted for API symmetry but ignored.

        Args:
            event_id: SportPesa internal game id (e.g. ``"8868005"``).
            live: Accepted for symmetry; ignored.

        Returns:
            Raw JSON: a list of length 1 whose `[0]` element has
            ``betradarId``, ``dateTimestamp``, ``competitors``, ``sport``,
            ``competition``, ``markets`` (subset). The full markets feed
            is at ``get_event_markets``.
        """
        del live  # accepted for symmetry with other clients
        return await self._request(
            "GET",
            "/api/upcoming/games",
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
            Raw JSON shaped as ``{<game_id>: [<market>, ...]}``. Each
            market has ``id``, ``name``, ``specValue``, ``selections``.
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

    async def get_sports(self, live: bool = True) -> dict[str, Any]:
        """Get the available sports list.

        SportPesa only exposes a dedicated sports endpoint for the live
        catalogue (``/api/live/sports``). The prematch catalogue has no
        sports endpoint — derive it by walking ``get_events`` per sport,
        or accept the live list as a reasonable approximation (SportPesa
        carries the same sports prematch and live).

        Args:
            live: Default ``True``. Calling with ``live=False`` is a
                no-op — the endpoint is the same; kept for API symmetry.

        Returns:
            Raw JSON shaped as ``{"sports": [{"id": int, "name": str,
            "eventNumber": int}, ...]}``. ``eventNumber`` is the count
            of currently-live events on that sport.
        """
        del live  # symmetry only — SportPesa has just the one sports endpoint
        return await self._request("GET", "/api/live/sports")

    async def get_events(
        self,
        sport_id: str = "1",
        competition_id: str | None = None,
        live: bool = False,
        pag_count: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get events for a sport (prematch via ``/api/upcoming/games``;
        live via ``/api/highlights/{sport_id}?live=true``).

        Args:
            sport_id: SportPesa sport id (default ``"1"`` for Football).
            competition_id: Optional competition id filter — passed as
                ``competitionId`` to ``/api/upcoming/games`` when set.
            live: If ``True``, query ``/api/highlights/{sport_id}?live=true``.
            pag_count: Optional page size; absent param means full list.

        Returns:
            Raw JSON list of game objects (each carrying ``id``,
            ``betradarId``, ``competition``, ``country``, ``sport``,
            ``competitors``, ``dateTimestamp``).
        """
        if live:
            params: dict[str, Any] = {"live": "true"}
            if pag_count is not None:
                params["pag_count"] = str(pag_count)
            return await self._request(
                "GET", f"/api/highlights/{sport_id}", params=params
            )
        params = {"sportId": sport_id}
        if competition_id:
            params["competitionId"] = competition_id
        if pag_count is not None:
            params["pag_count"] = str(pag_count)
        return await self._request("GET", "/api/upcoming/games", params=params)

    # NOTE: SportPesa has no dedicated tournament / competition list endpoint.
    # The closest you can do is group `get_events(sport_id=...)` by
    # `competition.id`. `get_countries` / `get_tournaments` are intentionally
    # absent from this client — adding placeholders would be misleading.
