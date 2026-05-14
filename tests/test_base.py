import httpx
import pytest
import respx
from conftest import MockBookmaker

from bookieskit.exceptions import (
    RateLimitError,
    RequestError,
    TimeoutError,
    UnsupportedCountryError,
)


def test_unsupported_country_raises():
    with pytest.raises(UnsupportedCountryError) as exc_info:
        MockBookmaker(country="ke")
    assert "ke" in str(exc_info.value)
    assert "ng" in str(exc_info.value)


def test_base_url_resolved_from_country():
    client = MockBookmaker(country="ng")
    assert client.base_url == "https://mock.example.com"

    client_gh = MockBookmaker(country="gh")
    assert client_gh.base_url == "https://mock-gh.example.com"


@pytest.mark.asyncio
@respx.mock
async def test_async_context_manager():
    async with MockBookmaker(country="ng") as client:
        assert client._http_client is not None
    assert client._http_client.is_closed


@pytest.mark.asyncio
@respx.mock
async def test_successful_request():
    respx.get("https://mock.example.com/api/test").respond(
        json={"result": "ok"}
    )
    async with MockBookmaker(country="ng") as client:
        result = await client._request("GET", "/api/test")
    assert result == {"result": "ok"}


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_server_error():
    route = respx.get("https://mock.example.com/api/test")
    route.side_effect = [
        httpx.Response(500, json={"error": "internal"}),
        httpx.Response(500, json={"error": "internal"}),
        httpx.Response(200, json={"result": "ok"}),
    ]
    async with MockBookmaker(country="ng", backoff_factor=0.01) as client:
        result = await client._request("GET", "/api/test")
    assert result == {"result": "ok"}
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_raises_request_error_after_max_retries():
    respx.get("https://mock.example.com/api/test").respond(500)
    async with MockBookmaker(
        country="ng", max_retries=2, backoff_factor=0.01
    ) as client:
        with pytest.raises(RequestError) as exc_info:
            await client._request("GET", "/api/test")
    assert exc_info.value.retries == 2


@pytest.mark.asyncio
@respx.mock
async def test_raises_rate_limit_error_on_429():
    respx.get("https://mock.example.com/api/test").respond(
        429, headers={"Retry-After": "5"}
    )
    async with MockBookmaker(
        country="ng", max_retries=1, backoff_factor=0.01
    ) as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client._request("GET", "/api/test")
    assert exc_info.value.bookmaker == "MockBookmaker"


@pytest.mark.asyncio
@respx.mock
async def test_timeout_raises_timeout_error():
    respx.get("https://mock.example.com/api/test").mock(
        side_effect=httpx.ReadTimeout("timed out")
    )
    async with MockBookmaker(
        country="ng", max_retries=1, backoff_factor=0.01
    ) as client:
        with pytest.raises(TimeoutError) as exc_info:
            await client._request("GET", "/api/test")
    assert exc_info.value.timeout == 30.0


@pytest.mark.asyncio
@respx.mock
async def test_absolute_path_reports_absolute_url_in_request_error():
    """When a subclass routes to a different host via an absolute URL,
    the URL recorded on a raised RequestError must be the absolute one,
    not ``base_url + absolute_url`` concatenated together."""
    respx.get("https://other.example.com/api/test").respond(500)
    async with MockBookmaker(
        country="ng", max_retries=1, backoff_factor=0.01,
    ) as client:
        with pytest.raises(RequestError) as exc_info:
            await client._request("GET", "https://other.example.com/api/test")
    assert exc_info.value.url == "https://other.example.com/api/test"


@pytest.mark.asyncio
@respx.mock
async def test_absolute_path_reports_absolute_url_in_rate_limit_error():
    respx.get("https://other.example.com/api/test").respond(
        429, headers={"Retry-After": "1"}
    )
    async with MockBookmaker(
        country="ng", max_retries=1, backoff_factor=0.01,
    ) as client:
        with pytest.raises(RateLimitError) as exc_info:
            await client._request("GET", "https://other.example.com/api/test")
    assert exc_info.value.url == "https://other.example.com/api/test"


@pytest.mark.asyncio
@respx.mock
async def test_custom_config_overrides_defaults():
    respx.get("https://mock.example.com/api/test").respond(json={"ok": True})
    async with MockBookmaker(
        country="ng", timeout=10.0, max_retries=5, max_concurrent=20
    ) as client:
        assert client._timeout == 10.0
        assert client._max_retries == 5
        assert client._max_concurrent == 20


def test_cookie_kwarg_included_in_built_headers():
    client = MockBookmaker(country="ng", cookie="bm_sv=abc; ak_bmsc=def")
    headers = client._build_headers()
    assert headers.get("cookie") == "bm_sv=abc; ak_bmsc=def"


def test_no_cookie_kwarg_means_no_cookie_header():
    client = MockBookmaker(country="ng")
    headers = client._build_headers()
    assert "cookie" not in headers


def test_set_cookie_before_context_updates_built_headers():
    client = MockBookmaker(country="ng")
    client.set_cookie("foo=1")
    assert client._build_headers().get("cookie") == "foo=1"


@pytest.mark.asyncio
@respx.mock
async def test_set_cookie_after_context_updates_live_headers():
    respx.get("https://mock.example.com/api/test").respond(json={"ok": True})
    async with MockBookmaker(country="ng") as client:
        client.set_cookie("session=xyz")
        await client._request("GET", "/api/test")
        assert client._http_client.headers.get("cookie") == "session=xyz"


@pytest.mark.asyncio
@respx.mock
async def test_cookie_kwarg_carried_into_live_headers():
    respx.get("https://mock.example.com/api/test").respond(json={"ok": True})
    async with MockBookmaker(country="ng", cookie="ck=1") as client:
        await client._request("GET", "/api/test")
        assert client._http_client.headers.get("cookie") == "ck=1"
