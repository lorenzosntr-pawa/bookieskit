"""Offline tests for scripts/capture_fixtures.py (fake clients, no network)."""

from __future__ import annotations

import asyncio
import json

from scripts.capture_fixtures import FETCH_METHOD, capture


class _Fake:
    def __init__(self, method: str, payload=None, exc: Exception | None = None):
        self.calls: list[tuple[str, dict]] = []
        self._payload = payload if payload is not None else {"ok": method}
        self._exc = exc
        setattr(self, method, self._fetch(method))

    def _fetch(self, method):
        async def fetch(**kwargs):
            self.calls.append((method, kwargs))
            if self._exc:
                raise self._exc
            return self._payload

        return fetch


def test_fetch_method_map():
    assert FETCH_METHOD["betika"] == "get_event_markets"
    assert FETCH_METHOD["betway"] == "get_event_markets_all"
    assert FETCH_METHOD["sportpesa"] == "get_event_markets"
    for book in ("betpawa", "sportybet", "bet9ja", "msport", "elephantbet"):
        assert FETCH_METHOD[book] == "get_event_detail"


def test_writes_files_for_given_books(tmp_path):
    clients = {
        "betpawa": _Fake("get_event_detail", {"é": 1}),
        "betway": _Fake("get_event_markets_all"),
    }
    res = asyncio.run(
        capture(clients, {"betpawa": "1", "betway": "2"}, "evt", tmp_path)
    )
    assert res == {"betpawa": "ok", "betway": "ok"}
    raw = (tmp_path / "betpawa" / "evt.json").read_text(encoding="utf-8")
    assert json.loads(raw) == {"é": 1}
    assert '\n "' in raw  # indent=1
    assert clients["betway"].calls == [("get_event_markets_all", {"event_id": "2"})]


def test_failure_does_not_stop_others(tmp_path):
    clients = {
        "betpawa": _Fake("get_event_detail", exc=RuntimeError("boom")),
        "betika": _Fake("get_event_markets"),
    }
    res = asyncio.run(
        capture(clients, {"betpawa": "1", "betika": "2"}, "evt", tmp_path)
    )
    assert res["betpawa"] == "RuntimeError: boom"
    assert res["betika"] == "ok"
    assert not (tmp_path / "betpawa" / "evt.json").exists()
    assert (tmp_path / "betika" / "evt.json").exists()


def test_nothing_written_without_id(tmp_path):
    clients = {"betpawa": _Fake("get_event_detail"), "msport": _Fake("get_event_detail")}
    res = asyncio.run(capture(clients, {"betpawa": "1"}, "evt", tmp_path))
    assert res == {"betpawa": "ok"}
    assert not (tmp_path / "msport").exists()
    assert clients["msport"].calls == []


def test_default_countries_are_supported_by_each_client():
    from scripts.capture_fixtures import CLIENTS, DEFAULT_COUNTRY

    assert set(DEFAULT_COUNTRY) == set(CLIENTS)
    for book, cc in DEFAULT_COUNTRY.items():
        assert cc in CLIENTS[book].DOMAINS, (book, cc)


def test_country_override_applied():
    import pytest

    from scripts.capture_fixtures import DEFAULT_COUNTRY, resolve_countries

    assert resolve_countries([]) == DEFAULT_COUNTRY
    out = resolve_countries(["betpawa=ke", "betika=ug"])
    assert out["betpawa"] == "ke"
    assert out["betika"] == "ug"
    assert out["bet9ja"] == "ng"
    with pytest.raises(ValueError):
        resolve_countries(["nope=ng"])
    with pytest.raises(ValueError):
        resolve_countries(["betpawa"])


def test_soccer_name_with_other_sport_prefix_warns():
    from scripts.capture_fixtures import fixture_name

    name, warning = fixture_name("basketball_x", "soccer")
    assert name == "basketball_x" and warning
    assert fixture_name("x", "tennis") == ("tennis_x", None)
    assert fixture_name("x", "soccer") == ("x", None)
