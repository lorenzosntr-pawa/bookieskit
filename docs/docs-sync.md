# Docs-sync gate

Documentation must stay in step with the library. Every change to
`src/bookieskit/**` ships with the docs it affects, in the **same PR**. This is
enforced two ways: a standing **cycle discipline** (process) and a **CI
hard-gate** (the teeth), with a `docs:n/a` escape hatch for internal-only work.

## The rule

If a PR's change set touches any path under `src/bookieskit/**`, then at least
one changed path must be a documentation surface:

- `docs/**`
- `README.md`
- `CHANGELOG.md`

Otherwise the gate fails. The check is **fail-closed**: "user-facing" is
approximated as *any* `src/bookieskit/**` change, rather than a brittle
per-path allow/deny list. The `docs:n/a` hatch (below) covers the
internal-refactor false-positives.

## Cycle discipline (process)

Any cycle whose PR changes user-facing library behavior MUST update the
affected docs in the same PR. The doc surface to keep in sync:

- `README.md`
- `CHANGELOG.md` — the `[Unreleased]` section (already required for
  library/market changes)
- `docs/markets.md`, `docs/coverage.md`
- the relevant per-book page: `docs/bet9ja.md`, `docs/betika.md`,
  `docs/betpawa.md`, `docs/betway.md`, `docs/msport.md`, `docs/sportpesa.md`,
  `docs/sportybet.md`
- `docs/examples.md` / `docs/matching.md` when behavior they describe changes

The `.github/pull_request_template.md` checklist and the reviewer checklist
(requesting-code-review) both carry a "docs in sync?" item.

## CI hard-gate

The `docs-sync` job in `.github/workflows/ci.yml` runs on every `pull_request`.
It computes the changed-file set against the base branch
(`git diff --name-only origin/<base>...HEAD`) and applies the rule above,
invoking the locally-runnable checker so the CI job and a developer's
self-check share one implementation.

## The `docs:n/a` escape hatch

For genuinely internal-only changes (refactors, test-only, tooling) that have
no user-facing impact, mark the PR with `docs:n/a` and the gate passes. Two
equivalent ways to set it:

- add a `docs:n/a` **label** to the PR, or
- add a line to the **PR body** that reads exactly `docs:n/a` (case-insensitive,
  surrounding whitespace ignored).

The body marker must be a deliberate **bare line** — a `docs:n/a` mention
inside prose or inside an HTML comment does **not** trip the hatch. This is
what stops the PR template's own explanatory text (which names the token) from
silently exempting every PR.

Non-`src` changes (docs-only, CI-only, orchestration-only) never trip the gate
in the first place — the hatch is only needed for a `src/bookieskit/**` change
you are deliberately shipping without docs.

## Self-check before pushing

The same checker the CI job runs is a `bookieskit.devtools` subcommand, so you
can verify locally before pushing:

```bash
# diff HEAD against the base branch (what CI does)
python -m bookieskit.devtools check-docs-sync --base origin/main

# or test the rule against an explicit file list
python -m bookieskit.devtools check-docs-sync \
    --changed src/bookieskit/markets/registry.py,docs/markets.md
```

Exit code `0` = in sync (or not applicable / exempt), `1` = library change
with no docs and no `docs:n/a` hatch. Add `--pr-body "<text>"` /
`--labels a,b` to exercise the escape-hatch detection, or `--json` for the
machine-readable result.
