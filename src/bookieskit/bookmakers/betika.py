"""Betika client — supports ke, ug, tz, mw, gh.

Betika's API is country-agnostic at the host level: every supported
country code resolves to the same ``api.betika.com`` (prematch) and
``live.betika.com`` (in-play) hosts. The country argument is preserved
on the instance for informational use (logging, UI labels) but does not
drive any URL, header, or filtering behaviour.

The API is open: no Cloudflare gate, no warmed cookies, no observed
rate limiting under bursty traffic.
"""

import asyncio
import math
from typing import Any, AsyncIterator

from bookieskit.base import BaseBookmaker
from bookieskit.bookmakers.types import PrematchEventStub
from bookieskit.config import BETIKA_MAX_CONCURRENT, BETIKA_REQUEST_DELAY

# Universal market sub_type_ids — 1X2, Double Chance, Over/Under, BTTS.
# Match the four canonical markets exposed in `BUILTIN_MAPPINGS`.
_UNIVERSAL_SUB_TYPE_IDS = ("1", "10", "18", "29")


class Betika(BaseBookmaker):
    """HTTP client for the Betika sportsbook API.

    Args:
        country: Country code (ke, ug, tz, mw, gh) — informational only.
        timeout: Request timeout in seconds (default: 30).
        max_retries: Max retry attempts (default: 3).
        backoff_factor: Exponential backoff base (default: 1.0).
        max_concurrent: Max parallel requests (default: 50).
        request_delay: Delay between requests in seconds (default: 0.0).
    """

    DOMAINS = {
        "ke": "https://api.betika.com",
        "ug": "https://api.betika.com",
        "tz": "https://api.betika.com",
        "mw": "https://api.betika.com",
        "gh": "https://api.betika.com",
    }
    LIVE_BASE_URL = "https://live.betika.com"
    DEFAULT_HEADERS = {
        "accept": "application/json, text/plain, */*",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/144.0.0.0 Safari/537.36"
        ),
    }
    MAX_CONCURRENT = BETIKA_MAX_CONCURRENT
    REQUEST_DELAY = BETIKA_REQUEST_DELAY
    NAME = "Betika"
    PLATFORM_KEY = "betika"

    async def _live_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Issue a request against ``live.betika.com``.

        Betika's live endpoints live on a separate host from the prematch
        API, but share authentication, headers, and rate limits. This
        helper reuses the base ``_request`` retry / semaphore stack by
        passing an absolute URL — httpx honours an absolute path even when
        a ``base_url`` is bound on the client.
        """
        return await self._request(
            method, f"{self.LIVE_BASE_URL}{path}", params=params
        )

    async def get_sports(self) -> dict[str, Any]:
        """Get the sport catalogue.

        Returns:
            Raw JSON shaped as ``{"data": [{"id": int, "name": str, ...},
            ...], "meta": {...}}``. Football is ``id=14``.
        """
        return await self._request("GET", "/v1/sports")

    async def get_navigation(self) -> dict[str, Any]:
        """Alias for :meth:`get_sports`.

        Betika does not expose a single endpoint that returns the full
        sport → category → competition tree (those live on separate
        endpoints). ``get_navigation`` is kept as an alias of
        :meth:`get_sports` so cross-bookmaker code that calls
        ``client.get_navigation()`` continues to receive *something*
        useful (the sport list) for Betika.
        """
        return await self.get_sports()

    async def get_matches(
        self,
        sport_id: int = 14,
        page: int = 1,
        limit: int = 100,
        sub_type_id: str | None = None,
        competition_id: str | None = None,
        match_id: str | None = None,
        period_id: int | None = None,
    ) -> dict[str, Any]:
        """Get prematch matches from ``/v1/uo/matches``.

        Args:
            sport_id: Betika sport id (default ``14`` = Football).
            page: 1-indexed page number.
            limit: Page size (max observed: 100).
            sub_type_id: Optional market filter (e.g. ``"18"`` to embed
                Over/Under markets in each match's ``odds`` list instead
                of the default 1X2).
            competition_id: Optional competition (league) filter.
            match_id: Fetch a single match (overrides paging).
            period_id: Optional date-window filter. The endpoint defaults
                to a rolling 48hr ``"Next 48hrs"`` view (~176 football
                events at writing); pass ``9`` for the full multi-month
                catalogue (~1210 football events). Other documented ids:
                ``-1`` Today, ``1`` Tomorrow, ``2``–``7`` named weekdays.

        Returns:
            JSON shaped as ``{"data": [<match>, ...], "meta":
            {"total": int, "page": int, ...}}``. ``meta.total`` arrives
            as a string in real responses; iterator code should coerce
            it with :func:`int` before paginating.
        """
        params: dict[str, Any] = {
            "sport_id": str(sport_id),
            "page": str(page),
            "limit": str(limit),
        }
        if sub_type_id is not None:
            params["sub_type_id"] = sub_type_id
        if competition_id is not None:
            params["competition_id"] = competition_id
        if match_id is not None:
            params["match_id"] = match_id
        if period_id is not None:
            params["period_id"] = str(period_id)
        return await self._request("GET", "/v1/uo/matches", params=params)

    async def get_live_matches(
        self,
        sport_id: int = 14,
        page: int = 1,
        limit: int = 100,
        match_id: str | None = None,
    ) -> dict[str, Any]:
        """Get currently-live matches from ``live.betika.com/v1/uo/matches``.

        Args:
            sport_id: Betika sport id (default ``14`` = Football).
            page: 1-indexed page number.
            limit: Page size.
            match_id: Fetch a single in-play match by id (overrides paging).

        Returns:
            JSON in the same shape as :meth:`get_matches`, plus the rich
            in-play fields documented in ``betika/RESOLVED.md``
            (``match_time``, ``event_status``, ``current_score`` etc.).
        """
        params: dict[str, Any] = {
            "sport_id": str(sport_id),
            "page": str(page),
            "limit": str(limit),
        }
        if match_id is not None:
            params["match_id"] = match_id
        return await self._live_request("GET", "/v1/uo/matches", params=params)

    async def get_event_detail(
        self,
        event_id: str,
        live: bool = False,
        competition_id: str | None = None,
    ) -> dict[str, Any]:
        """Get the event-detail payload for one match.

        Args:
            event_id: Betika internal ``match_id``.
            live: If True, fetch from ``live.betika.com``; otherwise from
                ``api.betika.com``.
            competition_id: Optional Betika ``competition_id`` filter.
                Betika's ``match_id`` is unique only within a
                ``(sport_id, competition_id)`` pair — a bare
                ``match_id`` lookup may resolve to a different match
                that happens to share the same id. Pass the
                ``competition_id`` from the listing response to
                disambiguate.

        Returns:
            JSON shaped as ``{"data": [<match>], "meta": {...}}``. The
            default response carries a single market group (1X2);
            :meth:`get_event_markets` aggregates the full universal set.
        """
        params: dict[str, Any] = {"match_id": event_id, "limit": "1"}
        if competition_id is not None:
            params["competition_id"] = str(competition_id)
        if live:
            return await self._live_request(
                "GET", "/v1/uo/matches", params=params
            )
        return await self._request("GET", "/v1/uo/matches", params=params)

    async def get_event_markets(
        self,
        event_id: str,
        live: bool = False,
        competition_id: str | None = None,
    ) -> dict[str, Any]:
        """Fetch the universal market set for one event in one merged payload.

        Betika's ``/v1/uo/matches`` returns a single market group per call
        by default; to fetch a different market you must repeat the call
        with ``&sub_type_id=N``. This method fans out the four universal
        market ids concurrently and stitches their ``odds`` groups into a
        single match-shaped response — exactly the shape the parser
        expects.

        Args:
            event_id: Betika internal ``match_id``.
            live: If True, fetch from ``live.betika.com``.
            competition_id: Optional Betika ``competition_id`` filter.
                Betika's ``match_id`` is unique only within a
                ``(sport_id, competition_id)`` pair — without this filter
                a bare ``match_id`` lookup may return a different match
                with the same id. Always pass this when you have it
                (the listing endpoint includes it on every match row).

        Returns:
            JSON shaped as ``{"data": [<match>], "meta": {...}}`` where
            ``<match>.odds`` contains one entry per universal market id
            (1, 10, 18, 29). If a particular market is unavailable for
            the event it is silently skipped.
        """
        async def _fetch_one(sub_type_id: str) -> dict[str, Any]:
            params: dict[str, Any] = {
                "match_id": event_id,
                "limit": "1",
                "sub_type_id": sub_type_id,
            }
            if competition_id is not None:
                params["competition_id"] = str(competition_id)
            if live:
                return await self._live_request(
                    "GET", "/v1/uo/matches", params=params
                )
            return await self._request("GET", "/v1/uo/matches", params=params)

        responses = await asyncio.gather(
            *(_fetch_one(s) for s in _UNIVERSAL_SUB_TYPE_IDS),
            return_exceptions=True,
        )

        merged_match: dict[str, Any] | None = None
        merged_odds: list[dict[str, Any]] = []
        merged_meta: dict[str, Any] = {}
        for r in responses:
            if isinstance(r, BaseException) or not isinstance(r, dict):
                continue
            data = r.get("data") or []
            if not isinstance(data, list) or not data:
                continue
            match = data[0]
            if not isinstance(match, dict):
                continue
            if merged_match is None:
                merged_match = dict(match)
                merged_match["odds"] = []
            for grp in match.get("odds") or []:
                if isinstance(grp, dict):
                    merged_odds.append(grp)
            if isinstance(r.get("meta"), dict):
                merged_meta = r["meta"]

        if merged_match is None:
            return {"data": [], "meta": {}}
        merged_match["odds"] = merged_odds
        return {"data": [merged_match], "meta": merged_meta}

    async def get_markets(
        self, event_id: str, registry: Any = None
    ) -> list:
        """Fetch the universal market set and return normalized markets.

        Overrides the base because Betika requires four calls (one per
        universal market id) to assemble a complete event payload.
        """
        from bookieskit.markets.parser import parse_markets

        raw = await self.get_event_markets(event_id=event_id)
        return parse_markets(
            raw, platform=self.PLATFORM_KEY, registry=registry
        )

    async def iter_all_prematch_events(
        self,
        sport_id: int = 14,
        limit: int = 100,
        period_id: int | None = 9,
    ) -> AsyncIterator[PrematchEventStub]:
        """Yield every prematch event in Betika's catalogue.

        Uses ``meta.total`` from the first page response to compute the
        total page count and fans the remaining pages out concurrently —
        bounded by the client's ``MAX_CONCURRENT`` semaphore.

        Args:
            sport_id: Betika sport id (default ``14`` = Football).
            limit: Page size (default 100, the API maximum).
            period_id: Date-window filter; defaults to ``9`` (All) so the
                iterator returns the full multi-month catalogue rather
                than the API's rolling-48hr default. Pass ``None`` to
                accept the API default.

        Yields:
            :class:`PrematchEventStub` for each match. ``event_id`` is
            Betika's internal ``match_id``; ``league_id`` is
            ``competition_id``; ``sport_id`` mirrors the requested sport.
        """
        first = await self.get_matches(
            sport_id=sport_id, page=1, limit=limit, period_id=period_id
        )
        for stub in _stubs_from_page(first, sport_id):
            yield stub

        meta = first.get("meta") if isinstance(first, dict) else None
        total = _coerce_int(meta.get("total")) if isinstance(meta, dict) else 0
        if total <= limit:
            return
        total_pages = math.ceil(total / limit)
        remaining = range(2, total_pages + 1)

        async def _fetch(page: int) -> dict[str, Any]:
            try:
                return await self.get_matches(
                    sport_id=sport_id, page=page, limit=limit,
                    period_id=period_id,
                )
            except Exception:
                return {"data": [], "meta": {}}

        results = await asyncio.gather(*(_fetch(p) for p in remaining))
        for r in results:
            for stub in _stubs_from_page(r, sport_id):
                yield stub


def _coerce_int(v: Any) -> int:
    """Best-effort int coercion — used for Betika's stringy ``meta.total``."""
    if isinstance(v, bool):
        return 0
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            return 0
    if isinstance(v, float):
        return int(v)
    return 0


def _stubs_from_page(
    response: Any, sport_id: int
) -> list[PrematchEventStub]:
    """Extract :class:`PrematchEventStub`s from one ``/v1/uo/matches`` page."""
    if not isinstance(response, dict):
        return []
    data = response.get("data") or []
    if not isinstance(data, list):
        return []
    stubs: list[PrematchEventStub] = []
    for match in data:
        if not isinstance(match, dict):
            continue
        mid = match.get("match_id")
        if mid is None:
            continue
        league = match.get("competition_id")
        stubs.append(
            PrematchEventStub(
                event_id=str(mid),
                league_id=str(league) if league is not None else "",
                sport_id=str(match.get("sport_id") or sport_id),
            )
        )
    return stubs
