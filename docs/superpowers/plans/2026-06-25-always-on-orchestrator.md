# Always-On Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the one-cycle `/orchestrate` loop unattended every 15 minutes on the owner's in-region Windows machine, with a Slack `pause`/`resume` kill-switch, a no-overlap lock, and the never-merge gate preserved.

**Architecture:** Testable Python for the logic — a pause marker (`control.py`, a `control:paused` sentinel Issue), a `pause`/`resume` command layer (`chatops.py` + CLI), and a tick lockfile (`runner.py` + CLI) — plus a thin PowerShell wrapper + Task Scheduler installer + setup doc that invoke headless `claude -p "/orchestrate"` under a constrained permission profile. The cycle skill checks the pause marker before building.

**Tech Stack:** Python 3.11+ stdlib (`json`, `os`, `re`, `time`, `dataclasses`); pytest; ruff; `gh` CLI via the injectable `GhRunner`; Windows Task Scheduler + PowerShell (`.ps1`); Claude Code headless (`claude -p`).

## Global Constraints

- **Python floor 3.11; stdlib only — no new dependencies.**
- **Never-merge gate is structural and preserved:** the unattended agent gets **no direct `gh pr merge`** tool and **no push to `main`**; merge happens only inside the allowlisted `chatops approve` CLI (which verifies a human Slack `approve`) as its own subprocess. Recommend GitHub **branch protection on `main`** (require PR + green CI) as the structural backstop.
- **Pause kill-switch:** `pause`/`resume` from `#tickets` (allowlist-gated) toggle a durable `control:paused` marker; the cycle skips building while paused.
- **Concurrency:** a timestamped lockfile; a tick that fires mid-build exits cleanly; a lock older than the stale timeout (default **7200 s = 2 h**) is reclaimed.
- **Quiet-on-empty:** no Slack post when there's nothing to do.
- **stdlib `now` injected** into lock logic (no hidden clock) for testability.
- `src/` stays ruff-clean; rejection/no-op outcomes exit 0, only operational errors non-zero.
- Authorization reuses the `.chatops.json` approver allowlist (only an approver may `pause`/`resume`).

---

## File Structure

- `src/bookieskit/orchestration/labels.py` — **modify.** Add `control:paused` (a `CONTROL_LABELS` dict merged into `ALL_LABELS`).
- `src/bookieskit/orchestration/control.py` — **new.** Pause marker: `is_paused`, `set_paused`, `clear_paused` over a `control:paused` sentinel Issue.
- `src/bookieskit/orchestration/chatops.py` — **modify.** Extend `parse_command` to recognize `pause`/`resume` (`PauseCommand`/`ResumeCommand`); add `paused`/`resumed` reply formatters.
- `src/bookieskit/orchestration/runner.py` — **new.** `acquire_lock`/`release_lock` tick lock.
- `src/bookieskit/orchestration/cli.py` — **modify.** Add `chatops pause`/`chatops resume`/`chatops paused` and `lock acquire`/`lock release` subcommands.
- `scripts/orchestrator-tick.ps1` — **new.** Lock → headless cycle → release → log.
- `scripts/install-orchestrator.ps1` — **new.** Register/refresh the 15-min Task Scheduler job.
- `.claude/orchestrator-settings.json` — **new.** Constrained permission allowlist for the unattended tick.
- `docs/ORCHESTRATOR_SETUP.md` — **new.** Owner runbook (install, branch protection, pause/resume, logs, limits).
- `.claude/skills/orchestrate/SKILL.md` — **modify.** Handle `pause`/`resume` in the intake step; pause-check before building.
- `CLAUDE.md` — **modify.** "Always-on orchestrator" section.
- `.gitignore` — **modify.** Ignore the lockfile + tick logs.
- Tests: `tests/orchestration/test_control.py`, `test_runner.py` (new); additions to `test_chatops.py`, `test_cli.py`, `test_labels.py`.

---

## Task 1: `control:paused` label + pause marker (`control.py`)

**Files:**
- Modify: `src/bookieskit/orchestration/labels.py`
- Create: `src/bookieskit/orchestration/control.py`
- Test: `tests/orchestration/test_control.py`, and update `tests/orchestration/test_labels.py`

**Interfaces:**
- Consumes: `GhRunner` (`list_issues(state=, labels=)`, `create_issue(title=, body=, labels=)`, `comment_issue`, `close_issue`).
- Produces:
  - `labels.CONTROL_LABELS: dict[str, tuple[str, str]]` (contains `"control:paused"`); merged into `ALL_LABELS`.
  - `control.PAUSE_LABEL = "control:paused"`
  - `control.is_paused(gh) -> bool`
  - `control.set_paused(gh, *, reason: str, author: str) -> int` (returns the marker Issue number)
  - `control.clear_paused(gh, *, author: str) -> list[int]` (returns closed Issue numbers)

- [ ] **Step 1: Write the failing tests**

```python
# tests/orchestration/test_control.py
from bookieskit.orchestration import control


class _FakeGh:
    def __init__(self, issues=None):
        self.issues = list(issues or [])
        self._next = max((i["number"] for i in self.issues), default=0) + 1
        self.comments = []
        self.closed = []

    def list_issues(self, *, labels=(), state="open"):
        out = [i for i in self.issues if state == "all" or i.get("state", "open") == state]
        for lb in labels:
            out = [i for i in out if lb in [x["name"] for x in i.get("labels", [])]]
        return out

    def create_issue(self, *, title, body, labels):
        n = self._next
        self._next += 1
        self.issues.append({"number": n, "title": title, "body": body,
                            "labels": [{"name": x} for x in labels], "state": "open"})
        return n

    def comment_issue(self, number, body):
        self.comments.append((number, body))

    def close_issue(self, number, *, comment=None):
        for i in self.issues:
            if i["number"] == number:
                i["state"] = "closed"
        self.closed.append((number, comment))


def test_not_paused_when_no_marker():
    assert control.is_paused(_FakeGh()) is False


def test_set_paused_creates_marker_then_is_paused():
    gh = _FakeGh()
    n = control.set_paused(gh, reason="canary noisy", author="U1")
    assert n >= 1
    assert control.is_paused(gh) is True
    # The marker carries the control:paused label.
    assert any("control:paused" in [x["name"] for x in i["labels"]]
               for i in gh.issues if i["number"] == n)


def test_set_paused_twice_comments_not_duplicates():
    gh = _FakeGh()
    n1 = control.set_paused(gh, reason="a", author="U1")
    n2 = control.set_paused(gh, reason="b", author="U1")
    assert n1 == n2  # same marker reused
    assert len([i for i in gh.issues if i["state"] == "open"]) == 1
    assert gh.comments  # second pause left a comment


def test_clear_paused_closes_marker():
    gh = _FakeGh()
    control.set_paused(gh, reason="a", author="U1")
    closed = control.clear_paused(gh, author="U1")
    assert closed and control.is_paused(gh) is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_control.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bookieskit.orchestration.control'`.

- [ ] **Step 3: Add the label**

In `src/bookieskit/orchestration/labels.py`, after `STATUS_LABELS`:

```python
CONTROL_LABELS: dict[str, tuple[str, str]] = {
    "control:paused": ("b60205", "Orchestrator paused — autonomous building halted"),
}

ALL_LABELS: dict[str, tuple[str, str]] = {
    **STREAM_LABELS,
    **STATUS_LABELS,
    **CONTROL_LABELS,
}
```

(Replace the existing `ALL_LABELS = {**STREAM_LABELS, **STATUS_LABELS}` line.)

- [ ] **Step 4: Write `control.py`**

```python
# src/bookieskit/orchestration/control.py
"""Durable pause marker for the autonomous orchestrator.

Pause state lives in GitHub (source of truth, owner-visible): a single open
Issue carrying the ``control:paused`` label. ``is_paused`` is what the cycle
checks before building; ``set_paused``/``clear_paused`` are driven by the Slack
``pause``/``resume`` commands.
"""

from bookieskit.orchestration.gh import GhRunner

PAUSE_LABEL = "control:paused"
_MARKER_TITLE = "Orchestrator: paused"


def _open_markers(gh: GhRunner) -> list[dict]:
    return gh.list_issues(state="open", labels=(PAUSE_LABEL,))


def is_paused(gh: GhRunner) -> bool:
    return bool(_open_markers(gh))


def set_paused(gh: GhRunner, *, reason: str, author: str) -> int:
    """Open (or re-comment) the pause marker. Returns its Issue number."""
    existing = _open_markers(gh)
    if existing:
        number = existing[0]["number"]
        gh.comment_issue(number, f"Re-paused by {author}: {reason}")
        return number
    return gh.create_issue(
        title=_MARKER_TITLE,
        body=f"Autonomous building paused by {author}.\n\nReason: {reason}",
        labels=(PAUSE_LABEL,),
    )


def clear_paused(gh: GhRunner, *, author: str) -> list[int]:
    """Close every open pause marker. Returns the numbers closed."""
    closed: list[int] = []
    for issue in _open_markers(gh):
        gh.close_issue(issue["number"], comment=f"Resumed by {author}")
        closed.append(issue["number"])
    return closed
```

- [ ] **Step 5: Fix the `test_labels.py` count ripple**

`control:paused` adds one label. Find the count assertions in `tests/orchestration/test_labels.py` (they assert the number of stream/status/total labels) and update them: there are now **4 stream + 3 status + 1 control = 8 total** labels. Update any `len(ALL_LABELS) == 7` / created-count assertions to `8`, and add an assertion that `"control:paused"` is in `ALL_LABELS`. (Run the file to see the exact assertions; this mirrors the earlier `status:blocked` ripple.)

- [ ] **Step 6: Run control + labels tests**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_control.py tests/orchestration/test_labels.py -v`
Expected: PASS.

- [ ] **Step 7: Lint + commit**

```bash
.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration/control.py src/bookieskit/orchestration/labels.py
git add src/bookieskit/orchestration/control.py src/bookieskit/orchestration/labels.py tests/orchestration/test_control.py tests/orchestration/test_labels.py
git commit -m "feat(orchestration): control:paused marker + pause-state helpers"
```

---

## Task 2: `pause`/`resume` command parsing + reply formatters

**Files:**
- Modify: `src/bookieskit/orchestration/chatops.py`
- Test: `tests/orchestration/test_chatops.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces (the CLI in Task 3 relies on these):
  - `@dataclass PauseCommand: reason: str = ""`
  - `@dataclass ResumeCommand: (no fields)`
  - `parse_command(text) -> ApproveCommand | PauseCommand | ResumeCommand | None` (recognizes `approve <pr>`, `pause [reason]`, `resume`)
  - `paused(reason: str) -> str`, `resumed() -> str` (Slack-mrkdwn replies)

- [ ] **Step 1: Write the failing tests** (append to `tests/orchestration/test_chatops.py`)

```python
from bookieskit.orchestration.chatops import (
    PauseCommand, ResumeCommand, paused, resumed,
)


def test_parse_command_recognizes_pause_with_optional_reason():
    assert parse_command("pause") == PauseCommand(reason="")
    assert parse_command("Pause canary too noisy") == PauseCommand(reason="canary too noisy")


def test_parse_command_recognizes_resume():
    assert parse_command("resume") == ResumeCommand()
    assert parse_command("  RESUME ") == ResumeCommand()


def test_parse_command_still_handles_approve_and_chatter():
    from bookieskit.orchestration.chatops import ApproveCommand
    assert parse_command("approve 12") == ApproveCommand(pr=12)
    assert parse_command("add Stake bookmaker") is None
    assert parse_command("pausing the project tomorrow") is None  # not a bare 'pause'


def test_pause_resume_reply_formatters():
    assert "pause" in paused("noisy").lower()
    assert "noisy" in paused("noisy")
    assert "resum" in resumed().lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_chatops.py -k "pause or resume" -v`
Expected: FAIL — `ImportError: cannot import name 'PauseCommand'`.

- [ ] **Step 3: Extend `chatops.py`**

Add the dataclasses (next to `ApproveCommand`):

```python
@dataclass
class PauseCommand:
    reason: str = ""


@dataclass
class ResumeCommand:
    pass
```

Add the regexes (next to `_APPROVE_RE`):

```python
_PAUSE_RE = re.compile(r"^\s*pause(?:\s+(.*\S))?\s*$", re.IGNORECASE)
_RESUME_RE = re.compile(r"^\s*resume\s*$", re.IGNORECASE)
```

Replace `parse_command` with the union-returning version:

```python
def parse_command(text: str):
    """Recognize an `approve <pr>`, `pause [reason]`, or `resume` command.
    Returns the matching command object, or None for anything else."""
    m = _APPROVE_RE.match(text)
    if m:
        return ApproveCommand(pr=int(m.group(1)))
    m = _PAUSE_RE.match(text)
    if m:
        return PauseCommand(reason=(m.group(1) or "").strip())
    if _RESUME_RE.match(text):
        return ResumeCommand()
    return None
```

Add the reply formatters (next to `queued`/`merged`/`rejected`):

```python
def paused(reason: str) -> str:
    tail = f" — {reason}" if reason else ""
    return f":double_vertical_bar: Orchestrator *paused*{tail}. Autonomous building halted until `resume`."


def resumed() -> str:
    return ":arrow_forward: Orchestrator *resumed*. Back to work next cycle."
```

(The `parse_command` return annotation may stay untyped or be a `Union`; keep it simple. The existing approve tests still pass — `pause`/`resume` texts weren't covered by them, and chatter like `"approve everything please"` / `"pausing..."` still returns None.)

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_chatops.py -v`
Expected: PASS (all chatops tests, old + new).

- [ ] **Step 5: Lint + commit**

```bash
.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration/chatops.py
git add src/bookieskit/orchestration/chatops.py tests/orchestration/test_chatops.py
git commit -m "feat(orchestration): parse pause/resume commands + replies"
```

---

## Task 3: `chatops pause`/`resume`/`paused` CLI

**Files:**
- Modify: `src/bookieskit/orchestration/cli.py`
- Test: `tests/orchestration/test_cli.py` (append)

**Interfaces:**
- Consumes: `chatops.load_config`, `chatops.is_authorized`, `chatops.paused`, `chatops.resumed`, `chatops.rejected`; `control.set_paused`, `control.clear_paused`, `control.is_paused`.
- Produces: CLI subcommands under the existing `chatops` group — `chatops pause --author <id> [--reason R] [--config P] [--json]`, `chatops resume --author <id> [--config P] [--json]`, `chatops paused [--json]`. `pause`/`resume` are allowlist-gated (reuse `.chatops.json`); `paused` is a read (no auth). All exit 0 on normal outcomes.

- [ ] **Step 1: Write the failing tests** (append to `tests/orchestration/test_cli.py`; reuse the existing `_FakeGh` + `_chatops_config` helper from the chatops tests)

```python
def test_chatops_pause_authorized_sets_marker(capsys, tmp_path):
    gh = _FakeGh()
    code = cli.run(cli.build_parser().parse_args(
        ["chatops", "pause", "--author", "U1", "--reason", "noisy",
         "--config", str(_chatops_config(tmp_path)), "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "paused"
    from bookieskit.orchestration import control
    assert control.is_paused(gh) is True


def test_chatops_pause_unauthorized_does_nothing(capsys, tmp_path):
    gh = _FakeGh()
    code = cli.run(cli.build_parser().parse_args(
        ["chatops", "pause", "--author", "U999",
         "--config", str(_chatops_config(tmp_path)), "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "rejected"
    from bookieskit.orchestration import control
    assert control.is_paused(gh) is False  # not paused by a non-approver


def test_chatops_resume_clears_marker(capsys, tmp_path):
    from bookieskit.orchestration import control
    gh = _FakeGh()
    control.set_paused(gh, reason="x", author="U1")
    code = cli.run(cli.build_parser().parse_args(
        ["chatops", "resume", "--author", "U1",
         "--config", str(_chatops_config(tmp_path)), "--json"]), gh=gh)
    assert code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "resumed"
    assert control.is_paused(gh) is False


def test_chatops_paused_reports_state(capsys):
    from bookieskit.orchestration import control
    gh = _FakeGh()
    control.set_paused(gh, reason="x", author="U1")
    code = cli.run(cli.build_parser().parse_args(["chatops", "paused", "--json"]), gh=gh)
    assert code == 0
    assert json.loads(capsys.readouterr().out)["paused"] is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -k "chatops_pause or chatops_resume or chatops_paused" -v`
Expected: FAIL — `invalid choice: 'pause'`.

- [ ] **Step 3: Add the parsers** (inside the existing `chsub` group in `build_parser`, next to `pause`/`approve`)

```python
    p_pause = chsub.add_parser("pause")
    p_pause.add_argument("--author", required=True)
    p_pause.add_argument("--reason", default="")
    p_pause.add_argument("--config", default=".chatops.json")
    p_pause.add_argument("--json", action="store_true", dest="as_json")

    p_resume = chsub.add_parser("resume")
    p_resume.add_argument("--author", required=True)
    p_resume.add_argument("--config", default=".chatops.json")
    p_resume.add_argument("--json", action="store_true", dest="as_json")

    p_paused = chsub.add_parser("paused")
    p_paused.add_argument("--json", action="store_true", dest="as_json")
```

- [ ] **Step 4: Add handlers + dispatch**

Add the import (with the existing orchestration imports): `from bookieskit.orchestration import control`.

```python
def _chatops_pause(args: argparse.Namespace, gh: GhRunner) -> int:
    approvers = tuple(chatops.load_config(args.config).get("approvers", []))
    if not chatops.is_authorized(args.author, approvers):
        _emit({"status": "rejected", "reason": "not authorized",
               "slack_text": chatops.rejected(0, "not authorized to pause")},
              args.as_json, [f"rejected pause by {args.author}: not authorized"])
        return 0
    control.set_paused(gh, reason=args.reason, author=args.author)
    _emit({"status": "paused", "reason": args.reason,
           "slack_text": chatops.paused(args.reason)},
          args.as_json, [f"paused: {args.reason}"])
    return 0


def _chatops_resume(args: argparse.Namespace, gh: GhRunner) -> int:
    approvers = tuple(chatops.load_config(args.config).get("approvers", []))
    if not chatops.is_authorized(args.author, approvers):
        _emit({"status": "rejected", "reason": "not authorized",
               "slack_text": chatops.rejected(0, "not authorized to resume")},
              args.as_json, [f"rejected resume by {args.author}: not authorized"])
        return 0
    control.clear_paused(gh, author=args.author)
    _emit({"status": "resumed", "slack_text": chatops.resumed()},
          args.as_json, ["resumed"])
    return 0


def _chatops_paused(args: argparse.Namespace, gh: GhRunner) -> int:
    _emit({"paused": control.is_paused(gh)}, args.as_json,
          [f"paused={control.is_paused(gh)}"])
    return 0
```

Dispatch in `run()` (with the other `chatops` branches):

```python
    if args.cmd == "chatops" and args.chatops_cmd == "pause":
        return _chatops_pause(args, gh)
    if args.cmd == "chatops" and args.chatops_cmd == "resume":
        return _chatops_resume(args, gh)
    if args.cmd == "chatops" and args.chatops_cmd == "paused":
        return _chatops_paused(args, gh)
```

- [ ] **Step 5: Run the new CLI tests + full orchestration suite**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -k "chatops_pause or chatops_resume or chatops_paused" -v`
Expected: PASS.
Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/ -q`
Expected: all pass.

- [ ] **Step 6: Lint + commit**

```bash
.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration/cli.py
git add src/bookieskit/orchestration/cli.py tests/orchestration/test_cli.py
git commit -m "feat(orchestration): chatops pause/resume/paused CLI"
```

---

## Task 4: tick lock (`runner.py` + `lock` CLI)

**Files:**
- Create: `src/bookieskit/orchestration/runner.py`
- Modify: `src/bookieskit/orchestration/cli.py`
- Test: `tests/orchestration/test_runner.py`, `tests/orchestration/test_cli.py` (append)

**Interfaces:**
- Produces:
  - `runner.acquire_lock(path: str, *, stale_after_s: float, now: float, pid: int = 0) -> bool`
  - `runner.release_lock(path: str) -> None`
  - CLI `lock acquire --path P --stale-after S [--json]` (exit **0** acquired / exit **3** busy) and `lock release --path P`. These need no `gh` — dispatch before the `GhRunner` is built.

- [ ] **Step 1: Write the failing tests**

```python
# tests/orchestration/test_runner.py
from bookieskit.orchestration import runner


def test_acquire_on_free_lock(tmp_path):
    p = str(tmp_path / "tick.lock")
    assert runner.acquire_lock(p, stale_after_s=7200, now=1000.0, pid=1) is True


def test_busy_when_fresh_lock_held(tmp_path):
    p = str(tmp_path / "tick.lock")
    assert runner.acquire_lock(p, stale_after_s=7200, now=1000.0, pid=1) is True
    # 10 minutes later, still within the 2h stale window -> busy
    assert runner.acquire_lock(p, stale_after_s=7200, now=1600.0, pid=2) is False


def test_reclaim_when_stale(tmp_path):
    p = str(tmp_path / "tick.lock")
    assert runner.acquire_lock(p, stale_after_s=7200, now=1000.0, pid=1) is True
    # 3 hours later -> stale -> reclaimed
    assert runner.acquire_lock(p, stale_after_s=7200, now=1000.0 + 3 * 3600, pid=2) is True


def test_release_is_idempotent(tmp_path):
    p = str(tmp_path / "tick.lock")
    runner.acquire_lock(p, stale_after_s=7200, now=1000.0, pid=1)
    runner.release_lock(p)
    runner.release_lock(p)  # no error on missing file
    assert runner.acquire_lock(p, stale_after_s=7200, now=1000.0, pid=3) is True


def test_corrupt_lock_is_reclaimed(tmp_path):
    p = tmp_path / "tick.lock"
    p.write_text("not json")
    assert runner.acquire_lock(str(p), stale_after_s=7200, now=1000.0, pid=1) is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bookieskit.orchestration.runner'`.

- [ ] **Step 3: Write `runner.py`**

```python
# src/bookieskit/orchestration/runner.py
"""Single-cycle tick lock for the unattended orchestrator.

A scheduled tick acquires this lock before running a cycle; a tick that fires
while a previous cycle is still running fails to acquire and skips. A lock
older than ``stale_after_s`` is treated as dead (a crashed/hung tick) and
reclaimed. ``now`` is injected so the fresh/stale branches are unit-testable.
"""

import json
import os


def acquire_lock(path: str, *, stale_after_s: float, now: float,
                 pid: int = 0) -> bool:
    """Try to take the lock. Returns True if acquired (writes the lock file),
    False if a fresh lock is already held. A stale or unreadable lock is
    reclaimed."""
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                ts = float(json.load(handle).get("ts", 0))
        except (ValueError, OSError):
            ts = 0.0  # corrupt/unreadable -> treat as stale
        if now - ts < stale_after_s:
            return False
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"ts": now, "pid": pid}, handle)
    return True


def release_lock(path: str) -> None:
    """Remove the lock file. Idempotent (a missing file is fine)."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_runner.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Add the `lock` CLI** (in `cli.py`)

Add `import os` and `import time` if not already imported. Add the parser group (after the `chatops` group):

```python
    p_lock = sub.add_parser("lock")
    lsub = p_lock.add_subparsers(dest="lock_cmd", required=True)
    p_lacq = lsub.add_parser("acquire")
    p_lacq.add_argument("--path", required=True)
    p_lacq.add_argument("--stale-after", type=float, default=7200.0, dest="stale_after")
    p_lacq.add_argument("--json", action="store_true", dest="as_json")
    p_lrel = lsub.add_parser("release")
    p_lrel.add_argument("--path", required=True)
    p_lrel.add_argument("--json", action="store_true", dest="as_json")
```

Add the handler + dispatch (the `lock` command needs no `gh`, so dispatch it FIRST in `run()`, before `gh` is constructed — like `notify`):

```python
from bookieskit.orchestration import runner  # with the other imports


def _lock(args: argparse.Namespace) -> int:
    if args.lock_cmd == "acquire":
        ok = runner.acquire_lock(
            args.path, stale_after_s=args.stale_after,
            now=time.time(), pid=os.getpid(),
        )
        _emit({"acquired": ok}, args.as_json,
              ["acquired" if ok else "busy"])
        return 0 if ok else 3
    runner.release_lock(args.path)
    _emit({"released": True}, args.as_json, ["released"])
    return 0
```

In `run()`, dispatch `lock` before the `gh = GhRunner()` line:

```python
    if args.cmd == "lock":
        return _lock(args)
```

- [ ] **Step 6: Write the failing CLI tests** (append to `tests/orchestration/test_cli.py`)

```python
def test_lock_acquire_then_busy_then_release(tmp_path, capsys):
    p = str(tmp_path / "tick.lock")
    assert cli.run(cli.build_parser().parse_args(
        ["lock", "acquire", "--path", p, "--json"])) == 0
    capsys.readouterr()
    # second acquire while held -> exit 3 (busy)
    assert cli.run(cli.build_parser().parse_args(
        ["lock", "acquire", "--path", p, "--json"])) == 3
    capsys.readouterr()
    # release, then acquire succeeds again
    assert cli.run(cli.build_parser().parse_args(
        ["lock", "release", "--path", p, "--json"])) == 0
    capsys.readouterr()
    assert cli.run(cli.build_parser().parse_args(
        ["lock", "acquire", "--path", p, "--json"])) == 0
```

- [ ] **Step 7: Run the CLI lock tests + full orchestration suite**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -k lock -v`
Expected: PASS.
Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/ -q`
Expected: all pass.

- [ ] **Step 8: Lint + commit**

```bash
.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration/runner.py src/bookieskit/orchestration/cli.py
git add src/bookieskit/orchestration/runner.py src/bookieskit/orchestration/cli.py tests/orchestration/test_runner.py tests/orchestration/test_cli.py
git commit -m "feat(orchestration): tick lock (runner) + lock CLI"
```

---

## Task 5: Unattended runner wiring (scripts, skill, perms, docs) + final gate

**Files:**
- Create: `scripts/orchestrator-tick.ps1`, `scripts/install-orchestrator.ps1`, `.claude/orchestrator-settings.json`, `docs/ORCHESTRATOR_SETUP.md`
- Modify: `.claude/skills/orchestrate/SKILL.md`, `CLAUDE.md`, `.gitignore`

**Interfaces:**
- Consumes: the `lock acquire/release`, `chatops pause/resume/paused`, and existing `/orchestrate` cycle from Tasks 1-4.
- Produces: the scheduled-tick wiring. Verified by structural review + the full gate (no pytest for `.ps1`/docs).

- [ ] **Step 1: Create `.gitignore` entries** — append:

```
.orchestrator/
```

(The lockfile lives at `.orchestrator/tick.lock` and logs at `.orchestrator/logs/`.)

- [ ] **Step 2: Create `scripts/orchestrator-tick.ps1`**

```powershell
# One unattended orchestrator tick: lock -> headless cycle -> release -> log.
# Registered to run every 15 min by install-orchestrator.ps1.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
$lockDir = Join-Path $repo ".orchestrator"
$lock = Join-Path $lockDir "tick.lock"
$logDir = Join-Path $lockDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("tick-" + (Get-Date -Format "yyyyMMdd") + ".log")
function Log($m) { "$(Get-Date -Format o) $m" | Add-Content -Encoding utf8 $log }

# Acquire the tick lock; skip cleanly if a previous cycle is still running.
& $py -m bookieskit.orchestration lock acquire --path $lock | Out-Null
if ($LASTEXITCODE -ne 0) { Log "busy — previous cycle still running; skipping tick"; exit 0 }

try {
    Log "tick start"
    # Headless one cycle under the constrained permission profile.
    & claude -p "/orchestrate" --settings (Join-Path $repo ".claude\orchestrator-settings.json") 2>&1 | Add-Content -Encoding utf8 $log
    Log "tick done (claude exit $LASTEXITCODE)"
}
finally {
    & $py -m bookieskit.orchestration lock release --path $lock | Out-Null
    Log "lock released"
}
```

(If `claude`'s `--settings` flag name differs in the installed version, the implementer adjusts to the current flag for supplying a permission/settings file — confirm with `claude --help`; the intent is "run headless with the constrained allowlist.")

- [ ] **Step 3: Create `.claude/orchestrator-settings.json`** — the constrained allowlist (no direct `gh pr merge`, no push to `main`):

```json
{
  "permissions": {
    "allow": [
      "Bash(.venv/Scripts/python.exe -m bookieskit.orchestration:*)",
      "Bash(.venv/Scripts/python.exe -m bookieskit.devtools:*)",
      "Bash(gh issue:*)",
      "Bash(gh pr create:*)",
      "Bash(gh pr view:*)",
      "Bash(gh pr checks:*)",
      "Bash(gh pr comment:*)",
      "Bash(gh pr edit:*)",
      "Bash(gh label:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git checkout:*)",
      "Bash(git switch:*)",
      "Bash(git push --set-upstream origin feat/*)",
      "Bash(git push origin feat/*)",
      "Read",
      "Write",
      "Edit",
      "Glob",
      "Grep",
      "Agent"
    ],
    "deny": [
      "Bash(gh pr merge:*)",
      "Bash(git push origin main:*)",
      "Bash(git push:* main)"
    ]
  }
}
```

(The merge route is the allowed `bookieskit.orchestration chatops approve` CLI, which gates on a human Slack `approve` and runs `gh pr merge` internally as a subprocess — not an agent tool call. `gh pr merge` as a *direct* agent tool is denied. The implementer verifies the exact `permissions` schema Claude Code's installed version expects and adjusts keys if needed, preserving the allow/deny intent.)

- [ ] **Step 4: Create `scripts/install-orchestrator.ps1`**

```powershell
# Register (or refresh) the every-15-minutes orchestrator tick in Task Scheduler.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$tick = Join-Path $repo "scripts\orchestrator-tick.ps1"
$taskName = "BookieskitOrchestrator"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$tick`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 15)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "bookieskit agent company — 15-min orchestrate tick" `
    -Force
Write-Host "Registered task '$taskName' (every 15 min). Remove with: Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
```

- [ ] **Step 5: Create `docs/ORCHESTRATOR_SETUP.md`**

```markdown
# Always-on orchestrator — owner setup

Runs the one-cycle `/orchestrate` loop unattended every 15 minutes on your
in-region machine, so `#tickets` is drained and PRs are built without the
console. Merge still requires your Slack `approve` (the gate never relaxes).

## Prerequisites
1. Slack cockpit wired (`docs/SLACK_SETUP.md`) — the tick reads/posts Slack via the MCP.
2. `.chatops.json` filled with real approver IDs + `#tickets` channel.
3. `gh auth status` is authenticated on this machine.
4. **Branch protection on `main`** (strongly recommended structural backstop):
   GitHub → repo → Settings → Branches → protect `main`: require a PR before
   merging + require CI to pass. Then no unattended process can land on `main`
   without a reviewed, approved PR — defense in depth behind the permission profile.

## Install
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-orchestrator.ps1
```
This registers a Task Scheduler job `BookieskitOrchestrator` firing every 15 min.

## Operate (from Slack `#tickets`)
- Post work requests → filed as `stream:directed` Issues and built.
- `approve <pr>` → merges a green loop PR (allowlist-gated).
- `pause` (optionally `pause <reason>`) → halts autonomous building (a `control:paused` marker Issue opens).
- `resume` → clears the pause; building resumes next tick.

## Observe / troubleshoot
- Logs: `.orchestrator/logs/tick-YYYYMMDD.log` (each tick's outcome; gitignored).
- A tick that fires mid-build logs "busy … skipping" and exits — by design.
- Check the task: `Get-ScheduledTask -TaskName BookieskitOrchestrator`.
- Stop it entirely: `Unregister-ScheduledTask -TaskName BookieskitOrchestrator -Confirm:$false`.

## Limits (current)
- Runs only while this machine is **on** (Task Scheduler `-StartWhenAvailable`
  catches up a missed tick, but a sleeping machine doesn't run). For true 24/7,
  relocate the same tick to an always-on in-region host (future upgrade).
- The tick uses a **constrained permission profile** (`.claude/orchestrator-settings.json`):
  it cannot `gh pr merge` directly or push to `main`; merge flows only through
  the human-gated `chatops approve`.
```

- [ ] **Step 6: Update the orchestrate skill** — in `.claude/skills/orchestrate/SKILL.md`, extend the ChatOps intake step (step 1) to handle `pause`/`resume`, and add a pause-check before building. In step 1's per-message handling, after the `approve` bullet, add:

```markdown
   - If it parses as `pause [reason]`: run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops pause --author <slack-user-id> --reason "<reason>" --json` and post the `slack_text` to `#tickets`.
   - If it parses as `resume`: run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops resume --author <slack-user-id> --json` and post the `slack_text` to `#tickets`.
```

After step 1 (intake) and before step 2 (Pick the top item), add a new pause-gate paragraph:

```markdown
1b. **Pause gate.** Run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops paused --json`. If `paused` is true → report "paused — skipping build this cycle" and END the cycle (do NOT claim or build). Intake + `approve` + `resume` above still ran; only building is gated.
```

- [ ] **Step 7: Add a "Always-on orchestrator" section to `CLAUDE.md`** (after the ChatOps section):

```markdown
## Always-on orchestrator (unattended)

The loop can run unattended via Windows Task Scheduler (`scripts/orchestrator-tick.ps1`,
every 15 min) — see `docs/ORCHESTRATOR_SETUP.md`. Each tick takes a lockfile
(`.orchestrator/tick.lock`; a mid-build tick skips, a stale lock is reclaimed) and
runs one headless `/orchestrate` cycle under a constrained permission profile
(`.claude/orchestrator-settings.json`: no direct `gh pr merge`, no push to `main`).
A `pause`/`resume` Slack command (allowlist-gated, a `control:paused` marker Issue)
is the kill-switch; the cycle skips building while paused. The never-merge gate is
unchanged — merge happens only via the human-gated `chatops approve`. Recommend
GitHub branch protection on `main` as the structural backstop.
```

- [ ] **Step 8: Final gate** — full suite + ruff + a smoke check of the new CLIs:

```bash
.venv/Scripts/python.exe -m pytest tests/ -q          # expect all pass, 1 skipped
.venv/Scripts/python.exe -m ruff check .              # All checks passed!
.venv/Scripts/python.exe -m bookieskit.orchestration chatops paused --json   # smoke: prints {"paused": ...}
```

- [ ] **Step 9: Commit**

```bash
git add scripts/orchestrator-tick.ps1 scripts/install-orchestrator.ps1 .claude/orchestrator-settings.json docs/ORCHESTRATOR_SETUP.md .claude/skills/orchestrate/SKILL.md CLAUDE.md .gitignore
git commit -m "feat(orchestration): unattended tick runner — scheduler, perms, pause gate, setup doc"
```

---

## Self-Review

**1. Spec coverage:**
- 15-min Task Scheduler tick → headless one-cycle → Task 5 (`orchestrator-tick.ps1` + `install-orchestrator.ps1`). ✅
- Concurrency lock + stale reclaim → Task 4 (`runner` + `lock` CLI) + Task 5 (`.ps1` uses it). ✅
- `pause`/`resume` kill-switch + durable marker → Task 1 (`control.py` + label), Task 2 (parse), Task 3 (CLI), Task 5 (skill handling + pause gate). ✅
- Constrained permission profile, no direct merge / no main push → Task 5 (`.claude/orchestrator-settings.json` + branch-protection rec in setup doc). ✅
- Structural never-merge (merge only via human-gated `chatops approve`) → preserved (allowlist denies `gh pr merge`; approve CLI runs it internally). ✅
- Quiet-on-empty → inherited from the existing cycle/notifications (no new empty posts added). ✅
- Setup doc + CLAUDE.md → Task 5 Steps 5,7. ✅
- Tests offline; live owner-gated/deferred → Tasks 1-4 offline; `.ps1`/scheduler owner-verified. ✅
- `status` (deferred) → not built (correct). ✅

**2. Placeholder scan:** No TBD/TODO. Task 5 notes "verify the exact `claude --settings`/`permissions` schema in the installed version" — a real instruction to confirm a version-specific flag/key against `claude --help`, with the concrete intent + example given (not a vague gap). Test-fakes reuse the established `_FakeGh`/`_chatops_config` helpers.

**3. Type consistency:** `control.is_paused/set_paused(reason,author)/clear_paused(author)` identical across Task 1 (def), Task 3 (CLI), and the skill (`chatops paused`). `parse_command → ApproveCommand|PauseCommand|ResumeCommand|None` consistent (Task 2 def, used by the skill). `runner.acquire_lock(path,*,stale_after_s,now,pid)/release_lock(path)` identical in Task 4 (def, CLI). `lock acquire` exit codes (0/3) consistent between the CLI (Task 4) and the `.ps1` (`$LASTEXITCODE -ne 0`). CLI groups (`chatops pause/resume/paused`, `lock acquire/release`) match the skill commands + the `.ps1`. Label `control:paused` consistent (labels.py, control.py, setup doc, CLAUDE.md).
