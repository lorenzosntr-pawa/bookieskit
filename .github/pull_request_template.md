<!-- Closes #<issue> -->

## What & why

<!-- One paragraph: what this PR changes and the reason. -->

## Assumptions (for supervised review)

<!-- Every decide-and-document assumption made during the build. -->

## Checklist

- [ ] Tests added/updated and the suite passes (`pytest -q`).
- [ ] `src/` is ruff-clean (`ruff check .`).
- [ ] **Docs in sync** — any change under `src/bookieskit/**` updates the
      affected docs in this PR (`README.md`, `CHANGELOG.md` `[Unreleased]`,
      `docs/markets.md`, `docs/coverage.md`, the relevant per-book
      `docs/<book>.md`, `docs/examples.md` / `docs/matching.md`). The CI
      `docs-sync` job enforces this. To bypass it for a genuinely
      internal-only change (refactor, test-only, tooling), add a `docs:n/a`
      label, or add a line reading exactly `docs:n/a` below the marker.
- [ ] Version stays in sync across `pyproject.toml` and
      `src/bookieskit/__init__.py` (if bumped).

<!-- docs-sync escape hatch: to bypass the gate for an internal-only change,
     add a line below this comment that reads exactly:  docs:n/a
     (a `docs:n/a` label works too). Leave this section as-is otherwise. -->
