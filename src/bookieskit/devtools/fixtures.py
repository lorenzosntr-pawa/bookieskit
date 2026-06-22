"""Write raw per-platform fixtures under tests/fixtures/event_info/."""

import json
from pathlib import Path
from typing import Any

# src/bookieskit/devtools/fixtures.py -> repo root is parents[3].
FIXTURES_ROOT = (
    Path(__file__).resolve().parents[3]
    / "tests" / "fixtures" / "event_info"
)


def capture(
    payload: Any,
    platform: str,
    name: str,
    *,
    root: Path | None = None,
) -> Path:
    """Write ``payload`` to ``<root>/<platform>/<name>.json`` and return it.

    Args:
        payload: Raw JSON-serializable markets payload.
        platform: Bookmaker key (subdirectory name).
        name: Fixture base name (no extension).
        root: Fixtures root (defaults to the repo's event_info dir).

    Returns:
        The written file path.
    """
    base = root if root is not None else FIXTURES_ROOT
    out_dir = base / platform
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
