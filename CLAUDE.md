# bookieskit — operating contract

This repo is run by an autonomous **agent company**. Every Claude Code session and agent in this repo inherits this contract. North-star + sub-project specs live in `docs/superpowers/specs/`; start from `2026-06-22-agent-company-north-star.md`.

## The loop
Signal → Work → Gate → Ship. Pieces (all on `main`): CI (the gate), `bookieskit.devtools` market-add harness (work tool), live canary (signal), release automation (ship), and `bookieskit.orchestration` (the work queue on GitHub Issues + the orchestrator). The orchestrator runs `/orchestrate` (looped with `/loop /orchestrate`) — one queue item per cycle → a supervised PR.

## Cross-cutting standards (binding on all work)
- **superpowers discipline**: brainstorming before creative work → writing-plans → subagent-driven-development → systematic-debugging for bugs → verification-before-completion → requesting-code-review before merge.
- **graphify**: query the structural graph before touching code; it is the fleet's structural memory (the `memory/` dir holds decisions/goals).
- **llm-council**: for genuine stakes/tradeoffs (design A-vs-B, risky/irreversible changes) — not mechanical work.
- **Karpathy principles**: smallest surgical change, no overcomplication, surface assumptions, verifiable success criteria. Reviewer-enforced.
- **Continuous capability review**: file `stream:capability` Issues to adopt skills/MCPs that strengthen the pipeline.

## Autonomy rules (when running unattended)
- **Decide-and-document**: there is no human to answer clarifying questions during an autonomous build. Make the most reasonable assumption, proceed, and record every assumption in the PR for the supervised review. Never block on a question.
- **Supervised gate**: the loop produces PRs and NEVER merges. The owner reviews (CI must be green) and merges; auto-merge for low-risk classes is future work, unlocked only after the supervised loop is proven.
- **Surface, never swallow**: assumptions → the PR; blockers → a comment on the Issue + `status:blocked`.

## In-region constraint
Live-bookmaker operations (the canary, the scout, harness live probes, any networked agent dispatch) MUST run from an in-region environment — the African bookmakers geo-block US/cloud IPs (BetPawa returns 403). CI (offline tests/lint) and release (build + GitHub Release) are network-agnostic and run anywhere.

## Work queue conventions (`bookieskit.orchestration`)
- Streams (priority order): `stream:directed` (owner asks) > `stream:maintenance` (canary drift) > `stream:expansion` (scout) > `stream:capability` (skill adoption).
- Status: `status:claimed` (being worked) → `status:in-review` (PR open) ; `status:blocked` (needs owner input). Open/closed are native.
- Each issue body carries a fenced yaml meta block with a stable `signature` for dedup. An owner merge of a `Closes #N` PR closes the Issue.

## Build discipline
- TDD; frequent commits; conventional-commit messages.
- `src/` stays 100% ruff-clean (`ruff check .`). Run tests with `.venv/Scripts/python.exe -m pytest` locally; CI uses bare `pytest`/`ruff` on 3.11/3.12/3.13.
- Version lives in BOTH `pyproject.toml` and `src/bookieskit/__init__.py` and must stay in sync (CI enforces). Ship with `python -m bookieskit.devtools release` (promotes the CHANGELOG `[Unreleased]` section, bumps both files, tags; `--push` fires the GitHub Release).
- Library/market-facing changes get a curated `## [Unreleased]` CHANGELOG entry.

## Slack cockpit (best-effort)

The owner watches the company through a Slack workspace (the korotovsky
`slack-mcp-server` MCP — see `docs/SLACK_SETUP.md`). Three channels:

- `#agent-activity` — cycle progress: claimed → PR opened → blocked.
- `#canary-alerts` — canary drift digests (only when drift changed).
- `#releases` — release announcements.

Posting is **best-effort**: format messages with
`python -m bookieskit.orchestration notify <kind> ...` (or read `slack_text`
from `sync-canary --json`) and post via the Slack `post_message` MCP tool — but
**only if that MCP tool is available**. With no Slack MCP configured, every
loop/canary/release runs unchanged and Slack stays quiet. A notification
failure must never fail a build, block a cycle, or leave an item half-done.

## ChatOps (best-effort write path)

The cockpit is two-way. From `#tickets` the owner (or a teammate) types a work
request — it becomes a `stream:directed` Issue — and `approve <pr>` merges that
PR from Slack. Merge authority is the **allowlist** in `.chatops.json` (Slack
user IDs; non-secret, committed, change via PR) and is gated by three
guardrails: authorized author, CI green, and the PR closes a `status:in-review`
Issue. This does NOT relax the supervised gate — `approve` is the human's
decision, relocated to Slack; the agent never auto-merges.

## Directed design in Slack

Directed (`#tickets`) features are *designed with the owner before they're built*.
A request becomes a `status:designing` Issue; each cycle the orchestrator runs one
brainstorm step in the Issue's `#tickets` thread (one question at a time, llm-council
on genuine tradeoffs), converging on a design written into the Issue body. The owner
approves with `design ok <issue#>` (allowlisted) → `status:ready`; only then does a
cycle build it (using that agreed design as the spec) → PR → `approve`. `design no
<issue#> <notes>` requests changes; `council <issue#>` forces a council pass.
Maintenance/canary stay decide-and-document. The loop runs on a cheap-gate continuous
tick (`gate` decides whether to wake the agent; ~1-min cadence).

## Always-on orchestrator (unattended)

The loop can run unattended via Windows Task Scheduler (`scripts/orchestrator-tick.ps1`,
every 1 min) — see `docs/ORCHESTRATOR_SETUP.md`. Each tick runs the `gate` CLI first;
if the gate reports nothing to do (no new Slack messages, no actionable queue items),
the tick exits cheaply without waking the agent. Only when the gate returns `run: true`
does the tick take the lockfile (`.orchestrator/tick.lock`; a mid-build tick skips, a
stale lock is reclaimed) and run one headless `/orchestrate` cycle under a constrained
permission profile (`.claude/orchestrator-settings.json`: no direct `gh pr merge`, no
push to `main`). After a cycle the tick writes the gate's `newest_ts` to
`.orchestrator/slack-watermark` so already-processed messages are not re-fired.
A `pause`/`resume` Slack command (allowlist-gated, a `control:paused` marker Issue)
is the kill-switch; the cycle skips building while paused. The never-merge gate is
unchanged — merge happens only via the human-gated `chatops approve`. Recommend
GitHub branch protection on `main` as the structural backstop.
