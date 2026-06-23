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
