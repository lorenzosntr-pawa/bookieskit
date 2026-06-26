# Slice C — graphify, for real (query-the-graph-before-code)

**Date:** 2026-06-26
**Status:** design — approved in brainstorming, pending spec review
**Stream:** capability (pipeline hardening)

## Problem

`CLAUDE.md` and the orchestrate skill both instruct every cycle to "query
graphify (the structural map) before touching code." That guidance is
**aspirational**: no graph has ever been built in this repo (`graphify-out/`
does not exist), so there is nothing to query. The instruction is a no-op.

graphify is installed (the `/graphify` skill: builds `graphify-out/graph.json`
+ `GRAPH_REPORT.md` + HTML, with `query`/`path`/`explain` tools and incremental
`--update`). "Slice 2 — graphify, for real" was explicitly deferred from the
directed-design slice as a recognized follow-up.

## Goal

Make "query-the-graph-before-code" real: build a structural graph of the
codebase, commit it as versioned fleet structural memory, and wire the loop's
build step to actually query it before editing — so changes are scoped from the
real dependency map (Karpathy: smallest surgical change).

## Decisions (from brainstorming)

- **Freshness: commit it, rebuild on demand.** Build once over `src/`, commit
  the reviewable artifacts, rebuild incrementally (`--update`) on demand — NOT
  every cycle (graphify extraction uses an LLM; per-cycle cost is not worth it).
- **Query path: the build step runs `graphify query`.** Targeted BFS answers
  ("what depends on X / where is Y wired") against the committed graph, only on
  real build cycles.
- **Graph scope: `src/` only** (the library + `orchestration/` — the code
  cycles touch). Tests/docs are noise for a structural blast-radius map.
- **Commit `graph.json` + `GRAPH_REPORT.md` only;** gitignore the
  heavy/regenerable rest (HTML, Obsidian vault, `raw/`, caches).

## Architecture / flow

```
one-time (this slice, in-region):  graphify src --directed
   -> graphify-out/graph.json        (committed: the structural map)
   -> graphify-out/GRAPH_REPORT.md   (committed: plain-language map)
   -> graphify-out/*.html, vault/    (gitignored: regenerable)

on demand (maintenance):           graphify src --update   (incremental)

every build cycle (orchestrate Step "Build it"):
   before editing -> graphify query "what depends on <thing> / where is <thing> wired"
   -> scope the smallest surgical change from the real dependency map
```

## Components

### The graph artifacts (generated + committed)

- Run the graphify pipeline over `src/` with `--directed` (source→target edges
  preserved, required for dependency/"what-depends-on" queries).
- Commit: `graphify-out/graph.json`, `graphify-out/GRAPH_REPORT.md`.
- Gitignore everything else graphify emits under `graphify-out/` (the
  interactive HTML, any Obsidian vault, `raw/`, and intermediate caches) — large
  and fully regenerable from `graph.json`.

### `.gitignore`

Add a `graphify-out/` block that ignores the directory **except** the two
committed artifacts, e.g.:

```gitignore
# graphify structural graph — commit the reviewable artifacts, ignore the rest
graphify-out/*
!graphify-out/graph.json
!graphify-out/GRAPH_REPORT.md
```

### `.claude/skills/orchestrate/SKILL.md`

In the **"Build it — autonomously — per stream"** step, the existing line
"query `graphify` for the structural map before touching code" becomes concrete:

> Before editing, query the committed structural graph for blast radius:
> `graphify query "what depends on <symbol> / where is <thing> wired"` (reads
> `graphify-out/graph.json`). Use the answer to scope the smallest surgical
> change and find all call sites. If the change adds/renames structure, refresh
> the graph afterward with `graphify <repo>/src --update` and commit the updated
> `graph.json` + `GRAPH_REPORT.md`.

### `CLAUDE.md` (operating contract)

Repoint the graphify line from aspirational to real: it now references the
committed `graphify-out/graph.json`, the `graphify query` command, and the
on-demand `--update` rebuild — so every session inherits a contract that
matches reality.

### Maintenance documentation

A short `docs/GRAPHIFY.md` (or a section appended to an existing ops doc)
covering: what the committed graph is, how to query it (`graphify query`/`path`/
`explain`), and how to refresh it (`graphify src --update` → commit). One page.

## Feasibility gate (first build step)

graphify's extraction needs the tool installed (uv/pipx per the skill's
detection) and an LLM available, and runs in-region. **Before** generating
anything, confirm graphify runs here (e.g. the skill's install-detection
succeeds and a trivial run starts). If it cannot run in this environment,
STOP and report — do not fabricate a graph by hand. The graph must be the
tool's genuine output (honest audit trail: EXTRACTED/INFERRED/AMBIGUOUS edges).

## Testing / verification

This slice is tool-run + config/doc wiring; there is little unit-testable code.
Verification is concrete and checkable:

- `graphify-out/graph.json` and `GRAPH_REPORT.md` exist, are non-trivial (the
  report names real `src/` modules — e.g. `gh`, `queue`, `priority`, `gate`,
  `appauth`), and parse as valid JSON / markdown.
- `git status` shows ONLY `graph.json` + `GRAPH_REPORT.md` tracked under
  `graphify-out/` (the HTML/vault/raw are ignored) — verify with
  `git check-ignore graphify-out/graph.html`.
- A sample `graphify query "what depends on GhRunner"` returns a relevant,
  non-empty answer citing real modules (smoke test the query path the loop
  will use).
- `ruff check .` and the existing suite stay green (no `src/` changes in this
  slice).

## Out of scope / fast-follow

- Automated freshness (tick `--update`, or rebuild-on-merge CI) — deferred; the
  chosen model is on-demand rebuild.
- graphify MCP server for live cycle queries — deferred; the CLI `graphify
  query` is the v1 query path.
- Graphing `tests/`, `docs/`, or `scripts/` — v1 scope is `src/` only.

## Files

- Create (generated, committed): `graphify-out/graph.json`,
  `graphify-out/GRAPH_REPORT.md`
- Modify: `.gitignore` (the `graphify-out/` keep-list block)
- Modify: `.claude/skills/orchestrate/SKILL.md` (concrete query-before-edit step)
- Modify: `CLAUDE.md` (graphify line → real command + committed graph)
- Create: `docs/GRAPHIFY.md` (query + refresh runbook)
- Modify: `CHANGELOG.md` (`[Unreleased]` — tooling/ops)
