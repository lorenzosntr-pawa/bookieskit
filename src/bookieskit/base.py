"""Base bookmaker client with shared HTTP, retry, and rate-limiting logic."""

import asyncio
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from bookieskit.markets.registry import MarketRegistry
    from bookieskit.markets.types import NormalizedMarket

from bookieskit.config import (
    DEFAULT_BACKOFF_FACTOR,
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_MAX_KEEPALIVE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    RETRYABLE_STATUS_CODES,
)
from bookieskit.exceptions import (
    RateLimitError,
    RequestError,
    ResponseError,
    TimeoutError,
    UnsupportedCountryError,
)


class BaseBookmaker:
    """Base class for all bookmaker HTTP clients.

    Subclasses must define:
        DOMAINS: dict[str, str] — country code to base URL mapping
        DEFAULT_HEADERS: dict[str, str] — platform-specific headers
        MAX_CONCURRENT: int — default max concurrent requests
        REQUEST_DELAY: float — default delay between requests (seconds)
        NAME: str — bookmaker display name
    """

    DOMAINS: dict[str, str] = {}
    DEFAULT_HEADERS: dict[str, str] = {}
    MAX_CONCURRENT: int = 50
    REQUEST_DELAY: float = 0.0
    NAME: str = "BaseBookmaker"
    PLATFORM_KEY: str = ""

    def __init__(
        self,
        country: str,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        max_concurrent: int | None = None,
        request_delay: float | None = None,
        cookie: str | None = None,
    ) -> None:
        """Initialise the client for the given country.

        Args:
            country: ISO country code (must be in DOMAINS).
            timeout: Request timeout in seconds.
            max_retries: Number of retry attempts for transient errors.
            backoff_factor: Exponential backoff multiplier.
            max_concurrent: Maximum concurrent requests (overrides class default).
            request_delay: Per-request delay in seconds (overrides class default).
            cookie: Optional ``Cookie:`` header value sent on every request.
                Primarily needed for SportPesa (Akamai-gated); callers can
                also use :meth:`set_cookie` to refresh mid-session.

        Raises:
            UnsupportedCountryError: If ``country`` is not in DOMAINS.
        """
        if country not in self.DOMAINS:
            raise UnsupportedCountryError(
                bookmaker=self.NAME,
                country=country,
                available=list(self.DOMAINS.keys()),
            )

        self._country = country
        self.base_url = self.DOMAINS[country]
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._max_concurrent = max_concurrent or self.MAX_CONCURRENT
        self._request_delay = (
            request_delay if request_delay is not None else self.REQUEST_DELAY
        )
        self._cookie = cookie
        self._http_client: httpx.AsyncClient | None = None
        self._semaphore: asyncio.Semaphore | None = None

    def _build_headers(self) -> dict[str, str]:
        """Build request headers. Override in subclass for country-specific headers.

        Subclasses that override should call ``super()._build_headers()`` first
        so cookie injection (set via the ``cookie=`` constructor kwarg or
        :meth:`set_cookie`) is preserved.
        """
        headers = dict(self.DEFAULT_HEADERS)
        if self._cookie:
            headers["cookie"] = self._cookie
        return headers

    def set_cookie(self, cookie: str) -> None:
        """Set or replace the ``Cookie:`` header for subsequent requests.

        Works both before entering the async context (sets the value
        :meth:`_build_headers` will pick up) and after (updates the
        live ``httpx.AsyncClient`` headers in-place so the next call
        carries the new cookie). Primarily needed for SportPesa, but
        available on every client.

        Args:
            cookie: Full ``Cookie:`` header value (semicolon-separated
                ``name=value`` pairs, as captured from a browser).
        """
        self._cookie = cookie
        if self._http_client is not None:
            self._http_client.headers["cookie"] = cookie

    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._build_headers(),
            timeout=httpx.Timeout(self._timeout),
            limits=httpx.Limits(
                max_connections=DEFAULT_MAX_CONNECTIONS,
                max_keepalive_connections=DEFAULT_MAX_KEEPALIVE,
            ),
        )
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        return self

    async def __aexit__(self, *args):
        if self._http_client:
            await self._http_client.aclose()

    def __enter__(self):
        """Sync context manager — creates event loop and async client."""
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self.__aenter__())
        return _SyncProxy(self, self._loop)

    def __exit__(self, *args):
        """Sync context manager cleanup."""
        self._loop.run_until_complete(self.__aexit__(*args))
        self._loop.close()
        self._loop = None

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with retry and rate-limiting.

        Args:
            method: HTTP method (GET, POST)
            path: URL path (appended to base_url)
            params: Query parameters
            json: JSON body (for POST)

        Returns:
            Parsed JSON response as dict

        Raises:
            TimeoutError: Request timed out after all retries
            RateLimitError: Platform returned 429
            RequestError: Request failed after all retries
        """
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            if attempt > 0:
                delay = self._backoff_factor * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

            try:
                async with self._semaphore:
                    if self._request_delay > 0:
                        await asyncio.sleep(self._request_delay)

                    response = await self._http_client.request(
                        method, path, params=params, json=json
                    )

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    last_error = RateLimitError(
                        bookmaker=self.NAME,
                        url=url,
                        retry_after=float(retry_after) if retry_after else None,
                    )
                    continue

                if response.status_code in RETRYABLE_STATUS_CODES:
                    last_error = RequestError(
                        url=url,
                        retries=attempt + 1,
                        message=f"HTTP {response.status_code}",
                    )
                    continue

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise ResponseError(
                        url=url,
                        status_code=e.response.status_code,
                        body=e.response.text[:500],
                    ) from e
                return response.json()

            except httpx.TimeoutException:
                last_error = TimeoutError(
                    url=url, retries=attempt + 1, timeout=self._timeout
                )
            except httpx.ConnectError as e:
                last_error = RequestError(
                    url=url, retries=attempt + 1, message=str(e)
                )

        raise last_error

    async def get_markets(
        self,
        event_id: str,
        registry: "MarketRegistry | None" = None,
    ) -> "list[NormalizedMarket]":
        """Fetch event detail and return normalized markets.

        Args:
            event_id: Platform-specific event ID
            registry: MarketRegistry (default: built-in 6 markets)

        Returns:
            List of NormalizedMarket for recognized markets.
        """
        from bookieskit.markets.parser import parse_markets

        raw = await self.get_event_detail(event_id=event_id)
        return parse_markets(
            raw, platform=self.PLATFORM_KEY, registry=registry
        )

    async def get_sportradar_id(self, event_id: str) -> str | None:
        """Fetch event detail and extract SportRadar ID.

        Args:
            event_id: Platform-specific event ID

        Returns:
            SportRadar ID string, or None if not available.
        """
        from bookieskit.matching.extractor import extract_sportradar_id

        raw = await self.get_event_detail(event_id=event_id)
        return extract_sportradar_id(
            raw, platform=self.PLATFORM_KEY
        )


class _SyncProxy:
    """Proxy that wraps async methods as sync calls."""

    def __init__(self, instance: BaseBookmaker, loop: asyncio.AbstractEventLoop):
        self._instance = instance
        self._loop = loop

    def __getattr__(self, name: str):
        attr = getattr(self._instance, name)
        if callable(attr) and asyncio.iscoroutinefunction(attr):
            def sync_wrapper(*args, **kwargs):
                return self._loop.run_until_complete(attr(*args, **kwargs))
            sync_wrapper.__name__ = name
            sync_wrapper.__doc__ = attr.__doc__
            return sync_wrapper
        return attr
