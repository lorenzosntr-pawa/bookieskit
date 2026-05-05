"""Bet9ja client — supports ng only."""

import asyncio
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

    # AUDIT: Several example files call get_sports(live=False) and
    # get_sports(live=True), but this method has no `live` parameter.
    # The live=True callers should use get_live_sports() instead.
    # Fix the example files or add a deprecation shim here.
    async def get_sports(self) -> dict[str, Any]:
        """Get all available sports with their category hierarchy (prematch).

        Returns:
            Raw JSON with R (status) and D.PAL hierarchy.
        """
        return await self._request(
            "GET",
            "/desktop/feapi/PalimpsestAjax/GetSports",
            params={"DISP": "0", "v_cache_version": _CACHE_VERSION},
        )

    async def get_live_events(
        self, sport_id: str | None = None
    ) -> dict[str, Any]:
        """Get live events.

        Args:
            sport_id: Live sport ID (e.g., "3000001" for Soccer,
                      "3000002" for Basketball). If None, returns
                      soccer by default. Use get_live_sports() first
                      to discover available live sport IDs.

        Returns:
            Raw JSON with D.S (sports), D.G (groups), D.E (events dict).
            Events keyed by ID with DS, EXTID, SID fields.
        """
        params: dict[str, str] = {"v_cache_version": _CACHE_VERSION}
        if sport_id:
            params["SID"] = sport_id
        return await self._request(
            "GET",
            "/desktop/feapi/PalimpsestLiveAjax/GetLiveEventsV3",
            params=params,
        )

    async def get_live_event_detail(
        self, event_id: str
    ) -> dict[str, Any]:
        """Get full live event detail (markets + odds) by Bet9ja internal id.

        Uses the live-specific endpoint (`GetLiveEvent`) which expects
        the parameter name `EVENTID`. The response shape mirrors the
        prematch event-detail (D.O odds dict) but odds keys use the
        `LIVES_` prefix instead of `S_` and odds values are wrapped as
        ``{"v": <float>}`` rather than bare strings.

        Args:
            event_id: Bet9ja internal numeric event id (use
                `find_event_id_by_sr_id` to resolve from a SportRadar id).

        Returns:
            Raw JSON with D.A (anchor: EXTID, score, time) and D.O
            (odds keyed by market_outcome).
        """
        return await self._request(
            "GET",
            "/desktop/feapi/PalimpsestLiveAjax/GetLiveEvent",
            params={"EVENTID": event_id, "v_cache_version": _CACHE_VERSION},
        )

    async def build_prematch_event_map(
        self, sport_id: str = "1"
    ) -> dict[str, str]:
        """Build a SR-id -> Bet9ja internal-id map for ALL prematch events
        under a sport.

        Bet9ja prematch events are scoped per-tournament (no flat global
        endpoint), so this walks every tournament under the sport and
        scans its event list for `EXTID` (the SportRadar match id).
        Reasonably fast in practice — calls are dispatched under the
        client's existing rate-limit semaphore (15 concurrent, 25ms
        delay). For Soccer (~367 tournaments) the walk takes a handful
        of seconds.

        Intended for callers that need to look up many SR ids in one
        session (e.g. a full-tournament odds compare): build the map
        once, then dict-lookup per SR id is O(1).

        Args:
            sport_id: Bet9ja prematch sport id (default "1" = Soccer).

        Returns:
            dict mapping SR numeric id (e.g. "69339436") -> Bet9ja
            internal event id (e.g. "9138769").
        """
        sports = await self.get_sports()
        sport = (sports.get("D") or {}).get("PAL", {}).get(sport_id, {})
        country_groups = sport.get("SG", {}) or {}

        # Collect every tournament id under this sport.
        tournament_ids: list[str] = []
        for country in country_groups.values():
            for tid in (country.get("G") or {}).keys():
                tournament_ids.append(str(tid))

        # Fetch every tournament's events concurrently. The base client's
        # semaphore + request_delay keep us under Bet9ja's rate limits.
        async def _fetch(tid: str) -> dict:
            try:
                return await self.get_events(tournament_id=tid)
            except Exception:
                return {}

        responses = await asyncio.gather(
            *(_fetch(tid) for tid in tournament_ids)
        )

        # Walk responses, build the SR -> internal id map.
        sr_map: dict[str, str] = {}
        for resp in responses:
            events = (resp.get("D") or {}).get("E") or []
            for ev in events:
                ext = str(ev.get("EXTID", "") or "")
                internal = str(ev.get("ID", "") or "")
                if ext and internal:
                    sr_map[ext] = internal
        return sr_map

    async def find_event_id_by_sr_id(
        self,
        sportradar_id: str,
        sport_id: str = "3000001",
    ) -> str | None:
        """Look up Bet9ja's internal event ID for a given SportRadar ID.

        Bet9ja's live events response (`D.E`) exposes `EXTID` (the SR
        numeric id) at the list level for every event, so we can scan
        once and match without per-event detail fetches.

        Currently scans live events only. Prematch events are scoped
        per-tournament and would require iterating all tournaments
        for the sport — call get_events(tournament_id) and inspect EXTID
        on each event if you know the tournament.

        Args:
            sportradar_id: SR id in either bare numeric ("69339436") or
                prefixed ("sr:match:69339436") form.
            sport_id: Live sport id to scope the search (default
                "3000001" = Soccer).

        Returns:
            Bet9ja internal event id as string, or None if not found.
        """
        target = sportradar_id
        if target.startswith("sr:match:"):
            target = target[len("sr:match:"):]

        live = await self.get_live_events(sport_id=sport_id)
        events = (live.get("D") or {}).get("E") or {}
        for internal_id, ev in events.items():
            ext = str(ev.get("EXTID", "") or "")
            if ext == target:
                return str(internal_id)
        return None

    async def get_live_sports(self) -> dict[str, Any]:
        """Get list of sports that currently have live events.

        Returns:
            Raw JSON with D.S dict keyed by live sport ID
            (e.g., "3000001"=Soccer, "3000002"=Basketball).
        """
        return await self._request(
            "GET",
            "/desktop/feapi/PalimpsestLiveAjax/GetLiveEventsV3",
            params={"v_cache_version": _CACHE_VERSION},
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
    ) -> dict[str, Any]:
        """Get events for a tournament/group.

        Args:
            tournament_id: Bet9ja group ID (e.g., "170880")

        Returns:
            Raw JSON with R (status) and D.E (events array).
        """
        return await self._request(
            "GET",
            "/desktop/feapi/PalimpsestAjax/GetEventsInGroup",
            params={
                "GROUPID": tournament_id,
                "DISP": "0",
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
