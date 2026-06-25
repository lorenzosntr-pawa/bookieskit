# Agent Identity Setup Runbook

This runbook provisions the **BookiesKit Agent** GitHub App so the autonomous
orchestrator loop acts as a separate identity that **cannot merge to `main`**.
Merges only happen through the allowlist-guarded Slack `approve` path, which
uses a distinct owner token. Perform these steps once, on your GitHub account.

> **WARNING: secrets stay gitignored.**
> `.orchestrator/` is already in `.gitignore`. Never commit `app.pem`,
> `identity.json`, `owner-token`, or `app-token.json`. If any of these files
> ever appear in `git status` as tracked, abort immediately and rotate the
> affected credential.

---

## Step 1 — Create the GitHub App

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**.
2. Fill in:
   - **GitHub App name:** `BookiesKit Agent`
   - **Homepage URL:** `https://github.com/<your-username>/bookieskit`
   - **Webhook — Active:** **uncheck** (no webhook needed).
3. Under **Repository permissions**, set exactly:

   | Permission      | Access level      |
   |-----------------|-------------------|
   | Contents        | Read and write    |
   | Pull requests   | Read and write    |
   | Issues          | Read and write    |
   | Checks          | Read-only         |
   | Metadata        | Read-only         |

   Leave **all other permissions** (Administration, Workflows, Secrets, etc.) at
   **No access**.

4. Under **Where can this GitHub App be installed?**, select **Only on this account**.
5. Click **Create GitHub App**.

You are now on the App's General settings page. Note the **App ID** shown at
the top (you will need it in Step 3 and Step 4).

---

## Step 2 — Install the App on the bookieskit repo

1. In the App's settings page, click **Install App** in the left sidebar.
2. Click **Install** next to your account.
3. On the installation screen, select **Only select repositories** and choose
   **bookieskit**.
4. Click **Install**.

After installation, GitHub redirects you to the installation settings page.
The URL will look like:

```
https://github.com/settings/installations/<INSTALLATION_ID>
```

**Note the `<INSTALLATION_ID>` number** from the URL — you will need it in
Step 4.

---

## Step 3 — Generate the private key and save it

1. Return to the App's **General** settings page
   (Settings → Developer settings → GitHub Apps → BookiesKit Agent).
2. Scroll to **Private keys** → click **Generate a private key**.
3. A `.pem` file is downloaded automatically. Move and rename it:

```powershell
# Run from the repo root
Move-Item "$env:USERPROFILE\Downloads\bookieskit-agent.*.private-key.pem" `
          ".orchestrator\app.pem"
```

Or simply copy the file to `.orchestrator\app.pem` using Explorer.

4. The **App ID** is shown at the top of the General settings page (labelled
   "App ID"). Keep it handy for the next step.

---

## Step 4 — Write `.orchestrator/identity.json`

Create the file with your App ID and Installation ID from Steps 1–2:

```powershell
# Substitute <APP_ID> and <INSTALLATION_ID> with the real numbers
@'
{ "app_id": <APP_ID>, "installation_id": <INSTALLATION_ID> }
'@ | Set-Content -Encoding utf8 .orchestrator\identity.json
```

Example (values are illustrative):

```json
{ "app_id": 123456, "installation_id": 78901234 }
```

---

## Step 5 — Create the owner fine-grained PAT

This token is the **merge key** — it is the only credential on the machine
that can approve and merge PRs. The orchestrator loop reads it exclusively
on the Slack `approve` path.

1. Go to **GitHub → Settings → Developer settings → Fine-grained tokens →
   Generate new token**.
2. Configure:
   - **Token name:** `BookiesKit owner merge key`
   - **Resource owner:** your account
   - **Repository access:** Only select repositories → **bookieskit**
   - **Repository permissions:**

     | Permission    | Access level   |
     |---------------|----------------|
     | Contents      | Read and write |
     | Pull requests | Read and write |
     | Metadata      | Read-only      |

3. Click **Generate token** and copy the token value immediately (it is shown
   only once).
4. Save the token (a single line, no trailing newline) to
   `.orchestrator/owner-token`:

```powershell
# Paste the token where it says <PASTE_TOKEN_HERE>
"<PASTE_TOKEN_HERE>" | Set-Content -Encoding utf8 -NoNewline .orchestrator\owner-token
```

> **Keep this token secure.** Anyone who reads `.orchestrator/owner-token`
> can merge PRs to `main` on your behalf.

---

## Step 6 — Verify token minting

With `app.pem`, `identity.json`, and the `[orchestration]` extra installed,
mint a live installation token:

```powershell
# Install the orchestration extra if you have not already
.venv\Scripts\python.exe -m pip install -e ".[orchestration]" -q

# Mint a token — should print a ghs_... string
.venv\Scripts\python.exe -m bookieskit.orchestration token
```

Expected output: a single line beginning with `ghs_`. If you see
`token: not provisioned`, check that `.orchestrator/identity.json` and
`.orchestrator/app.pem` exist and are readable.

---

## Step 7 — Harden the ruleset (require 1 approving review)

Run this **once** from the repo root. It bumps the `main` branch ruleset
(`id 18116963`) so every PR requires at least one approving review before it
can merge. The App cannot approve its own PRs, so only the owner (via the
Slack `approve` path) can satisfy the gate.

```bash
# Strip read-only fields, bump required_approving_review_count to 1, PUT back.
gh api repos/:owner/:repo/rulesets/18116963 \
  | python -c "import sys,json; d=json.load(sys.stdin); [r['parameters'].__setitem__('required_approving_review_count',1) for r in d['rules'] if r['type']=='pull_request']; body={k:d[k] for k in ('name','target','enforcement','conditions','rules','bypass_actors')}; print(json.dumps(body))" \
  > /tmp/ruleset.json
gh api --method PUT repos/:owner/:repo/rulesets/18116963 --input /tmp/ruleset.json
```

Confirm the change took effect:

```bash
gh api repos/:owner/:repo/rulesets/18116963 \
  --jq '.rules[]|select(.type=="pull_request").parameters.required_approving_review_count'
```

Expected output: `1`.

---

## Step 8 — Manual never-merge proof

Run this once after completing Steps 1–7 to confirm the structural guarantee
holds end-to-end.

1. Let the loop open a PR (trigger a normal orchestration cycle), or open a
   draft PR manually as the App identity.
2. As the App, attempt to merge without an approval:

   ```bash
   # Export the App token (minted in Step 6) and try to merge
   export GH_TOKEN=$(.venv/Scripts/python.exe -m bookieskit.orchestration token)
   gh pr merge <pr-number> --squash
   ```

   **Expected result:** GitHub rejects the merge with a message similar to
   "At least 1 approving review is required by reviewers with write access."

3. In Slack, type `approve <pr-number>` from an allowlisted account.
   **Expected result:** the approve path submits an owner-token review then
   merges — the PR closes successfully.

If Step 2 succeeds (merge goes through without approval), the ruleset was not
updated correctly — re-run Step 7.

---

## Step 9 — Token rotation note

The owner fine-grained PAT saved in `.orchestrator/owner-token` is long-lived
(GitHub fine-grained PATs can be set to expire in 30, 60, 90, or 365 days, or
never). Rotate it periodically:

1. Go to **GitHub → Settings → Developer settings → Fine-grained tokens**.
2. Find `BookiesKit owner merge key` → **Regenerate**.
3. Copy the new token and overwrite `.orchestrator/owner-token`:

   ```powershell
   "<NEW_TOKEN>" | Set-Content -Encoding utf8 -NoNewline .orchestrator\owner-token
   ```

The App private key (`.orchestrator/app.pem`) does not expire automatically,
but you can rotate it at any time from the App's **Private keys** settings page
(generate a new one, update the file, then delete the old key from GitHub).

---

## Security model & operational requirements

Read this before you trust the loop to run unattended.

**The structural guarantee is conditional on two things being true:**

1. **The ruleset is flipped** (Step 7 — `required_approving_review_count: 1`).
   Until you do this, a PR with green CI merges with **no approval**, so the
   App identity *can* merge. The separation of identity buys you nothing until
   the ruleset requires a review the App cannot give itself. **Do Steps 7–8
   before relying on the structural claim.**

2. **Token minting succeeds every tick.** The tick mints a fresh App token and
   exports it as the cycle's `git`/`gh` identity. **If minting fails** — the App
   is not provisioned yet, the `.pem` is wrong/expired, or GitHub is briefly
   unreachable — the tick **falls back to the ambient `gh` login, which is your
   owner account** (`repo` scope, merge-capable). In that window the loop is
   back to today's non-structural posture (never-merge then rests only on the
   `deny` rules in `.claude/orchestrator-settings.json` + skill behaviour).
   - This fallback exists so a provisioning gap never halts the company — but a
     **persistent** mint failure silently degrades protection. After completing
     this runbook, confirm `... orchestration token` prints a `ghs_...` token,
     and watch `.orchestrator/logs/` for the line
     `App token unavailable - falling back to ambient gh login` — if you see it
     repeatedly, the loop is running **unprotected** and you must fix minting.
   - *Fast-follow (not yet built):* upgrade that fallback log line to a loud
     `#agent-activity` Slack alert so a degraded posture can't go unnoticed.

**Why `gh api` breadth is safe (once the ruleset is flipped).** The
orchestrator's permission profile still allows `Bash(gh api:*)`, so the loop
could in principle call `gh api --method PUT .../merge`. Run as the **App**,
that call still cannot satisfy the 1-approving-review ruleset, so it is blocked
— the structural gate, not the allow-list, is what stops it. This is **only**
true after Step 7; before the flip, the broad `gh api` allow combined with the
owner-identity fallback (point 2) is a real merge path. Another reason to flip
the ruleset first.

**The guarantee also leans on GitHub forbidding an App from approving its own
PR** (true today). The manual proof in Step 8 is how you verify the whole chain
end to end — re-run it after any change to the ruleset or the App's
permissions.
