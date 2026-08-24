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
