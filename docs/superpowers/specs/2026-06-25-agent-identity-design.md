# Slice A — Separate Agent Identity (structural never-merge)

**Date:** 2026-06-25
**Status:** design — approved in brainstorming, pending spec review
**Stream:** capability (pipeline hardening)

## Problem

The autonomous orchestrator loop authenticates to GitHub as the **owner**
(`gh` is logged in as `lorenzosntr-pawa`, `repo` scope). So the loop *is* the
owner: the "never-merge" guarantee rests entirely on the `deny` rules in
`.claude/orchestrator-settings.json` plus the orchestrate skill's behaviour.
Nothing **structural** stops a runaway or mis-prompted loop from merging to
`main`.

Two concrete holes confirmed on 2026-06-25:

1. The loop's `git`/`gh` use the owner's stored credential — same identity as
   the human who is supposed to be the gate.
2. The `main` ruleset (`id 18116963`) requires a PR + green CI but
   **`required_approving_review_count: 0`** — a PR can merge with *no* approval.
   `bypass_actors: []` (good — not even admin bypasses).

## Goal

Give the loop a **separate identity that physically cannot merge**, and make
the merge gate **structural**: a PR requires an approving review the loop's
identity cannot supply, so only the owner can satisfy it.

## Decisions (from brainstorming)

- **Identity mechanism: GitHub App.** Scoped, auto-expiring (1h) installation
  tokens, revocable, no extra collaborator seat. The tick mints a fresh token
  each run; the loop's `git`/`gh` act as the App.
- **Approval model: Slack approve via a separate owner token (Model 1).** The
  loop *builds* as the App (cannot merge). The `approve <pr>` path uses a
  separate, loop-readable **owner token** to submit the approving review +
  merge — preserving today's Slack UX. The structural win: the loop's normal
  build identity can't merge; merging only happens down the allowlist-guarded
  approve path.

### Honest scope of the guarantee

Model 1 keeps a merge-capable owner token on the machine, reachable by the
approve code path. So enforcement is: **structural for all normal build
operations** (the App identity cannot merge), and **behavioural for the merge
itself** (the chatops allowlist + CI-green + loop-PR guardrails gate the owner
token). This is a deliberate trade for Slack-`approve` convenience over the
fully-airtight "owner approves on GitHub, no owner token on the machine"
alternative. Documented here so the supervised review sees the trade.

## Architecture

```
                       tick (every 1 min)
                            │
              ┌─────────────┴───────────────┐
              │  mint/refresh App token      │   python -m bookieskit.orchestration token
              │  export GH_TOKEN=<app token> │   (cached in .orchestrator/app-token.json)
              └─────────────┬───────────────┘
                            │
                   headless claude -p /orchestrate
                            │
        ┌───────────────────┴────────────────────┐
        │ build / PR ops          approve path     │
        │ (ambient GH_TOKEN        (owner token,    │
        │  = App identity)          loop-readable)  │
        │ → CANNOT merge           → review+merge    │
        └───────────────────────────────────────────┘
                            │
                  main ruleset: require 1 approving review
                  (App can't self-approve → only owner satisfies it)
```

## Components

### Owner-provisioned secrets (runbook — cannot be automated)

These require GitHub-account actions only the owner can perform. The spec ships
a precise runbook; the owner executes it once.

1. **GitHub App** "BookiesKit Agent", owned by the owner. Fine-grained repo
   permissions: **Contents R/W, Pull requests R/W, Issues R/W, Checks R,
   Metadata R** — **no Administration, no Workflows**. No webhook. Installed on
   the `bookieskit` repository only. Yields: **App ID**, **Installation ID**,
   and a downloaded **private key `.pem`**.
2. **Owner fine-grained PAT** scoped to `bookieskit`: **Contents R/W + Pull
   requests R/W** (enough to submit an approving review and squash-merge). This
   is the "merge key".
3. Secrets land **gitignored** under `.orchestrator/` (same posture as
   `.mcp.json`):
   - `.orchestrator/app.pem` — App private key
   - `.orchestrator/identity.json` — `{"app_id": <int>, "installation_id": <int>}`
   - `.orchestrator/owner-token` — the owner fine-grained PAT (single line)

### `src/bookieskit/orchestration/appauth.py` (new)

Mints a GitHub App installation token. Split for testability:

- `build_app_jwt(app_id: int, private_key_pem: str, now: int) -> str`
  — pure. Builds an RS256 JWT with claims `iat = now - 60`, `exp = now + 540`
  (9 min, under GitHub's 10-min cap), `iss = str(app_id)`. Lazy `import jwt`
  (PyJWT) inside the function so importing the module never requires the dep.
- `exchange_jwt_for_token(jwt_token: str, installation_id: int, *, http) -> dict`
  — POSTs to `https://api.github.com/app/installations/{id}/access_tokens` with
  `Authorization: Bearer <jwt>`, returns `{"token": ..., "expires_at": ...}`.
  `http` is an injectable callable (default = a urllib-backed seam, matching the
  existing `_slack_get`/`_slack_post` pattern in `cli.py`) so tests pass a fake.
- `mint_installation_token(*, app_id, private_key_pem, installation_id, now, http=...) -> dict`
  — composes the two; returns `{"token", "expires_at"}`.

### `token` CLI subcommand

`python -m bookieskit.orchestration token` — reads `identity.json` + `app.pem`,
mints a token, **caches** it to `.orchestrator/app-token.json`
(`{"token", "expires_at"}`). On each call, if the cached token has **> 2 min**
of life left it is reused (avoids minting every 1-min tick); otherwise re-mint.
Prints the bare token to stdout (for the tick to capture). Best-effort: clear
non-zero exit + stderr message on misconfiguration (missing files), never a
stack trace.

### `src/bookieskit/orchestration/gh.py` — identity-aware `_run`

- `_run(*args, token: str | None = None)` — when `token` is provided, runs the
  `gh` subprocess with `env = {**os.environ, "GH_TOKEN": token}` (copy, not
  mutate). When `None`, inherits the ambient environment (the App token the
  tick exported). Keeps `encoding="utf-8", errors="replace"` (the cp1252 fix).
- `review_approve(self, pr: int, *, token: str)` — `gh pr review <pr>
  --approve` run with the owner token.
- `merge_pr` gains an optional `token` forwarded to `_run`.
- The **approve path** (chatops approve in `cli.py`) reads
  `.orchestrator/owner-token`, then calls `review_approve(pr, token=owner)`
  followed by `merge_pr(pr, token=owner)`. All other GhRunner calls pass no
  token → App identity.

### `scripts/orchestrator-tick.ps1` — export the App identity

Before launching headless `claude` (and before any `git`/`gh` the cycle runs):

1. `$token = python -m bookieskit.orchestration token` (mint/refresh).
2. On success, `$env:GH_TOKEN = $token; $env:GITHUB_TOKEN = $token` for the
   `claude` invocation, so the loop's `gh` and `git` (over https as
   `x-access-token:<token>@github.com`) act as the App.
3. If minting fails (App not yet provisioned), **fall back to today's behaviour**
   (ambient `gh` login) and log a warning — so the loop keeps running before the
   owner finishes the runbook. ASCII-only (PowerShell 5.1 parse constraint).

Git push as the App: configure the cycle's pushes to use
`https://x-access-token:$token@github.com/<owner>/<repo>.git` (the App
installation token authenticates git over https). The
`orchestrator-settings.json` already allows `git push feat/*`.

### Ruleset hardening (one command — owner-authorised)

Flip the `main` ruleset's `pull_request` rule
`required_approving_review_count: 0 → 1`, leaving every other rule and
`bypass_actors: []` unchanged. After this:

- App opens a PR → App's own `gh pr merge` is **rejected** (no approving review,
  and GitHub forbids the author/App from approving its own PR).
- Owner Slack `approve <pr>` → owner-token `review --approve` + `merge` → merges.

The spec ships the exact `gh api --method PUT .../rulesets/18116963` payload.
Because this changes the merge gate, the owner runs it (or explicitly authorises
it) — it is **not** applied automatically by the loop.

### Dependency

Add `pyjwt[crypto]>=2.8` to a **new** `[project.optional-dependencies]`
`orchestration` extra (NOT the shipped runtime deps — the client stays
`httpx`-only). CI installs dev+orchestration. `appauth.py` lazy-imports `jwt`
so the rest of `orchestration` works without it.

## Testing

Unit (offline, no network, no real keys — use a test RSA key generated in the
test or a fixture):

- `build_app_jwt` — decodes to the expected `iss`, and `iat`/`exp` bracket the
  passed `now` within GitHub's window. (Verify with the public key.)
- `exchange_jwt_for_token` — fake `http` asserts the URL, `Bearer` header, and
  returns a canned `{token, expires_at}`; function returns it.
- token cache — a fresh (>2 min) cache file is reused (no mint call); an expired
  one triggers re-mint (seam records the call).
- `GhRunner._run` token injection — a recording fake asserts `GH_TOKEN` is set
  in `env` when `token=...`, and absent (ambient) when `token=None`. Extends the
  existing `_RecordingRun` in `tests/orchestration/test_gh.py`.
- `review_approve` / `merge_pr` — build the right argv and carry the owner token.
- approve path — selects the owner token for review+merge and the App identity
  (no token) for everything else.

Manual proof (documented in the runbook, run once after provisioning):
1. Loop (App) opens a test PR.
2. `gh pr merge` as the App → **rejected** by the ruleset (needs 1 approval).
3. Owner `approve <pr>` in Slack → review + merge → **merges**.

## Out of scope / future

- The fully-airtight model (no owner token on the machine; owner approves
  natively on GitHub + auto-merge) — deferred; revisit if Model 1's behavioural
  merge gate proves insufficient.
- Rotating/short-lived owner token — the fine-grained PAT is long-lived; note in
  the runbook to rotate periodically.

## Files

- Create: `src/bookieskit/orchestration/appauth.py`
- Create: `tests/orchestration/test_appauth.py`
- Modify: `src/bookieskit/orchestration/gh.py` (token-aware `_run`,
  `review_approve`, `merge_pr` token)
- Modify: `src/bookieskit/orchestration/cli.py` (`token` subcommand; approve path
  reads owner token + uses it for review+merge)
- Modify: `tests/orchestration/test_gh.py`, `tests/orchestration/test_cli.py`
- Modify: `scripts/orchestrator-tick.ps1` (mint + export App token, push as App)
- Modify: `pyproject.toml` (`[orchestration]` extra: `pyjwt[crypto]`)
- Modify: `.gitignore` (ensure `.orchestrator/owner-token`, `app.pem`,
  `identity.json`, `app-token.json` covered — `.orchestrator/` already ignored)
- Create: `docs/AGENT_IDENTITY_SETUP.md` (owner runbook: App, PAT, secrets,
  ruleset command, manual proof)
- Modify: `CHANGELOG.md` (`[Unreleased]` — tooling/ops change)
