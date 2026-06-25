# Slack Cockpit Visibility v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace stale, append-only Slack confusion with a single always-current `#status` board (edited in place each tick), concise `#agent-activity` events, and an on-demand `status` command.

**Architecture:** A pure `status` render + a `gather_state` reader (offline-tested) drive both a `status board` CLI (edits one `#status` message via the Slack Web API `chat.update`, message id in a state file) and a `chatops status` snapshot command. The tick runs `status board` every cycle.

**Tech Stack:** Python 3.11 stdlib (`json`, `urllib`); pytest; ruff; Slack Web API; PowerShell tick.

## Global Constraints
- Python 3.11, stdlib only — no new deps. Slack writes via `urllib` POST (`_slack_post` seam), monkeypatched in tests (no network in CI).
- **Best-effort:** any Slack/config failure in `status board` is a logged no-op — never aborts the tick or the loop.
- The `#status` board is **edited in place** (`chat.update`), never appended; its message id lives in `.orchestrator/status-board.json`.
- `#agent-activity` posts are **concise one-liners only** — never the cycle-report prose.
- `status_channel` (the `#status` channel id) lives in `.chatops.json`; absent → board skipped.
- `src/` ruff-clean; normal outcomes exit 0.

---

## File Structure
- `src/bookieskit/orchestration/status.py` — **new.** `render_board` (pure) + `gather_state` (gh read).
- `src/bookieskit/orchestration/chatops.py` — **modify.** `StatusCommand` + parse `status`.
- `src/bookieskit/orchestration/cli.py` — **modify.** `_slack_post` helper; `status board` + `chatops status` subcommands.
- `scripts/orchestrator-tick.ps1` — **modify.** Run `status board` each tick.
- `.claude/skills/orchestrate/SKILL.md` — **modify.** Concise events only; handle `status`.
- `docs/SLACK_SETUP.md` — **modify.** `#status` channel setup + `status_channel`.
- `.chatops.json` — **modify.** Add `status_channel` placeholder.
- `.gitignore` — already ignores `.orchestrator/` (board state file lives there).
- Tests: `tests/orchestration/test_status.py` (new); additions to `test_chatops.py`, `test_cli.py`.

---

## Task 1: `status.py` — render_board + gather_state

**Files:** Create `src/bookieskit/orchestration/status.py`, `tests/orchestration/test_status.py`.

**Interfaces — Produces:**
- `gather_state(gh, *, paused: bool) -> dict` → `{"paused": bool, "items": [{"number": int, "title": str, "status": str}], "building": int | None}` (`status` ∈ designing/ready/claimed/in-review/blocked/open from labels; `building` = the `status:claimed` item's number or None).
- `render_board(state: dict, *, now: str) -> str` (Slack mrkdwn).

- [ ] **Step 1: Failing tests** (`tests/orchestration/test_status.py`)

```python
from bookieskit.orchestration import status


class _FakeGh:
    def __init__(self, issues): self.issues = issues
    def list_issues(self, *, labels=(), state="open"):
        return [i for i in self.issues if state == "all" or i.get("state","open") == state]


def _issue(n, title, *labels):
    return {"number": n, "title": title, "labels": [{"name": x} for x in labels], "state": "open"}


def test_gather_state_classifies_by_status_label():
    gh = _FakeGh([
        _issue(19, "corners", "stream:directed", "status:claimed"),
        _issue(20, "ht/ft", "stream:directed", "status:designing"),
        _issue(21, "cards", "stream:directed", "status:ready"),
    ])
    st = status.gather_state(gh, paused=False)
    assert st["paused"] is False
    assert st["building"] == 19
    byn = {i["number"]: i["status"] for i in st["items"]}
    assert byn == {19: "claimed", 20: "designing", 21: "ready"}


def test_render_board_active_shows_now_and_queue():
    st = {"paused": False, "building": 19,
          "items": [{"number": 19, "title": "corners", "status": "claimed"},
                    {"number": 20, "title": "ht/ft", "status": "designing"}]}
    out = status.render_board(st, now="15:31")
    assert "active" in out.lower() and "15:31" in out
    assert "#19" in out  # now-building
    assert "#20" in out and "designing" in out  # queue


def test_render_board_paused_and_idle():
    out_p = status.render_board({"paused": True, "building": None, "items": []}, now="15:31")
    assert "pause" in out_p.lower()
    out_i = status.render_board({"paused": False, "building": None, "items": []}, now="15:31")
    assert "idle" in out_i.lower()
```

- [ ] **Step 2: Run → fail** (`ModuleNotFoundError ... status`).

- [ ] **Step 3: Write `status.py`**

```python
# src/bookieskit/orchestration/status.py
"""Render the live #status board + gather the loop's current state.

Pure render (offline-testable) + a single gh read. The CLI calls these and
pushes the text to Slack via chat.update; the tick refreshes it each cycle.
"""

_STATUS_BY_LABEL = (
    ("status:claimed", "claimed"),
    ("status:designing", "designing"),
    ("status:ready", "ready"),
    ("status:in-review", "in-review"),
    ("status:blocked", "blocked"),
)


def _status_of(labels: set[str]) -> str:
    for label, name in _STATUS_BY_LABEL:
        if label in labels:
            return name
    return "open"


def gather_state(gh, *, paused: bool) -> dict:
    items, building = [], None
    for issue in gh.list_issues(state="open"):
        labels = {lb["name"] for lb in issue.get("labels", [])}
        if not any(lb.startswith("stream:") for lb in labels):
            continue
        st = _status_of(labels)
        items.append({"number": issue["number"],
                      "title": issue.get("title", ""), "status": st})
        if st == "claimed":
            building = issue["number"]
    items.sort(key=lambda i: i["number"])
    return {"paused": paused, "items": items, "building": building}


def render_board(state: dict, *, now: str) -> str:
    if state["paused"]:
        head = f":double_vertical_bar: *Loop:* paused — last update {now}"
    else:
        head = f":green_circle: *Loop:* active — last update {now}"
    if state["building"] is not None:
        now_line = f"*Now:* building #{state['building']}"
    else:
        now_line = "*Now:* idle"
    if state["items"]:
        queue = " · ".join(f"#{i['number']} {i['status']}" for i in state["items"])
    else:
        queue = "empty"
    return f"{head}\n{now_line}\n*Queue:* {queue}"
```

- [ ] **Step 4: Run → pass** (3 tests). **Step 5: ruff + commit.**
```bash
.venv/Scripts/python.exe -m pytest tests/orchestration/test_status.py -v
.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration/status.py
git add src/bookieskit/orchestration/status.py tests/orchestration/test_status.py
git commit -m "feat(orchestration): status board render + gather_state"
```

---

## Task 2: `status` command parsing

**Files:** Modify `chatops.py`; append `tests/orchestration/test_chatops.py`.

**Interfaces — Produces:** `@dataclass StatusCommand` (no fields); `parse_command("status")` → `StatusCommand()` (still recognizes the existing commands; chatter → None).

- [ ] **Step 1: Failing tests**
```python
def test_parse_status_command():
    from bookieskit.orchestration.chatops import StatusCommand
    assert parse_command("status") == StatusCommand()
    assert parse_command("  STATUS ") == StatusCommand()
    assert parse_command("status of the build") is None  # bare word only
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Edit `chatops.py`** — add the dataclass + regex + a branch in `parse_command` (place after the design/council checks, before/with approve):
```python
@dataclass
class StatusCommand:
    pass

_STATUS_RE = re.compile(r"^\s*status\s*$", re.IGNORECASE)
```
In `parse_command`, before the `_APPROVE_RE` check:
```python
    if _STATUS_RE.match(text):
        return StatusCommand()
```

- [ ] **Step 4: Run the full chatops test file → pass** (old + new). **Step 5: ruff + commit.**
```bash
git add src/bookieskit/orchestration/chatops.py tests/orchestration/test_chatops.py
git commit -m "feat(orchestration): parse status command"
```

---

## Task 3: `status board` + `chatops status` CLI (+ `_slack_post`)

**Files:** Modify `cli.py`; append `tests/orchestration/test_cli.py`.

**Interfaces — Consumes:** `status.gather_state`/`render_board`, `control.is_paused`, `chatops.load_config`. **Produces:**
- `_slack_post(method, *, token, **params) -> dict` (urllib POST, module-level — monkeypatchable).
- `status board [--config .chatops.json] [--state-file .orchestrator/status-board.json]` — gather → render → `chat.update` the stored board msg, or `chat.postMessage` to `status_channel` + store `{channel, ts}`. Best-effort, exit 0.
- `chatops status [--json]` — gather + render → emit `{slack_text}` (the snapshot the skill posts to `#tickets`). Exit 0.

- [ ] **Step 1: Failing tests** (append to `tests/orchestration/test_cli.py`; reuse `_FakeGh`)

```python
def test_chatops_status_emits_snapshot(capsys):
    gh = _FakeGh(issues=[{"number": 21, "title": "cards", "state": "open",
        "labels": [{"name": "stream:directed"}, {"name": "status:ready"}]}])
    code = cli.run(cli.build_parser().parse_args(["chatops", "status", "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert "#21" in out["slack_text"] and "ready" in out["slack_text"]


def test_status_board_posts_then_updates(tmp_path, capsys, monkeypatch):
    gh = _FakeGh()
    calls = []
    def fake_post(method, **kw):
        calls.append(method)
        return {"ok": True, "ts": "111.0", "channel": "C_STATUS"}
    monkeypatch.setattr(cli, "_read_token", lambda: "xoxb-test")
    monkeypatch.setattr(cli, "_slack_post", fake_post)
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"approvers": ["U1"], "tickets_channel": "C1",
                               "status_channel": "C_STATUS"}))
    sf = tmp_path / "board.json"
    args = ["status", "board", "--config", str(cfg), "--state-file", str(sf)]
    # first run -> postMessage (no stored id)
    assert cli.run(cli.build_parser().parse_args(args), gh=gh) == 0
    assert calls == ["chat.postMessage"]
    # second run -> chat.update (id now stored)
    assert cli.run(cli.build_parser().parse_args(args), gh=gh) == 0
    assert calls[-1] == "chat.update"
```

- [ ] **Step 2: Run → fail** (`invalid choice: 'status'` / `chatops: invalid choice: 'status'`).

- [ ] **Step 3: Add `_slack_post`** (next to `_slack_get` in cli.py):
```python
def _slack_post(method: str, *, token: str, **params) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        "https://slack.com/api/" + method, data=data,
        headers={"Authorization": "Bearer " + token},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)
```

- [ ] **Step 4: Add parsers.** A top-level `status` group + a `chatops status`:
```python
    p_status = sub.add_parser("status")
    ssub = p_status.add_subparsers(dest="status_cmd", required=True)
    p_board = ssub.add_parser("board")
    p_board.add_argument("--config", default=".chatops.json")
    p_board.add_argument("--state-file", default=".orchestrator/status-board.json", dest="state_file")
    p_board.add_argument("--json", action="store_true", dest="as_json")
```
And in the `chsub` group: `p_cstatus = chsub.add_parser("status"); p_cstatus.add_argument("--json", action="store_true", dest="as_json")`.

- [ ] **Step 5: Add handlers + dispatch** (import `status` + `control`):
```python
def _status_board(args: argparse.Namespace, gh: GhRunner) -> int:
    from bookieskit.orchestration import control, status as status_mod
    import datetime
    try:
        cfg = chatops.load_config(args.config)
    except Exception:
        cfg = {}
    channel = cfg.get("status_channel")
    token = _read_token()
    if not (channel and token):
        _emit({"posted": False, "reason": "no status_channel/token"}, args.as_json,
              ["status board skipped"])
        return 0
    try:
        st = status_mod.gather_state(gh, paused=control.is_paused(gh))
        text = status_mod.render_board(st, now=datetime.datetime.now().strftime("%H:%M"))
        board = {}
        try:
            with open(args.state_file, encoding="utf-8") as f:
                board = json.load(f)
        except (OSError, ValueError):
            board = {}
        if board.get("ts"):
            r = _slack_post("chat.update", token=token, channel=board["channel"],
                            ts=board["ts"], text=text)
            if not r.get("ok"):  # message gone -> repost
                r = _slack_post("chat.postMessage", token=token, channel=channel, text=text)
        else:
            r = _slack_post("chat.postMessage", token=token, channel=channel, text=text)
        if r.get("ok") and r.get("ts"):
            import os
            os.makedirs(os.path.dirname(args.state_file) or ".", exist_ok=True)
            with open(args.state_file, "w", encoding="utf-8") as f:
                json.dump({"channel": r.get("channel", channel), "ts": r["ts"]}, f)
        _emit({"posted": bool(r.get("ok"))}, args.as_json, ["status board updated"])
    except Exception as exc:  # best-effort: never break the tick
        _emit({"posted": False, "error": str(exc)}, args.as_json, [f"status board error: {exc}"])
    return 0


def _chatops_status(args: argparse.Namespace, gh: GhRunner) -> int:
    from bookieskit.orchestration import control, status as status_mod
    import datetime
    st = status_mod.gather_state(gh, paused=control.is_paused(gh))
    text = status_mod.render_board(st, now=datetime.datetime.now().strftime("%H:%M"))
    _emit({"slack_text": text}, args.as_json, [text])
    return 0
```
Dispatch in `run()` (gh-using section): `if args.cmd == "status": return _status_board(args, gh)`; and in the chatops branches: `if args.cmd == "chatops" and args.chatops_cmd == "status": return _chatops_status(args, gh)`.

- [ ] **Step 6: Run new tests + full orchestration suite → pass. Step 7: ruff + commit.**
```bash
git add src/bookieskit/orchestration/cli.py tests/orchestration/test_cli.py
git commit -m "feat(orchestration): status board + chatops status CLI"
```

---

## Task 4: tick wiring + skill concise-events + setup + final gate

**Files:** Modify `scripts/orchestrator-tick.ps1`, `.claude/skills/orchestrate/SKILL.md`, `docs/SLACK_SETUP.md`, `.chatops.json`.

- [ ] **Step 1: Tick updates the board each run.** In `orchestrator-tick.ps1`, after the gate/cycle logic (both the idle-skip path and the build path), before exit, add a board refresh (ASCII only):
```powershell
# Refresh the live #status board every tick (cheap; keeps it current).
& $py -m bookieskit.orchestration status board | Out-Null
```
Place it so it runs on BOTH the idle-skip branch and after the cycle. (Simplest: a `function Board { & $py -m bookieskit.orchestration status board | Out-Null }` called before each `exit 0` and after the `finally`.)

- [ ] **Step 2: Skill — concise events + status command.** In `.claude/skills/orchestrate/SKILL.md`:
  - In the ChatOps intake step, add: `If a message parses as `status`: run `.venv/Scripts/python.exe -m bookieskit.orchestration chatops status --json` and post the `slack_text` to #tickets.`
  - Add an explicit rule to the Notifications section: **"Post ONLY the concise formatted slack_text lines to `#agent-activity` (claimed / PR / blocked / merged). Never paste the cycle report or your reasoning into Slack — that goes to the tick log only."**

- [ ] **Step 3: `.chatops.json`** — add the field (placeholder):
```json
{
  "approvers": ["U0BCB59NC83"],
  "tickets_channel": "C0BCMUJE11A",
  "status_channel": "C-REPLACE-WITH-STATUS-CHANNEL-ID"
}
```

- [ ] **Step 4: `docs/SLACK_SETUP.md`** — add a short subsection: create a `#status` channel, invite the bot, put its id in `.chatops.json` as `status_channel`. Note the board is a single message edited in place; if `status_channel` is unset the board is skipped (everything else still works).

- [ ] **Step 5: Final gate.**
```bash
.venv/Scripts/python.exe -m pytest tests/ -q          # all pass, 1 skipped
.venv/Scripts/python.exe -m ruff check .              # clean
.venv/Scripts/python.exe -c "print(all(c<128 for c in open('scripts/orchestrator-tick.ps1','rb').read()))"  # ASCII True
.venv/Scripts/python.exe -m bookieskit.orchestration chatops status --json   # smoke: prints a board snapshot
```

- [ ] **Step 6: Commit.**
```bash
git add scripts/orchestrator-tick.ps1 .claude/skills/orchestrate/SKILL.md docs/SLACK_SETUP.md .chatops.json
git commit -m "feat(orchestration): tick refreshes #status board + concise events + status setup"
```

---

## Self-Review
**Spec coverage:** live `#status` board (edit-in-place) → Task 1 (render/gather) + Task 3 (`status board` CLI + chat.update + state file) + Task 4 (tick refresh). Concise events → Task 4 (skill rule). `status` command → Task 2 (parse) + Task 3 (`chatops status`) + Task 4 (skill handling). Best-effort → Task 3 (`_status_board` try/except, exit 0, skip if no channel/token). Config/setup → Task 4. ✅
**Placeholder scan:** none; `.chatops.json` `C-REPLACE…` is an owner-filled value.
**Type consistency:** `gather_state(gh, *, paused)` / `render_board(state, *, now)` identical across Task 1 def + Task 3 calls; `StatusCommand` Task 2 def + skill; `_slack_post(method,*,token,**params)` def + monkeypatch in tests; `status board`/`chatops status` CLI names match the skill + tick.
