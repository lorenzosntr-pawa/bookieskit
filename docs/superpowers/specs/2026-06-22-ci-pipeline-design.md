# CI Pipeline — Design

**Date:** 2026-06-22
**Status:** Approved (pending written-spec review)
**Sub-project:** 1 of 4 in the "project workflow" track (CI → market-add harness → live canary tests → release automation)

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
| Version test fix | Assert against installed package metadata | `importlib.metadata.version("bookieskit")` is the single source of truth; the test never goes stale and also catches drift between `pyproject.toml` and the `__init__.py` literal. |
| Lint scope | `ruff check .` only | Matches current config (`select = ["E","F","I"]`). No formatting gate → no one-time churn. |

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

with an assertion against installed metadata (single source of truth):

```python
def test_version_matches_package_metadata():
    from importlib.metadata import version
    import bookieskit
    assert bookieskit.__version__ == version("bookieskit")
```

This requires the package to be installed (it is — `pip install -e ".[dev]"` in CI and
locally). The test is renamed to reflect what it actually verifies. (Optional: this test
is about packaging, not SportPesa — it could move to `tests/test_types.py` or a new
`tests/test_packaging.py`, but that is left out of scope to keep the diff minimal.)

## Success criteria

- `.github/workflows/ci.yml` exists and is valid YAML.
- On a pushed branch / opened PR, both `lint` and `test` jobs run and **pass**.
- `pytest -q` is green locally on 3.13 (0 failures; the prior version-test failure resolved).
- `ruff check .` reports no errors.
- A deliberately introduced lint error or test failure causes the corresponding job to go red (manually sanity-checked once, then reverted).

## Testing approach

- Local: run `pytest -q` and `ruff check .` and confirm both clean.
- Remote: push the branch and confirm the Actions run is green. Verify the matrix shows three `test` jobs (3.11/3.12/3.13) plus one `lint` job.
- One-time red-path check: temporarily break a test, confirm CI fails, revert.

## Out-of-scope follow-ups (later sub-projects)

- Scheduled live canary job (sub-project 3) will be a separate workflow file with `on: schedule` and `workflow_dispatch`, gated behind explicit opt-in, not blocking PRs.
- Release automation (sub-project 4) may add a `release.yml` triggered on tags.
