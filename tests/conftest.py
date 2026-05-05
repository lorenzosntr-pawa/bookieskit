"""Shared test fixtures."""

import pytest

from bookieskit.base import BaseBookmaker


class MockBookmaker(BaseBookmaker):
    """Concrete subclass for testing base functionality."""

    DOMAINS = {
        "ng": "https://mock.example.com",
        "gh": "https://mock-gh.example.com",
    }
    DEFAULT_HEADERS = {"x-mock": "true"}
    MAX_CONCURRENT = 50
    REQUEST_DELAY = 0.0
    NAME = "MockBookmaker"


@pytest.fixture
def mock_bookmaker():
    return MockBookmaker(country="ng")
