"""Exception hierarchy for bookieskit."""


class BookiesKitError(Exception):
    """Base exception for all bookieskit errors."""


class RequestError(BookiesKitError):
    """HTTP request failed after all retries (network, DNS, etc.)."""

    def __init__(self, url: str, retries: int, message: str):
        self.url = url
        self.retries = retries
        super().__init__(f"Request to {url} failed after {retries} retries: {message}")


class TimeoutError(BookiesKitError):
    """Request exceeded configured timeout."""

    def __init__(self, url: str, retries: int, timeout: float):
        self.url = url
        self.retries = retries
        self.timeout = timeout
        super().__init__(
            f"Request to {url} timed out after {timeout}s ({retries} retries)"
        )


class RateLimitError(BookiesKitError):
    """Platform returned rate-limit signal (429 or equivalent)."""

    def __init__(self, bookmaker: str, url: str, retry_after: float | None = None):
        self.bookmaker = bookmaker
        self.url = url
        self.retry_after = retry_after
        msg = f"Rate limited by {bookmaker} at {url}"
        if retry_after:
            msg += f" (retry after {retry_after}s)"
        super().__init__(msg)


class ResponseError(BookiesKitError):
    """Got a response but it indicates failure."""

    def __init__(self, url: str, status_code: int, body: str = ""):
        self.url = url
        self.status_code = status_code
        self.body = body
        super().__init__(f"Response error {status_code} from {url}: {body}")


class UnsupportedCountryError(BookiesKitError):
    """Invalid country code for this bookmaker."""

    def __init__(self, bookmaker: str, country: str, available: list[str]):
        self.bookmaker = bookmaker
        self.country = country
        self.available = available
        super().__init__(
            f"{bookmaker} does not support '{country}'. Available: {available}"
        )
