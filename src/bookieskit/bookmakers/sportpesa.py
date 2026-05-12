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
