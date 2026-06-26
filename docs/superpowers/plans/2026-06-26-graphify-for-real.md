# graphify, for real — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: execute task-by-task. This slice is tool-run + config/doc wiring (little unit-testable code); inline execution fits better than subagent fan-out. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make "query-the-graph-before-code" real — build + commit a structural graph of `src/`, gitignore the regenerable rest, and wire the loop's build step to query it.

**Architecture:** Generate `graphify-out/graph.json` + `GRAPH_REPORT.md` once over `src/` (`graphify --directed`), commit those two as fleet structural memory, rebuild on demand with `--update`. The orchestrate build step runs `graphify query` against the committed graph before editing.

**Tech Stack:** the installed `graphify` skill/CLI (uv/pipx); git; markdown.

## Global Constraints

- The graph MUST be graphify's genuine output — never hand-fabricated. If graphify can't run here, STOP and report (feasibility gate).
- Commit ONLY `graphify-out/graph.json` + `graphify-out/GRAPH_REPORT.md`; gitignore the rest under `graphify-out/`.
- No `src/` code changes in this slice → `ruff check .` and the suite stay green.
- `.claude/` is gitignored → `git add -f` for `SKILL.md`.
- Runs in-region (graphify's LLM extraction). Conventional commits.

---

### Task 1: Feasibility gate + generate the graph

**Files:** Create (generated): `graphify-out/graph.json`, `graphify-out/GRAPH_REPORT.md` (+ regenerable HTML/vault/raw).

- [ ] **Step 1: Verify graphify runs here.** Confirm the graphify install is detectable and a run can start (the `/graphify` skill's install-detection, or `graphify --help`). If it cannot run / no LLM available, STOP and report — do not proceed to generation.

- [ ] **Step 2: Build the graph over `src/`.** Invoke the graphify pipeline on `src/` with directed edges:
  - via the skill: `/graphify src --directed`, or the equivalent underlying command.
  - Let it produce `graphify-out/` (graph.json, GRAPH_REPORT.md, HTML, etc.).

- [ ] **Step 3: Verify the output is real and non-trivial.**
  - `graphify-out/graph.json` parses as JSON and has nodes/edges.
  - `graphify-out/GRAPH_REPORT.md` names real `src/` modules (expect to see e.g. `gh`, `queue`, `priority`, `gate`, `appauth`, `cli`, `maintenance`).
  - If the graph is empty/degenerate, investigate (wrong path? extraction failed?) before continuing.

- [ ] **Step 4: Smoke-test the query path the loop will use.**
  - Run `graphify query "what depends on GhRunner"` (or `graphify explain "GhRunner"`).
  - Expected: a non-empty answer citing real modules. Record the command + a one-line result in the build report.

---

### Task 2: Gitignore keep-list + commit the two artifacts

**Files:** Modify `.gitignore`; commit `graphify-out/graph.json` + `graphify-out/GRAPH_REPORT.md`.

- [ ] **Step 1: Add the keep-list block to `.gitignore`.**

```gitignore
# graphify structural graph — commit the reviewable artifacts, ignore the rest
graphify-out/*
!graphify-out/graph.json
!graphify-out/GRAPH_REPORT.md
```

- [ ] **Step 2: Verify the ignore rules.**
  - `git check-ignore graphify-out/graph.html` → prints the path (ignored).
  - `git status --porcelain graphify-out/` shows ONLY `graph.json` + `GRAPH_REPORT.md` as untracked/added.

- [ ] **Step 3: Commit the graph + gitignore.**

```bash
git add .gitignore graphify-out/graph.json graphify-out/GRAPH_REPORT.md
git commit -m "feat(graphify): commit src/ structural graph as fleet memory"
```

---

### Task 3: Wire the loop, contract, and runbook

**Files:** Modify `.claude/skills/orchestrate/SKILL.md`, `CLAUDE.md`, `CHANGELOG.md`; create `docs/GRAPHIFY.md`.

- [ ] **Step 1: Make the orchestrate build step concrete.** In `.claude/skills/orchestrate/SKILL.md`, under "Build it — autonomously — per stream", replace the aspirational graphify line with:

> Before editing, query the committed structural graph for blast radius:
> `graphify query "what depends on <symbol> / where is <thing> wired"` (reads
> `graphify-out/graph.json`). Scope the smallest surgical change and find all
> call sites from the answer. If the change adds/renames structure, refresh with
> `graphify src --update` and commit the updated `graph.json` + `GRAPH_REPORT.md`.

- [ ] **Step 2: Repoint `CLAUDE.md`.** Update the graphify line in the operating contract from aspirational to real — reference the committed `graphify-out/graph.json`, the `graphify query` command, and the on-demand `--update` rebuild.

- [ ] **Step 3: Write `docs/GRAPHIFY.md`** (one page): what the committed graph is; how to query it (`graphify query` / `path` / `explain`, with a worked example); how to refresh it (`graphify src --update` → commit `graph.json` + `GRAPH_REPORT.md`); and the commit policy (only those two artifacts).

- [ ] **Step 4: CHANGELOG.** Under `## [Unreleased]` → `### Added`:

```markdown
- Committed a graphify **structural graph** of `src/` (`graphify-out/graph.json`
  + `GRAPH_REPORT.md`) as fleet structural memory; the orchestrator build step
  now queries it (`graphify query`) before editing to scope changes. Refresh on
  demand with `graphify src --update`. See `docs/GRAPHIFY.md`.
```

- [ ] **Step 5: Verify + commit.**
  - `ruff check .` clean; full suite green (no `src/` changes).
  - Commit (force-add the gitignored skill):

```bash
git add -f .claude/skills/orchestrate/SKILL.md
git add CLAUDE.md docs/GRAPHIFY.md CHANGELOG.md
git commit -m "docs(orchestrate): wire graphify query-before-code into the loop"
```

---

## Self-Review

- **Spec coverage:** feasibility gate + generation (T1) ✓; gitignore keep-list + commit artifacts (T2) ✓; skill + CLAUDE.md + docs/GRAPHIFY.md + CHANGELOG (T3) ✓.
- **Placeholder scan:** the gitignore block, the skill text, and the verification commands are concrete.
- **Honest-output guard:** T1 Step 1 STOPs if graphify can't run — no hand-fabricated graph.
- **No `src/` changes** → CI stays green; the only tracked graph artifacts are the two named files.
