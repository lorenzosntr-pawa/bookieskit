# North Star — The `bookieskit` Agent Company

**Date:** 2026-06-22
**Status:** Vision / architecture (umbrella for the project-workflow track)
**Relationship to other specs:** This is the top-level vision. Each numbered sub-project below gets its own design spec → implementation plan → execution cycle. CI (sub-project 1) is already specced in `2026-06-22-ci-pipeline-design.md`.

## The goal (in the owner's words)

> A standing "agent company" you kick off, that then runs itself on a daily cadence —
> keeping the library working as bookmakers drift, autonomously discovering and adding
> new markets / sports / bookmakers as they appear, and also working through a backlog
> of jobs *you* hand it (new bookmakers, new features), with Slack as the cockpit where
> you watch the team and run tickets.

The realistic path is a **trust ladder**, not a switch: start *supervised* (agents open
PRs, you approve), then progressively auto-merge low-risk classes (fixture refreshes,
version bumps) as confidence builds. We earn autonomy gate by gate.

## The loop, in one sentence

**Signal → Work → Gate → Ship**, on a schedule, with Slack as the human cockpit and
GitHub Issues as the durable source of truth.

## Architecture

```
                         ┌──────────────────────────────────────────┐
   Slack cockpit  ◄────► │  Slack MCP (korotovsky/slack-mcp-server)   │
   #agent-activity        └──────────────────────────────────────────┘
   #canary-alerts                        ▲   │ (read #tickets, post status)
   #tickets  (you type) ─────────────────┘   ▼
   #releases                      ┌───────────────────────────┐
                                  │  Orchestrator agent (cron) │  "the EM"
                                  └───────────────────────────┘
                                     │ reads 3 intake streams,
                                     │ prioritizes, dispatches
              ┌──────────────────────┼───────────────────────────┐
              ▼                      ▼                            ▼
   ┌──────────────────┐  ┌────────────────────┐      ┌────────────────────┐
   │ Maintenance      │  │ Expansion (scout)  │      │ Directed (you)     │
   │ canary drift →   │  │ catalog diff →     │      │ Slack #tickets →   │
   │ task             │  │ task               │      │ task               │
   └──────────────────┘  └────────────────────┘      └────────────────────┘
              └──────────────────────┴───────────────────────────┘
                                     ▼
                        GitHub Issues (durable queue, real state, PR links)
                                     ▼
                   Implementer agents (worktree isolation, TDD + harness)
                                     ▼
                        Reviewer agent  →  CI gate (pytest + ruff)
                                     ▼
                   Supervised: PR awaits owner approval in Slack
                   (later) Auto-merge for low-risk classes  →  Release automation
```

### The three intake streams (where work comes from)

1. **Maintenance (automatic).** The **live canary** hits real bookmaker endpoints on a
   schedule and asserts payload shape. When Betika/etc. drifts, it files a task. An agent
   fixes the parser + refreshes the fixture; CI gates it. *Keeps the lib working.*
2. **Expansion (automatic discovery).** A **scout** agent periodically diffs each
   bookmaker's live catalog (sports / markets / competitions) against what the lib maps.
   New offering found → task filed → handled via the **market-add harness**. *Grows
   coverage with no human prompt.*
3. **Directed (the owner's backlog).** You type in Slack `#tickets` ("add bookmaker
   Stake", "add player-props"). The orchestrator converts the message into a GitHub Issue
   and dispatches it. *You give the team work.*

### The workforce (agent roles)

- **Orchestrator ("EM")** — scheduled (cron / scheduled cloud agent). Reads the 3 streams
  (canary results, scout findings, `#tickets` via Slack MCP), de-dupes against open
  Issues, prioritizes, dispatches implementer agents, posts status to `#agent-activity`.
- **Implementer** — does one task in an isolated git worktree, TDD-first, using the
  market-add harness for the common case. Opens a PR linked to its Issue.
- **Reviewer** — code-review / verification pass before merge (can reuse the
  pr-review-toolkit agents).
- **The gate** — CI (`pytest` + `ruff`) is automated truth; canary is the drift alarm.
  Together they are what make agent merges trustworthy without a human watching every diff.

### Cockpit (Slack) — interaction surface

- **Layering:** Slack = cockpit (human I/O + visibility); **GitHub Issues = source of
  truth** (state machine: open → claimed → in-review → done; native PR linkage). Slack
  channels *mirror* Issue state; they don't *hold* it.
- **MCP:** `korotovsky/slack-mcp-server` — no admin/permission setup, works with a token
  on an owned workspace, reads channel/thread history, posts messages. **Posting is
  disabled by default** (env-gated `SLACK_MCP_ADD_MESSAGE_TOOL`); we enable it deliberately.
- **No standalone listener needed.** Two-way ChatOps is achieved by the **scheduled
  orchestrator polling `#tickets`** via the MCP (latency = poll interval, ~15–30 min,
  fine for team cadence). A real-time event listener is an optional later upgrade, not a
  prerequisite.
- **Channels:** `#agent-activity` (live feed), `#canary-alerts` (drift), `#tickets` (you
  type work + commands: `approve 88`, `status`, `pause expansion`), `#releases`.

## Roadmap (each = its own spec → plan → execution)

| # | Sub-project | Loop role | Status |
|---|---|---|---|
| 1 | **CI pipeline** | The gate (makes agent merges safe) | Specced (`2026-06-22-ci-pipeline-design.md`) |
| 2 | **Market-add harness** | Doing the work (parameterized common task) | Not started |
| 3 | **Live canary tests** | The signal (maintenance + scout share its catalog-fetch core) | Not started |
| 4 | **Release automation** | Shipping (remove last human step) | Not started |
| 5 | **Orchestration + Slack cockpit** | Ties parts into a company (orchestrator, Issues queue, Slack MCP, scout) | Not started |

Build order = dependency order: the gate first, then the work tool, then the signal,
then shipping, then the orchestration capstone that wires them together. Every
sub-project is built to be **agent-runnable**: non-interactive, machine-readable output
(JSON where a downstream agent consumes it), scriptable, no hidden prompts.

## Design principles for every sub-project

1. **Agent-runnable first.** If an agent can't invoke it headlessly and parse its result,
   it doesn't serve the loop.
2. **Supervised before autonomous.** New capability ships behind owner approval; auto-mode
   is unlocked per low-risk class once proven.
3. **Durable state in Issues, not chat.** Slack is a view; the queue is the truth.
4. **The gate is sacred.** Nothing merges that CI hasn't passed. Canary failures are
   work items, never silent.
5. **Reuse existing tooling.** korotovsky Slack MCP, pr-review-toolkit, gsd/superpowers
   skills, scheduled cloud agents — compose, don't rebuild.

## Open questions (resolved as we reach each sub-project)

- **Orchestration runtime** (sub-project 5): scheduled cloud agents vs a GitHub Actions
  `schedule` workflow vs local `/loop`. Decide when we design orchestration.
- **Auto-merge policy**: exact list of "low-risk classes" eligible for unattended merge.
  Define empirically after a few supervised cycles.
- **Scout catalog-diff storage**: how the lib records "what we currently support" for the
  diff (likely derived from the market registry + a per-bookmaker catalog snapshot).
- **Exposing `bookieskit` as an MCP** (FastMCP): possible future so the cockpit can query
  odds conversationally. Out of current scope.

## Non-goals (for the whole track, for now)

- Full unattended autonomy on day one.
- A custom Slack bot / always-on service (the MCP + scheduled poll replaces it).
- Trading/staking logic, UI dashboards beyond Slack, or multi-repo orchestration.
