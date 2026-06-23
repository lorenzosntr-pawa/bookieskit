# Orchestrator 5b — Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Claude Code the in-region orchestrator ("EM") that consumes the 5a work queue: thin Python glue (priority rule + claim/mark-in-review/mark-blocked + CLI), an `orchestrate` skill (the one-cycle procedure + autonomy rules), and a repo-root `CLAUDE.md` operating contract.

**Architecture:** Three deliverables. (1) Python glue extending `bookieskit.orchestration`: `priority.py` (`next_work_item`, a pure priority function over gh issue-dicts), `Queue.claim`/`mark_in_review`/`mark_blocked`, a `status:blocked` label, and CLI subcommands `next`/`claim`/`mark-in-review`/`mark-blocked`. (2) `.claude/skills/orchestrate/SKILL.md` — the cycle procedure the looped session runs. (3) repo-root `CLAUDE.md` — the standing operating contract every agent run inherits. The Python glue is TDD'd and offline-tested; the skill and `CLAUDE.md` are authored prose verified by a structural check (and an owner-run supervised dry-run, deferred).

**Tech Stack:** Python 3.11+ stdlib only (`argparse`, `json`); runtime dep `httpx` only. Tests: `pytest`, offline behind a fake `GhRunner`. Claude Code skill (`SKILL.md`) + project `CLAUDE.md` (Markdown). No new deps.

## Global Constraints

- Python 3.11+ **stdlib only** for new logic; runtime dep is **`httpx` only**; **NO new deps**.
- New code extends `src/bookieskit/orchestration/` (`priority.py` new; `labels.py`, `queue.py`, `cli.py` modified). The skill is `.claude/skills/orchestrate/SKILL.md`; the contract is `CLAUDE.md` at the repo root.
- Ruff config: `select = ["E","F","I"]`, `line-length = 88`, `target-version = "py311"`. **`src/` must stay 100% ruff-clean.** `tests/**` ignores `E501`.
- ALL new Python tests are **offline** under `tests/orchestration/`, behind a fake `GhRunner` — no `gh` process, no network.
- Local commands use `.venv/Scripts/python.exe -m pytest ...` / `-m ruff ...` (Windows); CI uses bare `pytest` / `ruff`.
- Agent-runnable: CLI supports `--json`, non-interactive, exit 0 on success / non-zero on operational `gh` error.
- Priority rule (verbatim): stream order **directed > maintenance > expansion > capability**, FIFO (lowest issue number = oldest) within a stream; skip `status:claimed`; unknown-stream issues sort last.
- Supervised v1: the loop produces PRs and **never merges**; no auto-merge logic anywhere in 5b.

---

### Task 1: `priority.py` — `next_work_item`

**Files:**
- Create: `src/bookieskit/orchestration/priority.py`
- Create: `tests/orchestration/test_priority.py`

**Interfaces:**
- Consumes: gh issue-dict shape (`number: int`, `labels: list[{"name": str}]`).
- Produces: `STREAM_ORDER: tuple[str, ...]`, `next_work_item(open_issues: list[dict]) -> dict | None`. Consumed by the CLI (Task 3).

- [ ] **Step 1: Write the failing test**

Create `tests/orchestration/test_priority.py`:

```python
from bookieskit.orchestration.priority import STREAM_ORDER, next_work_item


def _issue(number, *labels):
    return {"number": number, "labels": [{"name": n} for n in labels]}


def test_stream_order_is_directed_maintenance_expansion_capability():
    assert STREAM_ORDER == (
        "stream:directed", "stream:maintenance",
        "stream:expansion", "stream:capability",
    )


def test_directed_beats_maintenance_even_if_newer():
    issues = [
        _issue(1, "stream:maintenance"),
        _issue(2, "stream:directed"),  # higher number but higher-priority stream
    ]
    assert next_work_item(issues)["number"] == 2


def test_fifo_within_a_stream_lowest_number_first():
    issues = [
        _issue(5, "stream:directed"),
        _issue(3, "stream:directed"),
        _issue(9, "stream:directed"),
    ]
    assert next_work_item(issues)["number"] == 3


def test_claimed_issues_are_skipped():
    issues = [
        _issue(1, "stream:directed", "status:claimed"),
        _issue(2, "stream:maintenance"),
    ]
    assert next_work_item(issues)["number"] == 2


def test_unknown_stream_sorts_last():
    issues = [
        _issue(1),  # no stream label
        _issue(2, "stream:capability"),
    ]
    assert next_work_item(issues)["number"] == 2


def test_none_when_empty_or_all_claimed():
    assert next_work_item([]) is None
    assert next_work_item([_issue(1, "stream:directed", "status:claimed")]) is None
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_priority.py -q`
Expected: `ModuleNotFoundError: No module named 'bookieskit.orchestration.priority'`.

- [ ] **Step 3: Implement `priority.py`**

Create `src/bookieskit/orchestration/priority.py`:

```python
"""Pick the next work item from the open-issue queue.

Pure functions over the ``gh issue list --json number,title,body,labels,state``
issue-dict shape (``labels`` is a list of ``{"name": ...}``). The orchestrator
CLI's ``next`` subcommand calls ``next_work_item``; the orchestrate skill acts
on its result.
"""

STREAM_ORDER: tuple[str, ...] = (
    "stream:directed",
    "stream:maintenance",
    "stream:expansion",
    "stream:capability",
)
_CLAIMED = "status:claimed"


def _label_names(issue: dict) -> set[str]:
    return {lb.get("name") for lb in issue.get("labels", [])}


def _stream_rank(issue: dict) -> int:
    names = _label_names(issue)
    for index, stream in enumerate(STREAM_ORDER):
        if stream in names:
            return index
    return len(STREAM_ORDER)  # unknown stream sorts last


def next_work_item(open_issues: list[dict]) -> dict | None:
    """Return the top actionable open issue, or None.

    Skips issues labeled ``status:claimed``; orders by STREAM_ORDER index then
    by issue number ascending (FIFO — lowest number is oldest).
    """
    candidates = [i for i in open_issues if _CLAIMED not in _label_names(i)]
    if not candidates:
        return None
    candidates.sort(key=lambda i: (_stream_rank(i), i["number"]))
    return candidates[0]
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_priority.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration tests/orchestration`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/orchestration/priority.py tests/orchestration/test_priority.py
git commit -m "feat(orchestration): next_work_item priority rule

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `Queue` claim/mark-in-review/mark-blocked + `status:blocked` label

**Files:**
- Modify: `src/bookieskit/orchestration/labels.py` (add `status:blocked`)
- Modify: `src/bookieskit/orchestration/queue.py` (add `claim`, `mark_in_review`, `mark_blocked`)
- Modify: `tests/orchestration/test_queue.py` (add transition tests)

**Interfaces:**
- Consumes: `GhRunner.edit_issue(number, *, add_labels, remove_labels)` + `comment_issue(number, body)` (Task-1-era 5a `gh.py`).
- Produces: `Queue.claim(number)`, `Queue.mark_in_review(number, pr_url)`, `Queue.mark_blocked(number, *, reason)`; the `status:blocked` label. Consumed by the CLI (Task 3) and the orchestrate skill (Task 4).

- [ ] **Step 1: Add the failing tests**

Append to `tests/orchestration/test_queue.py`:

```python
def test_claim_adds_status_claimed_label():
    gh = _FakeGh()
    n = gh.create_issue(title="t", body="b", labels=["stream:directed"])
    Queue(gh, ensure=False).claim(n)
    names = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:claimed" in names


def test_mark_in_review_swaps_labels_and_comments_pr():
    gh = _FakeGh()
    n = gh.create_issue(
        title="t", body="b", labels=["stream:directed", "status:claimed"]
    )
    Queue(gh, ensure=False).mark_in_review(n, "https://github.com/o/r/pull/9")
    names = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:in-review" in names and "status:claimed" not in names
    assert any("pull/9" in body for _, body in gh.comments)


def test_mark_blocked_swaps_labels_and_comments_reason():
    gh = _FakeGh()
    n = gh.create_issue(
        title="t", body="b", labels=["stream:directed", "status:claimed"]
    )
    Queue(gh, ensure=False).mark_blocked(n, reason="needs an API key")
    names = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:blocked" in names and "status:claimed" not in names
    assert any("needs an API key" in body for _, body in gh.comments)
```

The existing `_FakeGh` in `tests/orchestration/test_queue.py` records `comments` and stores `issues` with `labels` as `[{"name": ...}]`, but it may not have an `edit_issue`. If `pytest` shows `AttributeError: ... 'edit_issue'`, add exactly this method to `_FakeGh` (it mutates the matching issue's label dicts and optional body):

```python
    def edit_issue(self, number, *, body=None, add_labels=(), remove_labels=()):
        for issue in self.issues:
            if issue["number"] == number:
                names = {lb["name"] for lb in issue.get("labels", [])}
                names -= set(remove_labels)
                names |= set(add_labels)
                issue["labels"] = [{"name": n} for n in names]
                if body is not None:
                    issue["body"] = body
                return
```

(If `_FakeGh` lacks a `comments` recorder, confirm `comment_issue` appends `(number, body)` to a `self.comments` list — the existing queue tests already rely on `gh.comments`, so it should be present.)

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_queue.py -q`
Expected: FAIL — `AttributeError: 'Queue' object has no attribute 'claim'`.

- [ ] **Step 3: Add the `status:blocked` label**

In `src/bookieskit/orchestration/labels.py`, replace the `STATUS_LABELS` dict:

```python
STATUS_LABELS: dict[str, tuple[str, str]] = {
    "status:claimed": ("fbca04", "An agent is working this"),
    "status:in-review": ("0052cc", "PR open, awaiting review"),
}
```

with:

```python
STATUS_LABELS: dict[str, tuple[str, str]] = {
    "status:claimed": ("fbca04", "An agent is working this"),
    "status:in-review": ("0052cc", "PR open, awaiting review"),
    "status:blocked": ("e4e669", "Build blocked — needs owner input"),
}
```

- [ ] **Step 4: Add the `Queue` transition methods**

In `src/bookieskit/orchestration/queue.py`, add these methods to the `Queue` class (after `list_open`):

```python
    def claim(self, number: int) -> None:
        """Mark an issue as being worked (adds status:claimed)."""
        self.gh.edit_issue(number, add_labels=["status:claimed"])

    def mark_in_review(self, number: int, pr_url: str) -> None:
        """Transition to in-review: add status:in-review, drop status:claimed,
        and comment the PR link."""
        self.gh.edit_issue(
            number,
            add_labels=["status:in-review"],
            remove_labels=["status:claimed"],
        )
        self.gh.comment_issue(number, f"PR: {pr_url}")

    def mark_blocked(self, number: int, *, reason: str) -> None:
        """Transition to blocked: add status:blocked, drop status:claimed, and
        comment the blocker (surfaced for the owner, never silently dropped)."""
        self.gh.edit_issue(
            number,
            add_labels=["status:blocked"],
            remove_labels=["status:claimed"],
        )
        self.gh.comment_issue(number, f"Blocked: {reason}")
```

- [ ] **Step 5: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_queue.py -q`
Expected: all pass (the new 3 + the existing queue tests), 0 failed.

- [ ] **Step 6: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration tests/orchestration`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add src/bookieskit/orchestration/labels.py src/bookieskit/orchestration/queue.py tests/orchestration/test_queue.py
git commit -m "feat(orchestration): Queue claim/mark-in-review/mark-blocked + status:blocked

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: CLI — `next` / `claim` / `mark-in-review` / `mark-blocked`

**Files:**
- Modify: `src/bookieskit/orchestration/cli.py`
- Modify: `tests/orchestration/test_cli.py`

**Interfaces:**
- Consumes: `next_work_item` (Task 1); `Queue.claim`/`mark_in_review`/`mark_blocked` (Task 2); the existing `build_parser`/`run`/`_emit`/`parse_meta` scaffolding.
- Produces: `python -m bookieskit.orchestration {next,claim,mark-in-review,mark-blocked}`. Consumed by the orchestrate skill (Task 4).

- [ ] **Step 1: Add the failing tests**

Append to `tests/orchestration/test_cli.py`:

```python
from bookieskit.orchestration.workitem import WorkItem, render_body  # noqa: E402


def test_next_returns_top_item_json(capsys):
    gh = _FakeGh()
    gh.create_issue(title="fix betika", body=render_body(WorkItem(
        signature="canary:betika:structure", stream="stream:maintenance",
        title="fix betika", summary="s")), labels=["stream:maintenance"])
    gh.create_issue(title="add stake", body=render_body(WorkItem(
        signature="directed:add-stake", stream="stream:directed",
        title="add stake", summary="s")), labels=["stream:directed"])
    args = cli.build_parser().parse_args(["next", "--json"])
    code = cli.run(args, gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["stream"] == "stream:directed"  # directed beats maintenance
    assert out["title"] == "add stake"


def test_next_emits_null_when_queue_empty(capsys):
    args = cli.build_parser().parse_args(["next", "--json"])
    code = cli.run(args, gh=_FakeGh())
    assert code == 0
    assert json.loads(capsys.readouterr().out) is None


def test_claim_adds_label(capsys):
    gh = _FakeGh()
    n = gh.create_issue(title="t", body="b", labels=["stream:directed"])
    code = cli.run(cli.build_parser().parse_args(["claim", str(n)]), gh=gh)
    assert code == 0
    assert "status:claimed" in {lb["name"] for lb in gh.issues[0]["labels"]}


def test_mark_in_review_requires_pr_and_transitions(capsys):
    gh = _FakeGh()
    n = gh.create_issue(
        title="t", body="b", labels=["stream:directed", "status:claimed"])
    code = cli.run(cli.build_parser().parse_args(
        ["mark-in-review", str(n), "--pr", "https://x/pull/3"]), gh=gh)
    assert code == 0
    names = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:in-review" in names and "status:claimed" not in names


def test_mark_blocked_requires_reason(capsys):
    gh = _FakeGh()
    n = gh.create_issue(
        title="t", body="b", labels=["stream:directed", "status:claimed"])
    code = cli.run(cli.build_parser().parse_args(
        ["mark-blocked", str(n), "--reason", "no key"]), gh=gh)
    assert code == 0
    assert "status:blocked" in {lb["name"] for lb in gh.issues[0]["labels"]}
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -q`
Expected: FAIL — `invalid choice: 'next'`.

- [ ] **Step 3: Wire the subcommands into `cli.py`**

In `src/bookieskit/orchestration/cli.py`, add to the imports:

```python
from bookieskit.orchestration.priority import next_work_item
```

In `build_parser`, before `return parser`, add:

```python
    p_next = sub.add_parser("next")
    p_next.add_argument("--json", action="store_true", dest="as_json")

    p_claim = sub.add_parser("claim")
    p_claim.add_argument("number", type=int)
    p_claim.add_argument("--json", action="store_true", dest="as_json")

    p_review = sub.add_parser("mark-in-review")
    p_review.add_argument("number", type=int)
    p_review.add_argument("--pr", required=True)
    p_review.add_argument("--json", action="store_true", dest="as_json")

    p_blocked = sub.add_parser("mark-blocked")
    p_blocked.add_argument("number", type=int)
    p_blocked.add_argument("--reason", required=True)
    p_blocked.add_argument("--json", action="store_true", dest="as_json")
```

Add these handler functions (after `_queue_list`):

```python
def _next(args: argparse.Namespace, gh: GhRunner) -> int:
    issues = Queue(gh, ensure=False).list_open()
    item = next_work_item(issues)
    if item is None:
        _emit(None, args.as_json, ["queue empty"])
        return 0
    stream = next(
        (lb["name"] for lb in item.get("labels", [])
         if lb["name"].startswith("stream:")),
        "",
    )
    out = {
        "number": item["number"],
        "title": item.get("title", ""),
        "stream": stream,
        "signature": parse_meta(item.get("body", "")).get("signature", ""),
    }
    _emit(out, args.as_json, [f"#{out['number']} [{stream}] {out['title']}"])
    return 0


def _claim(args: argparse.Namespace, gh: GhRunner) -> int:
    Queue(gh).claim(args.number)
    _emit({"claimed": args.number}, args.as_json, [f"claimed #{args.number}"])
    return 0


def _mark_in_review(args: argparse.Namespace, gh: GhRunner) -> int:
    Queue(gh).mark_in_review(args.number, args.pr)
    _emit(
        {"in_review": args.number, "pr": args.pr},
        args.as_json,
        [f"in-review #{args.number} -> {args.pr}"],
    )
    return 0


def _mark_blocked(args: argparse.Namespace, gh: GhRunner) -> int:
    Queue(gh).mark_blocked(args.number, reason=args.reason)
    _emit(
        {"blocked": args.number, "reason": args.reason},
        args.as_json,
        [f"blocked #{args.number}: {args.reason}"],
    )
    return 0
```

In `run`, add the dispatch branches before the final `raise SystemExit`:

```python
    if args.cmd == "next":
        return _next(args, gh)
    if args.cmd == "claim":
        return _claim(args, gh)
    if args.cmd == "mark-in-review":
        return _mark_in_review(args, gh)
    if args.cmd == "mark-blocked":
        return _mark_blocked(args, gh)
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -q`
Expected: all pass, 0 failed.

- [ ] **Step 5: Smoke-test `--help` (offline)**

Run: `.venv/Scripts/python.exe -m bookieskit.orchestration --help`
Expected: usage listing `{sync-canary,ensure-labels,queue,next,claim,mark-in-review,mark-blocked}`; exit 0.

- [ ] **Step 6: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration tests/orchestration`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add src/bookieskit/orchestration/cli.py tests/orchestration/test_cli.py
git commit -m "feat(orchestration): next/claim/mark-in-review/mark-blocked CLI

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: The `orchestrate` skill

**Files:**
- Create: `.claude/skills/orchestrate/SKILL.md`

**Interfaces:**
- Consumes: the CLI `next`/`claim`/`mark-in-review`/`mark-blocked` (Task 3); the superpowers skills; the `CLAUDE.md` contract (Task 5).
- Produces: the `/orchestrate` skill — one work cycle. This is authored prose, not code; "tested" by a structural check + an owner-run supervised dry-run (deferred).

- [ ] **Step 1: Author the skill**

Create `.claude/skills/orchestrate/SKILL.md` with exactly:

```markdown
---
name: orchestrate
description: Run ONE work cycle of the bookieskit agent company — read the GitHub-Issues queue, claim the top item, build it autonomously via the superpowers pipeline, open a supervised PR, and mark it in-review. Invoke directly as /orchestrate, or loop it with /loop /orchestrate. Run in-region (live-bookmaker work needs the reachable network).
---

# Orchestrate — one work cycle

You are the engineering manager of the `bookieskit` agent company. This skill runs **exactly one** work cycle and then stops. `/loop /orchestrate` repeats it.

Read the operating contract in the repo-root `CLAUDE.md` first — it binds this cycle (cross-cutting standards, autonomy rules, in-region constraint, queue conventions).

## The cycle

1. **Pick the top item.** Run
   `.venv/Scripts/python.exe -m bookieskit.orchestration next --json`
   - If the output is `null` → report "queue empty — nothing to do" and END the cycle.
   - Otherwise parse `{number, title, stream, signature}`.
2. **Claim it.** `.venv/Scripts/python.exe -m bookieskit.orchestration claim <number>`. This sets `status:claimed` so no other cycle double-works it.
3. **Build it — autonomously — per stream:**
   - `stream:directed` (owner asked for a bookmaker / market / feature): `superpowers:brainstorming` → `writing-plans` → `subagent-driven-development` → `requesting-code-review`. There is NO human to answer clarifying questions: **decide-and-document** — make the most reasonable assumption, proceed, and record every assumption in the PR body. Use `llm-council` for genuine stakes/tradeoffs.
   - `stream:maintenance` (canary drift): `superpowers:systematic-debugging` → fix → TDD tests → `requesting-code-review`.
   - `stream:expansion` / `stream:capability`: spec → plan → `subagent-driven-development`.
   - Always: query `graphify` for the structural map before touching code; apply Karpathy principles; keep `src/` ruff-clean; TDD.
   - Work on a **per-Issue branch** (subagent-driven isolates work). NEVER commit to `main`.
4. **Open the PR** against `main`, body starting with `Closes #<number>`, summarizing what you built and listing every assumption you made for the supervised review.
5. **Mark in-review.** `.venv/Scripts/python.exe -m bookieskit.orchestration mark-in-review <number> --pr <pr-url>`.
6. **Report** the outcome (item, branch, PR url, key assumptions) and STOP. The PR awaits the owner's approval; you do NOT merge.

## If you hit a genuine blocker

If you cannot proceed safely (e.g. a missing credential, an ambiguous requirement no reasonable assumption resolves, an external dependency you can't satisfy): run
`.venv/Scripts/python.exe -m bookieskit.orchestration mark-blocked <number> --reason "<the blocker>"`,
report it, and END the cycle. Never silently fail or merge a half-built change.

## Hard rules
- **One item per cycle.** Pick one, build one, stop.
- **Never merge.** Every cycle ends at a PR awaiting owner approval (supervised v1).
- **In-region only** for live-bookmaker work (canary/scout/harness live use); CI/release are network-agnostic.
- **Surface, never swallow.** Assumptions go in the PR; blockers go on the Issue.
```

- [ ] **Step 2: Structural verification (the skill has its required parts)**

Run:
```bash
.venv/Scripts/python.exe -c "import pathlib,sys; t=pathlib.Path('.claude/skills/orchestrate/SKILL.md').read_text(encoding='utf-8'); req=['name: orchestrate','## The cycle','orchestration next --json','orchestration claim','mark-in-review','mark-blocked','decide-and-document','Never merge','Closes #']; missing=[r for r in req if r not in t]; sys.exit('MISSING: '+', '.join(missing) if missing else print('SKILL OK'))"
```
Expected: `SKILL OK`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/orchestrate/SKILL.md
git commit -m "feat(orchestration): orchestrate skill — one autonomous work cycle

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: The `CLAUDE.md` operating contract + final gate

**Files:**
- Create: `CLAUDE.md` (repo root)

**Interfaces:**
- Consumes: nothing (standing contract).
- Produces: the project operating contract every Claude Code session/agent in this repo inherits.

- [ ] **Step 1: Author `CLAUDE.md`**

Create `CLAUDE.md` at the repo root with exactly:

```markdown
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
```

- [ ] **Step 2: Structural verification**

Run:
```bash
.venv/Scripts/python.exe -c "import pathlib,sys; t=pathlib.Path('CLAUDE.md').read_text(encoding='utf-8'); req=['operating contract','Cross-cutting standards','Autonomy rules','In-region constraint','Work queue conventions','Build discipline','Decide-and-document','NEVER merge']; missing=[r for r in req if r not in t]; sys.exit('MISSING: '+', '.join(missing) if missing else print('CLAUDE.md OK'))"
```
Expected: `CLAUDE.md OK`

- [ ] **Step 3: Full suite + whole-tree lint (final gate)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: full suite green, 0 failed.

Run: `.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "feat(orchestration): repo-root CLAUDE.md operating contract

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 5: (Deferred — owner-run) Supervised dry-run cycle**

After merge, the owner seeds one trivial `stream:directed` test Issue (e.g. "add a one-line note to README"), runs `/orchestrate` once in an in-region session under supervision, and confirms it: claims the issue → builds on a branch → opens a PR (`Closes #N`) with assumptions listed → marks `status:in-review`, then reviews/merges or closes. This validates the skill + contract end-to-end. Do not block plan completion on this step.

---

## Notes for the executor

- Run commands with the project venv: `.venv/Scripts/python.exe -m <tool>` (Windows). CI uses bare `pytest`/`ruff`.
- Tasks 1–3 are TDD Python glue (offline behind the existing `_FakeGh`). Tasks 4–5 are authored prose (skill + contract) verified structurally; their true acceptance test is the deferred supervised dry-run.
- `CLAUDE.md` binds future Claude Code sessions in this repo (intended). Keep it accurate and concise — it is a contract, not a dumping ground.
- 5b adds NO `.github/workflows/` files, so the branch pushes with the normal `gh` credential (no `workflow` scope needed).
