# Orchestration 5b — Orchestrator Loop (Claude Code as the EM) — Design

**Date:** 2026-06-23
**Status:** Approved (pending written-spec review)
**Sub-project:** 5b of the orchestration capstone (sub-project 5). Umbrella: `2026-06-22-agent-company-north-star.md`. Builds on 5a (the work queue + maintenance stream). Siblings: 5c Slack cockpit, 5d scout.

## Problem

5a gives the company a durable work queue (GitHub Issues) and the maintenance stream. But nothing **consumes** the queue — turning a work item into a PR. 5b is the **brain**: the scheduled, in-region "engineering manager" that reads the queue, picks the top item, and runs the build pipeline to produce a supervised PR. It is the piece that makes the company *run itself*.

## Execution model (the defining decision)

**Claude Code IS the orchestrator.** The owner kicks off an in-region Claude Code session and runs `/loop /orchestrate`; each cycle works one Issue. The build "agents" are Claude Code + its subagents running the superpowers pipeline natively (the exact flow used to build sub-projects 1–5a). 5b **configures** Claude Code to be the EM — it does **not** build a bespoke agent engine. This reuses everything: the superpowers skills, subagent-driven-development, the cross-cutting standards, and the in-region environment (where the bookmakers are reachable).

## Goals

- A one-cycle **orchestrate procedure**: read queue → claim top item → build → open PR → mark in-review → report.
- An **operating contract** every agent run in the repo inherits (cross-cutting standards + autonomy rules + queue conventions).
- **Autonomous build** without a human in the loop: decide-and-document, `llm-council` for stakes, surface assumptions in the PR.
- **Supervised** by default: every cycle ends with a PR awaiting owner approval; the loop never merges.
- Thin, deterministic **Python glue** (prioritize / claim / mark-in-review), agent-runnable and offline-tested.

## Non-goals

- A from-scratch agent framework / SDK orchestrator (Claude Code is the engine).
- Auto-merge of any class (v1 is fully supervised; auto-merge is a future trust-ladder step).
- The capability-review *discovery* task, the scout (5d), the Slack cockpit (5c) — the loop *consumes* whatever fills the queue; those *fill* it.
- Parallel multi-issue cycles (one Issue per cycle in v1).
- A cloud scheduler (the loop is in-region — live-bookmaker builds need the reachable network).

## Decisions

| Decision | Choice |
|---|---|
| Execution mechanism | Claude Code as orchestrator, driven by `/loop /orchestrate` (in-region) |
| Work granularity | One Issue per cycle (each cycle → one reviewable PR) |
| Prioritization | Stream order **directed > maintenance > expansion > capability**, FIFO (oldest = lowest issue number) within a stream; skip `status:claimed` |
| Supervision | Fully supervised v1: PR awaits owner approval; loop never merges; owner merge auto-closes the Issue (`Closes #N`) |
| Glue location | `bookieskit.orchestration` (extends 5a): `priority.py` + `Queue.claim`/`mark_in_review` + CLI `next`/`claim`/`mark-in-review` |

## Architecture — three deliverables

### 1. The `orchestrate` skill — `.claude/skills/orchestrate/SKILL.md`

The EM's procedure for **one cycle** (invoked as `/orchestrate`, looped via `/loop /orchestrate`):

1. `item = python -m bookieskit.orchestration next --json` (top open, unclaimed, by priority).
2. If `item` is null → report "queue empty", end the cycle (the `/loop` will retry later).
3. `python -m bookieskit.orchestration claim <item.number>` (sets `status:claimed`).
4. **Build** per `item.stream` (native superpowers pipeline, **autonomous**):
   - `stream:directed` (add bookmaker / market / feature) → `superpowers:brainstorming` (decide-and-document mode) → `writing-plans` → `subagent-driven-development` → `requesting-code-review` → open PR.
   - `stream:maintenance` (canary drift) → `systematic-debugging` → fix → TDD tests → open PR.
   - `stream:expansion` / `stream:capability` → spec → plan → subagent-driven execution → open PR.
   The build runs on a per-Issue branch (subagent-driven already isolates work; never commit to `main`).
5. Open the PR with body `Closes #<n>` so an owner merge auto-closes the Issue.
6. `python -m bookieskit.orchestration mark-in-review <n> --pr <url>` (`status:in-review`, drop `status:claimed`, comment the PR link).
7. Report the cycle outcome and **STOP** — the supervised PR awaits owner approval; the next cycle picks the next Issue.

**Autonomy rules** the skill encodes (because there is no human to answer clarifying questions):
- **Decide-and-document**: make the most reasonable assumption, proceed, and record every assumption in the PR body for the supervised review — never block on a question.
- **`llm-council`** for genuine stakes/tradeoffs (design A-vs-B, risky/irreversible choices).
- **`graphify`** the structural map before touching code; **Karpathy** principles on all code.
- **Genuine blocker** (cannot proceed safely): comment the blocker on the Issue, add a `blocked` label, release the claim, and move on — never silent-fail.

### 2. The operating contract — `CLAUDE.md` (repo root)

The persistent project instructions every Claude Code session/agent in this repo inherits. Sections:
- **Mission & north-star** pointer (the agent company; link the specs).
- **Cross-cutting standards** (verbatim from the north-star): superpowers discipline (brainstorm → plan → subagent-driven → systematic-debugging → verification → review); **graphify** (query before touching code), **llm-council** (stakes), **Karpathy** (all code, reviewer-enforced), continuous capability review.
- **Autonomy rules** (decide-and-document; supervised-PR gate; no auto-merge).
- **In-region constraint**: live-bookmaker operations (canary/scout/harness live use) run only in-region; CI/release are offline/cloud-safe.
- **Queue conventions**: streams, signatures, status labels (from 5a).
- **Build discipline**: TDD, frequent commits, `src/` ruff-clean, the `.venv/Scripts/python.exe` invocation, conventional commits, the version-sync invariant, `release` for shipping.

This is authored as a focused, accurate contract — not a dumping ground. It binds *our* future sessions too (intended).

### 3. Python glue — `bookieskit.orchestration` (extends 5a)

- `priority.py`:
  ```python
  STREAM_ORDER = ("stream:directed", "stream:maintenance",
                  "stream:expansion", "stream:capability")
  def next_work_item(open_issues: list[dict]) -> dict | None:
      """The top actionable issue: skip any with the status:claimed label;
      order by STREAM_ORDER index, then by issue number ascending (FIFO);
      return the issue dict or None. Issues without a known stream label sort
      last. Pure function over the gh issue-dict shape (number, labels)."""
  ```
- `queue.py` additions:
  ```python
  def claim(self, number: int) -> None:          # edit add status:claimed
  def mark_in_review(self, number: int, pr_url: str) -> None:
      # edit add status:in-review + remove status:claimed; comment the PR link
  ```
- `cli.py` additions: `next [--json]` (prints the next work item or a null/`none` sentinel), `claim <number>`, `mark-in-review <number> --pr <url>`. The skill calls these for the deterministic queue ops; Claude Code does the build.

## Supervision & the trust ladder

v1 is **fully supervised**: every cycle produces a PR labeled `status:in-review`; the loop **never merges**. The owner reviews (CI must be green) and merges; the `Closes #N` in the PR body auto-closes the Issue, removing it from the queue. The trust ladder (auto-merge for low-risk classes like canary fixture refreshes / version bumps) is explicitly **future work**, unlocked only after the supervised loop is proven.

## Error handling / safety rails

- **Claim-before-build**: `status:claimed` is set before any build work, so a re-run or a second session won't double-work the same Issue (and `next_work_item` skips claimed items).
- **One Issue per cycle**: bounded context; each cycle is one reviewable PR.
- **Branch isolation**: builds happen on a per-Issue branch via subagent-driven-development; `main` is never touched by a cycle.
- **Genuine blocker**: the skill comments the blocker on the Issue, adds `blocked`, releases the claim, and the cycle ends — surfaced, never swallowed. (A `blocked` label is added to 5a's taxonomy by this sub-project.)
- **Crash mid-cycle**: the Issue is left `status:claimed`; the owner (or a future reaper) can un-claim. Documented as a known v1 limitation.

## Testing approach

- **Python glue (offline, in CI):** `tests/orchestration/test_priority.py` — `next_work_item` over issue-dict fixtures: stream-order precedence, FIFO-within-stream (lowest number first), `status:claimed` skipped, unknown-stream sorts last, empty/`None`. `Queue.claim` / `mark_in_review` against a fake `GhRunner` (correct label add/remove + comment). CLI `next`/`claim`/`mark-in-review` `--json` + exit codes.
- **Skill + `CLAUDE.md` (prose/config):** verified by a **supervised dry-run cycle** (owner-run, deferred): seed one `stream:directed` test Issue (e.g. a trivial doc task), run `/orchestrate` once under supervision, confirm it claims → builds → opens a PR (`Closes #N`) → marks `status:in-review`, and the owner reviews the output. This is the acceptance test for the non-code deliverables; it is not a CI unit test.
- No live network in the CI tests (the build/loop is exercised by the supervised dry-run, not CI).

## Success criteria

- `python -m bookieskit.orchestration next --json` returns the correct top item by the priority rule (or null when the queue is empty/all-claimed); `claim` / `mark-in-review` transition the labels correctly.
- The `orchestrate` skill exists and encodes the full cycle procedure + autonomy rules; `/loop /orchestrate` is runnable in-region.
- `CLAUDE.md` exists at the repo root with the operating-contract sections.
- New `tests/orchestration/test_priority.py` (+ queue/cli additions) pass; full suite + `ruff check .` green in CI.
- **Owner-verified (deferred):** a supervised `/orchestrate` cycle on a seeded directed Issue produces a correct PR awaiting approval.

## Reuse hooks for 5c / 5d

- **5c Slack cockpit**: mirrors cycle reports + `status:*` transitions to channels; `approve <PR>` / `status` / `pause` ChatOps drive the same queue/PR operations. Tickets typed in Slack become `stream:directed` Issues the loop then works.
- **5d scout** + the capability-review task: fill the queue with `stream:expansion` / `stream:capability` Issues that this loop consumes unchanged — no orchestrator change needed.
