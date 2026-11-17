"""Offline mapping-coverage report -> docs/coverage.md.

Usage: python -X utf8 scripts/coverage_report.py

Per book x sport: distinct raw market types in the captured payloads vs how
many resolve to a registry mapping for that book and sport.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # allow `python scripts/coverage_report.py`

from bookieskit.markets.registry import MarketRegistry  # noqa: E402
from scripts.regen_golden import FIXTURES_DIR, GOLDEN_DIR  # noqa: E402

OUT = ROOT / "docs" / "coverage.md"
BOOKS = [
    "betpawa", "sportybet", "bet9ja", "betway",
    "msport", "sportpesa", "betika", "elephantbet",
]  # fmt: skip
FIELD = {
    "betpawa": "betpawa_id", "sportybet": "sportybet_id", "bet9ja": "bet9ja_key",
    "betway": "betway_id", "msport": "msport_id", "sportpesa": "sportpesa_id",
    "betika": "betika_id", "elephantbet": "elephantbet_id",
}  # fmt: skip


def raw_keys(book: str, d) -> set[str]:
    """Distinct raw market ids/names in one payload (per-book audit rules)."""
    out: set[str] = set()
    if book == "betpawa":
        for m in d.get("markets", []):
            out.add(str((m.get("marketType") or {}).get("id")))
    elif book in ("sportybet", "msport"):
        dd = d.get("data", d)
        for m in dd.get("markets", []):
            out.add(str(m.get("id")))
    elif book == "bet9ja":
        big = d.get("D")
        if not isinstance(big, dict):
            return out
        for key in big.get("O") or {}:
            kk = "S_" + key[6:] if key.startswith("LIVES_") else key
            out.add(kk.split("@")[0] if "@" in kk else kk.rsplit("_", 1)[0])
    elif book == "betway":
        for m in d.get("marketsInGroup", []):
            out.add(m.get("name"))
    elif book == "sportpesa":
        v = next(iter(d.values()), [])
        for m in v if isinstance(v, list) else []:
            out.add(str(m.get("id")))
    elif book == "betika":
        from bookieskit.bookmakers._betika_shape import betika_first_match

        for g in (betika_first_match(d) or {}).get("odds") or []:
            out.add(str(g.get("sub_type_id")))
    elif book == "elephantbet":
        for t in d.get("t") or []:
            for m in t.get("o") or []:
                out.add(str(m.get("id")))
    out.discard(None)
    return out


def _teams(book: str, d) -> tuple[str, str]:
    if book == "betway":
        se = d.get("sportEvent") or {}
        return se.get("homeTeam", ""), se.get("awayTeam", "")
    return "", ""


def _normalise(book: str, key: str, home: str, away: str) -> str:
    if book == "betway" and home and away:
        return key.replace(home, "[Home Team]").replace(away, "[Away Team]")
    return key


def _mapped_ids(reg: MarketRegistry, book: str, sport: str) -> set[str]:
    field = FIELD[book]
    return {
        getattr(m, field)
        for m in reg.list_markets()
        if m.sport == sport and getattr(m, field)
    }


def _collect(manifest: dict[str, str]):
    """(book, sport) -> (raw, mapped) sets; plus per-fixture sets."""
    reg = MarketRegistry()
    ids: dict[tuple[str, str], set[str]] = {}
    agg: dict[tuple[str, str], tuple[set, set]] = defaultdict(lambda: (set(), set()))
    per: dict[str, tuple[str, str, set, set]] = {}
    for rel, sport in manifest.items():
        book, name = rel.split("/", 1)
        d = json.loads((FIXTURES_DIR / book / name).read_text(encoding="utf-8"))
        home, away = _teams(book, d)
        known = ids.setdefault((book, sport), _mapped_ids(reg, book, sport))
        raw = {_normalise(book, k, home, away) for k in raw_keys(book, d)}
        mapped = {k for k in raw if k in known}
        agg[(book, sport)][0].update(raw)
        agg[(book, sport)][1].update(mapped)
        per[rel] = (book, sport, raw, mapped)
    return agg, per


def _row(book: str, sport: str, raw: set, mapped: set, **extra) -> dict:
    pct = round(100 * len(mapped) / len(raw), 1) if raw else 0.0
    return {
        "book": book, "sport": sport, "raw_types": len(raw),
        "mapped_types": len(mapped), "mapped_pct": pct, **extra,
    }  # fmt: skip


def coverage_rows(manifest: dict[str, str]) -> list[dict]:
    """One row per book x sport (distinct types unioned across fixtures)."""
    agg, _ = _collect(manifest)
    return [_row(b, s, raw, mapped) for (b, s), (raw, mapped) in sorted(agg.items())]


def fixture_rows(manifest: dict[str, str]) -> list[dict]:
    _, per = _collect(manifest)
    return [
        _row(b, s, raw, mapped, fixture=rel)
        for rel, (b, s, raw, mapped) in sorted(per.items())
    ]


def _matrix() -> list[str]:
    reg = MarketRegistry()
    lines = [
        "| canonical | " + " | ".join(BOOKS) + " |",
        "| --- | " + " | ".join("---" for _ in BOOKS) + " |",
    ]
    for m in sorted(reg.list_markets(), key=lambda m: m.canonical_id):
        cells = ["✓" if getattr(m, FIELD[b]) else "—" for b in BOOKS]
        lines.append(f"| {m.canonical_id} | " + " | ".join(cells) + " |")
    return lines


def render(rows: list[dict], fixtures: list[dict] | None = None) -> str:
    out = [
        "# bookieskit — Market Coverage",
        "",
        "Generated by `scripts/coverage_report.py` from the committed fixtures "
        "(offline). **raw types** = distinct market ids/names in the captured "
        "payloads (per-book rule); **mapped types** = those that resolve to a "
        "registry mapping for that book and sport (not the number of "
        "NormalizedMarkets after the completeness filter). Types are unioned "
        "across a book's fixtures for a sport.",
        "",
        "## Raw types mapped, per book x sport",
        "",
        "| book | sport | raw types | mapped types | mapped % |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for r in rows:
        out.append(
            f"| {r['book']} | {r['sport']} | {r['raw_types']} | "
            f"{r['mapped_types']} | {r['mapped_pct']} |"
        )
    if fixtures:
        out += [
            "",
            "## Per fixture",
            "",
            "| fixture | sport | raw types | mapped types | mapped % |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
        for r in fixtures:
            out.append(
                f"| {r['fixture']} | {r['sport']} | {r['raw_types']} | "
                f"{r['mapped_types']} | {r['mapped_pct']} |"
            )
    out += ["", "## Canonical x book matrix", ""] + _matrix() + [""]
    return "\n".join(out)


def main() -> None:
    manifest = json.loads((GOLDEN_DIR / "manifest.json").read_text(encoding="utf-8"))
    text = render(coverage_rows(manifest), fixture_rows(manifest))
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
