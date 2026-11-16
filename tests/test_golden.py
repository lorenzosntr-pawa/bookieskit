"""Golden snapshot of parse_markets output for every captured fixture."""

import json
from pathlib import Path

import pytest

from scripts.regen_golden import GOLDEN_DIR, discover, snapshot

MANIFEST = GOLDEN_DIR / "manifest.json"


def _entries() -> list[tuple[str, str]]:
    if not MANIFEST.exists():
        return []
    return sorted(json.loads(MANIFEST.read_text(encoding="utf-8")).items())


@pytest.mark.parametrize(("key", "sport"), _entries())
def test_golden(key: str, sport: str) -> None:
    from scripts.regen_golden import FIXTURES_DIR, golden_path

    book, name = key.split("/", 1)
    expected = json.loads(golden_path(book, name).read_text(encoding="utf-8"))
    assert snapshot(FIXTURES_DIR / book / name, book, sport) == expected


def test_manifest_covers_all_parseable_fixtures() -> None:
    assert MANIFEST.exists(), "run python -X utf8 scripts/regen_golden.py"
    assert json.loads(MANIFEST.read_text(encoding="utf-8")) == discover()
    assert isinstance(Path(MANIFEST), Path)
