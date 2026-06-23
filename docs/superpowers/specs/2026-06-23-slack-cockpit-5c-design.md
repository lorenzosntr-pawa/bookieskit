# Orchestration 5c — Slack Cockpit (notifications) — Design

**Date:** 2026-06-23
**Status:** Approved (pending written-spec review)
**Sub-project:** 5c of the orchestration capstone (sub-project 5). Umbrella: `2026-06-22-agent-company-north-star.md`. Builds on 5a (queue) + 5b (orchestrator). This is the **notifications** slice; the **ChatOps** slice (read `#tickets` → Issues, `approve`/`status`/`pause`) is the immediate next sub-project (5c-chatops).

## Problem

The supervised loop runs (5b) but is invisible — the owner has to watch a terminal or GitHub to know what the company is doing. The owner wants a **Slack cockpit**: a live feed of what the agents are working on (which item, which step, the PR opened, any drift/blocker, releases). 5c delivers that visibility. (The write path — typing a request in Slack and having the loop build it — is the next slice; this spec wires the read-only-from-Slack's-view feed.)

## Execution model

The cockpit is the orchestrator (Claude Code) **using the korotovsky Slack MCP** — "post to a channel" is an MCP `post_message` tool call the skill makes. 5c is therefore: **thin offline-tested Python formatters** (message text) + **skill/contract additions** (post at checkpoints, best-effort) + a **setup doc**. No custom Slack bot/service. Notifications are **best-effort**: if the Slack MCP is not configured, the loop/canary/release still run; Slack simply stays quiet.

## Goals

- A live `#agent-activity` feed showing cycle **progress checkpoints**: claimed → building → PR opened (and blocked).
- `#canary-alerts` drift digests; `#releases` announcements.
- All posting **best-effort / degrade-if-absent** — never a hard dependency on Slack.
- Consistent, tested message formatting (pure Python `notify` formatters).
- A precise **owner setup doc** for the workspace, bot token, channels, and MCP registration.

## Non-goals

- ChatOps: reading `#tickets` → filing Issues, and `approve`/`status`/`pause` commands (the next slice).
- A custom Slack bot/app/event-listener (the korotovsky MCP + the orchestrator's calls replace it).
- Block-kit/rich formatting beyond Slack mrkdwn text (YAGNI).
- The scout (5d).

## Decisions

| Decision | Choice |
|---|---|
| Mechanism | korotovsky Slack MCP; the orchestrate skill posts via the MCP `post_message` tool |
| Formatting | Pure `bookieskit.orchestration.notify` formatters (offline-tested); the skill/CLIs produce the text, the agent posts it |
| Dependency | **Best-effort**: post only if the Slack MCP is available; otherwise skip + log. The loop never hard-depends on Slack |
| Feed detail | Progress checkpoints (claimed → building → PR opened) + blocked, not just a final summary |
| Channels | `#agent-activity` (cycle feed), `#canary-alerts` (drift), `#releases` |
| Setup | Owner-run, documented in `docs/SLACK_SETUP.md`; live verification owner-gated |

## Architecture

### `bookieskit.orchestration.notify` — pure formatters (offline-tested)

Slack-mrkdwn message builders; no I/O:

```python
def cycle_started(number: int, title: str, stream: str) -> str:
    """e.g. ":hammer: *Cycle started* — #42 [directed] add Stake bookmaker" """

def cycle_pr(number: int, title: str, pr_url: str) -> str:
    """e.g. ":white_check_mark: *PR opened* for #42 add Stake — <pr_url>
    (awaiting review)" """

def cycle_blocked(number: int, title: str, reason: str) -> str:
    """e.g. ":no_entry: *#42 blocked* — add Stake: <reason>" """

def cycle_empty() -> str:
    """e.g. ":zzz: Queue empty — nothing to do this cycle." (optional post)"""

def canary_digest(opened: list[str], updated: list[str],
                  closed: list[str], sport: str) -> str:
    """e.g. ":warning: *Canary (soccer)* — 1 new drift, 0 persisting, 2 recovered
    \n• opened: canary:betika:structure ..." Returns "" when nothing changed
    (caller skips posting an empty digest)."""

def release_announcement(tag: str, current: str, new: str) -> str:
    """e.g. ":package: *Released vX.Y.Z* (0.16.0 -> 0.17.0)" """
```

The stream value is humanized (`stream:directed` → `directed`).

### How the text reaches Slack

The Slack MCP is a **Claude Code tool**, callable only by the agent — not by Python. So Python *formats*; the agent *posts*. Two integration points:

1. **Cycle checkpoints + release** (the agent): a small CLI formats, the agent posts. Add `python -m bookieskit.orchestration notify <kind> ...` with scalar args:
   - `notify cycle-started --number N --title T --stream S`
   - `notify cycle-pr --number N --title T --pr URL`
   - `notify cycle-blocked --number N --title T --reason R`
   - `notify release --tag vX.Y.Z --current C --new N`
   Each prints the formatted text on stdout; the agent passes it to the Slack MCP `post_message` (`#agent-activity` for the cycle kinds, `#releases` for release). Release uses the `notify` CLI (not a `slack_text` field on `devtools release`) because `devtools` must NOT import `orchestration` — `orchestration` already imports `devtools.canary`, so the reverse would be a circular import.
2. **Canary** (already emits JSON, and lives in `orchestration`): `sync-canary --json` gains a `"slack_text"` field built via `canary_digest` (a within-package import — no layering issue). The maintenance step posts it to `#canary-alerts` only when non-empty (i.e. there was a drift change).

### Skill / contract additions

- **`orchestrate` skill** — after `claim`, post `cycle-started` to `#agent-activity`; after the PR opens, post `cycle-pr`; on a blocker, post `cycle-blocked`. **Best-effort**: the skill first checks whether a Slack `post_message` MCP tool is available; if not, it skips posting and notes "Slack not configured — skipping notification" (the cycle proceeds regardless). Posting is never on the critical path.
- **`CLAUDE.md`** — a short "Slack cockpit" section: the three channels, the best-effort rule, and the checkpoint convention.
- **Release** path — when a release is cut (`release --push`), post the `release_announcement` to `#releases` (best-effort).

### `docs/SLACK_SETUP.md`

Exact owner steps (this is the gated prerequisite):
1. Create a Slack workspace (or use an existing one); invite the people who'll use it (owner + teammates).
2. Create the channels: `#agent-activity`, `#canary-alerts`, `#releases`.
3. Obtain a Slack token for the korotovsky MCP (per its README — a user/bot token; no admin needed).
4. Register the korotovsky `slack-mcp-server` in Claude Code's MCP settings (stdio), with `SLACK_MCP_ADD_MESSAGE_TOOL` set so the **post** tool is enabled (it is off by default).
5. Verify: in an in-region session, run one `/orchestrate` cycle (or `sync-canary`) and confirm messages land in the channels.

## Error handling

- **Slack MCP absent/unconfigured**: the skill detects no `post_message` tool and skips posting (logs a one-line note). The loop, canary, and release are unaffected — Slack is purely additive.
- **A post fails** (MCP error mid-cycle): the skill records it and continues the cycle (a notification failure must never fail the build or leave an item half-processed). Surfaced in the cycle report, not swallowed.
- **`notify` CLI**: pure formatting, no network; cannot fail on Slack grounds.

## Testing approach

- **`tests/orchestration/test_notify.py` (offline, in CI):** each formatter — `cycle_started`/`cycle_pr`/`cycle_blocked` produce the expected mrkdwn with the humanized stream and the PR url; `canary_digest` lists opened/updated/closed signatures and returns `""` when all three are empty; `release_announcement` formats the tag + version transition. CLI `notify <kind>` (incl. `release`) arg parsing + output + exit codes. `sync-canary --json` includes a `slack_text` field equal to the `canary_digest` text (empty string when no drift change).
- **Live posting (owner-gated, deferred):** after the owner completes `SLACK_SETUP.md`, a single `/orchestrate` cycle and a `sync-canary` run post real messages to the channels — the acceptance test for the MCP wiring. Not a CI test (no live Slack in CI; the MCP isn't connected there).

## Success criteria

- `notify` formatters + CLI exist (incl. the `release` kind) and are unit-tested; `sync-canary --json` includes `slack_text`.
- The `orchestrate` skill posts `cycle-started`/`cycle-pr`/`cycle-blocked` to `#agent-activity` **best-effort** (skips cleanly when the Slack MCP is absent — verifiable by running a cycle with no MCP configured: it completes normally, no Slack error).
- `CLAUDE.md` has the Slack cockpit section; `docs/SLACK_SETUP.md` documents the full owner setup.
- New tests pass; full suite + `ruff check .` green in CI.
- **Owner-verified (deferred):** with the MCP registered, a cycle/canary run posts the expected messages to the channels.

## Reuse hooks for the ChatOps slice (next)

- **Read path**: the same korotovsky MCP exposes channel-history tools; the ChatOps slice adds an intake step to the `orchestrate` cycle that reads new `#tickets` messages, turns each into a `stream:directed` `WorkItem` via the 5a `Queue` (attributing the Slack author), and handles `approve <pr>` / `status` / `pause` commands. The `notify` formatters here are reused for the replies.
- **Multi-person**: because the cockpit is a shared workspace, any member posting in `#tickets` is a valid requester; the attribution carries into the Issue body's meta.
