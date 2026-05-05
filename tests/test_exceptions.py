from bookieskit.exceptions import (
    BookiesKitError,
    RateLimitError,
    RequestError,
    ResponseError,
    TimeoutError,
    UnsupportedCountryError,
)


def test_exception_hierarchy():
    """All exceptions inherit from BookiesKitError."""
    assert issubclass(RequestError, BookiesKitError)
    assert issubclass(TimeoutError, BookiesKitError)
    assert issubclass(RateLimitError, BookiesKitError)
    assert issubclass(ResponseError, BookiesKitError)
    assert issubclass(UnsupportedCountryError, BookiesKitError)


def test_request_error_contains_context():
    err = RequestError(
        url="https://example.com/api", retries=3, message="Connection failed"
    )
    assert err.url == "https://example.com/api"
    assert err.retries == 3
    assert "Connection failed" in str(err)


def test_timeout_error_contains_context():
    err = TimeoutError(url="https://example.com/api", retries=3, timeout=30.0)
    assert err.url == "https://example.com/api"
    assert err.retries == 3
    assert err.timeout == 30.0


def test_rate_limit_error_contains_context():
    err = RateLimitError(
        bookmaker="bet9ja", url="https://sports.bet9ja.com/api", retry_after=5.0
    )
    assert err.bookmaker == "bet9ja"
    assert err.retry_after == 5.0


def test_response_error_contains_status():
    err = ResponseError(
        url="https://example.com/api", status_code=500, body="Internal error"
    )
    assert err.status_code == 500
    assert err.body == "Internal error"


def test_unsupported_country_error():
    err = UnsupportedCountryError(bookmaker="Bet9ja", country="gh", available=["ng"])
    assert "gh" in str(err)
    assert "ng" in str(err)
    assert "Bet9ja" in str(err)
