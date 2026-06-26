"""Tests for the docs-sync gate's pure classification logic."""

from pathlib import Path

from bookieskit.devtools.docssync import (
    DOCS_NA_TOKEN,
    check_docs_sync,
    docs_na_from,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_src_change_without_docs_fails():
    r = check_docs_sync(["src/bookieskit/markets/registry.py"])
    assert r.ok is False
    assert "docs" in r.reason.lower()
    assert r.src_changed == ["src/bookieskit/markets/registry.py"]
    assert r.doc_changed == []


def test_src_change_with_docs_passes():
    r = check_docs_sync(
        ["src/bookieskit/markets/registry.py", "docs/markets.md"]
    )
    assert r.ok is True
    assert r.doc_changed == ["docs/markets.md"]


def test_src_change_with_readme_passes():
    r = check_docs_sync(["src/bookieskit/foo.py", "README.md"])
    assert r.ok is True


def test_src_change_with_changelog_passes():
    r = check_docs_sync(["src/bookieskit/foo.py", "CHANGELOG.md"])
    assert r.ok is True


def test_no_src_change_passes_trivially():
    r = check_docs_sync(["tests/test_x.py", ".github/workflows/ci.yml"])
    assert r.ok is True
    assert r.src_changed == []


def test_docs_na_exempts_src_only_change():
    r = check_docs_sync(["src/bookieskit/foo.py"], docs_na=True)
    assert r.ok is True
    assert r.docs_na is True


def test_windows_paths_normalised():
    r = check_docs_sync(["src\\bookieskit\\foo.py", "docs\\x.md"])
    assert r.ok is True
    assert r.src_changed == ["src/bookieskit/foo.py"]


def test_blank_entries_ignored():
    r = check_docs_sync(["", "  ", "src/bookieskit/foo.py"])
    assert r.ok is False


def test_docs_na_from_body_bare_line():
    assert docs_na_from("some notes\ndocs:n/a\nmore", []) is True
    assert docs_na_from("DOCS:N/A", []) is True  # own line, case-insensitive
    assert docs_na_from("  docs:n/a  ", []) is True  # trimmed
    assert docs_na_from(None, []) is False
    assert docs_na_from("nothing here", []) is False


def test_docs_na_inline_prose_does_not_trip():
    # An unanchored substring match would wrongly exempt these.
    assert docs_na_from("add the docs:n/a marker to bypass", []) is False
    assert docs_na_from("DOCS:N/A please", []) is False


def test_docs_na_inside_html_comment_does_not_trip():
    assert docs_na_from("<!-- docs:n/a hint -->", []) is False
    assert docs_na_from("text\n<!--\ndocs:n/a\n-->\nmore", []) is False


def test_docs_na_from_label():
    assert docs_na_from("", ["docs:n/a"]) is True
    assert docs_na_from("", ["Docs:N/A"]) is True
    assert docs_na_from("", ["bug", "enhancement"]) is False


def test_default_pr_template_does_not_trip_the_hatch():
    """Regression: the committed PR template must NOT auto-exempt every PR.

    github.event.pull_request.body defaults to the rendered template, so if its
    prose/commented hint satisfied the hatch the gate would never fire.
    """
    template = (
        _REPO_ROOT / ".github" / "pull_request_template.md"
    ).read_text(encoding="utf-8")
    assert docs_na_from(template, []) is False


def test_docs_na_token_constant():
    assert DOCS_NA_TOKEN == "docs:n/a"
