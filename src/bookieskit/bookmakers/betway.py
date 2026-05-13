"""Betway client — supports ng, gh, ke, tz, ug, zm."""

import asyncio
from typing import Any, AsyncIterator

import httpx

from bookieskit.base import BaseBookmaker
from bookieskit.bookmakers.types import PrematchEventStub
from bookieskit.config import (  # noqa: E501
    BETWAY_MAX_CONCURRENT,
    BETWAY_REQUEST_DELAY,
    DEFAULT_TIMEOUT,
)

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
    MAX_CONCURRENT = BETWAY_MAX_CONCURRENT
    REQUEST_DELAY = BETWAY_REQUEST_DELAY
    NAME = "Betway"
    PLATFORM_KEY = "betway"

    def __init__(self, **kwargs: Any) -> None:
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

    async def get_live_events(
        self,
        sport_id: str = "soccer",
        skip: int = 0,
        take: int = 100,
        market_types: str = "",
    ) -> dict[str, Any]:
        """Get in-play (live) events for one sport.

        Args:
            sport_id: Sport slug (required by the API, e.g., "soccer").
            skip: Pagination offset.
            take: Page size.
            market_types: Comma-bracketed market-type filter. Default is
                an empty string, which the API treats as "no filter" and
                returns every in-play event for the sport regardless of
                which market types are available. Pass a specific value
                (e.g. ``"[Win/Draw/Win]"`` for football 1X2, or
                ``"[Match Winner]"`` for tennis) to filter. Passing a
                sport-incompatible filter (e.g. ``"[Win/Draw/Win]"`` for
                tennis) silently returns zero events — every sport carries
                its own ``defaultMarkets`` in the sports-list response.

        Returns:
            Raw JSON with the same shape as ``get_events``:
            ``events[]``, ``markets[]``, ``outcomes[]``, ``prices[]``.
            Each event carries ``leagueId``/``league``, ``isLive`` etc.
        """
        return await self._request(
            "GET",
            "/br/_apis/sport/v1/BetBook/LiveInPlay/",
            params={
                "countryCode": self._country_code,
                "sportId": sport_id,
                "Skip": str(skip),
                "Take": str(take),
                "cultureCode": "en-US",
                "isEsport": "false",
                "boostedOnly": "false",
                "marketTypes": market_types,
            },
        )

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

    async def get_markets(self, event_id: str, registry: Any = None) -> list:
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

    async def iter_all_prematch_events(
        self,
    ) -> AsyncIterator[PrematchEventStub]:
        """Yield every prematch event in Betway's catalogue.

        Walks all sports (``get_sports()``) → regions/leagues
        (``get_countries(sport_id)``) → per-league events
        (``get_events(region_id, league_id, sport_id, take=100)``).
        The unfiltered Highlights endpoint caps at 29 events and ignores
        ``skip``, so per-league fan-out via the BetBook/Filtered endpoint
        is the only way to enumerate the full multi-day catalogue.

        Per-league calls run concurrently under the client's
        ``MAX_CONCURRENT=50`` semaphore. Sports without
        ``hasUpcomingEvents`` are skipped. Failed per-league calls yield
        no events and don't abort the walk.

        Yields:
            :class:`PrematchEventStub` for each unique event across all
            sports. ``event_id`` is the Betway eventId (=SR numeric id),
            ``league_id`` is the league slug (e.g. ``premier-league``),
            ``sport_id`` is the sport slug (e.g. ``soccer``).
        """
        sports_resp = await self.get_sports()
        sports = [
            s
            for s in sports_resp.get("sports", [])
            if s.get("sportType") == "Sport" and s.get("hasUpcomingEvents")
        ]

        # Collect every (sport_id, region_id, league_id) triple.
        league_calls: list[tuple[str, str, str]] = []
        for s in sports:
            sid = s.get("sportId")
            if not sid:
                continue
            try:
                regions = (await self.get_countries(sport_id=sid)).get(
                    "regions", []
                )
            except Exception:
                continue
            for r in regions:
                rid = r.get("regionId")
                if not rid:
                    continue
                for lg in r.get("leagues", []) or []:
                    lid = lg.get("leagueId")
                    if lid:
                        league_calls.append((sid, rid, lid))

        async def _fetch(
            sid: str, rid: str, lid: str
        ) -> tuple[str, str, list]:
            # Pass market_types="" — the default "[Win/Draw/Win]" is
            # football-specific and silently drops events from sports
            # that don't carry 1X2 (tennis, basketball, etc.).
            try:
                resp = await self.get_events(
                    region_id=rid,
                    league_id=lid,
                    sport_id=sid,
                    take=100,
                    market_types="",
                )
                return sid, lid, resp.get("events", []) or []
            except Exception:
                return sid, lid, []

        results = await asyncio.gather(
            *[_fetch(sid, rid, lid) for sid, rid, lid in league_calls]
        )
        seen: set[str] = set()
        for sid, lid, events in results:
            for ev in events:
                eid = ev.get("eventId")
                if eid is None:
                    continue
                eid_str = str(eid)
                if eid_str in seen:
                    continue
                seen.add(eid_str)
                yield PrematchEventStub(
                    event_id=eid_str, league_id=lid, sport_id=sid
                )
