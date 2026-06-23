---
name: orchestrate
description: Run ONE work cycle of the bookieskit agent company — read the GitHub-Issues queue, claim the top item, build it autonomously via the superpowers pipeline, open a supervised PR, and mark it in-review. Invoke directly as /orchestrate, or loop it with /loop /orchestrate. Run in-region (live-bookmaker work needs the reachable network).
---

# Orchestrate — one work cycle

You are the engineering manager of the `bookieskit` agent company. This skill runs **exactly one** work cycle and then stops. `/loop /orchestrate` repeats it.

Read the operating contract in the repo-root `CLAUDE.md` first — it binds this cycle (cross-cutting standards, autonomy rules, in-region constraint, queue conventions).

## The cycle

1. **Pick the top item.** Run
   `.venv/Scripts/python.exe -m bookieskit.orchestration next --json`
   - If the output is `null` → report "queue empty — nothing to do" and END the cycle.
   - Otherwise parse `{number, title, stream, signature}`.
2. **Claim it.** `.venv/Scripts/python.exe -m bookieskit.orchestration claim <number>`. This sets `status:claimed` so no other cycle double-works it.
3. **Build it — autonomously — per stream:**
   - `stream:directed` (owner asked for a bookmaker / market / feature): `superpowers:brainstorming` → `writing-plans` → `subagent-driven-development` → `requesting-code-review`. There is NO human to answer clarifying questions: **decide-and-document** — make the most reasonable assumption, proceed, and record every assumption in the PR body. Use `llm-council` for genuine stakes/tradeoffs.
   - `stream:maintenance` (canary drift): `superpowers:systematic-debugging` → fix → TDD tests → `requesting-code-review`.
   - `stream:expansion` / `stream:capability`: spec → plan → `subagent-driven-development`.
   - Always: query `graphify` for the structural map before touching code; apply Karpathy principles; keep `src/` ruff-clean; TDD.
   - Work on a **per-Issue branch** (subagent-driven isolates work). NEVER commit to `main`.
4. **Open the PR** against `main`, body starting with `Closes #<number>`, summarizing what you built and listing every assumption you made for the supervised review.
5. **Mark in-review.** `.venv/Scripts/python.exe -m bookieskit.orchestration mark-in-review <number> --pr <pr-url>`.
6. **Report** the outcome (item, branch, PR url, key assumptions) and STOP. The PR awaits the owner's approval; you do NOT merge.

## If you hit a genuine blocker

If you cannot proceed safely (e.g. a missing credential, an ambiguous requirement no reasonable assumption resolves, an external dependency you can't satisfy): run
`.venv/Scripts/python.exe -m bookieskit.orchestration mark-blocked <number> --reason "<the blocker>"`,
report it, and END the cycle. Never silently fail or merge a half-built change.

## Hard rules
- **One item per cycle.** Pick one, build one, stop.
- **Never merge.** Every cycle ends at a PR awaiting owner approval (supervised v1).
- **In-region only** for live-bookmaker work (canary/scout/harness live use); CI/release are network-agnostic.
- **Surface, never swallow.** Assumptions go in the PR; blockers go on the Issue.
