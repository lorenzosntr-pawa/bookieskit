"""Docs-sync gate: keep docs in step with every library change (#41).

Pure classification shared by the ``check-docs-sync`` CLI subcommand and the
CI ``docs-sync`` job. The rule: if a change set touches ``src/bookieskit/**``,
at least one changed path must be a documentation surface (``docs/**``,
``README.md`` or ``CHANGELOG.md``) — unless the PR carries the ``docs:n/a``
escape hatch (a token in the PR body or a label) for a genuinely internal-only
change. The gate fails closed: any library change with no docs and no escape
hatch is reported as out-of-sync.
"""

import re
import subprocess
from dataclasses import dataclass, field

SRC_PREFIX = "src/bookieskit/"
DOC_PREFIX = "docs/"
ROOT_DOCS = ("README.md", "CHANGELOG.md")
DOCS_NA_TOKEN = "docs:n/a"

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass
class DocsSyncResult:
    """Outcome of a docs-sync check over a set of changed files."""

    ok: bool
    reason: str
    src_changed: list[str] = field(default_factory=list)
    doc_changed: list[str] = field(default_factory=list)
    docs_na: bool = False


def _norm(path: str) -> str:
    """Normalise a path for comparison (trim, forward slashes)."""
    return path.strip().replace("\\", "/")


def is_src(path: str) -> bool:
    """True when ``path`` is a library source file under src/bookieskit/."""
    return _norm(path).startswith(SRC_PREFIX)


def is_doc(path: str) -> bool:
    """True when ``path`` is a tracked documentation surface."""
    p = _norm(path)
    return p.startswith(DOC_PREFIX) or p in ROOT_DOCS


def docs_na_from(pr_body: str | None = None, labels=()) -> bool:
    """Detect the ``docs:n/a`` escape hatch from a PR body or its labels.

    The hatch is set by a ``docs:n/a`` label, or by a line in the PR body that
    — outside any HTML comment — reads exactly ``docs:n/a`` (case-insensitive,
    surrounding whitespace ignored). The bare-line rule is deliberate: an
    unanchored substring match would be satisfied by the explanatory prose in
    the PR template (which names the token inline and inside an HTML comment),
    silently exempting every PR. So prose mentions and commented hints never
    trip it — only a line the author deliberately adds.
    """
    if any(_norm(label).lower() == DOCS_NA_TOKEN for label in labels):
        return True
    if not pr_body:
        return False
    visible = _HTML_COMMENT_RE.sub("", pr_body)
    return any(
        line.strip().lower() == DOCS_NA_TOKEN for line in visible.splitlines()
    )


def check_docs_sync(changed_files, *, docs_na: bool = False) -> DocsSyncResult:
    """Classify a change set against the docs-sync rule.

    Returns an OK result when the change touches no library source, when docs
    were updated alongside the source, or when the ``docs:n/a`` hatch is set;
    otherwise a failing result naming the remedy.
    """
    files = [_norm(f) for f in changed_files if f and f.strip()]
    src = [f for f in files if is_src(f)]
    docs = [f for f in files if is_doc(f)]
    if not src:
        return DocsSyncResult(
            True,
            "no library (src/bookieskit) changes — docs-sync gate not applicable",
            src, docs, docs_na,
        )
    if docs_na:
        return DocsSyncResult(
            True,
            "docs:n/a escape hatch present — library change exempt from docs sync",
            src, docs, docs_na,
        )
    if docs:
        return DocsSyncResult(
            True,
            f"docs updated alongside the library change ({len(docs)} doc file(s))",
            src, docs, docs_na,
        )
    return DocsSyncResult(
        False,
        "library files under src/bookieskit/ changed but no docs were updated. "
        "Update docs/**, README.md or CHANGELOG.md in this PR, or add the "
        "`docs:n/a` marker (PR body token or label) for an internal-only change.",
        src, docs, docs_na,
    )


def changed_files_from_git(base: str) -> list[str]:
    """Files changed between ``base`` and HEAD (three-dot, like the CI gate)."""
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [line for line in out.splitlines() if line.strip()]
