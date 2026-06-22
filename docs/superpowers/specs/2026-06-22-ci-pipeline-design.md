# CI Pipeline — Design

**Date:** 2026-06-22
**Status:** Approved (pending written-spec review)
**Sub-project:** 1 of 5 in the "project workflow" track (CI → market-add harness → live canary tests → release automation → orchestration + Slack cockpit). See the umbrella vision: `2026-06-22-agent-company-north-star.md`.

## Problem

`bookieskit` has 30 test files (566 tests, fully offline via `respx`) and a `ruff` lint
config, but **no CI**. `.github/` is empty. Tests and lint run only when a developer
remembers to run them locally, so nothing automatically guards a merge or catches
regressions. A concrete symptom already exists on the current branch:
`tests/test_sportpesa.py::test_top_level_version_bumped` fails because it hardcodes
`assert bookieskit.__version__ == "0.15.0"` while the package is now `0.15.1` — exactly
the class of breakage CI is meant to catch at PR time.

## Goals

- Run `pytest` and `ruff check` automatically on every push to `main` and every pull request.
- Validate across the supported Python range (3.11, 3.12, 3.13).
- Make the suite green by de-brittling the version assertion test.
- Keep it fast and low-maintenance (pip caching, concurrency cancellation).

## Non-goals

- Live/network tests against real bookmaker endpoints (that is sub-project 3, "live canary tests" — a *scheduled*, non-PR-gated job).
- Release/publish automation, tagging, or building artifacts (sub-project 4).
- Coverage reporting, formatting enforcement, type-checking, or multi-OS testing.
- Changing how `__version__` is sourced at runtime (it stays a literal in `__init__.py`).

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Python matrix | 3.11, 3.12, 3.13 | 3.11 is the declared minimum (`requires-python>=3.11`); 3.13 is the dev version; jobs run in parallel so wall-clock cost is flat. |
| OS | `ubuntu-latest` only | Pure-Python + httpx; platform-independent. Fastest/cheapest. |
| Version test fix | Assert `__version__` against `pyproject.toml` (parsed with stdlib `tomllib`) | `pyproject.toml` is the real single source of truth and is install-independent. NOTE: `importlib.metadata.version()` was rejected because editable-install metadata goes stale (locally it reports `0.13.0` while pyproject/`__init__` are `0.15.1`), so a metadata-based test fails locally until reinstall. `tomllib` (stdlib, 3.11+) reads the repo file directly — passes locally and in CI, and still catches `__init__`↔pyproject drift. |
| Lint scope | `ruff check .`, with `scripts/` excluded and `E501` ignored under `tests/**` | `scripts/` holds disposable probe scripts being replaced by the market-add harness (sub-project 2) — gating CI on them is wasted effort (YAGNI). `tests/**` fixture literals legitimately exceed 88 cols. `src/` stays fully clean. |

## Design

### 1. Workflow file: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: pyproject.toml
      - run: pip install -e ".[dev]"
      - run: ruff check .

  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
          cache-dependency-path: pyproject.toml
      - run: pip install -e ".[dev]"
      - run: pytest -q
```

Notes:
- `lint` runs once on 3.13 (lint results are Python-version-independent for this ruleset).
- `fail-fast: false` so one failing Python version still reports the others.
- `concurrency` cancels an in-flight run when a new commit lands on the same ref.
- `cache: pip` + `cache-dependency-path: pyproject.toml` reuses the wheel cache between runs.

### 2. De-brittle the version test

In `tests/test_sportpesa.py`, replace:

```python
def test_top_level_version_bumped():
    import bookieskit
    assert bookieskit.__version__ == "0.15.0"
```

with an assertion against `pyproject.toml` (the real single source of truth, read directly
so it never depends on a fresh install):

```python
def test_version_matches_pyproject():
    import tomllib
    from pathlib import Path

    import bookieskit

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert bookieskit.__version__ == data["project"]["version"]
```

`tomllib` is stdlib in Python 3.11+ (matches `requires-python`). The test is renamed to
reflect what it verifies. It stays in `tests/test_sportpesa.py` to keep the diff minimal
(it is arguably misplaced, but relocating it is out of scope).

### 3. Lint debt (make `ruff check .` green)

`ruff check .` currently reports 38 pre-existing errors (this was the implicit assumption
the original spec got wrong). Resolution:

- **`pyproject.toml` ruff config** — exclude disposable scripts and ignore long fixture
  lines in tests:
  ```toml
  [tool.ruff]
  target-version = "py311"
  line-length = 88
  extend-exclude = ["scripts"]

  [tool.ruff.lint]
  select = ["E", "F", "I"]

  [tool.ruff.lint.per-file-ignores]
  "tests/**" = ["E501"]
  ```
- **`src/`** — fix the only 2 violations, both over-long inline comments in
  `src/bookieskit/markets/builtin_mappings.py` (lines 650 and 690): reduce the alignment
  padding before the `#` so the line fits in 88 cols. `src/` must stay 100% clean.
- **`tests/`** — auto-fix the 6 import-sort (`I001`) issues with `ruff check tests --fix`;
  the 7 `E501` fixture lines are covered by the per-file ignore above.

## Success criteria

**Locally verifiable now:**
- `.github/workflows/ci.yml` exists and parses as valid YAML.
- `pytest -q` is green locally (0 failures; the prior version-test failure resolved).
- `ruff check .` reports **no errors**.

**Deferred — requires a GitHub remote (none exists yet):**
- On a pushed branch / opened PR, both `lint` and `test` jobs run and **pass**, with three
  `test` jobs (3.11/3.12/3.13) plus one `lint` job.
- A deliberately introduced lint error or test failure turns the corresponding job red
  (one-time sanity check, then reverted).

This repo is currently local-only (no `origin`). The workflow file ships and is locally
validated now; the end-to-end "CI runs green on GitHub" verification happens the first
time the repo is pushed to a remote. That push is owner-triggered.

## Testing approach

- Local: run `pytest -q` and `ruff check .`; confirm both clean. Parse the workflow YAML
  (PyYAML is not a project dependency, so install it ephemerally just for the check, or
  rely on GitHub's parse on first push).
- Remote (deferred): push, confirm the Actions run is green and the matrix is as expected;
  one-time red-path check, then revert.

## Out-of-scope follow-ups (later sub-projects)

- Scheduled live canary job (sub-project 3) will be a separate workflow file with `on: schedule` and `workflow_dispatch`, gated behind explicit opt-in, not blocking PRs.
- Release automation (sub-project 4) may add a `release.yml` triggered on tags.
