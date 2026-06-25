# Separate Agent Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the autonomous loop a GitHub App identity that cannot merge, and route Slack `approve` through a separate owner token, so never-merge is structural for all normal build operations.

**Architecture:** The tick mints a short-lived GitHub App installation token (`appauth.py` + `token` CLI), exports it as `GH_TOKEN` so the loop's `git`/`gh` act as the App. `gh.py`'s `_run` gains a per-call `token` override; the chatops approve path reads a separate owner token and uses it for `pr review --approve` + `pr merge`. The `main` ruleset is bumped to require 1 approving review (owner-run command) — the App can't self-approve, so only the owner satisfies the gate.

**Tech Stack:** Python 3.11+, `gh` CLI, PyJWT (`pyjwt[crypto]`, new `[orchestration]` extra), urllib, PowerShell 5.1 (tick).

## Global Constraints

- `src/` stays 100% ruff-clean (`ruff check .`). Run tests with `.venv/Scripts/python.exe -m pytest`.
- The **shipped client dependency surface stays `httpx`-only** — `pyjwt[crypto]` goes ONLY in the new `[project.optional-dependencies].orchestration` extra. `appauth.py` must **lazy-import `jwt`** inside functions so importing the module never requires the dep.
- Preserve the cp1252 fix in every `gh`/`git` subprocess: `encoding="utf-8", errors="replace"`.
- Secrets live gitignored under `.orchestrator/` (already ignored) — never commit `app.pem`, `identity.json`, `owner-token`, `app-token.json`.
- PowerShell tick script is **ASCII-only** (5.1 parse constraint — no em-dashes/emoji/smart quotes).
- The loop NEVER auto-merges; the approve path stays allowlist + CI-green + loop-PR gated. Do not relax those checks.
- TDD; frequent commits; conventional-commit messages.

---

### Task 1: `appauth.py` — App JWT, token exchange, freshness check

**Files:**
- Create: `src/bookieskit/orchestration/appauth.py`
- Create: `tests/orchestration/test_appauth.py`
- Modify: `pyproject.toml` (add `[orchestration]` extra)

**Interfaces:**
- Produces:
  - `build_app_jwt(app_id: int, private_key_pem: str, now: int) -> str`
  - `exchange_jwt_for_token(jwt_token: str, installation_id: int, *, http=_http_post) -> dict`
  - `mint_installation_token(*, app_id: int, private_key_pem: str, installation_id: int, now: int, http=_http_post) -> dict` → `{"token", "expires_at"}`
  - `token_is_fresh(cached: dict, now: float, *, min_life_s: int = 120) -> bool`
  - `_http_post(url: str, *, bearer: str) -> dict` (default injectable HTTP seam)

- [ ] **Step 1: Write the failing test**

```python
# tests/orchestration/test_appauth.py
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from bookieskit.orchestration import appauth


@pytest.fixture
def keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv, pub


def test_build_app_jwt_has_expected_claims(keypair):
    priv, pub = keypair
    tok = appauth.build_app_jwt(123, priv, now=1000)
    decoded = jwt.decode(
        tok, pub, algorithms=["RS256"], options={"verify_exp": False}
    )
    assert decoded["iss"] == "123"
    assert decoded["iat"] == 940      # now - 60 (clock-skew slack)
    assert decoded["exp"] == 1540     # now + 540 (under GitHub's 10-min cap)


def test_exchange_posts_bearer_jwt_to_installation_endpoint():
    calls = {}

    def fake_http(url, *, bearer):
        calls["url"] = url
        calls["bearer"] = bearer
        return {"token": "ghs_abc", "expires_at": "2026-06-25T16:00:00Z"}

    out = appauth.exchange_jwt_for_token("JWT", 999, http=fake_http)
    assert out["token"] == "ghs_abc"
    assert calls["url"].endswith("/app/installations/999/access_tokens")
    assert calls["bearer"] == "JWT"


def test_mint_composes_jwt_and_exchange(keypair):
    priv, _ = keypair
    seen = {}

    def fake_http(url, *, bearer):
        seen["bearer_is_jwt"] = bearer.count(".") == 2  # header.payload.sig
        return {"token": "ghs_xyz", "expires_at": "2026-06-25T16:00:00Z"}

    out = appauth.mint_installation_token(
        app_id=1, private_key_pem=priv, installation_id=2, now=1000,
        http=fake_http,
    )
    assert out == {"token": "ghs_xyz", "expires_at": "2026-06-25T16:00:00Z"}
    assert seen["bearer_is_jwt"]


def test_token_is_fresh_true_when_far_from_expiry():
    cached = {"token": "t", "expires_at": "2026-06-25T16:00:00Z"}
    # expiry = 2026-06-25T16:00:00Z = 1782403200; now well before it
    assert appauth.token_is_fresh(cached, now=1782403200 - 600) is True
    assert appauth.token_is_fresh(cached, now=1782403200 - 60) is False  # <120s
    assert appauth.token_is_fresh({"expires_at": "bad"}, now=0) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_appauth.py -v`
Expected: FAIL (`ModuleNotFoundError: bookieskit.orchestration.appauth`)

- [ ] **Step 3: Write minimal implementation**

```python
# src/bookieskit/orchestration/appauth.py
"""Mint GitHub App installation tokens so the autonomous loop acts as the App
(an identity the main ruleset bars from merging), not as the owner.

Split for testability: a pure JWT builder, an injectable HTTP exchange seam
(mirrors cli.py's _slack_post urllib seam), and a freshness predicate the token
cache uses. PyJWT is lazy-imported inside build_app_jwt so importing this module
never requires the [orchestration] extra.
"""

import datetime
import json
import urllib.request

_API = "https://api.github.com"


def build_app_jwt(app_id: int, private_key_pem: str, now: int) -> str:
    import jwt  # lazy: only needed when actually minting

    payload = {"iat": now - 60, "exp": now + 540, "iss": str(app_id)}
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def _http_post(url: str, *, bearer: str) -> dict:
    req = urllib.request.Request(
        url,
        data=b"",
        method="POST",
        headers={
            "Authorization": "Bearer " + bearer,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def exchange_jwt_for_token(jwt_token: str, installation_id: int, *, http=_http_post) -> dict:
    url = f"{_API}/app/installations/{installation_id}/access_tokens"
    return http(url, bearer=jwt_token)


def mint_installation_token(
    *, app_id: int, private_key_pem: str, installation_id: int, now: int, http=_http_post
) -> dict:
    jwt_token = build_app_jwt(app_id, private_key_pem, now)
    resp = exchange_jwt_for_token(jwt_token, installation_id, http=http)
    return {"token": resp["token"], "expires_at": resp["expires_at"]}


def token_is_fresh(cached: dict, now: float, *, min_life_s: int = 120) -> bool:
    try:
        exp = (
            datetime.datetime.strptime(cached["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=datetime.timezone.utc)
            .timestamp()
        )
    except (KeyError, ValueError, TypeError):
        return False
    return exp - now > min_life_s
```

Add the extra to `pyproject.toml` under `[project.optional-dependencies]`:

```toml
orchestration = [
    "pyjwt[crypto]>=2.8",
]
```

- [ ] **Step 4: Install the extra + run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pip install -e ".[orchestration]" -q`
Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_appauth.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/orchestration/appauth.py tests/orchestration/test_appauth.py pyproject.toml
git commit -m "feat(orchestration): GitHub App installation-token minting (appauth)"
```

---

### Task 2: `token` CLI subcommand with on-disk cache

**Files:**
- Modify: `src/bookieskit/orchestration/cli.py` (add `token` subparser + `_token` handler + dispatch)
- Modify: `tests/orchestration/test_cli.py` (add token-cache tests)

**Interfaces:**
- Consumes: `appauth.mint_installation_token`, `appauth.token_is_fresh` (Task 1).
- Produces: CLI `python -m bookieskit.orchestration token [--identity PATH] [--cache PATH]` — prints the bare installation token to stdout; exit 1 with a stderr message (no traceback) when unprovisioned.

- [ ] **Step 1: Write the failing test**

```python
# tests/orchestration/test_cli.py  (add)
import json

from bookieskit.orchestration import cli


def test_token_reuses_fresh_cache(tmp_path, monkeypatch, capsys):
    cache = tmp_path / "app-token.json"
    cache.write_text(
        json.dumps({"token": "ghs_fresh", "expires_at": "2999-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    ident = tmp_path / "identity.json"
    ident.write_text(json.dumps({"app_id": 1, "installation_id": 2}), encoding="utf-8")

    def boom(**kwargs):  # mint must NOT be called when cache is fresh
        raise AssertionError("should not mint")

    monkeypatch.setattr(cli.appauth, "mint_installation_token", boom)
    rc = cli.main(["token", "--identity", str(ident), "--cache", str(cache)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "ghs_fresh"


def test_token_mints_when_cache_stale(tmp_path, monkeypatch, capsys):
    cache = tmp_path / "app-token.json"  # absent -> stale
    ident = tmp_path / "identity.json"
    ident.write_text(json.dumps({"app_id": 1, "installation_id": 2}), encoding="utf-8")
    pem = tmp_path / "app.pem"
    pem.write_text("KEY", encoding="utf-8")

    monkeypatch.setattr(
        cli.appauth, "mint_installation_token",
        lambda **kw: {"token": "ghs_new", "expires_at": "2999-01-01T00:00:00Z"},
    )
    rc = cli.main(
        ["token", "--identity", str(ident), "--cache", str(cache), "--key", str(pem)]
    )
    assert rc == 0
    assert capsys.readouterr().out.strip() == "ghs_new"
    assert json.loads(cache.read_text())["token"] == "ghs_new"


def test_token_exit1_when_unprovisioned(tmp_path, capsys):
    rc = cli.main(["token", "--identity", str(tmp_path / "missing.json")])
    assert rc == 1
    assert "not provisioned" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -k token -v`
Expected: FAIL (no `token` subcommand / `AttributeError`)

- [ ] **Step 3: Write minimal implementation**

Add the import near the other orchestration imports at the top of `cli.py`:

```python
from bookieskit.orchestration import appauth
```

Add the subparser in the parser-building section (alongside `p_gate`):

```python
    p_token = sub.add_parser("token")
    p_token.add_argument("--identity", default=".orchestrator/identity.json")
    p_token.add_argument("--key", default=".orchestrator/app.pem")
    p_token.add_argument("--cache", default=".orchestrator/app-token.json")
```

Add the handler (near `_lock`/`_gate`):

```python
def _token(args: argparse.Namespace) -> int:
    """Print a GitHub App installation token, reusing a cached one while it has
    > 2 min of life left (avoids minting on every 1-min tick)."""
    try:
        with open(args.cache, encoding="utf-8") as f:
            cached = json.load(f)
        if appauth.token_is_fresh(cached, now=time.time()):
            print(cached["token"])
            return 0
    except (OSError, ValueError):
        pass
    try:
        with open(args.identity, encoding="utf-8") as f:
            ident = json.load(f)
        with open(args.key, encoding="utf-8") as f:
            pem = f.read()
    except OSError as exc:
        print(f"token: not provisioned ({exc})", file=sys.stderr)
        return 1
    res = appauth.mint_installation_token(
        app_id=ident["app_id"],
        private_key_pem=pem,
        installation_id=ident["installation_id"],
        now=int(time.time()),
    )
    os.makedirs(os.path.dirname(args.cache) or ".", exist_ok=True)
    with open(args.cache, "w", encoding="utf-8") as f:
        json.dump(res, f)
    print(res["token"])
    return 0
```

Wire dispatch in `main` (add to the command dispatch chain):

```python
    if args.command == "token":
        return _token(args)
```

(Confirm `sys`, `os`, `time`, `json` are already imported at the top of `cli.py` — they are used elsewhere in the file; add any that are missing.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -k token -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/orchestration/cli.py tests/orchestration/test_cli.py
git commit -m "feat(orchestration): token CLI mints/caches App installation token"
```

---

### Task 3: Identity-aware `gh._run` + `review_approve` + `merge_pr` token

**Files:**
- Modify: `src/bookieskit/orchestration/gh.py`
- Modify: `tests/orchestration/test_gh.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `GhRunner._run(*args, token: str | None = None)` — when `token` is set, runs `gh` with `env = {**os.environ, "GH_TOKEN": token}`.
  - `GhRunner.review_approve(pr: int, *, token: str) -> None` — `gh pr review <pr> --approve`.
  - `GhRunner.merge_pr(pr: int, *, method: str = "squash", token: str | None = None) -> None`.

- [ ] **Step 1: Write the failing test**

Extend `_RecordingRun` in `tests/orchestration/test_gh.py` to capture `env`, then add tests:

```python
# in _RecordingRun.__call__, after the existing asserts:
        self.env = kwargs.get("env")
```

```python
def test_run_injects_gh_token_env_when_token_given(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.merge_pr(11, token="ghp_owner")
    assert rec.env is not None
    assert rec.env["GH_TOKEN"] == "ghp_owner"


def test_run_uses_ambient_env_when_no_token(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.list_labels()
    assert rec.env is None  # inherit ambient (the App token the tick exported)


def test_review_approve_builds_argv_with_token(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.review_approve(11, token="ghp_owner")
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "pr", "review"]
    assert "11" in argv and "--approve" in argv
    assert rec.env["GH_TOKEN"] == "ghp_owner"
```

(The existing `_RecordingRun` returns a single canned stdout; if a test issues two `gh` calls, have it keep returning the same canned value — that is already its behaviour.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_gh.py -v`
Expected: FAIL (`_run` has no `token`; `review_approve` missing)

- [ ] **Step 3: Write minimal implementation**

In `gh.py`, add `import os` at the top, then:

```python
    def _run(self, *args: str, token: str | None = None) -> str:
        # Force UTF-8 decoding (gh emits UTF-8; text=True would use cp1252 on
        # Windows and blind the loop). When token is given, run gh as that
        # identity (GH_TOKEN) without mutating this process's environment.
        env = {**os.environ, "GH_TOKEN": token} if token is not None else None
        result = subprocess.run(
            ["gh", *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        return result.stdout
```

```python
    def review_approve(self, pr: int, *, token: str) -> None:
        self._run("pr", "review", str(pr), "--approve", token=token)

    def merge_pr(self, pr: int, *, method: str = "squash", token: str | None = None) -> None:
        self._run("pr", "merge", str(pr), f"--{method}", token=token)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_gh.py -v`
Expected: PASS (all, including the 3 new)

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/orchestration/gh.py tests/orchestration/test_gh.py
git commit -m "feat(orchestration): identity-aware gh._run + review_approve"
```

---

### Task 4: Approve path submits owner-token review then merges

**Files:**
- Modify: `src/bookieskit/orchestration/cli.py` (`_chatops_approve` + `_read_owner_token`)
- Modify: `tests/orchestration/test_cli.py`

**Interfaces:**
- Consumes: `GhRunner.review_approve`, `GhRunner.merge_pr(token=...)` (Task 3).
- Produces: `_read_owner_token(path=".orchestrator/owner-token") -> str | None`. Approve flow: read owner token → reject if missing → `review_approve(pr, token=owner)` → `merge_pr(pr, method="squash", token=owner)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/orchestration/test_cli.py  (add)
def test_approve_uses_owner_token_for_review_and_merge(tmp_path, monkeypatch):
    # owner token on disk
    monkeypatch.setattr(cli, "_read_owner_token", lambda: "ghp_owner")

    class FakeGh:
        def __init__(self):
            self.review = None
            self.merge = None

        def pr_view(self, pr):
            return {"state": "OPEN", "statusCheckRollup": [],
                    "closingIssuesReferences": [{"number": 8}]}

        def list_issues(self, *, state, labels=()):
            return [{"number": 8}]

        def review_approve(self, pr, *, token):
            self.review = (pr, token)

        def merge_pr(self, pr, *, method="squash", token=None):
            self.merge = (pr, method, token)

    fake = FakeGh()
    monkeypatch.setattr(cli.chatops, "checks_pass", lambda rollup: True)
    monkeypatch.setattr(cli.chatops, "is_authorized", lambda a, allow: True)
    monkeypatch.setattr(cli.chatops, "load_config", lambda cfg: {"approvers": ["U"]})
    monkeypatch.setattr(cli.chatops, "closing_issue_numbers", lambda v: [8])

    import argparse
    args = argparse.Namespace(pr=11, author="U", config="x", as_json=True)
    rc = cli._chatops_approve(args, fake)
    assert rc == 0
    assert fake.review == (11, "ghp_owner")
    assert fake.merge == (11, "squash", "ghp_owner")


def test_approve_rejects_when_no_owner_token(monkeypatch):
    monkeypatch.setattr(cli, "_read_owner_token", lambda: None)
    monkeypatch.setattr(cli.chatops, "is_authorized", lambda a, allow: True)
    monkeypatch.setattr(cli.chatops, "load_config", lambda cfg: {"approvers": ["U"]})

    class FakeGh:
        def pr_view(self, pr):
            return {"state": "OPEN", "statusCheckRollup": [],
                    "closingIssuesReferences": [{"number": 8}]}

        def list_issues(self, *, state, labels=()):
            return [{"number": 8}]

    import argparse
    monkeypatch.setattr(cli.chatops, "checks_pass", lambda rollup: True)
    monkeypatch.setattr(cli.chatops, "closing_issue_numbers", lambda v: [8])
    args = argparse.Namespace(pr=11, author="U", config="x", as_json=True)
    rc = cli._chatops_approve(args, FakeGh())
    assert rc == 0  # a rejection is a handled outcome
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -k approve -v`
Expected: FAIL (`_read_owner_token` missing; approve still calls `merge_pr` without token)

- [ ] **Step 3: Write minimal implementation**

Add near `_read_token` in `cli.py`:

```python
def _read_owner_token(path: str = ".orchestrator/owner-token") -> str | None:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip() or None
    except OSError:
        return None
```

Replace the merge tail of `_chatops_approve` (the `gh.merge_pr(args.pr, method="squash")` line) with:

```python
    owner = _read_owner_token()
    if owner is None:
        return _chatops_reject(args, "no owner token configured")
    gh.review_approve(args.pr, token=owner)
    gh.merge_pr(args.pr, method="squash", token=owner)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -k approve -v`
Expected: PASS

Run the full orchestration suite: `.venv/Scripts/python.exe -m pytest tests/orchestration -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/orchestration/cli.py tests/orchestration/test_cli.py
git commit -m "feat(orchestration): approve path uses owner token for review+merge"
```

---

### Task 5: Tick script exports the App identity

**Files:**
- Modify: `scripts/orchestrator-tick.ps1`

**Interfaces:**
- Consumes: `python -m bookieskit.orchestration token` (Task 2).
- Produces: side effect — `$env:GH_TOKEN`/`$env:GITHUB_TOKEN` set to the App token for the `claude` invocation; git pushes authenticate as the App. Falls back to ambient `gh` login (today's behaviour) if minting fails.

- [ ] **Step 1: Add token export before the headless claude run (ASCII only)**

Insert, after the lock is taken and before the `claude -p "/orchestrate"` invocation:

```powershell
# Mint/refresh the GitHub App installation token so the loop's git/gh act as
# the App (an identity the main ruleset bars from merging), not as the owner.
# If the App is not provisioned yet, fall back to the ambient gh login.
$AppToken = & $Py -m bookieskit.orchestration token 2>$null
if ($LASTEXITCODE -eq 0 -and $AppToken) {
    $env:GH_TOKEN = $AppToken.Trim()
    $env:GITHUB_TOKEN = $AppToken.Trim()
    # Authenticate git-over-https as the App for this cycle's pushes.
    & git config --local "http.https://github.com/.extraheader" ("AUTHORIZATION: basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("x-access-token:" + $env:GH_TOKEN)))
    Write-Output "tick: using GitHub App identity for this cycle"
} else {
    Write-Output "tick: App token unavailable - falling back to ambient gh login"
}
```

Add cleanup of the per-cycle git header at the end of the cycle (near where the lock is released):

```powershell
& git config --local --unset "http.https://github.com/.extraheader" 2>$null
```

(`$Py` is the existing Python-path variable in the script; match its actual name. Keep the file pure ASCII.)

- [ ] **Step 2: Verify the script parses**

Run: `powershell -NoProfile -Command "& { . { $null = Get-Command }; [scriptblock]::Create((Get-Content -Raw scripts/orchestrator-tick.ps1)) | Out-Null; 'parse ok' }"`
Expected: `parse ok` (no parse error)

- [ ] **Step 3: Commit**

```bash
git add scripts/orchestrator-tick.ps1
git commit -m "feat(orchestrator): tick exports GitHub App identity per cycle"
```

---

### Task 6: Owner runbook + ruleset command + CHANGELOG

**Files:**
- Create: `docs/AGENT_IDENTITY_SETUP.md`
- Modify: `CHANGELOG.md` (`[Unreleased]`)

**Interfaces:** none (docs).

- [ ] **Step 1: Write the runbook**

Create `docs/AGENT_IDENTITY_SETUP.md` covering, with exact click-paths and commands:

1. **Create the GitHub App** (Settings → Developer settings → GitHub Apps → New):
   name "BookiesKit Agent"; Homepage URL = repo URL; uncheck Webhook → Active.
   Repository permissions: **Contents: Read and write, Pull requests: Read and
   write, Issues: Read and write, Checks: Read-only, Metadata: Read-only**.
   Leave everything else "No access". Create.
2. **Install it** on the `bookieskit` repo only (Install App → Only select
   repositories → bookieskit). Note the **Installation ID** (the number in the
   install settings URL `.../installations/<ID>`).
3. **Generate a private key** (App settings → Private keys → Generate) → save the
   downloaded `.pem` as `.orchestrator/app.pem`. Note the **App ID** (App
   settings → General).
4. Write `.orchestrator/identity.json`:
   ```json
   { "app_id": <APP_ID>, "installation_id": <INSTALLATION_ID> }
   ```
5. **Create the owner fine-grained PAT** (Settings → Developer settings →
   Fine-grained tokens → Generate): resource owner = you, repository access =
   only `bookieskit`, permissions **Contents: Read and write, Pull requests:
   Read and write, Metadata: Read-only**. Save the token (one line) to
   `.orchestrator/owner-token`.
6. **Verify minting:** `\.venv\Scripts\python.exe -m bookieskit.orchestration token`
   prints a `ghs_...` token.
7. **Harden the ruleset** (require 1 approving review) — run once:
   ```bash
   # Strip read-only fields, bump required_approving_review_count to 1, PUT back.
   gh api repos/:owner/:repo/rulesets/18116963 \
     | python -c "import sys,json; d=json.load(sys.stdin); [r['parameters'].__setitem__('required_approving_review_count',1) for r in d['rules'] if r['type']=='pull_request']; body={k:d[k] for k in ('name','target','enforcement','conditions','rules','bypass_actors')}; print(json.dumps(body))" \
     > /tmp/ruleset.json
   gh api --method PUT repos/:owner/:repo/rulesets/18116963 --input /tmp/ruleset.json
   ```
   Confirm: `gh api repos/:owner/:repo/rulesets/18116963 --jq '.rules[]|select(.type=="pull_request").parameters.required_approving_review_count'` → `1`.
8. **Manual never-merge proof** (run once after the above):
   - Let the loop open a PR (or open one as the App).
   - As the App, `gh pr merge <pr>` → expect **rejection** ("at least 1 approving review required").
   - In Slack, `approve <pr>` → expect review + merge → **merged**.
9. **Token rotation note:** the owner fine-grained PAT is long-lived — rotate it
   periodically and replace `.orchestrator/owner-token`.

- [ ] **Step 2: CHANGELOG entry**

Under `## [Unreleased]` in `CHANGELOG.md`, add:

```markdown
### Changed
- Orchestrator now runs under a dedicated **GitHub App identity** that cannot
  merge to `main`; the Slack `approve` path uses a separate owner token to
  submit the approving review + merge. Never-merge is now structural for all
  build operations. See `docs/AGENT_IDENTITY_SETUP.md`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/AGENT_IDENTITY_SETUP.md CHANGELOG.md
git commit -m "docs(orchestrator): agent-identity setup runbook + CHANGELOG"
```

---

## Self-Review

- **Spec coverage:** appauth (T1) ✓, token CLI/cache (T2) ✓, identity-aware gh + review_approve (T3) ✓, owner-token approve path (T4) ✓, tick export (T5) ✓, runbook + ruleset command + CHANGELOG (T6) ✓. Dependency extra in T1 ✓.
- **Type consistency:** `mint_installation_token` returns `{"token","expires_at"}` used by `_token` (T2). `review_approve(pr,*,token)` / `merge_pr(pr,*,method,token)` defined T3, consumed T4. `_read_owner_token` defined+consumed T4. ✓
- **Placeholder scan:** every code step carries full code; ruleset command is concrete. ✓
- **Scope:** single focused capability; owner-only GitHub-account steps isolated to the T6 runbook (cannot be automated). ✓
