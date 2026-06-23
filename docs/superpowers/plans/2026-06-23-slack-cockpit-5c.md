# Slack Cockpit (5c, notifications) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the owner a live Slack feed of the agent company — cycle progress checkpoints (`#agent-activity`), canary drift digests (`#canary-alerts`), and release announcements (`#releases`) — via pure offline-tested message formatters plus best-effort posting from the orchestrate skill.

**Architecture:** A new `bookieskit.orchestration.notify` module holds pure Slack-mrkdwn formatters (no I/O). A `notify <kind>` CLI subcommand prints the formatted text on stdout for the agent to post via the korotovsky Slack MCP `post_message` tool; `sync-canary --json` gains a `slack_text` field built from `canary_digest`. The `orchestrate` skill and `CLAUDE.md` document posting at checkpoints, best-effort (skip cleanly when the MCP is absent). A `docs/SLACK_SETUP.md` covers owner setup. No custom Slack bot/service.

**Tech Stack:** Python 3.11+ (stdlib only — `argparse`, `dataclasses.asdict`); pytest; ruff. korotovsky `slack-mcp-server` (owner-registered, used by the agent, not by Python).

## Global Constraints

- **Python floor:** 3.11 (CI matrix 3.11/3.12/3.13). stdlib only — add no dependencies.
- **Layering:** `devtools` must NOT import `orchestration` (`orchestration` already imports `devtools.canary`; the reverse is a circular import). Release announcements therefore go through the `notify` CLI, NOT a `slack_text` field on `devtools release`.
- **Best-effort:** Slack posting is never on the critical path. The loop/canary/release run unchanged when the Slack MCP is absent; Slack just stays quiet. Posting code lives in the skill (agent-side), never in a way that can fail a build.
- **Formatting:** Slack mrkdwn text only (no block-kit). The stream value is humanized (`stream:directed` → `directed`).
- **`src/` stays ruff-clean.** Tests may keep existing ruff ignores (E501 in tests).
- **Channels:** `#agent-activity` (cycle feed), `#canary-alerts` (drift), `#releases` (releases).
- **Karpathy principles:** surgical, no overcomplication; pure functions; verifiable via offline tests.

---

## File Structure

- `src/bookieskit/orchestration/notify.py` — **new.** Pure formatters: `cycle_started`, `cycle_pr`, `cycle_blocked`, `cycle_empty`, `canary_digest`, `release_announcement`. No I/O.
- `src/bookieskit/orchestration/cli.py` — **modify.** Add the `notify` subcommand (kinds: `cycle-started`, `cycle-pr`, `cycle-blocked`, `release`); add `slack_text` to `_sync_canary`'s emitted payload.
- `tests/orchestration/test_notify.py` — **new.** Formatter unit tests + `notify` CLI tests.
- `tests/orchestration/test_cli.py` (or the existing CLI test module) — **modify.** Assert `sync-canary --json` includes `slack_text`.
- `.claude/skills/orchestrate/SKILL.md` — **modify.** Add a "Notifications (best-effort)" section; reference it from the cycle steps.
- `CLAUDE.md` (repo root) — **modify.** Add a "Slack cockpit" section.
- `docs/SLACK_SETUP.md` — **new.** Owner setup doc.

---

## Task 1: `notify` formatters

**Files:**
- Create: `src/bookieskit/orchestration/notify.py`
- Test: `tests/orchestration/test_notify.py`

**Interfaces:**
- Consumes: nothing (pure stdlib).
- Produces (later tasks rely on these exact signatures):
  - `cycle_started(number: int, title: str, stream: str) -> str`
  - `cycle_pr(number: int, title: str, pr_url: str) -> str`
  - `cycle_blocked(number: int, title: str, reason: str) -> str`
  - `cycle_empty() -> str`
  - `canary_digest(opened: list[str], updated: list[str], closed: list[str], sport: str) -> str` (returns `""` when all three lists are empty)
  - `release_announcement(tag: str, current: str, new: str) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/orchestration/test_notify.py
from bookieskit.orchestration.notify import (
    canary_digest,
    cycle_blocked,
    cycle_empty,
    cycle_pr,
    cycle_started,
    release_announcement,
)


def test_cycle_started_humanizes_stream_and_includes_number_title():
    msg = cycle_started(42, "add Stake bookmaker", "stream:directed")
    assert "#42" in msg
    assert "add Stake bookmaker" in msg
    assert "directed" in msg
    assert "stream:" not in msg  # humanized
    assert "*Cycle started*" in msg


def test_cycle_pr_includes_pr_url_and_awaiting_review():
    msg = cycle_pr(42, "add Stake", "https://github.com/o/r/pull/12")
    assert "#42" in msg
    assert "https://github.com/o/r/pull/12" in msg
    assert "awaiting review" in msg.lower()
    assert "*PR opened*" in msg


def test_cycle_blocked_includes_reason():
    msg = cycle_blocked(42, "add Stake", "missing API credential")
    assert "#42" in msg
    assert "blocked" in msg.lower()
    assert "missing API credential" in msg


def test_cycle_empty_is_nonempty_text():
    msg = cycle_empty()
    assert msg.strip()
    assert "empty" in msg.lower()


def test_canary_digest_lists_each_signature_and_counts():
    msg = canary_digest(
        opened=["canary:betika:structure"],
        updated=[],
        closed=["canary:msport:structure", "canary:sporty:structure"],
        sport="soccer",
    )
    assert "soccer" in msg
    assert "canary:betika:structure" in msg
    assert "canary:msport:structure" in msg
    assert "canary:sporty:structure" in msg
    # counts reflect 1 opened / 0 updated / 2 closed
    assert "1" in msg and "2" in msg


def test_canary_digest_empty_when_no_change():
    assert canary_digest([], [], [], "soccer") == ""


def test_release_announcement_shows_tag_and_transition():
    msg = release_announcement("v0.17.0", "0.16.0", "0.17.0")
    assert "v0.17.0" in msg
    assert "0.16.0" in msg
    assert "0.17.0" in msg
    assert "*Released" in msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_notify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bookieskit.orchestration.notify'`.

- [ ] **Step 3: Write the implementation**

```python
# src/bookieskit/orchestration/notify.py
"""Pure Slack-mrkdwn message formatters for the agent-company cockpit.

No I/O: each function returns the message *text*. The orchestrate skill (or the
``notify`` CLI) produces the text; the agent posts it via the Slack MCP
``post_message`` tool. Keeping these pure makes them offline-testable in CI,
where no Slack MCP is connected.
"""


def _humanize_stream(stream: str) -> str:
    """``stream:directed`` -> ``directed`` (leave a bare value unchanged)."""
    return stream.removeprefix("stream:")


def cycle_started(number: int, title: str, stream: str) -> str:
    return (
        f":hammer: *Cycle started* — #{number} "
        f"[{_humanize_stream(stream)}] {title}"
    )


def cycle_pr(number: int, title: str, pr_url: str) -> str:
    return (
        f":white_check_mark: *PR opened* for #{number} {title} — "
        f"{pr_url} (awaiting review)"
    )


def cycle_blocked(number: int, title: str, reason: str) -> str:
    return f":no_entry: *#{number} blocked* — {title}: {reason}"


def cycle_empty() -> str:
    return ":zzz: Queue empty — nothing to do this cycle."


def canary_digest(
    opened: list[str], updated: list[str], closed: list[str], sport: str
) -> str:
    """Drift digest for ``#canary-alerts``. Returns ``""`` when nothing changed
    (the caller skips posting an empty digest)."""
    if not (opened or updated or closed):
        return ""
    lines = [
        f":warning: *Canary ({sport})* — {len(opened)} new, "
        f"{len(updated)} persisting, {len(closed)} recovered"
    ]
    lines += [f"• opened: {s}" for s in opened]
    lines += [f"• still drifting: {s}" for s in updated]
    lines += [f"• recovered: {s}" for s in closed]
    return "\n".join(lines)


def release_announcement(tag: str, current: str, new: str) -> str:
    return f":package: *Released {tag}* ({current} → {new})"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_notify.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Lint the new source**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration/notify.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/orchestration/notify.py tests/orchestration/test_notify.py
git commit -m "feat(orchestration): notify formatters for Slack cockpit"
```

---

## Task 2: `notify` CLI subcommand + `sync-canary` slack_text

**Files:**
- Modify: `src/bookieskit/orchestration/cli.py`
- Test: `tests/orchestration/test_notify.py` (append CLI tests), and the existing CLI test module for the `sync-canary` assertion (see Step 7).

**Interfaces:**
- Consumes: `bookieskit.orchestration.notify` (Task 1) — all six formatters.
- Produces: the `notify` subcommand with nested kinds and the `slack_text` field on `sync-canary --json` output. The agent (orchestrate skill, Task 3) calls `python -m bookieskit.orchestration notify <kind> ...` and reads `slack_text` from `sync-canary --json`.

**Context — current CLI shape (`src/bookieskit/orchestration/cli.py`):** uses `argparse` with a `sub = parser.add_subparsers(dest="command", required=True)`; existing subcommands include `sync-canary`, `ensure-labels`, `queue`, `next`, `claim`, `mark-in-review`, `mark-blocked`. A helper `_emit(payload: dict, as_json: bool, human_lines: list[str]) -> None` prints either `json.dumps(payload)` or the human lines. `_sync_canary(args, runner, gh)` currently calls `_emit(asdict(result), args.as_json, [...])`. The `notify` kinds need no `gh`/network — they are pure formatting, so the `notify` handler must NOT construct a `GhRunner`.

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/orchestration/test_notify.py`. These invoke the CLI's `main` entry the same way the existing CLI tests do — import the module's `main` and call it with an argv list, capturing stdout via `capsys`. (Check the existing CLI test module for the exact entry-point name and adapt if `main` differs.)

```python
# --- appended to tests/orchestration/test_notify.py ---
import json

from bookieskit.orchestration.cli import main


def test_cli_notify_cycle_started(capsys):
    rc = main([
        "notify", "cycle-started",
        "--number", "42", "--title", "add Stake", "--stream", "stream:directed",
    ])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert "#42" in out and "directed" in out and "add Stake" in out
    assert "stream:" not in out


def test_cli_notify_cycle_pr(capsys):
    rc = main([
        "notify", "cycle-pr",
        "--number", "42", "--title", "add Stake",
        "--pr", "https://github.com/o/r/pull/12",
    ])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert "https://github.com/o/r/pull/12" in out
    assert "awaiting review" in out.lower()


def test_cli_notify_cycle_blocked(capsys):
    rc = main([
        "notify", "cycle-blocked",
        "--number", "42", "--title", "add Stake", "--reason", "no creds",
    ])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert "blocked" in out.lower() and "no creds" in out


def test_cli_notify_release(capsys):
    rc = main([
        "notify", "release",
        "--tag", "v0.17.0", "--current", "0.16.0", "--new", "0.17.0",
    ])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert "v0.17.0" in out and "0.16.0" in out and "0.17.0" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_notify.py -k cli -v`
Expected: FAIL — `argument command: invalid choice: 'notify'` (the subcommand does not exist yet).

- [ ] **Step 3: Add the `notify` subcommand to the parser**

In `cli.py`, where the other subparsers are registered (after `mark-blocked`), add:

```python
    p_notify = sub.add_parser(
        "notify", help="Format a Slack-cockpit message (prints text to stdout)"
    )
    nsub = p_notify.add_subparsers(dest="notify_kind", required=True)

    n_started = nsub.add_parser("cycle-started")
    n_started.add_argument("--number", type=int, required=True)
    n_started.add_argument("--title", required=True)
    n_started.add_argument("--stream", required=True)

    n_pr = nsub.add_parser("cycle-pr")
    n_pr.add_argument("--number", type=int, required=True)
    n_pr.add_argument("--title", required=True)
    n_pr.add_argument("--pr", required=True)

    n_blocked = nsub.add_parser("cycle-blocked")
    n_blocked.add_argument("--number", type=int, required=True)
    n_blocked.add_argument("--title", required=True)
    n_blocked.add_argument("--reason", required=True)

    n_release = nsub.add_parser("release")
    n_release.add_argument("--tag", required=True)
    n_release.add_argument("--current", required=True)
    n_release.add_argument("--new", required=True)
```

- [ ] **Step 4: Add the dispatch handler**

Add the import at the top of `cli.py` (with the other `from bookieskit.orchestration...` imports):

```python
from bookieskit.orchestration import notify as notify_fmt
```

Add a handler function:

```python
def _notify(args: argparse.Namespace) -> int:
    """Pure formatting — no gh/network. Prints the Slack message text."""
    if args.notify_kind == "cycle-started":
        text = notify_fmt.cycle_started(args.number, args.title, args.stream)
    elif args.notify_kind == "cycle-pr":
        text = notify_fmt.cycle_pr(args.number, args.title, args.pr)
    elif args.notify_kind == "cycle-blocked":
        text = notify_fmt.cycle_blocked(args.number, args.title, args.reason)
    elif args.notify_kind == "release":
        text = notify_fmt.release_announcement(args.tag, args.current, args.new)
    else:  # argparse `required=True` makes this unreachable
        return 2
    print(text)
    return 0
```

In `main`, dispatch `notify` BEFORE the branches that build a `GhRunner` (so a missing `gh` binary never blocks pure formatting):

```python
    if args.command == "notify":
        return _notify(args)
```

- [ ] **Step 5: Run the CLI tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_notify.py -k cli -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Add `slack_text` to `_sync_canary` output**

Replace the `_emit(asdict(result), ...)` call in `_sync_canary` so the payload carries `slack_text`:

```python
    payload = {
        **asdict(result),
        "slack_text": notify_fmt.canary_digest(
            result.opened, result.updated, result.closed, args.sport
        ),
    }
    _emit(
        payload,
        args.as_json,
        [f"sync-canary opened={len(result.opened)} "
         f"updated={len(result.updated)} closed={len(result.closed)} "
         f"errors={len(result.errors)}"]
        + [f"  opened {s}" for s in result.opened]
        + [f"  updated {s}" for s in result.updated]
        + [f"  closed {s}" for s in result.closed]
        + [f"  ERROR {e}" for e in result.errors],
    )
    return 0
```

- [ ] **Step 7: Add/locate a `sync-canary --json` slack_text test**

Find the existing `sync-canary` CLI test (it injects a fake `runner` and a fake `gh`/`Queue`). Add a test asserting the JSON payload includes `slack_text` equal to the digest. If the existing test harness makes injecting a drift-producing runner easy, assert the non-empty digest; otherwise assert the key is present and equals `canary_digest(opened, updated, closed, sport)` for the fake result. Minimal version (place wherever the `sync-canary` CLI tests live):

```python
def test_sync_canary_json_includes_slack_text(... existing fixtures ...):
    # invoke `main(["sync-canary", "--sport", "soccer", "--json", ...])`
    # with the existing fake runner+gh that yields a known SyncResult
    payload = json.loads(capsys.readouterr().out)
    assert "slack_text" in payload
    from bookieskit.orchestration.notify import canary_digest
    assert payload["slack_text"] == canary_digest(
        payload["opened"], payload["updated"], payload["closed"], "soccer"
    )
```

- [ ] **Step 8: Run the full orchestration test suite**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/ -v`
Expected: PASS (all orchestration tests, including the existing `sync-canary` tests still green).

- [ ] **Step 9: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration/cli.py`
Expected: `All checks passed!`

- [ ] **Step 10: Commit**

```bash
git add src/bookieskit/orchestration/cli.py tests/orchestration/
git commit -m "feat(orchestration): notify CLI + sync-canary slack_text"
```

---

## Task 3: orchestrate skill + CLAUDE.md best-effort posting

**Files:**
- Modify: `.claude/skills/orchestrate/SKILL.md`
- Modify: `CLAUDE.md` (repo root)

**Interfaces:**
- Consumes: the `notify` CLI (Task 2) and the `slack_text` field on `sync-canary --json`.
- Produces: documented checkpoints that the agent follows — no code, so this task is verified by structural review (the sections exist, name the right channels/commands, and state the best-effort rule).

This task is authored prose. There is no automated test; the deliverable is reviewed for: (a) the three channels named correctly, (b) the four `notify` kinds wired to the right cycle steps, (c) the best-effort/skip-if-absent rule stated, (d) consistency with the `notify` CLI command names from Task 2.

- [ ] **Step 1: Add a "Notifications (best-effort)" section to the orchestrate skill**

Append this section to `.claude/skills/orchestrate/SKILL.md` after the "Hard rules" section:

```markdown
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
```

- [ ] **Step 2: Reference notifications from the cycle steps**

In the orchestrate skill's "The cycle" list, add a best-effort posting note to steps 2, 4, and the blocker section so the agent posts inline. Edit step 2's line to end with:

```markdown
   Then (best-effort, see Notifications) post `cycle-started` to `#agent-activity`.
```

Edit step 4's line to end with:

```markdown
   Then (best-effort, see Notifications) post `cycle-pr` to `#agent-activity`.
```

In the "If you hit a genuine blocker" section, after the `mark-blocked` command, add:

```markdown
Then (best-effort, see Notifications) post `cycle-blocked` to `#agent-activity`.
```

- [ ] **Step 3: Add a "Slack cockpit" section to `CLAUDE.md`**

Add this section to the repo-root `CLAUDE.md` (after the queue-conventions / build-discipline material, before any closing section):

```markdown
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
```

- [ ] **Step 4: Structural self-check**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q` (confirm nothing broke — prose-only change, suite stays green).
Verify by reading: the skill has a "Notifications (best-effort)" section naming all three channels and the four `notify` kinds with command names matching Task 2 (`cycle-started`/`cycle-pr`/`cycle-blocked`/`release`); `CLAUDE.md` has the "Slack cockpit" section; the best-effort/skip-if-absent rule appears in both.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/orchestrate/SKILL.md CLAUDE.md
git commit -m "docs(orchestration): orchestrate skill + CLAUDE.md Slack cockpit notifications"
```

---

## Task 4: `docs/SLACK_SETUP.md` owner setup doc + final gate

**Files:**
- Create: `docs/SLACK_SETUP.md`

**Interfaces:**
- Consumes: nothing (documentation).
- Produces: the gated owner-setup runbook the spec's success criteria require.

- [ ] **Step 1: Write the setup doc**

```markdown
# Slack cockpit — owner setup

The agent company posts a live feed to Slack via the korotovsky
`slack-mcp-server` MCP. This is **best-effort**: until these steps are done, the
loop, canary, and release all run normally — Slack simply stays quiet. Complete
this once to light up the cockpit.

## 1. Workspace + channels

1. Use an existing Slack workspace or create one; invite the people who'll use
   it (owner + teammates).
2. Create three channels:
   - `#agent-activity` — cycle progress (claimed → PR opened → blocked).
   - `#canary-alerts` — canary drift digests.
   - `#releases` — release announcements.

## 2. Slack token

Obtain a token for the korotovsky MCP per its README
(<https://github.com/korotovsky/slack-mcp-server>). A user or bot token is
enough; no workspace-admin rights are required. Add the bot/user to the three
channels above so it can post.

## 3. Register the MCP in Claude Code

Register `slack-mcp-server` as an MCP server (stdio) in Claude Code's MCP
settings. **Crucially, enable the message-post tool** — it is OFF by default:
set the `SLACK_MCP_ADD_MESSAGE_TOOL` environment variable (per the server's
README) so the `post_message`/`conversations_add_message` tool is exposed.
Without it, the agent can format messages but cannot post them.

## 4. Verify (in-region)

Live-bookmaker work runs in-region (the African APIs geo-block US/cloud IPs),
so verify from an in-region session:

1. Run one `/orchestrate` cycle on a queue with at least one open item. Confirm
   a `cycle-started` message lands in `#agent-activity`, and a `cycle-pr`
   message when the PR opens.
2. Run `python -m bookieskit.orchestration sync-canary --sport soccer --json`.
   If it reports drift, confirm the digest lands in `#canary-alerts`. (No drift
   → no post, by design.)

If nothing posts and no error appears, the `post_message` tool is not enabled —
re-check step 3 (`SLACK_MCP_ADD_MESSAGE_TOOL`).

## Channels at a glance

| Channel | Posted by | When |
|---|---|---|
| `#agent-activity` | orchestrate skill | each cycle: claimed → PR opened → blocked |
| `#canary-alerts` | orchestrate/maintenance | a `sync-canary` run reports drift |
| `#releases` | release flow | a release is cut |

## Next slice — ChatOps

A later sub-project adds a `#tickets` channel where you (or a teammate) type a
request — "add bookmaker X" — and the loop files it as a `stream:directed`
issue and builds it, plus `approve`/`status`/`pause` commands. This setup is
the foundation for it.
```

- [ ] **Step 2: Run the full suite + lint as the final gate**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all pass (737+ passed, 1 skipped, plus the new notify tests).

Run: `.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3: Commit**

```bash
git add docs/SLACK_SETUP.md
git commit -m "docs: SLACK_SETUP.md owner runbook for the Slack cockpit"
```

---

## Self-Review

**1. Spec coverage:**
- `notify` formatters (cycle_started/pr/blocked/empty, canary_digest, release_announcement) → Task 1. ✅
- `notify` CLI (cycle-started/cycle-pr/cycle-blocked/release) → Task 2 Steps 1–5. ✅
- `sync-canary --json` `slack_text` → Task 2 Steps 6–7. ✅ (release via CLI, not slack_text — layering constraint honored.)
- orchestrate skill best-effort posting at checkpoints → Task 3 Steps 1–2. ✅
- `CLAUDE.md` Slack cockpit section → Task 3 Step 3. ✅
- `docs/SLACK_SETUP.md` → Task 4 Step 1. ✅
- Best-effort / degrade-if-absent → stated in skill + CLAUDE.md + setup doc. ✅
- Offline-tested formatters + CLI; live posting owner-gated/deferred → Task 1/2 tests offline; Task 4 verify step is owner-gated. ✅

**2. Placeholder scan:** No TBD/TODO. Task 2 Step 7 references "the existing CLI test harness/fixtures" — this is a real instruction to reuse the established `sync-canary` test fakes (the implementer must read the existing test module), with a concrete minimal fallback test given. Task 3 is prose with exact text to insert.

**3. Type consistency:** `canary_digest(opened, updated, closed, sport)` signature is identical in Task 1 (def), Task 2 (CLI call + test), and the `sync-canary` payload. `notify` kind names (`cycle-started`/`cycle-pr`/`cycle-blocked`/`release`) are identical across Task 2 (parser), Task 3 (skill table), and the tests. `release_announcement(tag, current, new)` matches the `notify release --tag/--current/--new` args.
