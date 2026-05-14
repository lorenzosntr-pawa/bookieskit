"""Betika client — supports ke, ug, tz, mw, gh.

Betika's API is country-agnostic at the host level: every supported
country code resolves to the same ``api.betika.com`` (prematch) and
``live.betika.com`` (in-play) hosts. The country argument is preserved
on the instance for informational use (logging, UI labels) but does not
drive any URL, header, or filtering behaviour.

The API is open: no Cloudflare gate, no warmed cookies, no observed
rate limiting under bursty traffic.
"""

from typing import Any

from bookieskit.base import BaseBookmaker
from bookieskit.config import BETIKA_MAX_CONCURRENT, BETIKA_REQUEST_DELAY


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
