# CI Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub Actions CI pipeline that runs `pytest` (matrix 3.11/3.12/3.13) and `ruff check` on every push to `main` and every PR, and make the suite + lint green so the gate passes.

**Architecture:** One workflow file with two jobs (`lint`, `test`). Before the workflow can be green, two pre-existing problems are fixed: a brittle hardcoded version assertion, and 38 pre-existing `ruff` violations (resolved via config + minimal `src` fixes + test import auto-fix; disposable `scripts/` excluded).

**Tech Stack:** GitHub Actions, `pytest` + `pytest-asyncio` + `respx`, `ruff`, stdlib `tomllib`. Runtime dep is `httpx` only; dev extras provide the rest.

## Global Constraints

- Python floor: **3.11** (`requires-python>=3.11`); `tomllib` is stdlib from 3.11 — OK to use.
- Runtime dependencies: **`httpx` only**. Do NOT add runtime deps. Do NOT add `pyyaml` to `pyproject.toml` (ephemeral local use only).
- Ruff config: `select = ["E","F","I"]`, `line-length = 88`, `target-version = "py311"`.
- `src/` must remain **100% ruff-clean**. `tests/**` ignores `E501`. `scripts/` is excluded from ruff.
- The whole test suite is **offline** (respx-mocked); never introduce live network calls.
- This repo has **no GitHub remote**. The "CI runs green on GitHub" check is deferred until the owner pushes to a remote; everything else is verified locally.
- Apply Karpathy principles: smallest surgical change, no overcomplication.

---

### Task 1: De-brittle the version test (suite goes green)

**Files:**
- Modify: `tests/test_sportpesa.py` (the `test_top_level_version_bumped` function, ~lines 197-200)

**Interfaces:**
- Consumes: `bookieskit.__version__` (existing, a string literal in `src/bookieskit/__init__.py`); `pyproject.toml` `[project].version`.
- Produces: nothing other tasks depend on.

- [ ] **Step 1: Run the currently-failing test to confirm the failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sportpesa.py::test_top_level_version_bumped -v`
Expected: FAIL — `AssertionError: assert '0.15.1' == '0.15.0'`

- [ ] **Step 2: Replace the brittle test with a pyproject-backed assertion**

In `tests/test_sportpesa.py`, replace exactly:

```python
def test_top_level_version_bumped():
    import bookieskit
    assert bookieskit.__version__ == "0.15.0"
```

with:

```python
def test_version_matches_pyproject():
    import tomllib
    from pathlib import Path

    import bookieskit

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert bookieskit.__version__ == data["project"]["version"]
```

(Rationale: `pyproject.toml` is the real single source of truth and is read directly, so the test never goes stale and never depends on a fresh editable install. `importlib.metadata.version()` was rejected because editable metadata is stale locally — reports `0.13.0`.)

- [ ] **Step 3: Run the new test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sportpesa.py::test_version_matches_pyproject -v`
Expected: PASS

- [ ] **Step 4: Run the full suite to confirm it is now green**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: `566 passed, 1 skipped` (0 failed). The previously-failing version test is resolved.

- [ ] **Step 5: Commit**

```bash
git add tests/test_sportpesa.py
git commit -m "test: assert __version__ against pyproject (no longer hardcoded)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Make `ruff check .` green

**Files:**
- Modify: `pyproject.toml` (the `[tool.ruff]` / `[tool.ruff.lint]` sections)
- Modify: `src/bookieskit/markets/builtin_mappings.py` (lines 650 and 690)
- Modify (via auto-fix): test files with unsorted imports (6 `I001` occurrences across `tests/`)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: a clean lint baseline the `lint` CI job (Task 3) relies on.

- [ ] **Step 1: Confirm the current 38 violations**

Run: `.venv/Scripts/python.exe -m ruff check .`
Expected: `Found 38 errors.` (27 E501, 8 I001, 2 F401, 1 F841)

- [ ] **Step 2: Update the ruff config in `pyproject.toml`**

Replace exactly:

```toml
[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I"]
```

with:

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

(Rationale: `scripts/` holds disposable probe scripts being replaced by the market-add harness; `tests/**` fixture literals legitimately exceed 88 cols.)

- [ ] **Step 3: Fix the two over-long inline comments in `src`**

In `src/bookieskit/markets/builtin_mappings.py`, replace exactly (line 650):

```python
        bet9ja_key="S_HAOU",                   # shared with away_over_under_ft (see comment)
```

with:

```python
        bet9ja_key="S_HAOU",  # shared with away_over_under_ft (see comment)
```

and replace exactly (line 690):

```python
        bet9ja_key="S_HAOU",                   # shared with home_over_under_ft (see comment)
```

with:

```python
        bet9ja_key="S_HAOU",  # shared with home_over_under_ft (see comment)
```

- [ ] **Step 4: Auto-fix the test import ordering**

Run: `.venv/Scripts/python.exe -m ruff check tests --fix`
Expected: `Found 6 errors (6 fixed, 0 remaining).` (the `I001` import-sort fixes; `E501` is now ignored under `tests/**`)

- [ ] **Step 5: Verify the lint gate is green**

Run: `.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: Verify tests still pass (import reordering changed nothing behaviorally)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: `566 passed, 1 skipped` (0 failed)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/bookieskit/markets/builtin_mappings.py tests/
git commit -m "chore(lint): make ruff check clean (exclude scripts, ignore E501 in tests)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Add the CI workflow file

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: green `pytest` (Task 1) and green `ruff check .` (Task 2).
- Produces: the CI gate (verified on GitHub once a remote exists).

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

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

- [ ] **Step 2: Validate the YAML parses (ephemeral PyYAML — NOT added to project deps)**

Run:
```bash
.venv/Scripts/python.exe -m pip install -q pyyaml && \
.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"
```
Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions pipeline (pytest matrix 3.11-3.13 + ruff)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: (Deferred — owner-triggered) Verify green on GitHub**

This repo has no remote yet. Once an `origin` exists and the branch is pushed:
- Confirm the Actions run shows 1 `lint` job + 3 `test` jobs (3.11/3.12/3.13), all green.
- One-time red-path check: temporarily break a test, push, confirm CI fails, then revert.

Do not block plan completion on this step; record it as the post-remote follow-up.

---

## Notes for the executor

- Run commands with the project venv: `.venv/Scripts/python.exe -m <tool>` (Windows). On CI (Ubuntu) the workflow uses plain `pytest` / `ruff` after `pip install -e ".[dev]"`.
- Task order matters: Task 1 makes the suite green; Task 2 makes lint green while keeping the suite green; Task 3 ships the workflow. Each task ends in an independently verifiable state.
