# Slack Cockpit Visibility v2 — Design

**Date:** 2026-06-25
**Status:** Approved (pending written-spec review)
**Sub-project:** a refinement of the Slack cockpit (5c + always-on + directed-design). Umbrella: `2026-06-22-agent-company-north-star.md`.

## Problem

Slack is append-only, so the cockpit accumulates stale state: an old "⚠️ blocked" message stays after the item is unblocked, "cycle started" lingers after the PR lands, and a long build is silent between checkpoints — so the owner can't tell *current* state from scrolling, and had to cross-check GitHub. Earlier the agent also dumped verbose cycle-reasoning into `#tickets`, adding noise. The fix: a single always-current view + clean events + an on-demand snapshot.

## Scope

**In (3 components):**
1. **Live `#status` board** — ONE message in a dedicated `#status` channel that the orchestrator **edits in place** every tick (via Slack `chat.update`), so it is always current. Shows: loop active/paused, what it's doing now, the queue snapshot, last shipped, last tick time.
2. **Concise `#agent-activity` events** — the loop posts only crisp one-liners (`claimed #N`, `PR #N opened`, `blocked #N: <reason>`, `merged #N`); never the internal cycle-report reasoning.
3. **`status` command** — `status` in `#tickets` → an on-demand snapshot reply.

**Out (separate follow-ups):** conversing on / requesting changes to an already-open PR (the gap #19 surfaced); the separate-agent-identity hardening; richer block-kit formatting.

## Decisions

| Decision | Choice |
|---|---|
| Current-state view | A **dedicated `#status` channel** with ONE message, **edited in place** (`chat.update`) every tick — never appended |
| Update mechanism | The **Python layer** (a `status` CLI) calls Slack `chat.update` via the Web API (the MCP can't edit messages); the board's message id is stored in a state file |
| Cadence | The tick updates the board **every run** (idle or build) — cheap (one edited message), keeps "now/last-tick" fresh |
| Events | `#agent-activity` stays the append log but **concise only** (formatted one-liners, no cycle-report dumps) |
| On-demand | `status` `#tickets` command → snapshot reply (reuses the board's gather/render) |
| Config | `#status` channel id in `.chatops.json` (`status_channel`); board message id in `.orchestrator/status-board.json` |

## Architecture

### `bookieskit.orchestration.status` — pure render + state gather (offline-tested)

```python
def render_board(state: dict, *, now: str) -> str:
    """Pure Slack-mrkdwn for the live board from a state dict. e.g.:
    🟢 *Loop:* active · last tick 15:31
    *Now:* building #19 (probing) / designing #20 / idle
    *Queue:* #20 designing · #21 ready · canary: clean
    *Last shipped:* #18 merged"""

def gather_state(gh, *, paused: bool, now: str) -> dict:
    """Read the open queue (by status) + paused flag → the state dict
    render_board consumes. The single gh read; no Slack I/O here."""
```

`render_board` is pure (testable with a fixed state + `now`). `gather_state` does one `gh` read.

### `status` CLI + Slack edit-in-place

- A `_slack_post(method, *, token, **params)` helper (urllib POST) alongside the existing `_slack_get`, for `chat.postMessage` / `chat.update`.
- `status board [--config .chatops.json] [--state-file .orchestrator/status-board.json]`: gather → render → if a stored board message id exists, `chat.update` it; else `chat.postMessage` to `#status` and store the id. If `chat.update` fails (message gone), re-post + restore the id. Best-effort: any Slack failure is logged and skipped — never aborts the tick.
- `chatops status [--json]`: gather + render a snapshot, emit it (the skill posts it to `#tickets` on the `status` command).

### Tick + skill wiring
- `scripts/orchestrator-tick.ps1`: after the gate/cycle each tick, run `python -m bookieskit.orchestration status board` (cheap; keeps the board fresh on idle *and* build ticks).
- `chatops.parse_command`: add `status` → `StatusCommand`; the skill maps it to `chatops status` and posts the reply to `#tickets`.
- orchestrate skill: post **concise** events to `#agent-activity` only (the formatted `slack_text` lines) — explicitly NOT the cycle-report prose. (Fixes the verbose dump.)

### Config + owner setup
`#status` channel created by the owner, bot invited, its id added to `.chatops.json` as `status_channel`. Documented in `SLACK_SETUP.md`. If `status_channel` is absent, the board is skipped (best-effort) and the rest works.

## Data flow

```
each tick → status board: gather_state(gh, paused) → render_board → chat.update(#status board msg)  (or post+store id)
cycle events → concise slack_text → #agent-activity (append, one-liners)
owner types `status` in #tickets → chatops status → snapshot reply in #tickets
```

## Error handling
- **No `status_channel` / Slack down:** the board update is skipped (logged); the loop, builds, and other posts are unaffected. Best-effort, like all cockpit posts.
- **Stored board id stale** (message deleted): `chat.update` fails → re-post a fresh board + overwrite the stored id.
- **State-file unreadable:** treat as "no board yet" → post a new one.
- `status board` never raises out of the tick; a failure is a logged no-op.

## Testing approach
- **`render_board` (offline, CI):** given a state dict + `now`, asserts the mrkdwn shows loop state, current activity, queue items, last-shipped — and the paused vs active variants.
- **`gather_state` (offline, fake gh):** builds the right state dict from open issues (by status label) + the paused flag.
- **`chatops status` CLI (fake gh):** emits a snapshot; `parse_command("status")` → `StatusCommand`.
- **`_slack_post` / board update:** the Slack call is behind the injectable seam (monkeypatched in tests — no network); assert post-then-update path + the stored-id round-trip via a fake.
- **Concise events:** structural — the skill posts only formatted lines (reviewed, no pytest).
- **Live (owner-gated):** after creating `#status`, watch the board update in place each tick and `status` return a snapshot.

## Success criteria
- A single `#status` message reflects current state, **edited in place** each tick (no new messages, no staleness).
- `#agent-activity` shows only concise event one-liners (no cycle-report dumps).
- `status` in `#tickets` returns an on-demand snapshot.
- Best-effort: with no `#status` channel / Slack down, the loop runs unchanged.
- New offline tests pass; full suite + `ruff` green in CI.
- **Owner-verified (deferred):** the board stays current through an idle → build → merged sequence without the owner cross-checking GitHub.

## Reuse hooks
- `gather_state` is the single source for both the board and the `status` command — and for a future "respond on in-review PRs" flow (it already knows in-review items).
