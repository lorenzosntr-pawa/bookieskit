# PR Review-Response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the owner comments on an open loop PR, the loop wakes and responds — answers questions and implements change requests on the PR branch — without merging.

**Architecture:** A pure gate predicate (`pr_reply_waiting`) detects a `status:in-review` PR whose newest actionable event is human (stateless, mirrors the design-thread trick). The `gate` CLI folds it into `should_run`; a new `pr-review pending` CLI returns the PR + thread; the orchestrate skill gets a Step 0 that answers/implements before picking new queue work.

**Tech Stack:** Python 3.11+, `gh` CLI (`gh pr list`, `gh api`, `gh pr comment`).

## Global Constraints

- `src/` stays 100% ruff-clean (`.venv/Scripts/python.exe -m ruff check src/`). Run tests with `.venv/Scripts/python.exe -m pytest`.
- Preserve the cp1252 fix on every `gh` subprocess (`encoding="utf-8", errors="replace"` — already in `_run`; new methods route through `_run`).
- The loop NEVER merges. New methods comment/read only; pushing fixes happens in the skill step on a `feat/*` branch as the App. Do not add any merge path.
- `should_run` must stay backward-compatible: add `pr_reply` as a keyword with a default so existing callers/tests are unaffected.
- The gate is cheap: only scan PRs when `status:in-review` Issues exist, and break on the first PR that owes a reply. Degrade silently (existing signals only) if any gh call raises.
- TDD; frequent commits; conventional-commit messages.

---

### Task 1: `gate.py` — `pr_reply_waiting` + `should_run` gains `pr_reply`

**Files:**
- Modify: `src/bookieskit/orchestration/gate.py`
- Modify: `tests/orchestration/test_gate.py`

**Interfaces:**
- Produces:
  - `pr_reply_waiting(comments: list[dict], reviews: list[dict]) -> bool`
  - `should_run(*, queue_actionable, new_ticket, designing_reply, pr_reply: bool = False) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
# tests/orchestration/test_gate.py  (add)
def _c(ts, *, bot=False):
    return {"created_at": ts, "user": {"type": "Bot" if bot else "User"}}

def _r(ts, *, state="COMMENTED", body="", bot=False):
    return {"submitted_at": ts, "state": state, "body": body,
            "user": {"type": "Bot" if bot else "User"}}


def test_pr_reply_waiting_true_when_newest_comment_human():
    assert gate.pr_reply_waiting([_c("2026-06-25T10:00:00Z")], []) is True


def test_pr_reply_waiting_false_when_newest_is_bot_reply():
    comments = [_c("2026-06-25T10:00:00Z"), _c("2026-06-25T11:00:00Z", bot=True)]
    assert gate.pr_reply_waiting(comments, []) is False


def test_pr_reply_waiting_true_for_human_changes_requested_empty_body():
    reviews = [_r("2026-06-25T10:00:00Z", state="CHANGES_REQUESTED")]
    assert gate.pr_reply_waiting([], reviews) is True


def test_pr_reply_waiting_ignores_bare_approval():
    # a lone APPROVED review with no text is not actionable
    reviews = [_r("2026-06-25T10:00:00Z", state="APPROVED")]
    assert gate.pr_reply_waiting([], reviews) is False


def test_pr_reply_waiting_interleaves_comments_and_reviews_by_time():
    comments = [_c("2026-06-25T12:00:00Z")]                 # human, newest
    reviews = [_r("2026-06-25T11:00:00Z", body="looks ok", bot=True)]
    assert gate.pr_reply_waiting(comments, reviews) is True
    # now the bot comment is newest -> resolved
    comments2 = [_c("2026-06-25T10:00:00Z"), _c("2026-06-25T13:00:00Z", bot=True)]
    assert gate.pr_reply_waiting(comments2, reviews) is False


def test_pr_reply_waiting_false_when_empty():
    assert gate.pr_reply_waiting([], []) is False


def test_should_run_includes_pr_reply():
    assert gate.should_run(queue_actionable=False, new_ticket=False,
                           designing_reply=False, pr_reply=True) is True
    assert gate.should_run(queue_actionable=False, new_ticket=False,
                           designing_reply=False) is False  # default pr_reply=False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_gate.py -v`
Expected: FAIL (`pr_reply_waiting` missing; `should_run` has no `pr_reply`)

- [ ] **Step 3: Write minimal implementation**

```python
# src/bookieskit/orchestration/gate.py  (add)
def _is_bot(user: dict | None) -> bool:
    return bool(user and user.get("type") == "Bot")


def pr_reply_waiting(comments: list[dict], reviews: list[dict]) -> bool:
    """True if the newest actionable event on a PR is from a human (the loop
    owes a response). Actionable = any conversation comment, or a review that
    requested changes or carries a non-empty body. A bare APPROVED/COMMENTED
    review with no text is ignored, so a plain approval never triggers a reply.
    Stateless: the App's own reply is authored by a Bot and becomes the newest
    event, flipping the state off — no watermark needed.
    ``comments`` carry ``created_at``; ``reviews`` carry ``submitted_at``. Both
    timestamps are ISO-8601 UTC (lexically sortable)."""
    events: list[tuple[str, bool]] = []
    for c in comments:
        events.append((c.get("created_at", ""), _is_bot(c.get("user"))))
    for r in reviews:
        body = (r.get("body") or "").strip()
        if r.get("state") == "CHANGES_REQUESTED" or body:
            events.append((r.get("submitted_at", ""), _is_bot(r.get("user"))))
    if not events:
        return False
    events.sort(key=lambda e: e[0])
    return not events[-1][1]  # newest event authored by a human
```

Update `should_run`:

```python
def should_run(*, queue_actionable: bool, new_ticket: bool,
               designing_reply: bool, pr_reply: bool = False) -> bool:
    """Wake the agent iff any wake-signal is set."""
    return bool(queue_actionable or new_ticket or designing_reply or pr_reply)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_gate.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/orchestration/gate.py tests/orchestration/test_gate.py
git commit -m "feat(orchestration): pr_reply_waiting gate predicate + should_run pr_reply"
```

---

### Task 2: `gh.py` — PR comment/review reads + `comment_pr`

**Files:**
- Modify: `src/bookieskit/orchestration/gh.py`
- Modify: `tests/orchestration/test_gh.py`

**Interfaces:**
- Produces (on `GhRunner`):
  - `list_open_prs() -> list[dict]`
  - `pr_comments(pr: int) -> list[dict]`
  - `pr_reviews(pr: int) -> list[dict]`
  - `comment_pr(pr: int, body: str) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/orchestration/test_gh.py  (add)
def test_list_open_prs_requests_closing_issue_fields(monkeypatch):
    gh, rec = _gh(
        monkeypatch,
        stdout='[{"number":11,"closingIssuesReferences":[{"number":8}],'
        '"headRefName":"feat/x"}]',
    )
    out = gh.list_open_prs()
    assert out[0]["closingIssuesReferences"][0]["number"] == 8
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "pr", "list"]
    assert "--state" in argv and "open" in argv
    json_idx = argv.index("--json")
    fields = argv[json_idx + 1]
    for field in ("number", "closingIssuesReferences", "headRefName"):
        assert field in fields


def test_pr_comments_hits_issue_comments_endpoint(monkeypatch):
    gh, rec = _gh(monkeypatch, stdout='[{"body":"hi","user":{"type":"User"}}]')
    out = gh.pr_comments(11)
    assert out[0]["body"] == "hi"
    argv = rec.calls[0]
    assert argv[:2] == ["gh", "api"]
    assert "repos/:owner/:repo/issues/11/comments" in argv


def test_pr_reviews_hits_pulls_reviews_endpoint(monkeypatch):
    gh, rec = _gh(monkeypatch, stdout='[{"state":"CHANGES_REQUESTED","body":"x"}]')
    out = gh.pr_reviews(11)
    assert out[0]["state"] == "CHANGES_REQUESTED"
    argv = rec.calls[0]
    assert argv[:2] == ["gh", "api"]
    assert "repos/:owner/:repo/pulls/11/reviews" in argv


def test_comment_pr_builds_gh_pr_comment(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.comment_pr(11, "answering your question")
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "pr", "comment"]
    assert "11" in argv
    assert "--body" in argv and "answering your question" in argv
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_gh.py -v`
Expected: FAIL (methods missing)

- [ ] **Step 3: Write minimal implementation**

```python
# src/bookieskit/orchestration/gh.py  (add methods to GhRunner)
    def list_open_prs(self) -> list[dict]:
        out = self._run(
            "pr", "list", "--state", "open",
            "--json", "number,closingIssuesReferences,headRefName",
        )
        return json.loads(out)

    def pr_comments(self, pr: int) -> list[dict]:
        out = self._run("api", f"repos/:owner/:repo/issues/{pr}/comments")
        return json.loads(out)

    def pr_reviews(self, pr: int) -> list[dict]:
        out = self._run("api", f"repos/:owner/:repo/pulls/{pr}/reviews")
        return json.loads(out)

    def comment_pr(self, pr: int, body: str) -> None:
        self._run("pr", "comment", str(pr), "--body", body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_gh.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/orchestration/gh.py tests/orchestration/test_gh.py
git commit -m "feat(orchestration): gh PR comment/review reads + comment_pr"
```

---

### Task 3: `cli.py` — gate folds in PR-reply + `pr-review pending`

**Files:**
- Modify: `src/bookieskit/orchestration/cli.py`
- Modify: `tests/orchestration/test_cli.py`

**Interfaces:**
- Consumes: `gate.pr_reply_waiting`, `should_run(pr_reply=...)` (Task 1); `GhRunner.list_open_prs/pr_comments/pr_reviews` (Task 2).
- Produces:
  - `gate --json` now includes `pr_awaiting` (PR number or null) and reports `reason == "pr-reply"` when a PR owes a reply (preempts the other reasons in the label).
  - New subcommand `pr-review pending [--json]` → `{pr, issue, head, comments, reviews}` for the lowest-numbered in-review PR owing a reply, or `null`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/orchestration/test_cli.py  (add)
# Extend _FakeGh with PR methods (add inside the class, near pr_view):
#     def list_open_prs(self): return list(self._open_prs)
#     def pr_comments(self, pr): return list(self._pr_comments.get(pr, []))
#     def pr_reviews(self, pr): return list(self._pr_reviews.get(pr, []))
#     def comment_pr(self, pr, body): self.pr_comments_posted.append((pr, body))
# and in __init__: self._open_prs=[]; self._pr_comments={}; self._pr_reviews={};
#     self.pr_comments_posted=[]

def _in_review_issue(n):
    from bookieskit.orchestration.workitem import WorkItem, render_body
    return {"number": n, "title": "t",
            "body": render_body(WorkItem(signature="directed:x",
                stream="stream:directed", title="t", summary="s")),
            "labels": [{"name": "stream:directed"}, {"name": "status:in-review"}],
            "state": "open"}


def test_pr_review_pending_returns_pr_with_human_comment(capsys):
    gh = _FakeGh(issues=[_in_review_issue(8)])
    gh._open_prs = [{"number": 11, "headRefName": "feat/x",
                     "closingIssuesReferences": [{"number": 8}]}]
    gh._pr_comments = {11: [{"created_at": "2026-06-25T10:00:00Z",
                             "user": {"type": "User"}, "body": "why?"}]}
    code = cli.run(cli.build_parser().parse_args(["pr-review", "pending", "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pr"] == 11 and out["issue"] == 8 and out["head"] == "feat/x"


def test_pr_review_pending_null_when_newest_is_bot(capsys):
    gh = _FakeGh(issues=[_in_review_issue(8)])
    gh._open_prs = [{"number": 11, "headRefName": "feat/x",
                     "closingIssuesReferences": [{"number": 8}]}]
    gh._pr_comments = {11: [{"created_at": "2026-06-25T10:00:00Z",
                             "user": {"type": "Bot"}, "body": "done"}]}
    code = cli.run(cli.build_parser().parse_args(["pr-review", "pending", "--json"]), gh=gh)
    out = json.loads(capsys.readouterr().out)
    assert out is None


def test_gate_reports_pr_reply(monkeypatch, capsys, tmp_path):
    gh = _FakeGh(issues=[_in_review_issue(8)])
    gh._open_prs = [{"number": 11, "headRefName": "feat/x",
                     "closingIssuesReferences": [{"number": 8}]}]
    gh._pr_comments = {11: [{"created_at": "2026-06-25T10:00:00Z",
                             "user": {"type": "User"}, "body": "why?"}]}
    # No Slack token -> new_ticket/designing skipped; queue has only an in-review
    # item (not actionable). Point --config/--watermark at empty tmp paths.
    args = cli.build_parser().parse_args(
        ["gate", "--json", "--config", str(tmp_path / "c.json"),
         "--watermark", str(tmp_path / "wm")])
    code = cli.run(args, gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["run"] is True
    assert out["reason"] == "pr-reply"
    assert out["pr_awaiting"] == 11
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -k "pr_review or gate" -v`
Expected: FAIL (`pr-review` subcommand missing; `gate` has no `pr_awaiting`)

- [ ] **Step 3: Write minimal implementation**

Add the subparser (near `p_gate`):

```python
    p_prr = sub.add_parser("pr-review")
    prsub = p_prr.add_subparsers(dest="pr_review_cmd", required=True)
    p_prpend = prsub.add_parser("pending")
    p_prpend.add_argument("--json", action="store_true", dest="as_json")
```

Add a helper used by both `_gate` and the new handler:

```python
def _pr_awaiting_reply(gh: GhRunner) -> dict | None:
    """The lowest-numbered open PR that closes a status:in-review Issue and whose
    newest actionable event is human, with its thread. None if no PR owes a reply."""
    from bookieskit.orchestration import gate
    in_review = {
        i["number"]
        for i in Queue(gh, ensure=False).list_open()
        if "status:in-review" in {lb["name"] for lb in i.get("labels", [])}
    }
    if not in_review:
        return None
    for pr in sorted(gh.list_open_prs(), key=lambda p: p["number"]):
        closes = {r.get("number") for r in pr.get("closingIssuesReferences", [])}
        match = next((n for n in closes if n in in_review), None)
        if match is None:
            continue
        comments = gh.pr_comments(pr["number"])
        reviews = gh.pr_reviews(pr["number"])
        if gate.pr_reply_waiting(comments, reviews):
            return {"pr": pr["number"], "issue": match,
                    "head": pr.get("headRefName", ""),
                    "comments": comments, "reviews": reviews}
    return None


def _pr_review_pending(args: argparse.Namespace, gh: GhRunner) -> int:
    chosen = _pr_awaiting_reply(gh)
    _emit(chosen, args.as_json,
          [f"PR #{chosen['pr']} awaits reply (closes #{chosen['issue']})"
           if chosen else "no PR awaiting reply"])
    return 0
```

In `_gate`, after the designing-thread block and before computing `run`, add:

```python
    # 4) an in-review PR with a human comment awaiting our reply?
    pr_awaiting = None
    try:
        owed = _pr_awaiting_reply(gh)
        pr_awaiting = owed["pr"] if owed else None
    except Exception:
        pr_awaiting = None
    pr_reply = pr_awaiting is not None
```

Change the `run`/`reason`/`_emit` in `_gate` to:

```python
    run = gate.should_run(queue_actionable=actionable, new_ticket=new_ticket,
                          designing_reply=designing_reply, pr_reply=pr_reply)
    reason = ("pr-reply" if pr_reply else
              "actionable-queue" if actionable else
              "new-ticket" if new_ticket else
              "design-reply" if designing_reply else "idle")
    _emit({"run": run, "reason": reason, "newest_ts": newest_ts,
           "pr_awaiting": pr_awaiting}, args.as_json,
          [f"run={run} ({reason})"])
    return 0
```

Wire dispatch in `main` (near the other `args.cmd` branches):

```python
    if args.cmd == "pr-review":
        return _pr_review_pending(args, gh)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -k "pr_review or gate" -v`
Expected: PASS

Run the full orchestration suite: `.venv/Scripts/python.exe -m pytest tests/orchestration -q`
Expected: PASS (no regressions; existing gate tests still pass because `pr_reply` defaults False and the PR scan is guarded by `if not in_review`)

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/orchestration/cli.py tests/orchestration/test_cli.py
git commit -m "feat(orchestration): gate detects PR-reply + pr-review pending CLI"
```

---

### Task 4: orchestrate skill Step 0 + CHANGELOG

**Files:**
- Modify: `.claude/skills/orchestrate/SKILL.md`
- Modify: `CHANGELOG.md` (`[Unreleased]`)

**Interfaces:** none (docs/process).

- [ ] **Step 1: Insert Step 0 into the cycle**

In `.claude/skills/orchestrate/SKILL.md`, under `## The cycle`, insert a new step **before** the current step 1 (ChatOps intake), and renumber by adding it as step `1.` titled "PR review-response" while the existing steps shift — OR (simpler, no renumber) insert it as an explicit pre-step. Use this text:

```markdown
0. **PR review-response (preempts new work).** Run
   `.venv/Scripts/python.exe -m bookieskit.orchestration pr-review pending --json`.
   - If it returns `null` → proceed to ChatOps intake / the queue as normal.
   - Otherwise it returns `{pr, issue, head, comments, reviews}` — the owner is
     waiting on an open PR, which **outranks new queue work**. Handle it THIS
     cycle and then STOP:
     1. Read `comments` + `reviews`. Identify each human comment/review not yet
        addressed by a later bot reply.
     2. For a **question**: post an answer with
        `gh pr comment <pr> --body "<answer>"`.
     3. For a **change request**: `git switch <head>` (or check it out), make the
        change with the subagent-driven / TDD pipeline, run the suite, push to
        `<head>` (you are the App — pushing to a `feat/*` branch is allowed;
        **never merge**), let CI re-run, then `gh pr comment <pr>` a summary of
        the commit.
     4. Finish with one consolidated reply so the newest event is the loop's
        (this clears the gate signal). Best-effort post a `pr-reply` note to
        `#agent-activity`.
   - This is one cycle's work (one item per cycle). Do NOT also pick a queue item.
```

(Keep the existing steps; this pre-step runs first. The `## Hard rules` —
one item per cycle, never merge — already bind it.)

- [ ] **Step 2: CHANGELOG entry**

Under `## [Unreleased]` → `### Added` (create if absent) in `CHANGELOG.md`:

```markdown
- The orchestrator now **responds to comments on its open PRs**: a human comment
  or change-request on a `status:in-review` PR wakes the loop (gate signal
  `pr-reply`), which answers questions and implements requested changes on the PR
  branch (pushed as the App, never merged) before picking new queue work.
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/orchestrate/SKILL.md CHANGELOG.md
git commit -m "docs(orchestrate): Step 0 PR review-response + CHANGELOG"
```

---

## Self-Review

- **Spec coverage:** detection predicate (T1) ✓, gh reads/comment (T2) ✓, gate fold-in + `pr-review pending` + preempt-reason (T3) ✓, skill Step 0 answer+implement + CHANGELOG (T4) ✓.
- **Type consistency:** `pr_reply_waiting(comments, reviews)` defined T1, consumed by `_pr_awaiting_reply` T3. `list_open_prs`/`pr_comments`/`pr_reviews`/`comment_pr` defined T2, consumed T3 + skill T4. `should_run(pr_reply=...)` defined T1, called T3. `_pr_awaiting_reply` shared by `_gate` and `_pr_review_pending`.
- **Placeholder scan:** all code complete; `gh api` paths and `--json` fields concrete.
- **Backward-compat:** `should_run` keeps a default `pr_reply=False`; the PR scan is guarded by `if not in_review: return None`, so idle ticks add at most one `gh pr list` call only when in-review Issues exist.
- **Never-merge:** new code only reads + comments; the skill pushes to `feat/*` and explicitly never merges.
