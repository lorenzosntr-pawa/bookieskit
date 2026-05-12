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
        league_id: str | None = None,
        live: bool = False,
        pag_count: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get events for a sport (prematch via ``/api/upcoming/games``;
        live via ``/api/highlights/{sport_id}?live=true``).

        Args:
            sport_id: SportPesa sport id (default ``"1"`` for Football).
            league_id: Optional league/competition filter — passed as
                ``leagueId`` to ``/api/upcoming/games``. **Important:** the
                ``leagueId`` filter walks past the rolling-100-event window
                and returns the full league catalogue, which is the only
                way to enumerate prematch events beyond the rolling view.
                (Earlier versions accepted ``competition_id`` which mapped
                to ``competitionId`` — that query parameter is silently
                ignored by the SportPesa API; use ``league_id`` instead.)
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
        if league_id:
            params["leagueId"] = league_id
        if pag_count is not None:
            params["pag_count"] = str(pag_count)
        return await self._request("GET", "/api/upcoming/games", params=params)

    async def get_live_events_started(
        self, sport_id: str = "1"
    ) -> dict[str, Any]:
        """Get events that are currently in-play (ball-is-rolling) for a sport.

        This is the authoritative source for "live now" counts. The
        ``eventNumber`` field on ``/api/live/sports`` is a separately-cached
        counter that is unreliable (observed returning all zeros even when
        many events are in-play).

        Args:
            sport_id: SportPesa sport id (default ``"1"`` for Football).

        Returns:
            JSON dict with ``events`` list. Each event has ``id``,
            ``legacyId``, ``externalId``, ``marketCount``, ``kickoffTimeUTC``,
            ``sport``, ``country``, ``tournament``, ``competitors``.
        """
        return await self._request(
            "GET", f"/api/live/sports/{sport_id}/events/started"
        )

    async def get_live_sport_events(
        self, sport_id: str = "1"
    ) -> dict[str, Any]:
        """Get every event available for live betting on a sport.

        Broader than ``get_live_events_started``: includes both currently
        in-play matches AND events that have not started yet but will be
        offered with live markets when they kick off. Useful for an
        "available-for-live" catalogue count.

        Args:
            sport_id: SportPesa sport id.

        Returns:
            JSON dict with ``events`` list (same shape as
            ``get_live_events_started``).
        """
        return await self._request(
            "GET", f"/api/live/sports/{sport_id}/events"
        )

    async def get_navigation(self) -> list[dict[str, Any]]:
        """Get the full sport → country → league navigation tree.

        This is the endpoint that powers SportPesa's left-nav. It is the
        only way to enumerate the complete league catalogue: the per-sport
        ``/api/upcoming/games`` endpoint hard-caps at 100 events in a
        rolling window, but ``get_navigation()`` exposes every league
        SportPesa knows about, including leagues whose events fall outside
        that window.

        Returns:
            JSON list of sport objects::

                [
                    {
                        "id": 1, "name": "Football", "order": 0,
                        "has_matches": True,
                        "countries": [
                            {
                                "id": 61, "name": "England", "iso_name": "eng",
                                "leagues": [
                                    {"id": 67600, "name": "Premier League",
                                     "top_league_pos": 2},
                                    ...
                                ],
                            },
                            ...
                        ],
                    },
                    ...
                ]

        Pair with ``get_events(sport_id, league_id=L)`` to enumerate the
        full per-league event catalogue.
        """
        return await self._request("GET", "/api/navigation")

    # NOTE: SportPesa has no dedicated tournament / competition list endpoint
    # in the classic shape — `get_navigation()` is the equivalent and returns
    # the full sport → country → league tree in one call. `get_countries`
    # and `get_tournaments` are intentionally absent from this client.
