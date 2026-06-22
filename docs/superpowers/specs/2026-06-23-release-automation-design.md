# Release Automation (`bookieskit.devtools.release`) — Design

**Date:** 2026-06-23
**Status:** Approved (pending written-spec review)
**Sub-project:** 4 of 5 in the project-workflow track. Umbrella: `2026-06-22-agent-company-north-star.md`. (1=CI ✅, 2=harness ✅, 3=canary ✅, 4=this, 5=orchestration + Slack cockpit.)

## Problem

Releasing `bookieskit` is manual and drifts: the version lives in two files (`pyproject.toml` + `__init__.py`) that must stay in sync (CI enforces it), the CHANGELOG is hand-written, and a git tag must be created. Under manual pressure these steps get skipped — current state proves it: version is `0.15.1`, but the newest CHANGELOG entry is `0.15.0`, and the last git tag is `v0.13.0` (so `0.14.0`/`0.15.0`/`0.15.1` were never tagged). This is the **Ship** step of the agent loop (*Signal → Work → Gate → Ship*); without it the loop can build and verify but not release.

## Goals

- One command bumps both version files, finalizes the CHANGELOG, commits, and tags — atomically and correctly.
- **Agent-runnable**: `--json`, `--dry-run`, non-interactive, meaningful exit codes; the orchestrator runs it to ship.
- Preserve the CHANGELOG's hand-curated prose (promote an `[Unreleased]` section rather than auto-generate from commit subjects).
- Produce a visible artifact: a tag-triggered GitHub Release with the changelog section + built wheel/sdist.
- All pure logic offline-unit-tested; git orchestration tested against a temp local repo.

## Non-goals

- Publishing to PyPI (the package is installed via `git+https`; no PyPI distribution). The tooling leaves a clean seam to add it later but does not implement it.
- Backfilling historical tags (`0.14.0`/`0.15.0`/`0.15.1`) — a one-time optional owner cleanup, out of scope. The tool handles releases going forward.
- Auto-generating CHANGELOG content from commits (the `[Unreleased]` convention keeps human/agent curation).
- Slack/Issue notification of a release (that is the orchestrator, sub-project 5).

## Decisions

| Decision | Choice |
|---|---|
| CHANGELOG strategy | Promote a Keep-a-Changelog `## [Unreleased]` section → `## [X.Y.Z] - <date>`; insert a fresh empty `[Unreleased]` |
| Version bump | Infer from conventional commits since last tag (override with `--bump`); **SemVer-0.x rule: while major==0, breaking → minor** |
| Artifact | Bump+commit+tag CLI **plus** a tag-triggered `release.yml` that builds wheel/sdist + creates a GitHub Release |
| Location / invocation | `src/bookieskit/devtools/release.py` + `python -m bookieskit.devtools release` (and `release-notes`) |
| Safety | Commit + tag **locally**; push (→ triggers the Release) only with `--push`; `--dry-run` mutates nothing |

## Architecture

New module `src/bookieskit/devtools/release.py` (pure functions + a thin orchestrator) and two CLI subcommands on the existing `cli.py`. One-time CHANGELOG edit to add the `[Unreleased]` section. New `.github/workflows/release.yml`.

### Pure functions (offline-tested)

```python
def infer_bump(subjects: list[str], current_major: int) -> str | None:
    """Conventional-commit subjects -> "major"|"minor"|"patch"|None.

    breaking (a "!" before the colon, e.g. "feat!:"/"fix(x)!:", or a
    "BREAKING CHANGE" token) -> "major", EXCEPT while current_major == 0
    where breaking -> "minor" (SemVer 0.x). Else any "feat" -> "minor".
    Else any "fix" -> "patch". Else None (no release-worthy commit)."""

def next_version(current: str, bump: str) -> str:
    """ "0.15.1" + "minor" -> "0.16.0"; "+patch" -> "0.15.2";
    "+major" -> "1.0.0". Resets lower components."""

def bump_pyproject(text: str, new: str) -> str:
    """Replace the `version = "..."` line under [project]. Idempotent;
    raises if the line is absent or ambiguous."""

def bump_init(text: str, new: str) -> str:
    """Replace the `__version__ = "..."` line. Raises if absent."""

def promote_changelog(text: str, version: str, date: str) -> str:
    """Rename `## [Unreleased]` -> `## [<version>] - <date>` and insert a
    fresh empty `## [Unreleased]` above it. Raises if there is no
    `## [Unreleased]` section or it has no entries (refuse empty release)."""

def extract_section(text: str, version: str) -> str:
    """Return the body of the `## [<version>] ...` section (between that
    header and the next `## [` header), stripped. Raises if not found."""
```

### Orchestrator

```python
@dataclass
class ReleasePlan:
    current: str
    new: str
    bump: str
    tag: str                 # "v<new>"
    changelog_section: str   # the promoted section body
    pushed: bool

def run_release(
    *,
    bump: str | None = None,
    dry_run: bool = False,
    push: bool = False,
    root: Path | None = None,        # repo root (default: discovered)
    today: str | None = None,        # date override for tests
    git: GitRunner | None = None,    # injectable git command runner (tests)
) -> ReleasePlan:
    ...
```

`run_release`:
1. **Preconditions**: working tree clean (via `git status --porcelain`); on success continue. Read `current` from `pyproject.toml`.
2. **Bump**: `bump or infer_bump(<subjects since last v* tag>, current_major)`; error (non-zero) if both None. `new = next_version(current, bump)`.
3. **Edit files** (skipped under `dry_run`): `bump_pyproject`, `bump_init`, `promote_changelog(..., today or date.today().isoformat())`. `changelog_section = extract_section(new_changelog, new)`.
4. **Commit + tag** (skipped under `dry_run`): stage the 3 files; `git commit -m "chore(release): v<new>"`; `git tag -a v<new> -m "v<new>"`.
5. **Push** (only if `push and not dry_run`): `git push <remote> <branch>` then `git push <remote> v<new>`.
6. Return `ReleasePlan` (with `pushed`).

`GitRunner` is a tiny wrapper around `subprocess`/git so tests inject a fake (or point at a temp repo). Git commands are the only side effects; the text transforms are pure.

### CLI subcommands (on `cli.py`)

- `release [--bump {major,minor,patch}] [--dry-run] [--json] [--push]`
  - Human mode: prints the plan (current → new, tag, changelog section, pushed?).
  - `--json`: serialized `ReleasePlan`.
  - Exit code: `0` on success; `1` on precondition failure (dirty tree), no-bump-inferable-without-`--bump`, or missing/empty `[Unreleased]`.
- `release-notes <version> [--json]`: prints `extract_section(CHANGELOG, version)` (used by `release.yml` to build the GitHub Release body). Exit `1` if the section is absent.

### One-time CHANGELOG setup

The current `CHANGELOG.md` has no `## [Unreleased]` section. As part of this work, insert an empty one immediately after the intro paragraph and before `## [0.15.0]`:

```markdown
## [Unreleased]

## [0.15.0] - 2026-05-22
```

Future library/market changes are recorded under `[Unreleased]`; `release` promotes it.

### GitHub Release workflow

New `.github/workflows/release.yml`:

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

Runs only on a pushed `v*` tag. Builds wheel + sdist, extracts the changelog body via `release-notes`, and creates a GitHub Release (artifacts attached) using the built-in token. No PyPI.

## Error handling

- **Dirty working tree** → refuse with a clear message (release must be from a clean tree), exit 1.
- **No release-worthy commits and no `--bump`** → refuse (don't guess a bump), exit 1.
- **Missing/empty `[Unreleased]`** → refuse (don't cut an empty release), exit 1.
- **`bump_*`/`extract_section` can't find their target** → raise (surfaces as a non-zero CLI failure) rather than silently no-op — a malformed pyproject/CHANGELOG must fail loudly.
- Git command failures propagate (non-zero exit) with the git stderr shown.

## Testing approach

Offline unit tests under `tests/devtools/test_release.py`:
- `infer_bump`: feat→minor, fix→patch, breaking(`feat!:`/`BREAKING CHANGE`)→major when major≥1, breaking→**minor** when major==0, docs/chore-only→None.
- `next_version`: patch/minor/major arithmetic incl. lower-component reset and 0.x.
- `bump_pyproject` / `bump_init`: replaces only the version line; raises when absent; round-trips the exact current strings (`version = "0.15.1"`, `__version__ = "0.15.1"`).
- `promote_changelog`: Unreleased→versioned with date + fresh empty Unreleased; raises on missing/empty Unreleased.
- `extract_section`: returns the right block; raises when absent.
- `run_release` against a **temp git repo** (`tmp_path`, local `git init`, seed pyproject/__init__/CHANGELOG + an `[Unreleased]` entry + a `feat:` commit): asserts new version in both files, CHANGELOG promoted, a `chore(release)` commit and a `v<new>` tag created, `today` injected; `--dry-run` leaves the tree and tags untouched; `--push` path exercised with a **bare local remote** (offline) or asserted via the injected `GitRunner` (no real network).
- CLI: `release --json` / `release-notes` arg parsing, output shape, and exit codes (dirty tree → 1, no-bump → 1).
- No live network in any test. The `release.yml` workflow's GitHub interaction is owner-verified once after merge (a real tag push).

## Success criteria

- `python -m bookieskit.devtools release --dry-run --json` prints a correct `ReleasePlan` for the current repo without mutating anything.
- A real `release --bump patch` (in a test/throwaway context) bumps both files to the next version, promotes the CHANGELOG, commits `chore(release): vX.Y.Z`, and creates the `vX.Y.Z` tag; `--push` pushes both.
- `release-notes <version>` prints exactly that version's CHANGELOG body.
- `.github/workflows/release.yml` exists, valid YAML, triggers only on `v*` tags, has `contents: write`.
- New `tests/devtools/test_release.py` passes; full suite + `ruff check .` green in CI.
- CHANGELOG has an `[Unreleased]` section; the version test still passes (both files in sync).
- Owner-verified once after merge: pushing a `v*` tag creates a GitHub Release with the changelog body + wheel/sdist.

## Reuse hooks for later sub-projects

- **Orchestrator (sub-project 5):** after CI is green on `main`, runs `release --bump <x> --push --json`; the JSON `ReleasePlan` + the tag-triggered workflow complete the loop's **Ship** step and give a release URL to announce in Slack `#releases`.
