"""Regenerate golden snapshots of parse_markets output for every fixture.

Usage: python -X utf8 scripts/regen_golden.py
"""

from __future__ import annotations

import json
from pathlib import Path

from bookieskit.markets import parse_markets

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "event_info"
GOLDEN_DIR = ROOT / "tests" / "golden"

_GAP = "KNOWN GAP: embedded-markets shape not parsed - Step 3 SportPesa adapter"

# Fixtures deliberately left out of the snapshot ("<book>/<file>" -> reason).
EXCLUDED: dict[str, str] = {
    "bet9ja/dc_1x2_1up_catalogue.json": "catalogue payload: O is empty, no odds",
    "bet9ja/live.json": "all 69 outcomes at odds 1.0 placeholder",
    "betpawa/live.json": "all 239 prices suspended at capture",
    "betway/live.json": "event-header capture only (sportEvent), no markets",
    "msport/live.json": "markets list empty at capture (match finished)",
    "sportybet/live.json": "markets list empty at capture (match finished)",
    "betway/prematch.json": "event-header capture only (sportEvent), no markets",
    "elephantbet/live.json": "event-index list (not a detail payload)",
    "elephantbet/events.json": "event-index list (not a detail payload)",
    "sportpesa/basketball.json": "empty list",
    "sportpesa/games_upcoming.json": _GAP,
    "sportpesa/live.json": _GAP,
    "sportpesa/prematch.json": _GAP,
    "sportpesa/sports_live.json": "sports index (top-level 'sports'), not an event",
}


def sport_for(name: str) -> str:
    if name.startswith("basketball"):
        return "basketball"
    if name.startswith("tennis"):
        return "tennis"
    return "soccer"


def golden_path(book: str, name: str) -> Path:
    return GOLDEN_DIR / f"{book}__{name}"


def _outcome(o) -> dict:
    return {
        "canonical_name": o.canonical_name,
        "platform_name": o.platform_name,
        "odds": o.odds,
        "true_probability": o.true_probability,
        "void_probability": o.void_probability,
    }


def _parse(fixture_path: Path, platform: str, sport: str):
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    try:
        return parse_markets(data, platform, sport=sport, probability="with_void")
    except (AttributeError, KeyError, TypeError):
        return []  # not an event payload


def snapshot(fixture_path: Path, platform: str, sport: str) -> list[dict]:
    markets = _parse(fixture_path, platform, sport)
    out = []
    for m in sorted(markets, key=lambda m: m.canonical_id):
        lines = None
        if m.lines is not None:
            lines = {
                str(k): [_outcome(o) for o in m.lines[k]]
                for k in sorted(m.lines, key=float)
            }
        out.append(
            {
                "canonical_id": m.canonical_id,
                "name": m.name,
                "outcomes": [_outcome(o) for o in m.outcomes],
                "lines": lines,
            }
        )
    return out


def discover() -> dict[str, str]:
    manifest: dict[str, str] = {}
    for book_dir in sorted(p for p in FIXTURES_DIR.iterdir() if p.is_dir()):
        for f in sorted(book_dir.glob("*.json")):
            sport = sport_for(f.name)
            key = f"{book_dir.name}/{f.name}"
            if _parse(f, book_dir.name, sport):
                if key in EXCLUDED:
                    raise SystemExit(f"stale EXCLUDED entry (now parses): {key}")
                manifest[key] = sport
            elif key not in EXCLUDED:
                raise SystemExit(f"{key} parses to 0 markets and is not in EXCLUDED")
    return manifest


def _write(path: Path, obj) -> None:
    text = json.dumps(obj, indent=1, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for old in GOLDEN_DIR.glob("*.json"):
        old.unlink()
    manifest = discover()
    _write(GOLDEN_DIR / "manifest.json", manifest)
    for key, sport in manifest.items():
        book, name = key.split("/", 1)
        snap = snapshot(FIXTURES_DIR / book / name, book, sport)
        _write(golden_path(book, name), snap)
    print(f"wrote {len(manifest)} snapshots")


if __name__ == "__main__":
    main()
