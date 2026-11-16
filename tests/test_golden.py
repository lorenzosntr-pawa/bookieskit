"""Golden snapshot of parse_markets output for every captured fixture."""

import json

import pytest

from scripts.regen_golden import (
    EXCLUDED,
    FIXTURES_DIR,
    GOLDEN_DIR,
    discover,
    golden_path,
    snapshot,
)

MANIFEST = GOLDEN_DIR / "manifest.json"


def _entries() -> list[tuple[str, str]]:
    if not MANIFEST.exists():
        return []
    return sorted(json.loads(MANIFEST.read_text(encoding="utf-8")).items())


@pytest.mark.parametrize(("key", "sport"), _entries())
def test_golden(key: str, sport: str) -> None:
    book, name = key.split("/", 1)
    expected = json.loads(golden_path(book, name).read_text(encoding="utf-8"))
    assert snapshot(FIXTURES_DIR / book / name, book, sport) == expected


def test_manifest_covers_all_parseable_fixtures() -> None:
    assert MANIFEST.exists(), "run python -X utf8 scripts/regen_golden.py"
    assert json.loads(MANIFEST.read_text(encoding="utf-8")) == discover()


def test_every_fixture_is_manifested_or_excluded() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    on_disk = {
        f"{f.parent.name}/{f.name}" for f in FIXTURES_DIR.glob("*/*.json")
    }
    assert on_disk == set(manifest) | set(EXCLUDED)
    assert not set(manifest) & set(EXCLUDED)


def test_discover_fails_on_unlisted_zero_market_fixture(monkeypatch) -> None:
    key = next(iter(EXCLUDED))
    monkeypatch.delitem(EXCLUDED, key)
    with pytest.raises(SystemExit, match="not in EXCLUDED"):
        discover()


def test_discover_fails_on_stale_excluded_entry(monkeypatch) -> None:
    key = next(iter(json.loads(MANIFEST.read_text(encoding="utf-8"))))
    monkeypatch.setitem(EXCLUDED, key, "stale")
    with pytest.raises(SystemExit, match="stale EXCLUDED"):
        discover()
