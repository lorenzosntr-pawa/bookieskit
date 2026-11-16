"""Offline tests for scripts/coverage_report.py (reads committed fixtures)."""

from __future__ import annotations

import json

from scripts.coverage_report import coverage_rows, render
from scripts.regen_golden import GOLDEN_DIR

MANIFEST = json.loads((GOLDEN_DIR / "manifest.json").read_text(encoding="utf-8"))


def test_rows_for_betpawa_prematch():
    rows = coverage_rows({"betpawa/prematch.json": "soccer"})
    (row,) = [r for r in rows if r["book"] == "betpawa" and r["sport"] == "soccer"]
    assert row["raw_types"] > row["mapped_types"] > 0
    assert row["mapped_pct"] == round(100 * row["mapped_types"] / row["raw_types"], 1)


def test_render_has_one_row_per_book_sport():
    rows = coverage_rows(MANIFEST)
    pairs = [(r["book"], r["sport"]) for r in rows]
    assert len(pairs) == len(set(pairs)) > 8
    text = render(rows)
    for book, sport in pairs:
        assert f"| {book} | {sport} |" in text
    assert "| canonical |" in text  # the canonical x book matrix is kept
