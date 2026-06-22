# Release Automation (`bookieskit.devtools.release`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested, offline-verifiable, agent-runnable release command to `bookieskit`. One command (`python -m bookieskit.devtools release`) infers the SemVer bump from conventional commits since the last `v*` tag (overridable with `--bump`), bumps both version files (`pyproject.toml` + `__init__.py`) atomically, promotes the CHANGELOG's `[Unreleased]` section to a dated version section, commits `chore(release): vX.Y.Z`, and creates an annotated `vX.Y.Z` tag — locally by default, pushing only with `--push`. A sibling `release-notes <version>` command extracts a version's CHANGELOG body (consumed by the new tag-triggered `release.yml` to build the GitHub Release body). This is the **Ship** step of the agent loop (*Signal → Work → Gate → Ship*); sub-project 4 of 5 in the project-workflow track.

**Architecture:** One new focused module `src/bookieskit/devtools/release.py` — pure text/version functions (`infer_bump`, `next_version`, `bump_pyproject`, `bump_init`, `promote_changelog`, `extract_section`) plus a thin orchestrator (`ReleasePlan` dataclass, `run_release`) over an injectable `GitRunner` (the only side-effect surface). Two CLI subcommands (`release`, `release-notes`) are added to the existing `src/bookieskit/devtools/cli.py`, wired exactly like the `canary` subcommand (own subparsers, injected runner seams, an early-return branch in `run` before the resolver fan-out). One one-time edit to `CHANGELOG.md` inserts an empty `## [Unreleased]` section. A new `.github/workflows/release.yml` builds wheel/sdist + creates a GitHub Release on a pushed `v*` tag. The orchestrator (sub-project 5) later runs `release --bump <x> --push --json` after CI is green and turns the JSON `ReleasePlan` + the tag-triggered workflow into the release URL it announces in Slack.

**Tech Stack:** Python 3.11+ stdlib only for new logic (`tomllib`, `re`, `subprocess`, `dataclasses`, `datetime`, `argparse`, `pathlib`); runtime dep `httpx` only. Tests: `pytest` (no asyncio needed — `release` is synchronous), with `tmp_path` temp local git repos (offline; local git is not network) and an injected `GitRunner` fake. No new runtime or dev dependencies.

## Global Constraints

- Python 3.11+ **stdlib only** for new logic (`tomllib`, `re`, `subprocess`, `dataclasses`, `datetime`, `argparse`, `pathlib`); runtime dep is **`httpx` only**; do **NOT** add dependencies (no new runtime or dev deps).
- New code lives in `src/bookieskit/devtools/release.py`; invoked as `python -m bookieskit.devtools release` and `python -m bookieskit.devtools release-notes` — **ADD both subcommands** to the existing `cli.py`.
- Ruff config: `select = ["E","F","I"]`, `line-length = 88`, `target-version = "py311"`. **`src/` must stay 100% ruff-clean.** `tests/**` ignores `E501`.
- ALL new tests are **offline**, under `tests/devtools/test_release.py`. The pure text/version functions are tested directly. `run_release` is tested against a **TEMP LOCAL git repo** created in the test (`tmp_path` + `subprocess` `git init`/`add`/`commit`/`tag` — local git is offline, no network). `--push` is **NOT** exercised against a real remote: this plan uses an **injected `GitRunner` fake** to assert push calls (chosen over a bare local remote and used consistently). No live network in any test.
- Local commands use `.venv/Scripts/python.exe -m pytest ...` / `-m ruff ...` (Windows); CI uses bare `pytest` / `ruff`.
- Agent-runnable: `release` / `release-notes` support `--json`, are non-interactive, and have meaningful exit codes: dirty tree → **1**; no bump inferable and no `--bump` → **1**; missing/empty `[Unreleased]` → **1**; `release-notes` section absent → **1**; else **0**.
- Karpathy principle: smallest surgical change; one focused single-responsibility module; **no speculative extension points** (no PyPI publish, no historical-tag backfill).
- The version-sync invariant must hold: `bookieskit.__version__ == pyproject [project].version` (asserted by `tests/test_sportpesa.py::test_version_matches_pyproject`). After every bump both files move together; that test must still pass.
- Suggested sequence (each task ends green and is independently testable): (1) pure version/file-bump functions → (2) `promote_changelog` + `extract_section` → (3) one-time CHANGELOG `[Unreleased]` insert → (4) `run_release` orchestrator (+ `GitRunner`) with temp-repo tests → (5) `release` + `release-notes` CLI subcommands → (6) `release.yml` workflow + YAML validate.

---

### Task 1: `release.py` — pure version functions (`infer_bump`, `next_version`, `bump_pyproject`, `bump_init`)

**Files:**
- Create: `src/bookieskit/devtools/release.py`
- Create: `tests/devtools/test_release.py`

**Interfaces:**
- Consumes: nothing (pure stdlib `re`).
- Produces: `infer_bump(subjects, current_major) -> str | None`, `next_version(current, bump) -> str`, `bump_pyproject(text, new) -> str`, `bump_init(text, new) -> str`. Consumed by `run_release` (Task 4) and the CLI (Task 5).

Design notes (encoded from the spec's "Pure functions" section; verified against source strings):
- `infer_bump`: breaking (a `!` before the colon, e.g. `feat!:` / `fix(x)!:`, **or** a `BREAKING CHANGE` token in the subject) → `"major"`, **EXCEPT** while `current_major == 0` where breaking → `"minor"` (SemVer 0.x rule). Else any `feat` → `"minor"`. Else any `fix` → `"patch"`. Else `None` (no release-worthy commit). Scan ALL subjects and take the highest precedence found.
- `next_version`: `("0.15.1", "minor") -> "0.16.0"`; `+patch -> "0.15.2"`; `+major -> "1.0.0"`. **Resets lower components** (minor resets patch; major resets minor+patch).
- `bump_pyproject`: replaces the **anchored** `version = "..."` line. CRITICAL: the ruff config has `target-version = "py311"` — the regex MUST be anchored at line-start (`^version = "..."` with `re.MULTILINE`) with **no prefix allowed**, so it matches `version = "0.15.1"` under `[project]` but **never** `target-version = "py311"`. Idempotent on the value; raises `ValueError` if the line is absent or matches more than once.
- `bump_init`: replaces the anchored `__version__ = "..."` line. Raises `ValueError` if absent.
- The exact current strings (verified): `version = "0.15.1"` (pyproject line 7), `__version__ = "0.15.1"` (`__init__.py` line 23).

- [ ] **Step 1: Write the failing test**

Create `tests/devtools/test_release.py`:

```python
import pytest

from bookieskit.devtools.release import (
    bump_init,
    bump_pyproject,
    infer_bump,
    next_version,
)


def test_infer_bump_feat_is_minor():
    assert infer_bump(["feat: add market", "docs: tidy"], 0) == "minor"


def test_infer_bump_fix_is_patch():
    assert infer_bump(["fix: guard empty id", "chore: bump"], 1) == "patch"


def test_infer_bump_breaking_bang_is_major_when_major_ge_1():
    assert infer_bump(["feat!: drop old api"], 1) == "major"
    assert infer_bump(["fix(parser)!: rename id"], 2) == "major"


def test_infer_bump_breaking_token_is_major_when_major_ge_1():
    assert infer_bump(["feat: x\n\nBREAKING CHANGE: y"], 1) == "major"


def test_infer_bump_breaking_is_minor_while_major_zero():
    # SemVer 0.x: breaking -> minor (not major) while major == 0.
    assert infer_bump(["feat!: drop old api"], 0) == "minor"
    assert infer_bump(["fix!: rename"], 0) == "minor"


def test_infer_bump_highest_precedence_wins():
    assert infer_bump(["fix: a", "feat: b"], 1) == "minor"
    assert infer_bump(["feat: a", "fix!: b"], 2) == "major"


def test_infer_bump_none_when_no_release_worthy_commit():
    assert infer_bump(["docs: a", "chore: b", "ci: c"], 1) is None
    assert infer_bump([], 1) is None


def test_next_version_patch_minor_major_reset_lower():
    assert next_version("0.15.1", "patch") == "0.15.2"
    assert next_version("0.15.1", "minor") == "0.16.0"
    assert next_version("0.15.1", "major") == "1.0.0"
    assert next_version("1.2.3", "minor") == "1.3.0"


def test_next_version_rejects_bad_bump():
    with pytest.raises(ValueError):
        next_version("0.15.1", "nope")


def test_bump_pyproject_replaces_only_the_project_version_line():
    text = (
        '[project]\n'
        'name = "bookieskit"\n'
        'version = "0.15.1"\n'
        '\n'
        '[tool.ruff]\n'
        'target-version = "py311"\n'
    )
    out = bump_pyproject(text, "0.16.0")
    assert 'version = "0.16.0"' in out
    # target-version is NEVER touched.
    assert 'target-version = "py311"' in out
    assert 'version = "0.15.1"' not in out


def test_bump_pyproject_raises_when_absent():
    with pytest.raises(ValueError):
        bump_pyproject('[project]\nname = "x"\n', "0.16.0")


def test_bump_init_replaces_dunder_version():
    text = '"""doc"""\n\n__version__ = "0.15.1"\n__all__ = []\n'
    out = bump_init(text, "0.16.0")
    assert '__version__ = "0.16.0"' in out
    assert '__version__ = "0.15.1"' not in out


def test_bump_init_raises_when_absent():
    with pytest.raises(ValueError):
        bump_init('"""doc"""\n', "0.16.0")
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_release.py -q`
Expected: collection/import error — `ModuleNotFoundError: No module named 'bookieskit.devtools.release'`.

- [ ] **Step 3: Implement the pure version functions**

Create `src/bookieskit/devtools/release.py`:

```python
"""Release automation: infer the SemVer bump from conventional commits, bump
the two version files + promote the CHANGELOG, then commit and tag.

Pure text/version functions (offline-tested directly) plus a thin orchestrator
(``run_release``) over an injectable ``GitRunner`` — git is the only side
effect. Invoked as ``python -m bookieskit.devtools release`` (and
``release-notes``). The ReleasePlan JSON is the stable contract the
orchestrator (sub-project 5) turns into a release announcement.
"""

import re

_BUMPS = ("major", "minor", "patch")

# Anchored at line-start with NO prefix so it matches the [project]
# `version = "..."` line but NEVER `target-version = "py311"`.
_PYPROJECT_VERSION_RE = re.compile(r'^version = "[^"]*"', re.MULTILINE)
_INIT_VERSION_RE = re.compile(r'^__version__ = "[^"]*"', re.MULTILINE)


def infer_bump(subjects: list[str], current_major: int) -> str | None:
    """Conventional-commit subjects -> "major"|"minor"|"patch"|None.

    Breaking (a "!" before the colon, e.g. "feat!:"/"fix(x)!:", or a
    "BREAKING CHANGE" token) -> "major", EXCEPT while ``current_major == 0``
    where breaking -> "minor" (SemVer 0.x). Else any "feat" -> "minor". Else
    any "fix" -> "patch". Else None (no release-worthy commit). The highest
    precedence found across all subjects wins.
    """
    saw_feat = False
    saw_fix = False
    for subject in subjects:
        head = subject.split("\n", 1)[0]
        type_token = head.split(":", 1)[0]  # e.g. "feat!", "fix(parser)!"
        breaking = type_token.endswith("!") or "BREAKING CHANGE" in subject
        if breaking:
            return "minor" if current_major == 0 else "major"
        base = type_token.split("(", 1)[0]
        if base == "feat":
            saw_feat = True
        elif base == "fix":
            saw_fix = True
    if saw_feat:
        return "minor"
    if saw_fix:
        return "patch"
    return None


def next_version(current: str, bump: str) -> str:
    """ "0.15.1"+"minor" -> "0.16.0"; "+patch" -> "0.15.2"; "+major" ->
    "1.0.0". Resets all lower components."""
    if bump not in _BUMPS:
        raise ValueError(f"unknown bump {bump!r} (expected one of {_BUMPS})")
    major, minor, patch = (int(p) for p in current.split("."))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _replace_one(pattern: re.Pattern[str], text: str, repl: str, what: str) -> str:
    matches = pattern.findall(text)
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {what} line, found {len(matches)}"
        )
    return pattern.sub(repl, text, count=1)


def bump_pyproject(text: str, new: str) -> str:
    """Replace the anchored ``version = "..."`` line under [project].

    Raises ValueError if the line is absent or ambiguous. Never matches
    ``target-version = "py311"`` (the regex is anchored with no prefix).
    """
    return _replace_one(
        _PYPROJECT_VERSION_RE, text, f'version = "{new}"', "project version"
    )


def bump_init(text: str, new: str) -> str:
    """Replace the anchored ``__version__ = "..."`` line. Raises if absent."""
    return _replace_one(
        _INIT_VERSION_RE, text, f'__version__ = "{new}"', "__version__"
    )
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_release.py -q`
Expected: `13 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/release.py tests/devtools/test_release.py
git commit -m "feat(release): pure version functions (infer_bump, next_version, bump files)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `release.py` — CHANGELOG functions (`promote_changelog`, `extract_section`)

**Files:**
- Modify: `src/bookieskit/devtools/release.py` (add `promote_changelog` + `extract_section`)
- Modify: `tests/devtools/test_release.py` (add CHANGELOG-function tests)

**Interfaces:**
- Consumes: nothing new (pure stdlib `re`).
- Produces: `promote_changelog(text, version, date) -> str`, `extract_section(text, version) -> str`. Consumed by `run_release` (Task 4) and the `release-notes` CLI (Task 5).

Design notes (encoded from the spec; headers verified against `CHANGELOG.md`):
- CHANGELOG headers are `## [x.y.z] - YYYY-MM-DD`; the top is `# Changelog` + an intro paragraph; the first versioned section today is `## [0.15.0] - 2026-05-22`.
- `promote_changelog`: rename `## [Unreleased]` → `## [<version>] - <date>` and insert a **fresh empty** `## [Unreleased]` header above it (so future work lands under a new Unreleased). **Raises `ValueError`** if there is no `## [Unreleased]` section OR the Unreleased section has no entries (refuse to cut an empty release). "Has entries" = there is non-whitespace, non-blank content between the `## [Unreleased]` header and the next `## [` header.
- `extract_section`: return the body between `## [<version>]` (any suffix, e.g. ` - 2026-05-22`) and the next `## [` header, **stripped**. Raises `ValueError` if the version section is not found. (Used by `release-notes` and, via `run_release`, to capture the just-promoted section.)

- [ ] **Step 1: Add the failing tests**

Append to `tests/devtools/test_release.py`:

```python
from bookieskit.devtools.release import (  # noqa: E402
    extract_section,
    promote_changelog,
)

_CHANGELOG = (
    "# Changelog\n"
    "\n"
    "Intro paragraph.\n"
    "\n"
    "## [Unreleased]\n"
    "\n"
    "### Added\n"
    "- New market foo.\n"
    "\n"
    "## [0.15.0] - 2026-05-22\n"
    "\n"
    "### Added\n"
    "- Old stuff.\n"
)


def test_promote_changelog_renames_unreleased_and_inserts_fresh():
    out = promote_changelog(_CHANGELOG, "0.16.0", "2026-06-23")
    assert "## [0.16.0] - 2026-06-23" in out
    # A fresh empty Unreleased sits above the promoted section.
    assert "## [Unreleased]" in out
    assert out.index("## [Unreleased]") < out.index("## [0.16.0] - 2026-06-23")
    # The promoted section keeps its curated body.
    assert "- New market foo." in out
    # The old 0.15.0 section is untouched and still below.
    assert out.index("## [0.16.0] - 2026-06-23") < out.index(
        "## [0.15.0] - 2026-05-22"
    )


def test_promote_changelog_raises_when_no_unreleased():
    text = "# Changelog\n\nIntro.\n\n## [0.15.0] - 2026-05-22\n\n- x.\n"
    with pytest.raises(ValueError):
        promote_changelog(text, "0.16.0", "2026-06-23")


def test_promote_changelog_raises_when_unreleased_empty():
    text = (
        "# Changelog\n\nIntro.\n\n## [Unreleased]\n\n"
        "## [0.15.0] - 2026-05-22\n\n- x.\n"
    )
    with pytest.raises(ValueError):
        promote_changelog(text, "0.16.0", "2026-06-23")


def test_extract_section_returns_stripped_body():
    body = extract_section(_CHANGELOG, "0.15.0")
    assert body == "### Added\n- Old stuff."


def test_extract_section_middle_section_stops_at_next_header():
    out = promote_changelog(_CHANGELOG, "0.16.0", "2026-06-23")
    body = extract_section(out, "0.16.0")
    assert body == "### Added\n- New market foo."


def test_extract_section_raises_when_absent():
    with pytest.raises(ValueError):
        extract_section(_CHANGELOG, "9.9.9")
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_release.py -q`
Expected: FAIL — `ImportError: cannot import name 'promote_changelog'`.

- [ ] **Step 3: Implement the CHANGELOG functions**

In `src/bookieskit/devtools/release.py`, add after `bump_init`:

```python
_UNRELEASED_HEADER = "## [Unreleased]"


def promote_changelog(text: str, version: str, date: str) -> str:
    """Rename ``## [Unreleased]`` -> ``## [<version>] - <date>`` and insert a
    fresh empty ``## [Unreleased]`` above it.

    Raises ValueError if there is no ``## [Unreleased]`` section or it has no
    entries (refuse an empty release).
    """
    match = re.search(r"^## \[Unreleased\][^\n]*\n", text, re.MULTILINE)
    if match is None:
        raise ValueError("no '## [Unreleased]' section in CHANGELOG")
    # Body = everything from after the Unreleased header to the next '## ['.
    rest = text[match.end():]
    next_header = re.search(r"^## \[", rest, re.MULTILINE)
    body = rest[: next_header.start()] if next_header else rest
    if not body.strip():
        raise ValueError("'## [Unreleased]' section is empty — refusing release")
    promoted = f"{_UNRELEASED_HEADER}\n\n## [{version}] - {date}\n"
    return text[: match.start()] + promoted + text[match.end():]


def extract_section(text: str, version: str) -> str:
    """Return the stripped body of the ``## [<version>] ...`` section.

    Body is the text between that header and the next ``## [`` header. Raises
    ValueError if the version section is not found.
    """
    header = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n", text, re.MULTILINE
    )
    if header is None:
        raise ValueError(f"no section for version {version!r} in CHANGELOG")
    rest = text[header.end():]
    next_header = re.search(r"^## \[", rest, re.MULTILINE)
    body = rest[: next_header.start()] if next_header else rest
    return body.strip()
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_release.py -q`
Expected: `19 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/release.py tests/devtools/test_release.py
git commit -m "feat(release): promote_changelog + extract_section

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: One-time CHANGELOG `[Unreleased]` insert

**Files:**
- Modify: `CHANGELOG.md` (insert an empty `## [Unreleased]` section)

**Interfaces:**
- Consumes / Produces: no code. This is a one-time content edit so `promote_changelog` has an `[Unreleased]` section to promote going forward. No new test; the existing version-sync test and full suite must still pass afterwards.

Design notes (verified against `CHANGELOG.md`): the file currently has `# Changelog`, an intro paragraph, then `## [0.15.0] - 2026-05-22` as the first versioned section — there is **NO** `## [Unreleased]` section. Insert an empty one between the intro paragraph and `## [0.15.0]`.

- [ ] **Step 1: Insert the empty `[Unreleased]` section**

In `CHANGELOG.md`, change the region immediately before the `## [0.15.0]` header from:

```markdown
All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.15.0] - 2026-05-22
```

to:

```markdown
All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.15.0] - 2026-05-22
```

(Only `## [Unreleased]` + a trailing blank line are added; the intro paragraph and the `0.15.0` section are unchanged.)

- [ ] **Step 2: Confirm the version-sync test + full suite still pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sportpesa.py::test_version_matches_pyproject -q`
Expected: `1 passed`.

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: full suite green, 0 failed.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): add empty [Unreleased] section for release automation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `run_release` orchestrator + `GitRunner` (temp-repo tests)

**Files:**
- Modify: `src/bookieskit/devtools/release.py` (add `GitRunner`, `ReleasePlan`, `run_release`)
- Modify: `tests/devtools/test_release.py` (add orchestrator tests against a temp local git repo + an injected `GitRunner` fake for `--push`)

**Interfaces:**
- Consumes: the pure functions (Tasks 1–2); `tomllib` (read current version); `subprocess` (git); `pathlib.Path`; `datetime.date`.
- Produces: `GitRunner` (thin injectable git wrapper), `ReleasePlan` dataclass, `run_release(*, bump=None, dry_run=False, push=False, root=None, today=None, git=None) -> ReleasePlan`. Consumed by the CLI (Task 5).

Design notes (encoded from the spec's Orchestrator section):
- `ReleasePlan` fields exactly: `current`, `new`, `bump`, `tag` (`"v<new>"`), `changelog_section` (the promoted section body), `pushed` (bool).
- `GitRunner` is a thin wrapper over `subprocess` git calls, all relative to a `root` repo dir:
  - `status_porcelain() -> str` (working-tree dirty check via `git status --porcelain`),
  - `last_tag() -> str | None` (most recent `v*` tag, e.g. `git describe --tags --match "v*" --abbrev=0`; `None` when no tag),
  - `subjects_since(tag) -> list[str]` (commit subjects since the tag; full range when `tag` is None — `git log --format=%s [<tag>..HEAD]`),
  - `add(paths)`, `commit(message)`, `tag(name, message)` (annotated: `git tag -a <name> -m <message>`),
  - `push_branch()` + `push_tag(name)` (push current branch, then the tag).
  Each method runs `subprocess.run([...], cwd=self.root, capture_output=True, text=True, check=True)`; a non-zero git exit raises `subprocess.CalledProcessError` (propagates with git stderr).
- `run_release` steps (exactly as spec):
  1. **Preconditions**: `git status --porcelain` must be empty → else raise `ReleaseError("working tree not clean")`. Read `current` from `pyproject.toml` via `tomllib` (`[project].version`).
  2. **Bump**: `bump or infer_bump(git.subjects_since(git.last_tag()), int(current.split(".")[0]))`; if still None → raise `ReleaseError("no release-worthy commits; pass --bump")`. `new = next_version(current, bump)`.
  3. **Edit files** (skipped under `dry_run`): apply `bump_pyproject`, `bump_init`, `promote_changelog(..., today or date.today().isoformat())` to the three files on disk; `changelog_section = extract_section(new_changelog_text, new)`. Under `dry_run`, compute `new` and `changelog_section` from the in-memory promotion **without writing** (so `--dry-run --json` still shows the section).
  4. **Commit + tag** (skipped under `dry_run`): `git.add([pyproject, init, changelog])`; `git.commit(f"chore(release): v{new}")`; `git.tag(f"v{new}", f"v{new}")`.
  5. **Push** (only if `push and not dry_run`): `git.push_branch()` then `git.push_tag(f"v{new}")`; set `pushed = True`.
  6. Return `ReleasePlan(current, new, bump, f"v{new}", changelog_section, pushed)`.
- `ReleaseError(Exception)` is a small module-level exception so the CLI maps it to exit 1 (Task 5). The `bump_*` / `extract_section` `ValueError`s also propagate to a non-zero CLI exit.
- Default `root` is the repo root discovered from the module location (`Path(__file__).resolve().parents[3]`); tests always pass an explicit `root=tmp_path`.

- [ ] **Step 1: Add the failing tests**

Append to `tests/devtools/test_release.py`:

```python
import subprocess  # noqa: E402
from dataclasses import asdict  # noqa: E402
from pathlib import Path  # noqa: E402

from bookieskit.devtools.release import (  # noqa: E402
    GitRunner,
    ReleaseError,
    ReleasePlan,
    run_release,
)

_PYPROJECT = (
    "[project]\n"
    'name = "bookieskit"\n'
    'version = "0.15.1"\n'
    "\n"
    "[tool.ruff]\n"
    'target-version = "py311"\n'
)
_INIT = '"""doc"""\n\n__version__ = "0.15.1"\n'
_CL = (
    "# Changelog\n\nIntro.\n\n## [Unreleased]\n\n"
    "### Added\n- New thing.\n\n## [0.15.0] - 2026-05-22\n\n- Old.\n"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _seed_repo(root: Path, *, subject: str = "feat: add thing") -> None:
    """Create a temp local git repo with the three release files committed."""
    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "T")
    (root / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    (root / "src" / "bookieskit").mkdir(parents=True)
    (root / "src" / "bookieskit" / "__init__.py").write_text(
        _INIT, encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text(_CL, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "chore: seed")
    _git(root, "tag", "-a", "v0.15.1", "-m", "v0.15.1")
    # A release-worthy commit AFTER the tag (so infer_bump sees it).
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", subject)


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def test_run_release_bumps_files_promotes_changelog_commits_and_tags(tmp_path):
    _seed_repo(tmp_path, subject="feat: add thing")
    plan = run_release(root=tmp_path, today="2026-06-23")

    assert plan.current == "0.15.1"
    assert plan.new == "0.16.0"  # feat -> minor
    assert plan.bump == "minor"
    assert plan.tag == "v0.16.0"
    assert plan.pushed is False
    assert "New thing." in plan.changelog_section

    assert 'version = "0.16.0"' in _read(tmp_path, "pyproject.toml")
    assert 'target-version = "py311"' in _read(tmp_path, "pyproject.toml")
    assert '__version__ = "0.16.0"' in _read(
        tmp_path, "src/bookieskit/__init__.py"
    )
    cl = _read(tmp_path, "CHANGELOG.md")
    assert "## [0.16.0] - 2026-06-23" in cl
    assert "## [Unreleased]" in cl

    # A chore(release) commit and a v0.16.0 tag now exist.
    log = subprocess.run(
        ["git", "log", "--format=%s", "-1"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert log == "chore(release): v0.16.0"
    tags = subprocess.run(
        ["git", "tag"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout.split()
    assert "v0.16.0" in tags


def test_run_release_explicit_bump_overrides_inference(tmp_path):
    _seed_repo(tmp_path, subject="fix: small")
    plan = run_release(root=tmp_path, bump="major", today="2026-06-23")
    assert plan.new == "1.0.0"
    assert plan.bump == "major"


def test_run_release_dry_run_mutates_nothing(tmp_path):
    _seed_repo(tmp_path, subject="feat: add thing")
    before_pyproject = _read(tmp_path, "pyproject.toml")
    before_tags = subprocess.run(
        ["git", "tag"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout
    plan = run_release(root=tmp_path, dry_run=True, today="2026-06-23")

    # Plan still reports the computed version + section.
    assert plan.new == "0.16.0"
    assert "New thing." in plan.changelog_section
    assert plan.pushed is False
    # Files and tags untouched.
    assert _read(tmp_path, "pyproject.toml") == before_pyproject
    after_tags = subprocess.run(
        ["git", "tag"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout
    assert after_tags == before_tags


def test_run_release_raises_on_dirty_tree(tmp_path):
    _seed_repo(tmp_path, subject="feat: add thing")
    (tmp_path / "dirty.txt").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "dirty.txt")
    with pytest.raises(ReleaseError):
        run_release(root=tmp_path, today="2026-06-23")


def test_run_release_raises_when_no_bump_inferable(tmp_path):
    _seed_repo(tmp_path, subject="docs: tidy only")
    with pytest.raises(ReleaseError):
        run_release(root=tmp_path, today="2026-06-23")


def test_run_release_raises_on_empty_unreleased(tmp_path):
    _seed_repo(tmp_path, subject="feat: add thing")
    # Wipe the Unreleased body -> promote_changelog must refuse.
    cl = (
        "# Changelog\n\nIntro.\n\n## [Unreleased]\n\n"
        "## [0.15.0] - 2026-05-22\n\n- Old.\n"
    )
    (tmp_path / "CHANGELOG.md").write_text(cl, encoding="utf-8")
    _git(tmp_path, "commit", "-am", "docs: blank unreleased")
    with pytest.raises(ValueError):
        run_release(root=tmp_path, bump="patch", today="2026-06-23")


class _FakeGit:
    """Injected GitRunner fake: clean tree, one feat since tag, records calls."""

    def __init__(self):
        self.pushed_branch = False
        self.pushed_tags: list[str] = []
        self.committed: list[str] = []
        self.tagged: list[str] = []

    def status_porcelain(self):
        return ""

    def last_tag(self):
        return "v0.15.1"

    def subjects_since(self, tag):
        return ["feat: add thing"]

    def add(self, paths):
        pass

    def commit(self, message):
        self.committed.append(message)

    def tag(self, name, message):
        self.tagged.append(name)

    def push_branch(self):
        self.pushed_branch = True

    def push_tag(self, name):
        self.pushed_tags.append(name)


def test_run_release_push_invokes_git_push_via_injected_runner(tmp_path):
    # Files must exist for the on-disk edits; git side effects go to the fake.
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    (tmp_path / "src" / "bookieskit").mkdir(parents=True)
    (tmp_path / "src" / "bookieskit" / "__init__.py").write_text(
        _INIT, encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(_CL, encoding="utf-8")
    fake = _FakeGit()
    plan = run_release(
        root=tmp_path, push=True, today="2026-06-23", git=fake
    )
    assert plan.pushed is True
    assert fake.committed == ["chore(release): v0.16.0"]
    assert fake.tagged == ["v0.16.0"]
    assert fake.pushed_branch is True
    assert fake.pushed_tags == ["v0.16.0"]


def test_run_release_no_push_leaves_pushed_false_via_injected_runner(tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    (tmp_path / "src" / "bookieskit").mkdir(parents=True)
    (tmp_path / "src" / "bookieskit" / "__init__.py").write_text(
        _INIT, encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(_CL, encoding="utf-8")
    fake = _FakeGit()
    plan = run_release(root=tmp_path, today="2026-06-23", git=fake)
    assert plan.pushed is False
    assert fake.pushed_branch is False
    assert fake.pushed_tags == []
    # ReleasePlan serializes cleanly for --json.
    d = asdict(plan)
    assert d["tag"] == "v0.16.0"


def test_gitrunner_status_porcelain_on_temp_repo(tmp_path):
    _seed_repo(tmp_path, subject="feat: add thing")
    git = GitRunner(tmp_path)
    assert git.status_porcelain() == ""  # clean after seed
    (tmp_path / "x.txt").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "x.txt")
    assert git.status_porcelain() != ""  # now dirty
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_release.py -q`
Expected: FAIL — `ImportError: cannot import name 'GitRunner'`.

- [ ] **Step 3: Implement `GitRunner`, `ReleasePlan`, `run_release`**

In `src/bookieskit/devtools/release.py`, add to the imports at the top (after `import re`):

```python
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
```

Then add at the end of the module:

```python
class ReleaseError(Exception):
    """A release precondition failed (dirty tree, no inferable bump, ...)."""


class GitRunner:
    """Thin injectable wrapper over the git subprocess calls run_release needs.

    Every method runs git in ``root`` with ``check=True`` so a non-zero git
    exit raises CalledProcessError (its stderr propagates). Tests inject a fake
    instead of touching a real remote.
    """

    def __init__(self, root: Path):
        self.root = root

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def status_porcelain(self) -> str:
        return self._run("status", "--porcelain")

    def last_tag(self) -> str | None:
        try:
            out = self._run(
                "describe", "--tags", "--match", "v*", "--abbrev=0"
            ).strip()
        except subprocess.CalledProcessError:
            return None  # no matching tag yet
        return out or None

    def subjects_since(self, tag: str | None) -> list[str]:
        rev = f"{tag}..HEAD" if tag else "HEAD"
        out = self._run("log", "--format=%s", rev)
        return [line for line in out.splitlines() if line.strip()]

    def add(self, paths: list[str]) -> None:
        self._run("add", *paths)

    def commit(self, message: str) -> None:
        self._run("commit", "-m", message)

    def tag(self, name: str, message: str) -> None:
        self._run("tag", "-a", name, "-m", message)

    def push_branch(self) -> None:
        self._run("push")

    def push_tag(self, name: str) -> None:
        self._run("push", "origin", name)


@dataclass
class ReleasePlan:
    """The result of a release run (serialized for --json)."""

    current: str
    new: str
    bump: str
    tag: str  # "v<new>"
    changelog_section: str  # the promoted section body
    pushed: bool


def _repo_root() -> Path:
    # src/bookieskit/devtools/release.py -> repo root is parents[3].
    return Path(__file__).resolve().parents[3]


def run_release(
    *,
    bump: str | None = None,
    dry_run: bool = False,
    push: bool = False,
    root: Path | None = None,
    today: str | None = None,
    git: "GitRunner | None" = None,
) -> ReleasePlan:
    """Bump both version files, promote the CHANGELOG, commit, and tag.

    Commits + tags locally; pushes only when ``push`` and not ``dry_run``.
    Raises ReleaseError on a dirty tree or when no bump can be inferred and
    none was supplied; ValueError when a target string is malformed.
    """
    if root is None:
        root = _repo_root()
    if git is None:
        git = GitRunner(root)

    # 1. Preconditions.
    if git.status_porcelain().strip():
        raise ReleaseError("working tree not clean — commit/stash first")
    pyproject_path = root / "pyproject.toml"
    init_path = root / "src" / "bookieskit" / "__init__.py"
    changelog_path = root / "CHANGELOG.md"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    current = tomllib.loads(pyproject_text)["project"]["version"]

    # 2. Bump (explicit overrides inference).
    if bump is None:
        bump = infer_bump(
            git.subjects_since(git.last_tag()), int(current.split(".")[0])
        )
    if bump is None:
        raise ReleaseError("no release-worthy commits since last tag; pass --bump")
    new = next_version(current, bump)
    iso_date = today or date.today().isoformat()

    # 3. Edit files (compute always; write only when not dry_run).
    new_pyproject = bump_pyproject(pyproject_text, new)
    init_text = init_path.read_text(encoding="utf-8")
    new_init = bump_init(init_text, new)
    changelog_text = changelog_path.read_text(encoding="utf-8")
    new_changelog = promote_changelog(changelog_text, new, iso_date)
    changelog_section = extract_section(new_changelog, new)

    pushed = False
    if not dry_run:
        pyproject_path.write_text(new_pyproject, encoding="utf-8")
        init_path.write_text(new_init, encoding="utf-8")
        changelog_path.write_text(new_changelog, encoding="utf-8")

        # 4. Commit + annotated tag.
        tag = f"v{new}"
        git.add([str(pyproject_path), str(init_path), str(changelog_path)])
        git.commit(f"chore(release): {tag}")
        git.tag(tag, tag)

        # 5. Push (only when requested).
        if push:
            git.push_branch()
            git.push_tag(tag)
            pushed = True

    return ReleasePlan(
        current=current,
        new=new,
        bump=bump,
        tag=f"v{new}",
        changelog_section=changelog_section,
        pushed=pushed,
    )
```

(Note: under `dry_run` the on-disk files are never written and no git mutation runs, but `new` + `changelog_section` are computed from the in-memory promotion so `--dry-run --json` still shows the full plan. The injected-`GitRunner` push tests bypass the temp-repo seed because the fake provides a clean tree + commit history; the on-disk files still exist so the file edits succeed.)

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_release.py -q`
Expected: `29 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/devtools/release.py tests/devtools/test_release.py
git commit -m "feat(release): run_release orchestrator + GitRunner (temp-repo tested)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `release` + `release-notes` CLI subcommands on `cli.py`

**Files:**
- Modify: `src/bookieskit/devtools/cli.py` (add the two subparsers + early-return branches + injected seams)
- Modify: `tests/devtools/test_release.py` (add CLI tests)

**Interfaces:**
- Consumes: `run_release` + `ReleasePlan` + `ReleaseError` + `extract_section` (Tasks 1–4); the existing `build_parser`/`run`/`_emit` scaffolding.
- Produces: `python -m bookieskit.devtools release [--bump {major,minor,patch}] [--dry-run] [--json] [--push]` and `python -m bookieskit.devtools release-notes <version> [--json]`. Exit code **1** on precondition failure (dirty tree, no inferable bump without `--bump`, missing/empty `[Unreleased]`) or `release-notes` section absent; else **0**.

Design notes — mirror the `canary` wiring (own subparsers, injected runner seam, early-return before the resolver fan-out):
- `release` and `release-notes` do **not** take the shared positional `seed` (`_common`), so each is its own subparser. `release-notes` takes a positional `version`.
- `run(args, *, resolver=..., runner=..., clients=...)` already early-returns for `canary`. Add two parallel injected seams: `releaser: Callable[..., ReleasePlan] = run_release` and `notes: Callable[[str, str], str] = extract_section` (the latter wrapped so the CLI reads `CHANGELOG.md` from disk and passes its text). Both branches early-return BEFORE `books = _books_arg(args)`.
- `release` (sync) runs `releaser(...)`; on `ReleaseError`/`ValueError` it prints the message and returns 1. `--json` emits `asdict(ReleasePlan)`. Human mode prints `current → new`, tag, pushed?, and the changelog section.
- `release-notes` reads `CHANGELOG.md` from the repo root and calls `notes(text, version)`; on `ValueError` (section absent) prints the message and returns 1. Default (non-`--json`) prints the raw section body (this is what `release.yml` redirects into `notes.md`); `--json` emits `{"version": ..., "notes": ...}`.
- Add `from bookieskit.devtools.release import (ReleaseError, ReleasePlan, extract_section, run_release)` and a `from pathlib import Path` import; declare a `Releaser = Callable[..., ReleasePlan]` type alias near the existing `Resolver`/`CanaryRunner` aliases.

- [ ] **Step 1: Add the failing tests**

Append to `tests/devtools/test_release.py`:

```python
import json  # noqa: E402

from bookieskit.devtools import cli  # noqa: E402


def test_build_parser_has_release_subcommand():
    args = cli.build_parser().parse_args(["release"])
    assert args.cmd == "release"
    assert args.bump is None
    assert args.dry_run is False
    assert args.push is False


def test_build_parser_release_accepts_flags():
    args = cli.build_parser().parse_args(
        ["release", "--bump", "minor", "--dry-run", "--push", "--json"]
    )
    assert args.bump == "minor"
    assert args.dry_run is True
    assert args.push is True
    assert args.as_json is True


def test_build_parser_has_release_notes_subcommand():
    args = cli.build_parser().parse_args(["release-notes", "0.15.0"])
    assert args.cmd == "release-notes"
    assert args.version == "0.15.0"


def _fake_releaser_ok(**kwargs):
    return ReleasePlan(
        current="0.15.1", new="0.16.0", bump="minor", tag="v0.16.0",
        changelog_section="### Added\n- New.", pushed=False,
    )


def _fake_releaser_dirty(**kwargs):
    raise ReleaseError("working tree not clean")


async def test_release_json_output_and_exit_zero(capsys):
    args = cli.build_parser().parse_args(["release", "--json"])
    code = await cli.run(args, releaser=_fake_releaser_ok)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["new"] == "0.16.0"
    assert out["tag"] == "v0.16.0"
    assert out["pushed"] is False


async def test_release_exit_one_on_release_error(capsys):
    args = cli.build_parser().parse_args(["release"])
    code = await cli.run(args, releaser=_fake_releaser_dirty)
    assert code == 1


async def test_release_notes_prints_section_and_exits_zero(capsys, tmp_path):
    # The CLI reads CHANGELOG.md from the repo root; inject root via a fake
    # notes function so the test stays offline and path-independent.
    def _notes(version):
        assert version == "0.15.0"
        return "### Added\n- Old stuff."

    args = cli.build_parser().parse_args(["release-notes", "0.15.0"])
    code = await cli.run(args, notes=_notes)
    assert code == 0
    assert "Old stuff." in capsys.readouterr().out


async def test_release_notes_exit_one_when_section_absent(capsys):
    def _notes(version):
        raise ValueError("no section")

    args = cli.build_parser().parse_args(["release-notes", "9.9.9"])
    code = await cli.run(args, notes=_notes)
    assert code == 1
```

(Note: the `notes` seam is a one-arg `Callable[[str], str]` taking just the version — the CLI's default binds the repo `CHANGELOG.md` read inside the default; tests inject a fake that returns the body directly, keeping them offline and path-independent.)

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_release.py -q`
Expected: FAIL — the `release` subparser does not exist (`SystemExit: invalid choice: 'release'`) and `run(..., releaser=...)` is an unexpected keyword argument.

- [ ] **Step 3: Wire the subcommands into `cli.py`**

In `src/bookieskit/devtools/cli.py`, add to the imports:

```python
from pathlib import Path

from bookieskit.devtools.release import (
    ReleaseError,
    ReleasePlan,
    extract_section,
    run_release,
)
```

and add a type alias near the existing `Resolver` / `CanaryRunner` lines:

```python
Releaser = Callable[..., ReleasePlan]
NotesFn = Callable[[str], str]
```

Add a module-level default notes reader (binds the repo `CHANGELOG.md`) after the type aliases:

```python
def _default_notes(version: str) -> str:
    """Read CHANGELOG.md from the repo root and extract a version's section."""
    root = Path(__file__).resolve().parents[3]
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    return extract_section(text, version)
```

In `build_parser`, after the `p_canary` block (before `return parser`), add the two subparsers (NOT via `_common`):

```python
    p_release = sub.add_parser("release")
    p_release.add_argument(
        "--bump", choices=["major", "minor", "patch"], default=None
    )
    p_release.add_argument("--dry-run", action="store_true", dest="dry_run")
    p_release.add_argument("--push", action="store_true")
    p_release.add_argument("--json", action="store_true", dest="as_json")

    p_notes = sub.add_parser("release-notes")
    p_notes.add_argument("version")
    p_notes.add_argument("--json", action="store_true", dest="as_json")
```

In `run`, add the two seams to the signature (alongside `runner`):

```python
async def run(
    args: argparse.Namespace,
    *,
    resolver: Resolver = resolve_event,
    runner: CanaryRunner = run_canary,
    releaser: Releaser = run_release,
    notes: NotesFn = _default_notes,
    clients: dict[str, Any] | None = None,
) -> int:
```

and add the two branches immediately after the existing `if args.cmd == "canary":` block (still before `books = _books_arg(args)`):

```python
    if args.cmd == "release":
        try:
            plan = releaser(
                bump=args.bump, dry_run=args.dry_run, push=args.push
            )
        except (ReleaseError, ValueError) as exc:
            print(f"release failed: {exc}")
            return 1
        _emit(
            asdict(plan),
            args.as_json,
            [f"release {plan.current} -> {plan.new} "
             f"tag={plan.tag} pushed={plan.pushed}",
             plan.changelog_section],
        )
        return 0

    if args.cmd == "release-notes":
        try:
            body = notes(args.version)
        except ValueError as exc:
            print(f"release-notes failed: {exc}")
            return 1
        _emit(
            {"version": args.version, "notes": body},
            args.as_json,
            [body],
        )
        return 0
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_release.py -q`
Expected: `37 passed`.

- [ ] **Step 5: Confirm the existing CLI tests still pass (no regression)**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools/test_cli.py tests/devtools/test_canary.py -q`
Expected: all pass, 0 failed.

- [ ] **Step 6: Smoke-test the entrypoint `--help` + a read-only `release-notes` (non-interactive, offline)**

Run: `.venv/Scripts/python.exe -m bookieskit.devtools --help`
Expected: usage text whose subcommand list now includes `release` and `release-notes` (i.e. `{resolve,discover,capture,verify,canary,release,release-notes}`); exit 0.

Run: `.venv/Scripts/python.exe -m bookieskit.devtools release --help`
Expected: usage text showing `--bump`, `--dry-run`, `--push`, `--json`; exit 0.

Run: `.venv/Scripts/python.exe -m bookieskit.devtools release-notes 0.15.0`
Expected: prints the body of the `## [0.15.0]` CHANGELOG section (read-only, safe); exit 0.

(Do NOT run `release --dry-run` against the real repo as a success check here: at this point the working tree is dirty with this task's uncommitted edits — so the clean-tree precondition fails — and the real CHANGELOG's `[Unreleased]` is empty, so `promote_changelog` would refuse. Both correctly cause exit 1; the dry-run *success* path is covered by `test_run_release_dry_run_mutates_nothing` against a temp repo with a populated `[Unreleased]`. The real-repo `release` only produces a plan once there are `[Unreleased]` entries and a clean tree — i.e. on `main` in the agent loop.)

- [ ] **Step 7: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/devtools tests/devtools`
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add src/bookieskit/devtools/cli.py tests/devtools/test_release.py
git commit -m "feat(release): release + release-notes CLI subcommands (--json + exit codes)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `.github/workflows/release.yml` + YAML validation

**Files:**
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: the working `python -m bookieskit.devtools release-notes` (Tasks 1–5); `python -m build`; `gh release create`.
- Produces: the tag-triggered GitHub Release. On a pushed `v*` tag it builds wheel + sdist, extracts the changelog body via `release-notes`, and creates a GitHub Release (artifacts attached) using the built-in token. Owner-verified once after merge with a real tag push.

Design notes (from the spec; uses `ci.yml`/`canary.yml` as structural templates):
- Triggers: `on: push: tags: ["v*"]` — **only** on a pushed `v*` tag, NOT push-to-branch / pull_request / schedule.
- `permissions: contents: write` (required for `gh release create`).
- One `release` job: `ubuntu-latest`, Python `"3.13"`, `pip install build`, `pip install -e .`, `python -m build`, `python -m bookieskit.devtools release-notes "${GITHUB_REF_NAME#v}" > notes.md`, then `gh release create "$GITHUB_REF_NAME" --title "$GITHUB_REF_NAME" --notes-file notes.md dist/*` with `env: GH_TOKEN: ${{ github.token }}`.

- [ ] **Step 1: Create `.github/workflows/release.yml`**

```yaml
name: Release

on:
  push:
    tags: ["v*"]

permissions:
  contents: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install build
      - run: pip install -e .
      - run: python -m build
      - run: python -m bookieskit.devtools release-notes "${GITHUB_REF_NAME#v}" > notes.md
      - run: gh release create "$GITHUB_REF_NAME" --title "$GITHUB_REF_NAME" --notes-file notes.md dist/*
        env:
          GH_TOKEN: ${{ github.token }}
```

- [ ] **Step 2: Validate the YAML parses (ephemeral PyYAML — NOT added to project deps)**

IMPORTANT: PyYAML parses the YAML `on:` key as the boolean `True` (the "Norway problem"), so the triggers live under `d[True]`, not `d["on"]`. Run exactly this:

```bash
.venv/Scripts/python.exe -m pip install -q pyyaml && \
.venv/Scripts/python.exe -c "import yaml; d=yaml.safe_load(open('.github/workflows/release.yml')); on=d[True]; assert 'push' in on and on['push']['tags']==['v*']; assert 'pull_request' not in on and 'schedule' not in on; assert d['permissions']['contents']=='write'; j=d['jobs']['release']; assert j['runs-on']=='ubuntu-latest'; steps=j['steps']; assert any('release-notes' in (s.get('run') or '') for s in steps); assert any('gh release create' in (s.get('run') or '') for s in steps); print('YAML OK')"
```
Expected: `YAML OK`

- [ ] **Step 3: Run the full devtools suite + lint the whole tree (final green gate)**

Run: `.venv/Scripts/python.exe -m pytest tests/devtools -q`
Expected: all pass, 0 failed (includes the full `tests/devtools/test_release.py`).

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: full suite green, 0 failed (the version-sync test in `tests/test_sportpesa.py` still passes — both files remained in sync after the Task 3 edit; no bump was committed).

Run: `.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add tag-triggered release workflow (build + gh release create)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 5: (Deferred — owner-triggered) Verify the live path on GitHub**

Once the branch is merged and on a remote with Actions enabled, the owner runs one real release end-to-end (`release --bump patch --push`, or pushes a `v*` tag) and confirms `release.yml` builds wheel + sdist and creates a GitHub Release whose body is the changelog section. Do not block plan completion on this step; record it as the post-remote follow-up.

---

## Notes for the executor

- Run commands with the project venv: `.venv/Scripts/python.exe -m <tool>` (Windows). On CI (Ubuntu) the workflows use plain `python -m ...` after `pip install`.
- `release` reaches git (a side effect) but never the network until `--push`; every test uses a `tmp_path` temp local repo (offline) or an injected `GitRunner` fake. Never run a real `release` (without `--dry-run`) against the live repo during the plan — it would commit + tag the working tree. `release --dry-run --json` is safe (writes nothing).
- The version-sync invariant (`bookieskit.__version__ == pyproject [project].version`, asserted in `tests/test_sportpesa.py`) holds throughout: the Task 3 CHANGELOG edit does not touch either version file, and `run_release` always bumps both together. No version bump is committed during plan execution.
- Karpathy: one focused module (`release.py`), smallest surgical CLI edit (two subparsers + two early-return branches + two injected seams), no speculative extension points — no PyPI publish, no historical-tag backfill (both explicitly out of scope per the spec's Non-goals).

## Controller self-review notes (verified against source; address during execution)

- `pyproject.toml` line 7 is exactly `version = "0.15.1"` under `[project]`; `[tool.ruff]` has `target-version = "py311"` (line 31). The anchored `^version = "..."` regex with `re.MULTILINE` matches the former and never the latter — this is the load-bearing reason `bump_pyproject` is anchored with no prefix (Task 1 test `test_bump_pyproject_replaces_only_the_project_version_line` proves it).
- `src/bookieskit/__init__.py` line 23 is exactly `__version__ = "0.15.1"`.
- `CHANGELOG.md` top is `# Changelog` + intro paragraph + `## [0.15.0] - 2026-05-22` (no `[Unreleased]` yet); Task 3 inserts the empty `[Unreleased]`. Headers are `## [x.y.z] - YYYY-MM-DD`.
- `tests/test_sportpesa.py::test_version_matches_pyproject` reads `pyproject [project].version` via `tomllib` and asserts equality with `bookieskit.__version__` — kept green because no version file is mutated during the plan.
- `cli.py` already early-returns for `args.cmd == "canary"` before `books = _books_arg(args)`, with an injected `runner` seam and `--json` via `_emit(asdict(...), args.as_json, [...])`. The `release`/`release-notes` branches mirror this exactly (own subparsers, injected `releaser`/`notes` seams, early-return). `_emit` already serializes dataclasses-as-dicts via `json.dumps(obj, default=str)`.
- `release` is synchronous (no asyncio); it is invoked from the async `run` directly (no `await`), so the injected `releaser` fake is a plain sync callable. `run` itself stays `async` because the other subcommands are async — the `release`/`release-notes` branches simply do not `await`.
- `.github/workflows/ci.yml` and `canary.yml` confirm the structural template (checkout@v4, setup-python@v5 with `python-version: "3.13"`); `release.yml` follows it minus the pip cache (build job installs `build` + the package fresh).
- **Minor (controller-flagged, non-blocking):** `GitRunner.subjects_since` uses `git log --format=%s` (subject lines only), so a `BREAKING CHANGE:` token in a commit *body/footer* will NOT be auto-detected — only `!`-marked breaking (`feat!:`/`fix(x)!:`) and an explicit `--bump major` trigger a major (or, under 0.x, minor). This is acceptable: the repo doesn't use BREAKING-CHANGE footers, and the `--bump` override always wins. If footer detection is wanted later, switch `subjects_since` to `--format=%B` with NUL record separation (`%x00`) and split on `\0`; `infer_bump` already scans the whole string for the token. `test_infer_bump_breaking_token_is_major_when_major_ge_1` exercises the function directly (it passes a multi-line subject), so the capability is proven even though the default git format doesn't feed it footers.
