# Collaborative Directed Design in Slack — Design

**Date:** 2026-06-25
**Status:** Approved (pending written-spec review)
**Sub-project:** Slice 1 of the "directed-work upgrade." Umbrella: `2026-06-22-agent-company-north-star.md`. Builds on the always-on orchestrator + ChatOps. **Slice 2 (graphify, for real) is a separate follow-up** and out of scope here.

## Problem

Directed features currently build **decide-and-document**: the loop guesses a design from a one-line `#tickets` request, builds it, and surfaces its assumptions only at PR-review time. The owner shapes the work *after* it's built. The owner wants to shape it *first* — the superpowers brainstorm, but in Slack: clarifying questions one at a time, the llm-council convened when there's a genuine tradeoff, converging on a design the owner approves **before** any build. The double-chance ticket showed the gap: it would have asked *"that market is already mapped for all 7 books — did you mean a variant?"* instead of building a near-no-op.

Two things block this today: (1) the runtime is a dumb 15-min poll — incompatible with a back-and-forth conversation; (2) there is no design phase — directed items go straight from `intake` to `build`.

## Scope

**In (Slice 1):**
- **Cheap-gate continuous runtime** — replace the 15-min full-cycle tick with a frequent, near-free Python gate that wakes the agent only when there's something to do (new `#tickets` message, actionable Issue, or a brainstorm reply waiting). Makes the dialogue conversational (~1-min responsiveness) without idle token burn.
- **Directed-design state machine** — a new request enters a Slack design dialogue (`status:designing`) before any build; the owner greenlights with `design ok <issue#>` → `status:ready` → a later cycle builds it following the agreed design.
- **llm-council wiring** — the agent convenes the council when it judges a genuine stakes/tradeoff and posts the recommendation to the thread for the owner.

**Out:**
- **Graphify, for real** (Slice 2 — separate; query-the-graph-before-code strengthens *all* builds, not just directed).
- Maintenance/canary stays **decide-and-document** (no brainstorm — drift fixes are mechanical).
- Event-driven Slack (Socket Mode) — the cheap-gate poll is sufficient; a true event listener is a future option.

## Decisions

| Decision | Choice |
|---|---|
| Dialogue style | Full **one-question-at-a-time** brainstorm (the owner picked A), in the ticket's `#tickets` thread; converges to a posted design |
| Runtime | **Cheap-gate continuous**: a pure-Python `should_run` gate runs every ~1 min (Slack Web API + queue, no agent); the `claude -p "/orchestrate"` cycle fires only on "yes" |
| Design→build gate | Explicit **`design ok <issue#>`** (allowlisted) → `status:ready`; the agent NEVER builds a directed item without it |
| Council | **Agent-decided** (fires on genuine stakes/tradeoff), recommendation posted to the thread; owner not bound. Optional `council <issue#>` to force it |
| States | New labels `status:designing` and `status:ready` |
| Build input | The build reads the **agreed design from the Issue body** as its spec (not a fresh decide-and-document guess) |
| Maintenance | Unchanged — decide-and-document, no design phase |

## Architecture

### 1. Cheap-gate continuous runtime — `bookieskit.orchestration.gate`

A pure-Python decision function (offline-tested) + a thin Slack read:

```python
def should_run(*, queue_actionable: bool, newest_ticket_ts: str | None,
               watermark_ts: str | None, designing_reply_waiting: bool) -> bool:
    """Wake the agent iff: an Issue is actionable (next != null), OR a #tickets
    message is newer than the watermark, OR a status:designing Issue has a new
    owner reply awaiting the agent."""
```

A `gate` CLI (`python -m bookieskit.orchestration gate --json`) gathers the inputs cheaply — reads `#tickets` history via the **Slack Web API directly** (the bot token from `.mcp.json`; no MCP, no agent), reads `next` + the `status:designing` issues via `gh` — and prints `{"run": bool, "reason": ...}` plus the current newest ts (so the caller can advance the watermark). A durable **watermark file** (`.orchestrator/slack-watermark`) records the last ts the agent processed, so restarts don't re-fire on old messages.

`scripts/orchestrator-tick.ps1` is re-pointed: each fire (now ~1 min) runs `gate`; **only if `run` is true** does it take the lock + invoke `claude -p "/orchestrate"`. The Task Scheduler interval drops from 15 min → ~1 min (the gate is cheap enough to run that often).

### 2. Directed-design state machine

The `orchestrate` cycle gains a **design phase** ahead of the build, for `stream:directed` items only:

- **Intake** (existing): a `#tickets` request → Issue, but now labeled **`status:designing`** (not immediately buildable).
- **Design step** (new, runs each cycle for a `status:designing` item that has a pending owner message): the agent reads the Issue's `#tickets` thread (the running conversation) + the codebase, then does **one** brainstorm step — posts the next clarifying question, OR (when confident) the converged design. If it judges a genuine stakes/tradeoff, it convenes **llm-council** and posts the recommendation first. It writes progress into the Issue body. Then it ends the cycle (the "wait" is the cycle ending; the cheap-gate resumes it when the owner replies).
- **Approval:** the owner replies **`design ok <issue#>`** (allowlisted) → the cycle flips the Issue to **`status:ready`** and finalizes the agreed design in the Issue body.
- **Build** (existing, now design-driven): `next` returns `status:ready` directed items; the build uses the Issue-body design as its spec → `writing-plans` → `subagent-driven-development` → PR → the owner's `approve <pr#>`.

Trivial tickets collapse naturally: when the agent is confident, its first design-step message *is* the proposed design ("here's the design — `design ok 42` to build, or tell me what to change"), so a clear ask isn't a slog.

### 3. Commands (extend `chatops.parse_command`)
- `design ok <issue#>` → `DesignOkCommand(issue)` (allowlist-gated; → `status:ready`).
- `design no <issue#> <notes>` → `DesignChangesCommand(issue, notes)` (keeps `status:designing`, feeds the notes back into the dialogue).
- `council <issue#>` → `CouncilCommand(issue)` (force a council pass).
- Existing `approve`/`pause`/`resume` unchanged. **Plain thread replies on a `status:designing` Issue are not commands** — they're brainstorm answers, attributed to the Issue by thread.

### 4. Labels
Add `status:designing` and `status:ready` to the taxonomy (ripples `test_labels.py` counts). `next_work_item`/priority treats `status:designing` as **not buildable** (it's mid-design) and `status:ready` as buildable.

## Data flow

```
scheduler (~1m) → gate (cheap: Slack Web API + gh) → run? --no--> exit
                                                    └--yes--> lock → claude -p /orchestrate
  cycle: ChatOps intake (new request → Issue status:designing; design ok/no/council/approve/pause/resume)
       → for a status:designing item with a pending owner reply: one brainstorm step
            (next question | council pass + recommendation | converged design) → post to thread → end
       → on `design ok`: status:designing → status:ready (+ finalize design in Issue body)
       → for a status:ready item: build per the agreed design → PR → owner `approve`
       → maintenance/canary: decide-and-document (unchanged)
```

## Error handling
- **No `design ok` → no build.** A directed item cannot be built while `status:designing` (priority skips it); the design gate is as strict as the merge gate, allowlist-enforced.
- **Council/Slack failure:** best-effort — a council error is surfaced in the thread and the dialogue continues; never blocks.
- **Gate failure** (Slack API down): the gate fails *safe* — if it can't read Slack, it falls back to the queue check alone (still builds `status:ready`/maintenance items; just won't detect new Slack messages until Slack recovers). Logged.
- **Watermark durability:** the last-processed ts persists in `.orchestrator/slack-watermark`; a restart doesn't re-fire on old messages or re-ask answered questions (the thread is the source of truth for the conversation).
- **Stuck design:** if the owner never replies, the item simply stays `status:designing` (the cheap-gate doesn't wake the agent for it) until they do — no spin, no timeout-build.

## Deployment note
The always-on orchestrator is already installed at a 15-min interval. Applying the cheap-gate cadence requires **re-running `install-orchestrator.ps1`** (the trigger interval is set at registration time) so the task fires ~1 min and runs the `gate` first. `install-orchestrator.ps1` is idempotent (`-Force`), so re-running it updates the existing task. Until re-installed, the merged code is dormant — the running 15-min task keeps working with the old behavior.

## Testing approach
- **`gate.should_run` (offline, CI):** each wake branch (actionable / newer-than-watermark / pending-reply) and the all-quiet → False case; injected inputs.
- **`parse_command` (offline):** `design ok <n>`, `design no <n> <notes>`, `council <n>`; still recognizes `approve`/`pause`/`resume`; plain text → None.
- **Label transition (offline, fake gh):** `status:designing` → `status:ready` on `design ok`; priority skips `designing`, picks `ready`.
- **Build-reads-design (offline):** the directed build step uses the Issue-body design as the plan input.
- **Live (owner-gated, deferred):** a real `#tickets` request runs a multi-turn Slack brainstorm, a council pass posts a recommendation, `design ok` flips to ready, and the next cycle builds the agreed design — all within the cheap-gate's ~1-min responsiveness.

## Success criteria
- The cheap-gate wakes the agent within ~1 min of a `#tickets` message / brainstorm reply, and idle ticks are near-free (no `claude` invocation when `run` is false).
- A directed request enters a Slack design dialogue (one question at a time), can convene llm-council, and does NOT build until the owner's `design ok` (allowlist-gated).
- The build follows the agreed Issue-body design; maintenance stays decide-and-document.
- New offline tests pass; full suite + `ruff` green in CI.
- **Owner-verified (deferred):** a real ticket is shaped in Slack then built as agreed.

## Reuse hooks for the next slice (graphify, for real)
- The directed **design step** is the natural place to insert "query graphify for the structural map" before drafting the design — Slice 2 wires the actual graph + that query into this step (and into the maintenance build).
- The cheap-gate's "is there anything to do?" pattern generalizes to other wake sources (scout/expansion intake) later.
