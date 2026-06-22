import pytest

from bookieskit.devtools.resolver import ALL_BOOKS, resolve_event
from bookieskit.devtools.types import Handle


class _FakeClient:
    """Minimal async-context client stub for resolver tests."""

    def __init__(self, **methods):
        self._methods = methods

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def __getattr__(self, name):
        if name in self._methods:
            return self._methods[name]
        raise AttributeError(name)


def test_all_books_lists_seven():
    assert ALL_BOOKS == (
        "betpawa", "sportybet", "msport", "bet9ja",
        "betway", "betika", "sportpesa",
    )


@pytest.mark.asyncio
async def test_resolve_from_sr_id_populates_handles_and_skips():
    async def _b9_map(sport_id):
        return {}  # SR id not in prematch map -> not found

    clients = {
        "sportybet": _FakeClient(),
        "msport": _FakeClient(),
        "betway": _FakeClient(),
        "bet9ja": _FakeClient(build_prematch_event_map=_b9_map),
    }
    ev = await resolve_event(
        "sr:match:42",
        "soccer",
        books=("sportybet", "msport", "betway", "bet9ja", "sportpesa"),
        clients=clients,
    )
    assert ev.sr_numeric == "42"
    assert ev.handles["sportybet"] == Handle("sportybet", "sr:match:42")
    assert ev.handles["betway"] == Handle("betway", "42")
    assert ev.skipped["bet9ja"] == "not found"
    # SportPesa requested without cookie -> cookie-missing skip.
    assert ev.skipped["sportpesa"] == "cookie missing"


@pytest.mark.asyncio
async def test_resolve_isolates_per_book_exceptions():
    async def _boom(sport_id):
        raise RuntimeError("kaboom")

    clients = {
        "betway": _FakeClient(),
        "bet9ja": _FakeClient(build_prematch_event_map=_boom),
    }
    ev = await resolve_event(
        "sr:match:42", "soccer",
        books=("betway", "bet9ja"), clients=clients,
    )
    assert ev.handles["betway"] == Handle("betway", "42")
    assert ev.skipped["bet9ja"].startswith("error:")
    assert "kaboom" in ev.skipped["bet9ja"]
