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
async def test_betpawa_seed_resolver():
    """resolve_event with betpawa_seed=True extracts sr_numeric and participants."""
    # Minimal BetPawa event-detail payload: the extractor walks widgets[] for
    # SPORTRADAR id and detail["participants"] for home/away.
    betpawa_detail = {
        "id": "33289995",
        "name": "Team A - Team B",
        "widgets": [
            {"id": "68995116", "type": "SPORTRADAR", "retention": "PREMATCH"},
        ],
        "participants": [
            {"id": "1", "name": "Team A", "position": 1},
            {"id": "2", "name": "Team B", "position": 2},
        ],
    }

    async def _get_event_detail(event_id):
        return betpawa_detail

    bp_client = _FakeClient(get_event_detail=_get_event_detail)

    ev = await resolve_event(
        "33289995",
        "soccer",
        books=("betpawa",),
        betpawa_seed=True,
        clients={"betpawa": bp_client},
    )

    assert ev.sr_numeric == "68995116"
    assert ev.home == "Team A"
    assert ev.away == "Team B"
    # betpawa is always skipped in the per-book loop; handles will be empty.
    assert ev.handles == {}


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
