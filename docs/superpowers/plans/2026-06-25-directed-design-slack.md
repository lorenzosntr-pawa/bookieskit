# Collaborative Directed Design in Slack — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade directed work from "decide-and-document autonomous build" to a collaborative Slack design dialogue (one question at a time, llm-council on real tradeoffs, owner-approved before build), running on a cheap-gate continuous runtime so it's conversational without idle token burn.

**Architecture:** Pure/offline-tested Python for the logic — a `gate` (cheap "should I wake the agent?" decision), `chatops` command parsing for `design ok`/`design no`/`council`, two new status labels + a priority rule — plus orchestrate-skill prose for the design phase and a re-pointed PowerShell tick that runs the gate before the agent.

**Tech Stack:** Python 3.11+ stdlib (`json`, `re`, `urllib`, `dataclasses`); pytest; ruff; `gh` via `GhRunner`; Slack Web API (bot token) for the cheap gate; Windows Task Scheduler / PowerShell; Claude Code headless.

## Global Constraints

- **Python floor 3.11; stdlib only — no new dependencies.** Slack reads in the gate use `urllib` (the bot token from `.mcp.json`), not the MCP.
- **No directed build without `design ok`** (allowlist-gated): a `status:designing` item is NOT buildable; only `status:ready` is. The design gate is as strict as the merge gate.
- **Maintenance/canary stay decide-and-document** — the design phase is `stream:directed` only.
- **Cheap-gate**: the frequent poll is pure Python (Slack Web API + `gh`, no agent); `claude -p "/orchestrate"` fires only when the gate returns `run: true`.
- **Council is best-effort + agent-decided** (genuine stakes/tradeoff), surfaced in the thread; the owner is never bound. `council <issue#>` can force it.
- **The build reads the agreed design from the Issue body** as its spec.
- `src/` stays ruff-clean; normal/no-op outcomes exit 0; only operational errors exit non-zero.
- Slack ts compared as `float` (never lexicographically).

---

## File Structure
- `src/bookieskit/orchestration/labels.py` — **modify.** Add `status:designing`, `status:ready` (a `DESIGN_LABELS` dict into `ALL_LABELS`).
- `src/bookieskit/orchestration/priority.py` — **modify.** Add `status:designing` to `_INACTIVE_STATUSES` (designing = not buildable; `status:ready` stays buildable).
- `src/bookieskit/orchestration/chatops.py` — **modify.** Add `DesignOkCommand`/`DesignChangesCommand`/`CouncilCommand` + parse them; add `design_ready`/`design_changes_ack` reply formatters.
- `src/bookieskit/orchestration/gate.py` — **new.** Pure wake-decision helpers.
- `src/bookieskit/orchestration/cli.py` — **modify.** Add `gate` and `chatops design-ok`/`design-no`/`council` subcommands.
- `.claude/skills/orchestrate/SKILL.md` — **modify.** Directed intake → `status:designing`; the design step; build reads Issue-body design.
- `scripts/orchestrator-tick.ps1` — **modify.** Run `gate` first; only invoke `claude` when `run`.
- `scripts/install-orchestrator.ps1` — **modify.** Interval 15 min → 1 min.
- `CLAUDE.md` — **modify.** "Directed design in Slack" note.
- Tests: `tests/orchestration/test_gate.py` (new); additions to `test_labels.py`, `test_priority.py`, `test_chatops.py`, `test_cli.py`.

---

## Task 1: status labels + priority rule

**Files:** Modify `labels.py`, `priority.py`; update `tests/orchestration/test_labels.py`, `tests/orchestration/test_priority.py`.

**Interfaces — Produces:** `labels.DESIGN_LABELS` (contains `status:designing`, `status:ready`), both in `ALL_LABELS`; `priority._INACTIVE_STATUSES` now includes `status:designing` (so `next_work_item` skips designing items; `status:ready` is selectable).

- [ ] **Step 1: Failing priority tests** (append to `tests/orchestration/test_priority.py`)

```python
def test_designing_items_are_not_built():
    issues = [_issue(1, "stream:directed", "status:designing"),
              _issue(2, "stream:maintenance")]
    assert next_work_item(issues)["number"] == 2  # designing skipped


def test_ready_items_are_buildable():
    issues = [_issue(5, "stream:directed", "status:ready")]
    assert next_work_item(issues)["number"] == 5  # ready is actionable
```

- [ ] **Step 2: Run → fail** — `.venv/Scripts/python.exe -m pytest tests/orchestration/test_priority.py -k "designing or ready" -v` → `test_designing_items_are_not_built` FAILS (designing item currently selected).

- [ ] **Step 3: Add the labels** (`labels.py`, after `CONTROL_LABELS`)

```python
DESIGN_LABELS: dict[str, tuple[str, str]] = {
    "status:designing": ("c5def5", "Directed item being designed with the owner in Slack"),
    "status:ready": ("0e8a16", "Design approved — ready to build"),
}

ALL_LABELS: dict[str, tuple[str, str]] = {
    **STREAM_LABELS,
    **STATUS_LABELS,
    **CONTROL_LABELS,
    **DESIGN_LABELS,
}
```
(Replace the existing `ALL_LABELS` assignment.)

- [ ] **Step 4: Add `status:designing` to the inactive set** (`priority.py`)

```python
_INACTIVE_STATUSES = frozenset(
    {"status:claimed", "status:in-review", "status:blocked", "status:designing"}
)
```

- [ ] **Step 5: Run priority tests → pass.**

- [ ] **Step 6: Fix the `test_labels.py` ripple.** Totals are now **4 stream + 3 status + 1 control + 2 design = 10**. Update the count assertions (`len(ALL_LABELS) == 10`, created-all = 10, created-missing recomputed) and assert `"status:designing"` and `"status:ready"` are in `ALL_LABELS`. Run `tests/orchestration/test_labels.py` → green.

- [ ] **Step 7: Full orchestration suite + ruff + commit**
```bash
.venv/Scripts/python.exe -m pytest tests/orchestration/ -q
.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration/labels.py src/bookieskit/orchestration/priority.py
git add src/bookieskit/orchestration/labels.py src/bookieskit/orchestration/priority.py tests/orchestration/test_labels.py tests/orchestration/test_priority.py
git commit -m "feat(orchestration): status:designing/ready labels + priority skips designing"
```

---

## Task 2: `design ok`/`design no`/`council` command parsing + replies

**Files:** Modify `chatops.py`; append to `tests/orchestration/test_chatops.py`.

**Interfaces — Produces:**
- `@dataclass DesignOkCommand: issue: int`
- `@dataclass DesignChangesCommand: issue: int; notes: str`
- `@dataclass CouncilCommand: issue: int`
- `parse_command` also returns these (recognizing `design ok <n>`, `design no <n> <notes>`, `council <n>`).
- `design_ready(issue: int) -> str`, `design_changes_ack(issue: int) -> str` (Slack-mrkdwn replies).

- [ ] **Step 1: Failing tests** (append to `tests/orchestration/test_chatops.py`)

```python
from bookieskit.orchestration.chatops import (
    CouncilCommand, DesignChangesCommand, DesignOkCommand,
    design_changes_ack, design_ready,
)


def test_parse_design_ok():
    assert parse_command("design ok 42") == DesignOkCommand(issue=42)
    assert parse_command("Design OK #42") == DesignOkCommand(issue=42)


def test_parse_design_no_with_notes():
    cmd = parse_command("design no 42 use a parameterized mapping instead")
    assert cmd == DesignChangesCommand(issue=42, notes="use a parameterized mapping instead")


def test_parse_council():
    assert parse_command("council 42") == CouncilCommand(issue=42)


def test_design_commands_dont_collide_with_others():
    from bookieskit.orchestration.chatops import ApproveCommand
    assert parse_command("approve 14") == ApproveCommand(pr=14)
    assert parse_command("designing something later") is None
    assert parse_command("design 42") is None  # needs ok/no


def test_design_reply_formatters():
    assert "#42" in design_ready(42) and "ready" in design_ready(42).lower()
    assert "#42" in design_changes_ack(42)
```

- [ ] **Step 2: Run → fail** (`ImportError: ... DesignOkCommand`).

- [ ] **Step 3: Extend `chatops.py`.** Add the dataclasses (after `ResumeCommand`):

```python
@dataclass
class DesignOkCommand:
    issue: int


@dataclass
class DesignChangesCommand:
    issue: int
    notes: str


@dataclass
class CouncilCommand:
    issue: int
```

Add regexes (with the others):

```python
_DESIGN_OK_RE = re.compile(r"^\s*design\s+ok\s+#?(\d+)\s*$", re.IGNORECASE)
_DESIGN_NO_RE = re.compile(r"^\s*design\s+no\s+#?(\d+)\s+(.*\S)\s*$", re.IGNORECASE)
_COUNCIL_RE = re.compile(r"^\s*council\s+#?(\d+)\s*$", re.IGNORECASE)
```

Extend `parse_command` (check these BEFORE the bare `approve`/`pause`/`resume`; order so `design ok`/`design no` match before anything else):

```python
def parse_command(text: str):
    m = _DESIGN_OK_RE.match(text)
    if m:
        return DesignOkCommand(issue=int(m.group(1)))
    m = _DESIGN_NO_RE.match(text)
    if m:
        return DesignChangesCommand(issue=int(m.group(1)), notes=m.group(2).strip())
    m = _COUNCIL_RE.match(text)
    if m:
        return CouncilCommand(issue=int(m.group(1)))
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

Add formatters (with the others):

```python
def design_ready(issue: int) -> str:
    return f":white_check_mark: Design for *#{issue}* approved — marked *ready to build*. I'll build it next cycle."


def design_changes_ack(issue: int) -> str:
    return f":pencil: Got it — revising the design for *#{issue}*. I'll repost shortly."
```

- [ ] **Step 4: Run the full chatops test file → pass** (old + new; verify `approve`/`pause`/`resume` + chatter still behave).

- [ ] **Step 5: ruff + commit**
```bash
.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration/chatops.py
git add src/bookieskit/orchestration/chatops.py tests/orchestration/test_chatops.py
git commit -m "feat(orchestration): parse design ok/no + council commands"
```

---

## Task 3: cheap-gate decision helpers (`gate.py`)

**Files:** Create `src/bookieskit/orchestration/gate.py`; create `tests/orchestration/test_gate.py`.

**Interfaces — Produces:**
- `new_ticket_waiting(newest_human_ts: str | None, watermark_ts: str | None) -> bool`
- `thread_reply_waiting(thread_messages: list[dict]) -> bool` (True iff the newest message in a design thread is from a human — the agent owes a reply)
- `should_run(*, queue_actionable: bool, new_ticket: bool, designing_reply: bool) -> bool`

- [ ] **Step 1: Failing tests** (`tests/orchestration/test_gate.py`)

```python
from bookieskit.orchestration import gate


def test_new_ticket_waiting():
    assert gate.new_ticket_waiting("1718900100.0", "1718900000.0") is True   # newer
    assert gate.new_ticket_waiting("1718900000.0", "1718900100.0") is False  # older
    assert gate.new_ticket_waiting("1718900000.0", None) is True             # no watermark yet
    assert gate.new_ticket_waiting(None, "1718900000.0") is False            # no message


def test_thread_reply_waiting_true_when_last_is_human():
    thread = [{"type": "message"}, {"type": "message", "bot_id": "B1"},
              {"type": "message"}]  # last is human -> agent owes reply
    assert gate.thread_reply_waiting(thread) is True


def test_thread_reply_waiting_false_when_last_is_bot():
    thread = [{"type": "message"}, {"type": "message", "bot_id": "B1"}]
    assert gate.thread_reply_waiting(thread) is False


def test_thread_reply_waiting_false_when_empty():
    assert gate.thread_reply_waiting([]) is False


def test_should_run_is_or_of_signals():
    assert gate.should_run(queue_actionable=True, new_ticket=False, designing_reply=False) is True
    assert gate.should_run(queue_actionable=False, new_ticket=True, designing_reply=False) is True
    assert gate.should_run(queue_actionable=False, new_ticket=False, designing_reply=True) is True
    assert gate.should_run(queue_actionable=False, new_ticket=False, designing_reply=False) is False
```

- [ ] **Step 2: Run → fail** (`ModuleNotFoundError ... gate`).

- [ ] **Step 3: Write `gate.py`**

```python
# src/bookieskit/orchestration/gate.py
"""Cheap wake-decision for the continuous orchestrator.

Pure logic only — the CLI gathers the inputs (a Slack Web API read + a gh
queue check) cheaply and calls these, so the expensive ``claude -p`` cycle
fires only when there is genuinely something to do.
"""


def new_ticket_waiting(newest_human_ts: str | None,
                       watermark_ts: str | None) -> bool:
    """True if a #tickets human message is newer than the watermark."""
    if newest_human_ts is None:
        return False
    if watermark_ts is None:
        return True
    return float(newest_human_ts) > float(watermark_ts)


def thread_reply_waiting(thread_messages: list[dict]) -> bool:
    """True if the NEWEST message in a design thread is from a human (the agent
    owes a reply). Slack tags bot messages with ``bot_id``. ``thread_messages``
    is oldest-first (as gh/Slack ``conversations.replies`` returns)."""
    msgs = [m for m in thread_messages if m.get("type") == "message"]
    if not msgs:
        return False
    return not msgs[-1].get("bot_id")


def should_run(*, queue_actionable: bool, new_ticket: bool,
               designing_reply: bool) -> bool:
    """Wake the agent iff any wake-signal is set."""
    return bool(queue_actionable or new_ticket or designing_reply)
```

- [ ] **Step 4: Run → pass** (7 tests).

- [ ] **Step 5: ruff + commit**
```bash
.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration/gate.py
git add src/bookieskit/orchestration/gate.py tests/orchestration/test_gate.py
git commit -m "feat(orchestration): cheap-gate wake-decision helpers"
```

---

## Task 4: `gate` CLI (Slack read + watermark + decision)

**Files:** Modify `cli.py`; append to `tests/orchestration/test_cli.py`.

**Interfaces — Consumes:** `gate.*`, `priority.next_work_item`, `GhRunner`. **Produces:** `gate [--config .chatops.json] [--watermark PATH] [--json]` — gathers signals and prints `{"run": bool, "reason": str, "newest_ts": str|null}`; exit 0 always (it's a read). It must run with **no `gh`/network failure aborting it** — wrap Slack/gh reads so a failure degrades to the queue check.

The CLI reads `#tickets` via the Slack Web API (token from the config's sibling `.mcp.json`, or an env var) — factor the HTTP into a tiny injectable `slack_get(method, **params)` seam so the test can supply a fake (no real network in tests).

- [ ] **Step 1: Failing test** (append to `tests/orchestration/test_cli.py`) — inject a fake Slack reader + fake gh and assert the `run`/`reason`:

```python
def test_gate_runs_when_queue_actionable(tmp_path, capsys, monkeypatch):
    # A ready directed issue -> actionable -> run=true even with no Slack signal.
    gh = _FakeGh(issues=[{"number": 5, "title": "t",
        "body": "```yaml\nsignature: s\nstream: stream:directed\n```",
        "labels": [{"name": "stream:directed"}, {"name": "status:ready"}],
        "state": "open"}])
    # Fake the Slack reader so no network happens.
    monkeypatch.setattr(cli, "_slack_get", lambda method, **kw: {"messages": [], "ok": True})
    code = cli.run(cli.build_parser().parse_args(
        ["gate", "--watermark", str(tmp_path / "wm"), "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["run"] is True


def test_gate_quiet_when_nothing_to_do(tmp_path, capsys, monkeypatch):
    gh = _FakeGh()  # empty queue
    monkeypatch.setattr(cli, "_slack_get", lambda method, **kw: {"messages": [], "ok": True})
    code = cli.run(cli.build_parser().parse_args(
        ["gate", "--watermark", str(tmp_path / "wm"), "--json"]), gh=gh)
    assert code == 0
    assert json.loads(capsys.readouterr().out)["run"] is False
```

- [ ] **Step 2: Run → fail** (`invalid choice: 'gate'`).

- [ ] **Step 3: Add the `gate` parser + `_slack_get` seam + handler.** In `cli.py`:

```python
import urllib.parse
import urllib.request

def _slack_get(method: str, *, token: str, **params) -> dict:
    url = "https://slack.com/api/" + method + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req) as r:
        return json.load(r)
```

Parser (top-level, like `notify`/`lock` — needs `gh` for the queue, so dispatch it in the gh-using section):
```python
    p_gate = sub.add_parser("gate")
    p_gate.add_argument("--config", default=".chatops.json")
    p_gate.add_argument("--watermark", default=".orchestrator/slack-watermark")
    p_gate.add_argument("--json", action="store_true", dest="as_json")
```

Handler — reads the bot token from `.mcp.json` (sibling of `.chatops.json`), the channel from `.chatops.json`, computes the three signals, decides, and prints. Slack/gh reads are guarded so a failure degrades to the queue-only decision:
```python
def _read_token() -> str | None:
    try:
        return json.load(open(".mcp.json"))["mcpServers"]["slack"]["env"]["SLACK_MCP_XOXB_TOKEN"]
    except (OSError, KeyError, ValueError):
        return None


def _gate(args: argparse.Namespace, gh: GhRunner) -> int:
    from bookieskit.orchestration import chatops, gate
    # 1) queue actionable?
    try:
        actionable = next_work_item(Queue(gh, ensure=False).list_open()) is not None
    except Exception:
        actionable = False
    # 2) new #tickets human message? + 3) a designing thread awaiting our reply?
    new_ticket = designing_reply = False
    newest_ts = None
    token = _read_token()
    cfg = {}
    try:
        cfg = chatops.load_config(args.config)
    except Exception:
        cfg = {}
    channel = cfg.get("tickets_channel")
    if token and channel:
        try:
            hist = _slack_get("conversations.history", token=token, channel=channel, limit=20)
            humans = [m for m in hist.get("messages", [])
                      if m.get("type") == "message" and not m.get("bot_id")]
            newest_ts = humans[0]["ts"] if humans else None  # history is newest-first
            wm = None
            try:
                wm = open(args.watermark, encoding="utf-8").read().strip() or None
            except OSError:
                wm = None
            new_ticket = gate.new_ticket_waiting(newest_ts, wm)
            # designing items: any thread whose last message is human?
            for issue in Queue(gh, ensure=False).list_open(stream="stream:directed"):
                if "status:designing" not in {lb["name"] for lb in issue.get("labels", [])}:
                    continue
                thread_ts = parse_meta(issue.get("body", "")).get("slack_ts")
                if not thread_ts:
                    continue
                rep = _slack_get("conversations.replies", token=token, channel=channel, ts=thread_ts)
                if gate.thread_reply_waiting(rep.get("messages", [])):
                    designing_reply = True
                    break
        except Exception:
            pass  # Slack unreachable -> degrade to queue-only
    run = gate.should_run(queue_actionable=actionable, new_ticket=new_ticket,
                          designing_reply=designing_reply)
    reason = ("actionable-queue" if actionable else
              "new-ticket" if new_ticket else
              "design-reply" if designing_reply else "idle")
    _emit({"run": run, "reason": reason, "newest_ts": newest_ts}, args.as_json,
          [f"run={run} ({reason})"])
    return 0
```

Dispatch in `run()` (gh-using section): `if args.cmd == "gate": return _gate(args, gh)`.

- [ ] **Step 4: Run the gate CLI tests + full orchestration suite → pass.**

- [ ] **Step 5: ruff + commit**
```bash
.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration/cli.py
git add src/bookieskit/orchestration/cli.py tests/orchestration/test_cli.py
git commit -m "feat(orchestration): gate CLI (cheap wake decision over Slack + queue)"
```

---

## Task 5: `chatops design-ok`/`design-no`/`council` CLI + label transition

**Files:** Modify `cli.py`; append to `tests/orchestration/test_cli.py`.

**Interfaces — Consumes:** `chatops.load_config`/`is_authorized`/`design_ready`/`design_changes_ack`; `GhRunner.edit_issue`/`comment_issue`. **Produces:** `chatops design-ok --issue <n> --author <id> [--config] [--json]` (allowlisted → flips `status:designing`→`status:ready`, comments the approval), `chatops design-no --issue <n> --author <id> --notes "..."` (comments the notes back on the Issue, keeps `status:designing`), `chatops council --issue <n> --author <id>` (comments a council-requested marker). All exit 0; unauthorized → `rejected`, no state change.

- [ ] **Step 1: Failing tests** (append to `tests/orchestration/test_cli.py`)

```python
def test_design_ok_flips_designing_to_ready(capsys, tmp_path):
    gh = _FakeGh(issues=[{"number": 7, "title": "t", "body": "b",
        "labels": [{"name": "stream:directed"}, {"name": "status:designing"}],
        "state": "open"}])
    code = cli.run(cli.build_parser().parse_args(
        ["chatops", "design-ok", "--issue", "7", "--author", "U1",
         "--config", str(_chatops_config(tmp_path)), "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ready"
    labels = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:ready" in labels and "status:designing" not in labels


def test_design_ok_unauthorized_no_change(capsys, tmp_path):
    gh = _FakeGh(issues=[{"number": 7, "title": "t", "body": "b",
        "labels": [{"name": "stream:directed"}, {"name": "status:designing"}],
        "state": "open"}])
    code = cli.run(cli.build_parser().parse_args(
        ["chatops", "design-ok", "--issue", "7", "--author", "U999",
         "--config", str(_chatops_config(tmp_path)), "--json"]), gh=gh)
    assert code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "rejected"
    labels = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:designing" in labels  # unchanged
```

- [ ] **Step 2: Run → fail** (`invalid choice: 'design-ok'`).

- [ ] **Step 3: Add the parsers** (into the existing `chsub` group):
```python
    p_dok = chsub.add_parser("design-ok")
    p_dok.add_argument("--issue", type=int, required=True)
    p_dok.add_argument("--author", required=True)
    p_dok.add_argument("--config", default=".chatops.json")
    p_dok.add_argument("--json", action="store_true", dest="as_json")

    p_dno = chsub.add_parser("design-no")
    p_dno.add_argument("--issue", type=int, required=True)
    p_dno.add_argument("--author", required=True)
    p_dno.add_argument("--notes", required=True)
    p_dno.add_argument("--config", default=".chatops.json")
    p_dno.add_argument("--json", action="store_true", dest="as_json")

    p_council = chsub.add_parser("council")
    p_council.add_argument("--issue", type=int, required=True)
    p_council.add_argument("--author", required=True)
    p_council.add_argument("--config", default=".chatops.json")
    p_council.add_argument("--json", action="store_true", dest="as_json")
```

- [ ] **Step 4: Handlers + dispatch**
```python
def _chatops_design_ok(args: argparse.Namespace, gh: GhRunner) -> int:
    approvers = tuple(chatops.load_config(args.config).get("approvers", []))
    if not chatops.is_authorized(args.author, approvers):
        _emit({"status": "rejected", "reason": "not authorized",
               "slack_text": chatops.rejected(args.issue, "not authorized to approve a design")},
              args.as_json, [f"rejected design-ok #{args.issue}"])
        return 0
    gh.edit_issue(args.issue, add_labels=["status:ready"], remove_labels=["status:designing"])
    gh.comment_issue(args.issue, f"Design approved by {args.author} -> status:ready.")
    _emit({"status": "ready", "issue": args.issue, "slack_text": chatops.design_ready(args.issue)},
          args.as_json, [f"design-ok #{args.issue} -> ready"])
    return 0


def _chatops_design_no(args: argparse.Namespace, gh: GhRunner) -> int:
    approvers = tuple(chatops.load_config(args.config).get("approvers", []))
    if not chatops.is_authorized(args.author, approvers):
        _emit({"status": "rejected", "reason": "not authorized",
               "slack_text": chatops.rejected(args.issue, "not authorized")},
              args.as_json, [f"rejected design-no #{args.issue}"])
        return 0
    gh.comment_issue(args.issue, f"Design change requested by {args.author}: {args.notes}")
    _emit({"status": "changes", "issue": args.issue,
           "slack_text": chatops.design_changes_ack(args.issue)},
          args.as_json, [f"design-no #{args.issue}: {args.notes}"])
    return 0


def _chatops_council(args: argparse.Namespace, gh: GhRunner) -> int:
    approvers = tuple(chatops.load_config(args.config).get("approvers", []))
    if not chatops.is_authorized(args.author, approvers):
        _emit({"status": "rejected", "reason": "not authorized"}, args.as_json,
              [f"rejected council #{args.issue}"])
        return 0
    gh.comment_issue(args.issue, f"llm-council pass requested by {args.author}.")
    _emit({"status": "council-requested", "issue": args.issue}, args.as_json,
          [f"council requested #{args.issue}"])
    return 0
```
Dispatch in `run()` with the other `chatops` branches (`args.chatops_cmd in {"design-ok","design-no","council"}`).

- [ ] **Step 5: Run new tests + full orchestration suite → pass. ruff. Commit**
```bash
git add src/bookieskit/orchestration/cli.py tests/orchestration/test_cli.py
git commit -m "feat(orchestration): chatops design-ok/design-no/council CLI"
```

---

## Task 6: orchestrate skill design phase + cheap-gate wiring + final gate

**Files:** Modify `.claude/skills/orchestrate/SKILL.md`, `scripts/orchestrator-tick.ps1`, `scripts/install-orchestrator.ps1`, `CLAUDE.md`.

**Interfaces — Consumes:** the `gate` CLI, the `chatops design-*` CLIs, the new labels. Authored/ops — verified by structural review + the gate.

- [ ] **Step 1: Re-point the tick to run the gate first** — edit `scripts/orchestrator-tick.ps1` so that, BEFORE acquiring the lock + invoking claude, it runs the gate and exits cheaply when there's nothing to do. Replace the lock/claude section with:

```powershell
# Cheap gate: only wake the agent when there's something to do.
$gateOut = & $py -m bookieskit.orchestration gate --json
$run = $false
try { $run = ([bool]((ConvertFrom-Json $gateOut).run)) } catch { $run = $true }  # parse fail -> run (fail open)
if (-not $run) { Log "gate: idle - skipping"; exit 0 }

& $py -m bookieskit.orchestration lock acquire --path $lock | Out-Null
if ($LASTEXITCODE -ne 0) { Log "busy - previous cycle still running; skipping tick"; exit 0 }
try {
    Log "tick start (gate: run)"
    & claude -p "/orchestrate" --settings (Join-Path $repo ".claude\orchestrator-settings.json") 2>&1 | Add-Content -Encoding utf8 $log
    $claudeExit = $LASTEXITCODE
    Log "tick done (claude exit $claudeExit)"
    # Advance the watermark to the newest #tickets ts the gate observed, so we
    # don't re-fire on already-processed messages.
    $newest = $null
    try { $newest = (ConvertFrom-Json $gateOut).newest_ts } catch { $newest = $null }
    if ($newest) { Set-Content -Encoding ascii (Join-Path $repo ".orchestrator\slack-watermark") $newest }
}
finally {
    & $py -m bookieskit.orchestration lock release --path $lock | Out-Null
    Log "lock released"
}
```
(Keep ASCII only — no em-dashes. The gate must be allow-listed: it's `Bash(.venv/Scripts/python.exe -m bookieskit.orchestration:*)`, already permitted.)

- [ ] **Step 2: Drop the scheduler interval to 1 min** — in `scripts/install-orchestrator.ps1`, change `(New-TimeSpan -Minutes 15)` to `(New-TimeSpan -Minutes 1)`.

- [ ] **Step 3: Add the design phase to the orchestrate skill** — in `.claude/skills/orchestrate/SKILL.md`:
  - In the **ChatOps intake** step: directed work-requests are filed with **`status:designing`** (add the label on intake — note the intake CLI files `stream:directed`; the skill adds `status:designing` via `gh issue edit` right after, or note it for the design step). Also handle the new commands: `design ok <n>` → `chatops design-ok --issue <n> --author <id>`; `design no <n> <notes>` → `chatops design-no --issue <n> --author <id> --notes "<notes>"`; `council <n>` → `chatops council ...`. Post each returned `slack_text` to `#tickets`.
  - Add a new **Design step** (before Pick/Build): "For the top `status:designing` directed Issue whose thread's last message is the owner's (i.e. the agent owes a reply): read the Issue's `#tickets` thread + the codebase; do ONE brainstorm step — post the next clarifying question, or (when confident) the converged design, to the thread (reply in the Issue's thread, `thread_ts` = the Issue's `slack_ts` meta). If the design has a genuine stakes/tradeoff, run `llm-council` first and post its recommendation. Write the current design into the Issue body. Then END the cycle (one step per cycle)."
  - In the **Build step**: when building a `status:ready` directed Issue, **use the agreed design in the Issue body as the spec** (feed it to `writing-plans`), rather than decide-and-document.
  - State clearly: maintenance/canary are unchanged (decide-and-document, no design phase).

- [ ] **Step 4: Add a "Directed design in Slack" section to `CLAUDE.md`**

```markdown
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
```

- [ ] **Step 5: Final gate**
```bash
.venv/Scripts/python.exe -m pytest tests/ -q          # all pass, 1 skipped
.venv/Scripts/python.exe -m ruff check .              # clean
.venv/Scripts/python.exe -c "for f in ['scripts/orchestrator-tick.ps1','scripts/install-orchestrator.ps1']:\n print(f, all(c<128 for c in open(f,'rb').read()))"   # ASCII True/True
.venv/Scripts/python.exe -m bookieskit.orchestration gate --json   # smoke: prints {"run":...}
```

- [ ] **Step 6: Commit**
```bash
git add .claude/skills/orchestrate/SKILL.md scripts/orchestrator-tick.ps1 scripts/install-orchestrator.ps1 CLAUDE.md
git commit -m "feat(orchestration): directed design phase + cheap-gate tick + 1-min cadence"
```

---

## Self-Review

**1. Spec coverage:**
- Cheap-gate runtime → Task 3 (`gate.py`) + Task 4 (`gate` CLI) + Task 6 (`.ps1` runs gate, 1-min interval). ✅
- Directed-design state machine (designing → ready → build) → Task 1 (labels + priority) + Task 6 (skill: intake→designing, design step, build-reads-design). ✅
- `design ok`/`design no`/`council` → Task 2 (parse) + Task 5 (CLI) + Task 6 (skill handles). ✅
- llm-council agent-decided + surfaced → Task 6 (design step runs council on stakes) + Task 5 (`council` force command). ✅
- No build without `design ok` (allowlisted) → Task 1 (priority skips designing) + Task 5 (allowlist-gated transition). ✅
- Build reads Issue-body design → Task 6 Step 3. ✅
- Maintenance stays decide-and-document → Task 6 (stated; design phase is directed-only). ✅
- Watermark durability → Task 4 (read) + Task 6 (.ps1 writes newest_ts after a cycle). ✅
- Gate fails safe (Slack down → queue-only) → Task 4 (guarded reads). ✅
- Deployment (re-install for 1-min) → Task 6 Step 2 + the spec's deployment note. ✅

**2. Placeholder scan:** No TBD/TODO. Task 6 is authored skill/ops prose with concrete edits; the `_slack_get` seam (Task 4) is a named injectable for offline tests. Label/priority/chatops ripples are called out with exact new totals (10 labels).

**3. Type consistency:** `DesignOkCommand(issue)`, `DesignChangesCommand(issue, notes)`, `CouncilCommand(issue)` identical across Task 2 (def) and Task 5/6 (CLI uses `--issue`). `gate.new_ticket_waiting`/`thread_reply_waiting`/`should_run` signatures identical in Task 3 (def) and Task 4 (CLI call). Labels `status:designing`/`status:ready` consistent across labels.py, priority `_INACTIVE_STATUSES`, the CLI transitions, the skill, and CLAUDE.md. `chatops design-ok`/`design-no`/`council` CLI names match the skill's command mapping.
