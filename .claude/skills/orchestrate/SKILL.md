---
name: orchestrate
description: Run ONE work cycle of the bookieskit agent company — read the GitHub-Issues queue, claim the top item, build it autonomously via the superpowers pipeline, open a supervised PR, and mark it in-review. Invoke directly as /orchestrate, or loop it with /loop /orchestrate. Run in-region (live-bookmaker work needs the reachable network).
---

# Orchestrate — one work cycle

You are the engineering manager of the `bookieskit` agent company. This skill runs **exactly one** work cycle and then stops. `/loop /orchestrate` repeats it.

Read the operating contract in the repo-root `CLAUDE.md` first — it binds this cycle (cross-cutting standards, autonomy rules, in-region constraint, queue conventions).

## The cycle

1. **ChatOps intake (best-effort — only if a Slack `post_message`/history MCP tool is available).** Read new `#tickets` messages (the channel id is in `.chatops.json`). For each message:
   - If it parses as `approve <pr>`: run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops approve --pr <pr> --author <slack-user-id> --json` and post the returned `slack_text` to `#tickets`. (The CLI enforces the allowlist + CI-green + loop-PR guardrails and merges with squash on success; a rejection is reported, never a merge.)
   - If it parses as `pause [reason]`: run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops pause --author <slack-user-id> --reason "<reason>" --json` and post the `slack_text` to `#tickets`.
   - If it parses as `resume`: run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops resume --author <slack-user-id> --json` and post the `slack_text` to `#tickets`.
   - If it parses as `design ok <n>`: run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops design-ok --issue <n> --author <slack-user-id> --json` and post the returned `slack_text` to `#tickets`.
   - If it parses as `design no <n> <notes>`: run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops design-no --issue <n> --author <slack-user-id> --notes "<notes>" --json` and post the returned `slack_text` to `#tickets`.
   - If it parses as `council <n>`: run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops council --issue <n> --author <slack-user-id> --json` and post the returned `slack_text` to `#tickets`.
   - Else if it's a work request: distil a short title + one-paragraph summary, run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops intake --author <slack-user-id> --ts <message-ts> --title "<title>" --summary "<summary>" --json`, and post the returned `slack_text` to `#tickets` **only when `status` is `opened`** (skip `duplicate`). The intake CLI files directed work-requests with `status:designing` automatically (so they are NOT buildable until the owner's `design ok`) — no separate labeling step is needed.
   - Else (chatter): ignore.
   If no Slack MCP is available, skip this entire step and proceed. ChatOps is never on the critical path.

1b. **Pause gate.** Run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops paused --json`. If `paused` is true → report "paused — skipping build this cycle" and END the cycle (do NOT claim or build). Intake + `approve` + `resume` above still ran; only building is gated.

1c. **Design step (directed Issues only).** Query `gh issue list --label status:designing --label stream:directed --state open --json number,title,body` to find open `status:designing` directed Issues. For the top one whose `#tickets` thread's last message is the owner's (i.e. the agent owes a reply):
   - Read the Issue's `#tickets` thread via Slack MCP (`thread_ts` = the Issue's `slack_ts` meta field in the Issue body yaml block) and the relevant codebase context.
   - Do **ONE** brainstorm step: post the next clarifying question, OR (when you have enough to converge) the complete proposed design. Reply in the Issue's thread using the Slack MCP `post_message` tool with `thread_ts` = the Issue's `slack_ts`.
   - If the design involves a genuine stakes/tradeoff (architectural choice, irreversible API decision, performance vs. simplicity), run `llm-council` first and post its recommendation as part of your reply.
   - Write the current design (or the latest question + context) into the Issue body (append/update the design section below the yaml meta block).
   - **END the cycle** immediately after this step — one design step per cycle, no building.
   - If no `status:designing` Issue needs a reply (queue empty, or last message is the agent's), skip to step 2.
   - Maintenance/canary Issues (`stream:maintenance`, `stream:expansion`, `stream:capability`) are **never** routed through the design phase — they stay decide-and-document.

2. **Pick the top item.** Run
   `.venv/Scripts/python.exe -m bookieskit.orchestration next --json`
   - If the output is `null` → report "queue empty — nothing to do" and END the cycle.
   - Otherwise parse `{number, title, stream, signature}`.
3. **Claim it.** `.venv/Scripts/python.exe -m bookieskit.orchestration claim <number>`. This sets `status:claimed` so no other cycle double-works it. Then (best-effort, see Notifications) post `cycle-started` to `#agent-activity`.
4. **Build it — autonomously — per stream:**
   - `stream:directed` with `status:ready` (design approved by owner): use the **agreed design written in the Issue body** as the spec — feed it directly to `writing-plans` instead of decide-and-document. Then `subagent-driven-development` → `requesting-code-review`. The design phase already resolved ambiguities; assumptions in the PR body should be minimal and reference the agreed design.
   - `stream:directed` without `status:ready` (should not reach here — `next` skips `status:designing` Issues): treat as blocked, `mark-blocked`, and END.
   - `stream:maintenance` (canary drift): `superpowers:systematic-debugging` → fix → TDD tests → `requesting-code-review`. Decide-and-document applies; no design phase.
   - `stream:expansion` / `stream:capability`: spec → plan → `subagent-driven-development`. Decide-and-document applies; no design phase.
   - Always: query `graphify` for the structural map before touching code; apply Karpathy principles; keep `src/` ruff-clean; TDD.
   - Work on a **per-Issue branch** (subagent-driven isolates work). NEVER commit to `main`.
5. **Open the PR** against `main`, body starting with `Closes #<number>`, summarizing what you built and listing every assumption you made for the supervised review. Then (best-effort, see Notifications) post `cycle-pr` to `#agent-activity`.
6. **Mark in-review.** `.venv/Scripts/python.exe -m bookieskit.orchestration mark-in-review <number> --pr <pr-url>`.
7. **Report** the outcome (item, branch, PR url, key assumptions) and STOP. The PR awaits the owner's approval; you do NOT merge.

## If you hit a genuine blocker

If you cannot proceed safely (e.g. a missing credential, an ambiguous requirement no reasonable assumption resolves, an external dependency you can't satisfy): run
`.venv/Scripts/python.exe -m bookieskit.orchestration mark-blocked <number> --reason "<the blocker>"`.
Then (best-effort, see Notifications) post `cycle-blocked` to `#agent-activity`.
Report it, and END the cycle. Never silently fail or merge a half-built change.

## Hard rules
- **One item per cycle.** Pick one, build one, stop.
- **Never merge.** Every cycle ends at a PR awaiting owner approval (supervised v1).
- **In-region only** for live-bookmaker work (canary/scout/harness live use); CI/release are network-agnostic.
- **Surface, never swallow.** Assumptions go in the PR; blockers go on the Issue.

## Notifications (best-effort Slack cockpit)

Post cycle progress to Slack **only if** a Slack `post_message` MCP tool is
available this session. If it is not, skip posting, note "Slack not configured
— skipping notification," and proceed — posting is NEVER on the critical path
and must never fail or delay the cycle.

When the MCP is available, post at these checkpoints (format the text with the
`notify` CLI, then call the Slack `post_message` tool):

| When | Format command | Channel |
|---|---|---|
| After step 2 (claimed), before building | `python -m bookieskit.orchestration notify cycle-started --number <n> --title "<t>" --stream <stream>` | `#agent-activity` |
| After step 4 (PR opened) | `python -m bookieskit.orchestration notify cycle-pr --number <n> --title "<t>" --pr <url>` | `#agent-activity` |
| On a blocker (mark-blocked path) | `python -m bookieskit.orchestration notify cycle-blocked --number <n> --title "<t>" --reason "<r>"` | `#agent-activity` |
| When a `sync-canary` run reports drift | read `slack_text` from `sync-canary --json`; post it **only if non-empty** | `#canary-alerts` |
| After a release is cut | `python -m bookieskit.orchestration notify release --tag <tag> --current <c> --new <n>` | `#releases` |

If a post fails (MCP error mid-cycle), record it in the cycle report and
continue — a notification failure must never fail the build or leave an item
half-processed.

## ChatOps (best-effort write path)

`#tickets` is the owner's inbox: typed work requests become `stream:directed`
Issues (attributed to the Slack author, deduped by message ts), and
`approve <pr>` merges a PR — **but only** when the author is in the
`.chatops.json` allowlist, the PR's CI is green, and the PR closes a
`status:in-review` Issue (a loop PR). The agent NEVER merges on its own; an
`approve` from Slack is the owner's decision. All of it is best-effort: with no
Slack MCP, the ChatOps step is skipped and the loop runs unchanged.
