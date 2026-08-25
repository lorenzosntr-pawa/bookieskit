"""HTTP client for ElephantBet (BtoBet platform).

ElephantBet runs BtoBet ``Sb.WebApi`` v8.2.0.29, which publishes an OpenAPI
spec at ``/swagger/v1/swagger.json``. The endpoints used here are the ones
the brand's own SPA calls, not the superficially-similar alternatives in the
spec: ``FEMobile/GetGroupedMatches`` and ``FEWMatches/MatchOdds`` return
data, while ``FEWFixture/TournamentMatchOdds`` and ``FEMobile/GetMatchOdds``
answer ``204 No Content`` for the same arguments.

Only Mozambique is supported. ElephantBet also has Angola, Sierra Leone and
Malawi brands, but their hosts sit behind a WAF that returns 403 to
non-browser clients, so they cannot be verified and are not listed.
"""

from typing import Any

from bookieskit.base import BaseBookmaker
from bookieskit.config import (
    ELEPHANTBET_MAX_CONCURRENT,
    ELEPHANTBET_REQUEST_DELAY,
)

# Country -> BtoBet `Culture` value. The API rejects requests without it.
_CULTURE_PER_COUNTRY = {"mz": "pt"}


class ElephantBet(BaseBookmaker):
    """HTTP client for the ElephantBet sportsbook API.

    Args:
        country: Country code (only "mz" supported)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Max retry attempts (default: 3)
        backoff_factor: Exponential backoff base (default: 1.0)
        max_concurrent: Max parallel requests (default: 50)
        request_delay: Delay between requests in seconds (default: 0)
    """

    DOMAINS = {
        "mz": "https://sports-core.elephantbet.com",
    }
    DEFAULT_HEADERS = {
        "accept": "application/json",
        "accept-language": "pt-PT,pt;q=0.9,en;q=0.8",
        "origin": "https://www.elephantbet.co.mz",
        "referer": "https://www.elephantbet.co.mz/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",  # noqa: E501
    }
    MAX_CONCURRENT = ELEPHANTBET_MAX_CONCURRENT
    REQUEST_DELAY = ELEPHANTBET_REQUEST_DELAY
    NAME = "ElephantBet"
    PLATFORM_KEY = "elephantbet"

    @property
    def _culture(self) -> str:
        """BtoBet culture code for this country."""
        return _CULTURE_PER_COUNTRY.get(self._country, "pt")

    async def get_sports(self) -> dict[str, Any]:
        """Get all available sports.

        Returns:
            Raw JSON list; each entry has ``id``, ``n`` (localised name) and
            ``c`` (stable slug, e.g. ``"soccer"``). The catalogue includes
            virtual and Zoom products, so filter on ``c``, not on position.
        """
        return await self._request(
            "GET",
            "/rest/FEWFixture/Sports",
            params={"Culture": self._culture},
        )

    async def get_countries(self, sport_id: str = "1") -> dict[str, Any]:
        """Get the full sport -> category -> tournament tree.

        BtoBet returns the whole menu in one call rather than per-sport, so
        ``sport_id`` is accepted for interface symmetry with the other
        clients and callers filter the ``s[]`` list themselves.

        Returns:
            Raw JSON with ``s[]`` (sports), each carrying ``i[]``
            (categories), each carrying ``i[]`` (tournaments).
        """
        return await self._request(
            "GET",
            "/rest/FEWFixture/FixturesMenu",
            params={"Culture": self._culture},
        )

    async def get_tournaments(self, sport_id: str = "1") -> dict[str, Any]:
        """Alias of :meth:`get_countries` — same endpoint, same payload."""
        return await self.get_countries(sport_id)

    async def get_events(
        self, tournament_id: str, limit: int = 50
    ) -> dict[str, Any]:
        """Get events for a tournament, with their main markets.

        Args:
            tournament_id: BtoBet tournament id (e.g. "1428062").
            limit: Page size.

        Returns:
            Raw JSON list of sports, each with ``t[]`` tournaments, each
            with ``m[]`` matches. Match fields include ``mid`` (match id),
            ``brid`` (SportRadar id), ``ht``/``at`` and ``d`` (kickoff).
        """
        return await self._request(
            "GET",
            "/rest/FEMobile/GetGroupedMatches",
            params={
                "TournamentData[]": tournament_id,
                "Culture": self._culture,
                "Limit": str(limit),
            },
        )

    async def get_live_events(
        self, sport_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get every in-play match, optionally filtered to one sport.

        BtoBet has no per-sport live endpoint: ``GetLiveMatchesMetaData``
        returns every live match across all sports in one call, so
        ``sport_id`` filters client-side on each entry's ``sid``.

        Note the id trap. On this feed ``brid`` is an 18-digit
        BtoBet-internal snowflake and the SportRadar id lives in ``obrid``
        (often ``None``) — the exact opposite of the prematch listing.
        Use :func:`bookieskit.extract_event_ids`, which handles both.

        Live prices are not returned in a parseable form: each entry carries
        a compressed ``aot`` odds string, and per-match live market endpoints
        answer ``204``. Live market parsing is a separate increment.

        Args:
            sport_id: Optional BtoBet sport id (e.g. ``"1"`` for soccer).

        Returns:
            List of live match entries with ``mid``, ``ht``/``at``, ``ms``
            (period), ``mt`` (minute) and ``sc`` (score "home:away").
        """
        raw = await self._request(
            "GET",
            "/rest/FEMobile/GetLiveMatchesMetaData",
            params={"Culture": self._culture},
        )
        if not isinstance(raw, list):
            return []
        if sport_id is None:
            return raw
        return [m for m in raw if str(m.get("sid")) == str(sport_id)]

    async def get_event_detail(self, event_id: str) -> dict[str, Any]:
        """Get full markets and odds for one match.

        Args:
            event_id: BtoBet match id (``mid``, e.g. "5998731").

        Returns:
            Raw JSON shaped ``{"s": ..., "t": [{"o": [<market>, ...]}]}`` —
            markets are nested under display tabs in ``t[].o[]``.
        """
        return await self._request(
            "GET",
            "/rest/FEWMatches/MatchOdds",
            params={"MatchID": event_id, "Culture": self._culture},
        )
