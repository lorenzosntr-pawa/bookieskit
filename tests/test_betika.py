"""Unit tests for the Betika client.

Betika is country-agnostic at the API layer — all five supported country
codes (ke, ug, tz, mw, gh) resolve to the same ``api.betika.com`` host.
Live in-play data is served from a separate host, ``live.betika.com``.
"""

import pytest

from bookieskit.bookmakers.betika import Betika


@pytest.mark.parametrize("country", ["ke", "ug", "tz", "mw", "gh"])
def test_betika_country_resolves_domain(country):
    client = Betika(country=country)
    assert client.base_url == "https://api.betika.com"


def test_betika_unsupported_country():
    from bookieskit.exceptions import UnsupportedCountryError
    with pytest.raises(UnsupportedCountryError):
        Betika(country="xx")


def test_betika_default_headers_have_user_agent():
    client = Betika(country="ke")
    headers = client._build_headers()
    assert "user-agent" in headers
    assert "Mozilla" in headers["user-agent"]


def test_betika_live_base_url_constant():
    assert Betika.LIVE_BASE_URL == "https://live.betika.com"


def test_betika_platform_key():
    assert Betika.PLATFORM_KEY == "betika"
