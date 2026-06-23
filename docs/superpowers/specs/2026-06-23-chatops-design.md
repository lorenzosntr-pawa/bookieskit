# Orchestration 5c-ChatOps — Slack ChatOps (intake + approve) — Design

**Date:** 2026-06-23
**Status:** Approved (pending written-spec review)
**Sub-project:** the ChatOps slice of the orchestration capstone (sub-project 5). Umbrella: `2026-06-22-agent-company-north-star.md`. Builds on 5a (queue), 5b (orchestrator), 5c (Slack notifications, the read-less feed). This slice adds the **write path**: the owner drives the company *from* Slack.

## Problem

5c made the company **visible** in Slack (the `#agent-activity` / `#canary-alerts` / `#releases` feed). But the owner still has to leave Slack to act — file work on GitHub, approve/merge PRs in the GitHub UI. The north-star cockpit is the owner opening a session ("the office opens") and from Slack: **adding work by typing it** ("add bookmaker X") and **approving/merging PRs**. This slice delivers exactly those two write capabilities, keeping Slack as the control plane.

This does **not** relax the supervised gate. The agent still NEVER auto-merges; `approve` is the **human's** decision, just relocated from the GitHub UI to Slack (with an allowlist + guardrails). True auto-merge of low-risk classes remains separate future work on the trust ladder.

## Scope

**In (scope B):**
- **Intake** — read new `#tickets` messages, turn each work-request into a `stream:directed` GitHub Issue (attributed to the Slack author).
- **Approve** — `approve <pr>` in `#tickets` merges that PR (allowlist + guardrails), closing its Issue.

**Deferred (fast-follow, same infrastructure):** `status` (queue/loop state → Slack) and `pause`/`resume` (loop kill-switch). Reuse hooks noted at the end.

**Out:** auto-merge of low-risk classes (trust-ladder future work); a custom Slack bot/service (the korotovsky MCP + the orchestrator's calls remain the mechanism); the scout (5d).

## Execution model

ChatOps is **folded into the `/orchestrate` cycle**: each cycle gains a **ChatOps intake step at the top** (read `#tickets` → file Issues + handle `approve`), then proceeds to the existing pick-one / build-one. One loop (`/loop /orchestrate`) does everything — matching the owner's "open a session, the office opens" model. **Best-effort:** if no Slack MCP is available, the ChatOps step is skipped entirely and the loop/canary/release run unchanged (identical contract to 5c). Trade-off accepted: during a long build, commands wait until the next cycle boundary (a few minutes); a dedicated fast intake loop is a future option if responsiveness ever bites.

The same split as 5c: **pure/offline-tested Python + a CLI** for the deterministic, side-effecting work; **agent-side skill prose** for the MCP interaction and the LLM judgment (classify a message, distil a title/summary).

## Decisions

| Decision | Choice |
|---|---|
| Scope | Intake + `approve <pr>` (status/pause deferred) |
| Execution | Folded into the `/orchestrate` cycle, best-effort (skip if no MCP) |
| Authorization (`approve`) | **Allowlist** of approver Slack user IDs; intake open to any channel member |
| Guardrails (`approve`) | (1) author in allowlist, (2) PR CI green, (3) PR is loop-created (`Closes #N` to a `status:in-review` Issue) |
| Allowlist + channel store | A committed, reviewable config (Slack user IDs + `#tickets` channel ID are non-secret); the bot token stays in `.mcp.json` |
| Intake idempotency | Dedup by signature `directed:slack:<ts>` checked across **open + closed** Issues; reply only on newly `opened` (no watermark store) |
| Merge method | Squash (consistent with 5a/5b/5c merges) |
| Replies | Slack-mrkdwn reply formatters (same style as the 5c `notify` formatters) |

## Architecture

### `bookieskit.orchestration.chatops` — pure helpers (offline-tested)

No I/O; deterministic and testable:

```python
def ticket_signature(ts: str) -> str:
    """e.g. "directed:slack:1718900000.000100" — the dedup key for a ticket."""

def build_ticket(author: str, ts: str, title: str, summary: str) -> WorkItem:
    """A stream:directed WorkItem: signature=ticket_signature(ts),
    meta={"requester": author, "slack_ts": ts}; summary carries the request +
    an attribution line."""

def parse_command(text: str) -> ApproveCommand | None:
    """Detect an `approve <pr>` command (pr int). Returns None for anything
    else (work-requests and chatter are not commands)."""

def is_authorized(author: str, approvers: tuple[str, ...]) -> bool:
    """author is in the approver allowlist."""

# Slack-mrkdwn reply formatters (same style as notify):
def queued(number: int, title: str) -> str: ...
def merged(pr: int, number: int) -> str: ...
def rejected(pr: int, reason: str) -> str: ...
```

### `GhRunner` — new PR operations (injected/faked in tests)

```python
def pr_checks(self, pr: int) -> str:        # overall CI conclusion: "success" / other
def pr_view(self, pr: int) -> dict:         # {state, body, closes: [int], ...}
def merge_pr(self, pr: int, *, method: str = "squash") -> None:
```

`pr_view` exposes the PR's state, body, and the Issue number(s) it closes (from `Closes #N`) — enough to enforce the loop-created guardrail.

### `chatops` CLI (two subcommands, the `slack_text`-emitting pattern from `notify`)

- `chatops intake --author U --ts T --title "..." --summary "..." [--json]` — files a `stream:directed` Issue via `Queue` with signature `directed:slack:T`; **idempotent** (skip if the signature exists in any open *or* closed Issue). Prints the result (`opened #N` / `duplicate`) and a `slack_text` reply (the `queued` formatter) — empty when `duplicate`.
- `chatops approve --pr N --author U [--json]` — runs authorization + guardrails, merges on success, marks the Issue. Prints the outcome (`merged` / `rejected: <reason>`) and the corresponding `slack_text` reply.

Both follow the `notify`/`sync-canary` precedent: deterministic, `--json`, injected `gh` seam → fully offline-tested. The approver allowlist is read from the committed config.

### orchestrate skill — the ChatOps intake step

A new first step in `The cycle` (best-effort, gated on the Slack MCP being present):
1. Read new `#tickets` messages via the Slack MCP (newer than the last processed; bounded lookback).
2. For each message, the agent classifies: **`approve <pr>` command** → `chatops approve`; **work-request** → distil a clean title + summary, `chatops intake`; **chatter** → ignore.
3. Post each command/intake's `slack_text` reply to `#tickets` (reply only on a newly `opened` ticket / a real approve outcome).
Then the existing pick-one / build-one proceeds. If no Slack MCP: skip the whole step, note it, continue.

### Config

A committed, reviewable config file (non-secret) holds the approver Slack-user-ID allowlist and the `#tickets` channel ID. The bot token remains in `.mcp.json` (gitignored). Auditable "who can merge to `main`" therefore lives in git and changes via PR.

## Data flow

**Intake:** `#tickets` message → agent classifies + distils title/summary → `chatops intake` → `Queue.open_or_update(build_ticket(...))` deduped by `directed:slack:<ts>` (open+closed) → `opened #N` → `queued` reply to `#tickets`. Re-reading the same message (or one whose Issue is already closed) → `duplicate` → no new Issue, no re-reply.

**Approve:** `approve N` by author U → `chatops approve --pr N --author U` → (1) `is_authorized(U, approvers)` → (2) `pr_checks(N)` green → (3) `pr_view(N)` closes an Issue currently `status:in-review` → `merge_pr(N, method="squash")` → the `Closes #N` auto-closes the Issue → `merged` reply. Any failed check → `rejected: <reason>` reply, no merge.

## Error handling

- **No Slack MCP / unconfigured:** the ChatOps step is skipped (logged one line); the loop, canary, and release are unaffected — identical best-effort contract to 5c.
- **Chatter / unparseable message:** ignored — no Issue, no crash.
- **Re-read message / already-built ticket:** idempotent via the cross-state signature check — no duplicate Issue, no re-reply.
- **`approve` guardrail failure** (not authorized / CI not green / not a loop PR): posted to `#tickets` as `rejected: <reason>`; **never merges**; the cycle continues.
- **gh / merge operational error:** surfaced as a reply and the cycle continues — never crash the cycle, never silently swallow.

## Testing approach

- **`tests/orchestration/test_chatops.py` (offline, CI):** the pure helpers — `ticket_signature` format; `build_ticket` (stream, signature, requester meta); `parse_command` (recognizes `approve 12`, rejects work-requests/chatter); `is_authorized`; the three reply formatters.
- **CLI tests (injected fake `GhRunner`):** `intake` opens once and is idempotent on re-run (and across a closed Issue with the same signature); `approve` each rejection path (not-authorized, CI-not-green, non-loop-PR — asserting **no** `merge_pr` call) and the success path (asserting `merge_pr` called once with `method="squash"` + the `merged` reply text). The Issue closes via the PR's `Closes #N` on merge (GitHub side) — `approve` issues no separate close call.
- **Live Slack read/post (owner-gated, deferred):** in-region, after the cockpit is wired — a real `#tickets` message becomes an Issue and a real `approve` merges a green loop PR. Not a CI test (no live Slack/MCP in CI).

## Success criteria

- `chatops` pure helpers + the `intake`/`approve` CLI exist and are unit-tested offline; new `GhRunner` PR ops are faked in tests.
- A `#tickets` work-request files a `stream:directed` Issue attributed to the Slack author, idempotently; `approve <pr>` merges only when the author is allowlisted **and** CI is green **and** the PR is a loop PR — otherwise it posts a clear rejection and does not merge.
- The orchestrate skill runs the ChatOps intake step best-effort (skips cleanly with no MCP — the cycle completes normally, no error).
- New tests pass; full suite + `ruff check .` green in CI.
- **Owner-verified (deferred):** with the MCP wired, a typed `#tickets` request builds and an `approve` merges, both from Slack.

## Reuse hooks for the deferred status/pause slice

- **`status`** reuses `Queue.list_open` + the `next`/priority view and a new reply formatter — a read-only digest of the queue/loop state posted to `#tickets`.
- **`pause`/`resume`** sets/clears a durable flag the cycle checks at the top before claiming work (Issues-as-source-of-truth: a `control:paused` marker, exact store decided in that slice's plan). The allowlist + `parse_command` extend to cover these commands.
