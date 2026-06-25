# Always-On Orchestrator — Design

**Date:** 2026-06-25
**Status:** Approved (pending written-spec review)
**Sub-project:** the standing/scheduled orchestrator of the orchestration capstone (sub-project 5). Umbrella: `2026-06-22-agent-company-north-star.md`. Builds on 5a (queue), 5b (orchestrator skill), 5c (notifications), ChatOps (intake + approve). This is the piece that makes the loop run **unattended**.

## Problem

The supervised loop works end-to-end (proved live 2026-06-23: `#tickets` → Issue → autonomous build → PR → Slack `approve` → merge). But it only runs **while a Claude Code session is actively looping `/orchestrate` in-region**. Close the session → `#tickets` messages wait, nothing builds. The owner's expectation — "post in Slack, walk away, it gets done" — needs a **standing scheduler** that fires the one-cycle orchestrator on a cadence, unattended, with safety rails. This delivers that.

## Goals

- The orchestrator runs **every 15 minutes, unattended**, on the owner's in-region machine — draining `#tickets`, building the top queue item, opening PRs, all without the console.
- **Safety rails:** a `pause`/`resume` Slack kill-switch, a single-cycle concurrency lock (no overlapping builds) with stale-lock reclaim, a **constrained** unattended permission profile (never a blanket skip), and the **structural never-merge gate** preserved (merge only via a verified human Slack `approve`).
- **Quiet-on-empty:** no Slack noise when there's nothing to do.
- Reuses the existing one-cycle `/orchestrate` skill verbatim — the scheduler just invokes it headless.

## Non-goals

- A 24/7 always-on host that survives the machine sleeping (that's the future **Approach B** — same loop relocated to an in-region VPS; out of scope here, noted as the upgrade path).
- `status` (a queue/loop-state Slack query) — deferred fast-follow (reuse hooks noted).
- Auto-merge of low-risk classes (trust-ladder future work; merge stays human-gated).
- Changing the in-region constraint (the scheduler runs on the owner's in-region box by definition).

## Decisions

| Decision | Choice |
|---|---|
| Runtime | Owner's Windows machine; **Windows Task Scheduler** fires a thin wrapper every **15 min** |
| Cycle invocation | Headless `claude -p "/orchestrate"` in the repo dir (Slack MCP loads) — one cycle per tick, the existing skill |
| Autonomy | **Full**: each tick drains `#tickets` (intake + `approve`), then builds the top queue item of any stream → PR |
| Concurrency | A timestamped **lockfile**; a tick that fires mid-build logs "busy, skip" and exits; **stale** lock (older than the timeout) is reclaimed |
| Pause kill-switch | `pause`/`resume` Slack commands → a durable **`control:paused` marker** (a label on a sentinel "Orchestrator control" GitHub Issue — visible in GitHub, survives host changes) |
| Unattended permissions | A **constrained allowlist** (orchestration CLI + `gh` issue/PR create/label/comment + git on non-main branches + build subagents); **NOT** `gh pr merge`; never a blanket `--dangerously-skip-permissions` |
| Merge gate | **Structural**: merge reachable only via `chatops approve`, which requires a verified human Slack `approve` — holds even unattended |
| Notifications | **Quiet-on-empty**; post checkpoints (cycle-started/pr/blocked, drift, paused/resumed) only when something happened |

## Architecture

The split mirrors the rest of the system: **thin OS-level wrapper** for scheduler integration + **testable Python** for the logic (lock, pause marker, command parsing).

### `bookieskit.orchestration.runner` — lock helper (offline-tested)

Pure-ish, no Slack/network beyond the filesystem:

```python
def acquire_lock(path: str, *, stale_after_s: float, now: float) -> bool:
    """Atomically acquire the tick lock. Returns True if acquired (writes a
    lock file holding `now` + pid). Returns False if a FRESH lock is held
    (a cycle is already running). A lock older than stale_after_s is treated
    as dead and reclaimed (acquired). `now` is injected for testability."""

def release_lock(path: str) -> None:
    """Remove the lock file (idempotent — missing file is fine)."""
```

The default stale timeout is generous (a large directed build can run long) — proposed **2 hours**; configurable. `now` is injected (no `Date.now()`-style hidden clock) so the stale/fresh branches are unit-testable.

### `pause`/`resume` — ChatOps commands + durable marker

- `chatops.parse_command` extends to also recognize `pause` and `resume` (today it only parses `approve <pr>`), returning a small command object (e.g. `PauseCommand` / `ResumeCommand`).
- A pause marker on the queue: `Queue` (or a small `control` helper) gets `set_paused(reason)` / `clear_paused()` / `is_paused()` backed by a **sentinel "Orchestrator control" Issue** carrying a `control:paused` label (a new label in the taxonomy). `is_paused()` is what the cycle checks.
- A `chatops` CLI surface for the commands (so the skill can invoke them the same way as `intake`/`approve`): `chatops pause --author <id> [--reason ...]` and `chatops resume --author <id>` — authorized by the same allowlist (only an approver may pause/resume), emitting `slack_text` replies.

### orchestrate skill — pause check + command handling

The skill's **ChatOps intake step** (step 1) extends to handle `pause`/`resume` commands (allowlist-gated, like `approve`). Then, **before** the pick/claim/build steps, the cycle checks `is_paused()`: if paused, it posts nothing (or a one-time "paused — skipping" note), skips building, and ends the cycle. `resume` (processed in the intake step) clears the marker so the next tick proceeds. Intake and `approve` still run while paused (so you can resume, and ship already-built PRs); only the *build* is gated.

### `scripts/orchestrator-tick.ps1` — the scheduled wrapper (thin)

1. Acquire the lock (call the Python `runner` helper, or an equivalent inline check); if not acquired → log "busy/locked, skipping this tick" and exit 0.
2. `cd` to the repo; run `claude -p "/orchestrate"` with the **constrained permission profile** (a dedicated settings/allowlist, see below), capturing output.
3. Release the lock in a `finally`/`trap` (always, even on error/crash).
4. Append a timestamped line to a rotating log (`logs/orchestrator/tick-*.log` or similar, gitignored).

### `scripts/install-orchestrator.ps1` + `docs/ORCHESTRATOR_SETUP.md`

- Installer registers a Windows Task Scheduler job: trigger every 15 minutes, action = run `orchestrator-tick.ps1`, "run only when machine is on," (owner picks run-whether-logged-on). Idempotent (updates if exists).
- The doc covers: prerequisites (the Slack MCP wired per `SLACK_SETUP.md`, `gh` auth present, `.chatops.json` filled), how to install/uninstall the task, where the logs are, how to `pause`/`resume` from Slack, and the known limitation (runs only while the machine is on → future in-region VPS upgrade).

### Constrained unattended permission profile

The headless tick must act without prompts (no human to approve each command) yet stay safe. A dedicated allowlist (Claude Code settings / `--allowedTools` or a permission-mode config for the tick) permits exactly:
- `python -m bookieskit.orchestration ...` and `python -m bookieskit.devtools ...`
- `gh issue ...`, `gh pr create|view|checks|comment|edit` (create/inspect — **not** `merge`), `gh label ...`
- `git` on non-`main` branches (branch/add/commit/push of feature branches), never a push to `main`
- the build subagents (the superpowers pipeline)

It explicitly does **NOT** grant the agent a direct `gh pr merge` tool, nor pushes to `main`. The only merge route is *inside* the allowlisted `chatops approve` CLI: when the agent runs `python -m bookieskit.orchestration chatops approve ...` (permitted), that process verifies a human Slack `approve` against the allowlist + guardrails and only then runs `gh pr merge` **as its own subprocess** (not an agent tool call). So the agent can never merge directly; merge happens solely through the human-gated CLI path. Distinguishing "agent may run the orchestration CLI" from "agent may directly invoke `gh pr merge`" is what keeps the never-merge-without-a-human invariant structural even unattended. (The plan pins the exact allowlist mechanism Claude Code supports for headless runs.)

## Data flow per tick

```
Task Scheduler (every 15m)
  → orchestrator-tick.ps1
      → acquire_lock()  ── held & fresh? → log "skip", exit 0
      → claude -p "/orchestrate"  (constrained perms, repo dir, MCP loaded)
          → [skill] ChatOps intake: #tickets → intake / approve / pause|resume   (allowlist-gated)
          → is_paused()? → yes: post nothing, skip build, end
          → no: next → claim → build (decide-and-document) → PR → mark-in-review
          → post checkpoints to Slack (quiet on empty)
      → release_lock()  (finally)
      → append rotating log
```

## Error handling

- **Overlapping ticks:** the lock makes a mid-build tick a clean no-op (logged). A genuinely hung build is bounded by the **stale-lock timeout** → the next tick after the timeout reclaims and proceeds.
- **Crash mid-tick:** each tick is an isolated headless session; the `finally` releases the lock; the next tick starts clean. No poisoned long-lived state.
- **Slack MCP absent / Slack down:** ChatOps + notifications are best-effort (existing contract) — the cycle still builds from the GitHub queue; Slack just stays quiet.
- **Paused:** builds are skipped (logged + optional one-time note); the loop keeps ticking cheaply until `resume`.
- **Permission/merge safety:** the constrained profile + structural never-merge mean the worst unattended outcome is *PRs awaiting review*, never bad code on `main`. A blanket skip-permissions is explicitly rejected.
- **Logs:** every tick appends an outcome line (acquired/skipped/built #N/blocked/paused/error) for post-hoc debugging.

## Testing approach

- **`runner.acquire_lock`/`release_lock` (offline, CI):** acquire on free lock; skip on fresh lock; reclaim on stale lock (inject `now`); release is idempotent.
- **`pause`/`resume` (offline, CI):** `parse_command` recognizes `pause`/`resume` and still recognizes `approve`/rejects chatter; `set_paused`/`is_paused`/`clear_paused` against a fake `gh` (sentinel-issue + `control:paused` label); the cycle-skip-when-paused logic (a thin testable predicate).
- **`chatops pause`/`resume` CLI (offline, fake gh):** authorized vs not-authorized; marker set/cleared; `slack_text` replies.
- **The `.ps1` wrapper + Task Scheduler:** not unit-tested (OS integration); validated by the owner running it (and a dry-run that locks + invokes a no-op). The testable logic lives in Python by design.
- **Live unattended (owner-gated, deferred):** after install, watch several real ticks — confirm `#tickets` drains, a build runs and opens a PR, `pause` halts new builds, `resume` restarts, and quiet-on-empty holds.

## Success criteria

- A Task Scheduler job runs `claude -p "/orchestrate"` every 15 min via `orchestrator-tick.ps1`, with lock-based no-overlap + stale reclaim.
- `pause`/`resume` from `#tickets` (allowlisted) durably halt/restart autonomous building; the cycle checks the marker and skips builds when paused.
- The unattended run uses a **constrained allowlist** (no `gh pr merge`, no push to `main`); merge still requires a human Slack `approve`.
- Quiet-on-empty; logs written per tick.
- New Python logic (lock, pause marker, command parsing, CLI) unit-tested; full suite + `ruff` green in CI.
- **Owner-verified (deferred):** unattended ticks drain `#tickets` / build / await approve / honor pause — with the console closed.

## Reuse hooks for the deferred slices

- **`status`** (next fast-follow): reuse `Queue.list_open` + priority view + a reply formatter → a `chatops status` command answering "what's the loop doing / queue depth / is it paused" in Slack. The `parse_command` extension here makes adding it a one-liner.
- **In-region 24/7 host (Approach B):** the same `orchestrator-tick.ps1` logic + a cron equivalent on an always-on in-region box; only the scheduler integration changes, not the cycle or the safety logic.
