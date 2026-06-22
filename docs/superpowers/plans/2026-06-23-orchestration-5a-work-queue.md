# Orchestration 5a — Work Queue + Maintenance Stream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the durable **work queue** (GitHub Issues) and the first intake stream (**maintenance**: canary drift → Issue) for the agent company. A new `src/bookieskit/orchestration/` subpackage models work items as stream/status **labels** + a hand-rolled fenced ` ```yaml ` **meta block** (signature, stream, …) + human prose, dedups by a stable **signature** per `(platform, drift-kind)`, and reconciles a `CanaryReport` into deduped, labeled Issues (open on drift, update on persistence, close on recovery). Invoked as `python -m bookieskit.orchestration <cmd>`. This is the foundation sub-project (5a) of the orchestration capstone; 5b/5c/5d plug into the taxonomy and `Queue` it establishes.

**Architecture:** Focused single-responsibility modules under `src/bookieskit/orchestration/`: `gh.py` (`GhRunner`, an injectable `gh` subprocess wrapper mirroring `devtools/release.py`'s `GitRunner`), `labels.py` (the stream/status taxonomy + idempotent `ensure_labels`), `workitem.py` (`WorkItem` dataclass + `render_body`/`parse_meta` hand-rolled flat `key: value` serializer/parser — NO PyYAML), `queue.py` (`Queue`: find/open/update/close/list by signature), `maintenance.py` (`canary_signatures` + `sync_canary` → `SyncResult`, the canary→Issue bridge consuming `devtools/canary.py`'s `CanaryReport`/`BookCheck`), and a SEPARATE CLI `cli.py` + `__main__.py` (subcommands `sync-canary`, `ensure-labels`, `queue list`, each `--json`, non-interactive, meaningful exit codes, injected seams for offline tests). All logic is offline-testable behind an injected fake `GhRunner` and an injected canary `runner` — no `gh` process, no network in any test.

**Tech Stack:** Python 3.11+ **stdlib only** for new logic (`subprocess`, `json`, `dataclasses`, `argparse`, `re`); runtime dep is **`httpx` only** (used transitively). Tests: `pytest` (no asyncio needed — orchestration is synchronous; the CLI's `run` calls the canary runner via the injected seam, which the tests supply as a plain callable). All new tests under `tests/orchestration/` (new dir; add `tests/orchestration/__init__.py`), behind a fake `GhRunner` + an injected canary `runner`.

## Global Constraints

- Python 3.11+ **stdlib only** for new logic (`subprocess`, `json`, `dataclasses`, `argparse`, `re`); runtime dep is **`httpx` only**; do **NOT** add dependencies — **NO new deps, NO pyyaml**. The meta block is a hand-rolled flat `key: value` serializer/parser.
- New code lives in `src/bookieskit/orchestration/` (`gh.py`, `labels.py`, `workitem.py`, `queue.py`, `maintenance.py`, `cli.py`, `__main__.py`, `__init__.py`); invoked as `python -m bookieskit.orchestration <cmd>`.
- Ruff config: `select = ["E","F","I"]`, `line-length = 88`, `target-version = "py311"`. **`src/` must stay 100% ruff-clean.** `tests/**` ignores `E501`.
- ALL new tests are **offline**, under `tests/orchestration/` (create `tests/orchestration/__init__.py`), behind an **injected fake `GhRunner`** and an **injected canary `runner`** — **NO `gh` process, NO network** in any test.
- Local commands use `.venv/Scripts/python.exe -m pytest ...` / `-m ruff ...` (Windows); CI uses bare `pytest` / `ruff`.
- Agent-runnable: the CLI supports `--json`, is non-interactive, and has meaningful exit codes — **0 on successful reconciliation** (drift is *recorded*, not a CLI failure); **non-zero only on an operational `gh`/canary error**.
- Karpathy principle: smallest surgical change; focused single-responsibility modules; no speculative extension points (no orchestrator loop, no Slack, no scout — those are 5b/5c/5d).
- Suggested sequence (each task ends green and is independently testable): (1) `GhRunner` → (2) `labels.ensure_labels` → (3) `workitem` `render_body`/`parse_meta` → (4) `Queue` → (5) `maintenance` (`canary_signatures` + `sync_canary`) → (6) CLI + `__main__`.

---

### Task 1: `gh.py` — `GhRunner` (injectable `gh` subprocess wrapper)

**Files:**
- Create: `src/bookieskit/orchestration/__init__.py`
- Create: `src/bookieskit/orchestration/gh.py`
- Create: `tests/orchestration/__init__.py`
- Create: `tests/orchestration/test_gh.py`

**Interfaces:**
- Consumes: `subprocess`, `json` (stdlib only).
- Produces: `GhRunner` with `list_issues(*, labels=(), state="open") -> list[dict]`, `create_issue(*, title, body, labels) -> int`, `comment_issue(number, body) -> None`, `edit_issue(number, *, body=None, add_labels=(), remove_labels=()) -> None`, `close_issue(number, *, comment=None) -> None`, `list_labels() -> list[str]`, `create_label(name, *, color, description) -> None`. Consumed by `labels.ensure_labels` (Task 2), `Queue` (Task 4), and the CLI (Task 6).

Design notes (encoded from the spec's `gh.py` section; MIRROR `devtools/release.py`'s `GitRunner._run`):
- A thin wrapper over the `gh` CLI. Every method runs `gh` via a private `_run(*args) -> str` that calls `subprocess.run(["gh", *args], check=True, capture_output=True, text=True)` and returns `result.stdout`. A non-zero `gh` exit raises `subprocess.CalledProcessError` (its stderr propagates) — same shape as `GitRunner._run` (which omits `cwd` because `gh` operates on the repo it's invoked in, inferred from the working directory; do NOT pass `cwd`).
- `list_issues`: `gh issue list --json number,title,body,labels,state --state <state>` plus a `--label <l>` per requested label; parse stdout with `json.loads`. Returns the parsed list of dicts (each has `number`, `title`, `body`, `labels`, `state`; `labels` is a list of `{"name": ...}` dicts as `gh` returns them).
- `create_issue`: `gh issue create --title <title> --body <body>` plus a `--label <l>` per label. `gh issue create` prints the new issue **URL** (e.g. `https://github.com/owner/repo/issues/42`) to stdout; extract the trailing integer with a `re` search (`r"/(\d+)\s*$"` on the stripped stdout) and return it as `int`. Raise `ValueError` if no number can be parsed (defensive — keeps a malformed `gh` response from silently returning a wrong number).
- `comment_issue`: `gh issue comment <number> --body <body>`.
- `edit_issue`: `gh issue edit <number>` with `--body <body>` when `body is not None`, plus a `--add-label <l>` per `add_labels` and a `--remove-label <l>` per `remove_labels`. If nothing to do (no body and no label changes), return without calling `gh` (avoids an empty `gh issue edit` that errors).
- `close_issue`: `gh issue close <number>` plus `--comment <comment>` when `comment is not None`.
- `list_labels`: `gh label list --json name`; parse with `json.loads` and return `[d["name"] for d in parsed]`.
- `create_label`: `gh label create <name> --color <color> --description <description>`.
- All list-of-labels parameters default to the empty tuple `()` (immutable default, ruff-safe — never a mutable `[]` default).

- [ ] **Step 1: Write the failing test**

Create `tests/orchestration/__init__.py` (empty file).

Create `src/bookieskit/orchestration/__init__.py`:

```python
"""Orchestration: the work queue (GitHub Issues) + intake streams.

Sub-project 5a of the agent-company capstone: a durable, queryable work queue
on GitHub Issues (stream/status labels + a hand-rolled yaml meta block) and the
maintenance stream (canary drift -> Issue). Invoked as
``python -m bookieskit.orchestration <cmd>``. All logic is offline-testable
behind an injectable ``GhRunner`` and an injected canary runner.
"""
```

Create `tests/orchestration/test_gh.py`:

```python
import subprocess

import pytest

from bookieskit.orchestration.gh import GhRunner


class _RecordingRun:
    """Captures the argv each gh call would run and returns a canned stdout."""

    def __init__(self, stdout: str = ""):
        self.stdout = stdout
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        assert kwargs.get("check") is True
        assert kwargs.get("capture_output") is True
        assert kwargs.get("text") is True
        return subprocess.CompletedProcess(argv, 0, self.stdout, "")


def _gh(monkeypatch, stdout: str = "") -> tuple[GhRunner, _RecordingRun]:
    rec = _RecordingRun(stdout)
    monkeypatch.setattr(subprocess, "run", rec)
    return GhRunner(), rec


def test_list_issues_builds_json_and_label_args(monkeypatch):
    gh, rec = _gh(
        monkeypatch,
        stdout='[{"number": 7, "title": "t", "body": "b", '
        '"labels": [{"name": "stream:maintenance"}], "state": "open"}]',
    )
    out = gh.list_issues(labels=["stream:maintenance"], state="open")
    assert out[0]["number"] == 7
    argv = rec.calls[0]
    assert argv[:2] == ["gh", "issue"]
    assert "list" in argv
    assert "--state" in argv and "open" in argv
    assert "--label" in argv and "stream:maintenance" in argv
    # The --json fields the queue needs are all requested.
    json_idx = argv.index("--json")
    fields = argv[json_idx + 1]
    for field in ("number", "title", "body", "labels", "state"):
        assert field in fields


def test_create_issue_parses_trailing_number_from_url(monkeypatch):
    gh, rec = _gh(
        monkeypatch, stdout="https://github.com/o/r/issues/42\n"
    )
    n = gh.create_issue(title="T", body="B", labels=["stream:maintenance"])
    assert n == 42
    argv = rec.calls[0]
    assert "create" in argv
    assert "--title" in argv and "T" in argv
    assert "--body" in argv and "B" in argv
    assert "--label" in argv and "stream:maintenance" in argv


def test_create_issue_raises_when_no_number_in_output(monkeypatch):
    gh, _ = _gh(monkeypatch, stdout="something went wrong\n")
    with pytest.raises(ValueError):
        gh.create_issue(title="T", body="B", labels=[])


def test_comment_issue_calls_gh_issue_comment(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.comment_issue(7, "a note")
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "issue", "comment"]
    assert "7" in argv
    assert "--body" in argv and "a note" in argv


def test_edit_issue_adds_and_removes_labels(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.edit_issue(7, add_labels=["status:claimed"], remove_labels=["x"])
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "issue", "edit"]
    assert "--add-label" in argv and "status:claimed" in argv
    assert "--remove-label" in argv and "x" in argv


def test_edit_issue_noop_does_not_call_gh(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.edit_issue(7)  # nothing to change
    assert rec.calls == []


def test_close_issue_with_comment(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.close_issue(7, comment="recovered")
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "issue", "close"]
    assert "7" in argv
    assert "--comment" in argv and "recovered" in argv


def test_list_labels_returns_names(monkeypatch):
    gh, _ = _gh(
        monkeypatch, stdout='[{"name": "stream:maintenance"}, {"name": "bug"}]'
    )
    assert gh.list_labels() == ["stream:maintenance", "bug"]


def test_create_label_passes_color_and_description(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.create_label("stream:maintenance", color="d73a4a", description="drift")
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "label", "create"]
    assert "stream:maintenance" in argv
    assert "--color" in argv and "d73a4a" in argv
    assert "--description" in argv and "drift" in argv


def test_run_raises_on_nonzero_exit(monkeypatch):
    def _boom(argv, **kwargs):
        raise subprocess.CalledProcessError(1, argv, "", "gh: not authed")

    monkeypatch.setattr(subprocess, "run", _boom)
    gh = GhRunner()
    with pytest.raises(subprocess.CalledProcessError):
        gh.list_labels()
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_gh.py -q`
Expected: collection/import error — `ModuleNotFoundError: No module named 'bookieskit.orchestration.gh'`.

- [ ] **Step 3: Implement `GhRunner`**

Create `src/bookieskit/orchestration/gh.py`:

```python
"""GhRunner: a thin injectable wrapper over the ``gh`` CLI calls the queue
needs. Mirrors ``devtools/release.py``'s ``GitRunner``: every method runs ``gh``
with ``check=True`` so a non-zero exit raises ``CalledProcessError`` (its stderr
propagates). Tests inject a fake instead of touching a real ``gh`` process.
"""

import json
import re
import subprocess

_ISSUE_NUMBER_RE = re.compile(r"/(\d+)\s*$")


class GhRunner:
    """Injectable wrapper over the ``gh`` subprocess calls the queue needs."""

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["gh", *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def list_issues(
        self, *, labels: tuple[str, ...] = (), state: str = "open"
    ) -> list[dict]:
        args = [
            "issue",
            "list",
            "--json",
            "number,title,body,labels,state",
            "--state",
            state,
        ]
        for label in labels:
            args += ["--label", label]
        return json.loads(self._run(*args))

    def create_issue(
        self, *, title: str, body: str, labels: tuple[str, ...]
    ) -> int:
        args = ["issue", "create", "--title", title, "--body", body]
        for label in labels:
            args += ["--label", label]
        out = self._run(*args).strip()
        match = _ISSUE_NUMBER_RE.search(out)
        if match is None:
            raise ValueError(f"could not parse issue number from {out!r}")
        return int(match.group(1))

    def comment_issue(self, number: int, body: str) -> None:
        self._run("issue", "comment", str(number), "--body", body)

    def edit_issue(
        self,
        number: int,
        *,
        body: str | None = None,
        add_labels: tuple[str, ...] = (),
        remove_labels: tuple[str, ...] = (),
    ) -> None:
        args = ["issue", "edit", str(number)]
        if body is not None:
            args += ["--body", body]
        for label in add_labels:
            args += ["--add-label", label]
        for label in remove_labels:
            args += ["--remove-label", label]
        if len(args) == 3:  # nothing to change beyond the number
            return
        self._run(*args)

    def close_issue(self, number: int, *, comment: str | None = None) -> None:
        args = ["issue", "close", str(number)]
        if comment is not None:
            args += ["--comment", comment]
        self._run(*args)

    def list_labels(self) -> list[str]:
        out = self._run("label", "list", "--json", "name")
        return [d["name"] for d in json.loads(out)]

    def create_label(
        self, name: str, *, color: str, description: str
    ) -> None:
        self._run(
            "label",
            "create",
            name,
            "--color",
            color,
            "--description",
            description,
        )
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_gh.py -q`
Expected: `10 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration tests/orchestration`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/orchestration/__init__.py src/bookieskit/orchestration/gh.py tests/orchestration/__init__.py tests/orchestration/test_gh.py
git commit -m "feat(orchestration): GhRunner injectable gh subprocess wrapper

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `labels.py` — taxonomy + idempotent `ensure_labels`

**Files:**
- Create: `src/bookieskit/orchestration/labels.py`
- Create: `tests/orchestration/test_labels.py`

**Interfaces:**
- Consumes: `GhRunner` (Task 1; only `list_labels` + `create_label` are used).
- Produces: `STREAM_LABELS`, `STATUS_LABELS` (dicts `name -> (color, description)`), `ALL_LABELS` (merged), and `ensure_labels(gh) -> list[str]` (the names it created). Consumed by `Queue` (Task 4) and the CLI `ensure-labels` (Task 6).

Design notes (encoded from the spec's `labels.py` section — colors/descriptions verbatim):
- `STREAM_LABELS` and `STATUS_LABELS` exactly as the spec lists them.
- `ensure_labels(gh)` reads `gh.list_labels()` once, then calls `gh.create_label(name, color=..., description=...)` only for names NOT already present. Idempotent: a second run with all labels present creates nothing and returns `[]`. Returns the list of names it created, in a stable order (stream labels first, then status labels — iterate `ALL_LABELS`).

- [ ] **Step 1: Write the failing test**

Create `tests/orchestration/test_labels.py`:

```python
from bookieskit.orchestration.labels import (
    STATUS_LABELS,
    STREAM_LABELS,
    ensure_labels,
)


class _FakeGh:
    """Fake GhRunner exposing just list_labels + create_label."""

    def __init__(self, existing: list[str]):
        self._existing = list(existing)
        self.created: list[tuple[str, str, str]] = []

    def list_labels(self) -> list[str]:
        return list(self._existing)

    def create_label(self, name, *, color, description):
        self._existing.append(name)
        self.created.append((name, color, description))


def test_taxonomy_has_the_four_streams_and_two_statuses():
    assert set(STREAM_LABELS) == {
        "stream:maintenance",
        "stream:expansion",
        "stream:directed",
        "stream:capability",
    }
    assert set(STATUS_LABELS) == {"status:claimed", "status:in-review"}


def test_ensure_labels_creates_all_when_none_exist():
    gh = _FakeGh(existing=[])
    created = ensure_labels(gh)
    assert set(created) == set(STREAM_LABELS) | set(STATUS_LABELS)
    assert len(gh.created) == 6
    # Color + description are passed through from the taxonomy.
    by_name = {c[0]: c for c in gh.created}
    name, color, desc = by_name["stream:maintenance"]
    assert color == STREAM_LABELS["stream:maintenance"][0]
    assert desc == STREAM_LABELS["stream:maintenance"][1]


def test_ensure_labels_creates_only_missing():
    gh = _FakeGh(existing=["stream:maintenance", "status:claimed", "bug"])
    created = ensure_labels(gh)
    assert "stream:maintenance" not in created
    assert "status:claimed" not in created
    assert "stream:expansion" in created
    assert "status:in-review" in created
    assert len(created) == 4


def test_ensure_labels_is_idempotent_second_run_is_noop():
    existing = list(STREAM_LABELS) + list(STATUS_LABELS)
    gh = _FakeGh(existing=existing)
    assert ensure_labels(gh) == []
    assert gh.created == []
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_labels.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bookieskit.orchestration.labels'`.

- [ ] **Step 3: Implement `labels.py`**

Create `src/bookieskit/orchestration/labels.py`:

```python
"""Work-queue label taxonomy + idempotent ``ensure_labels``.

Stream labels route work to an intake stream; status labels carry the in-flight
state (open/closed are native issue state; ``status:claimed``/``status:in-review``
+ assignee + linked PR carry the rest). ``ensure_labels`` creates only the
missing labels, so it is safe to call on every queue use.
"""

from bookieskit.orchestration.gh import GhRunner

STREAM_LABELS: dict[str, tuple[str, str]] = {
    "stream:maintenance": ("d73a4a", "Canary drift / keep-it-working"),
    "stream:expansion": ("0e8a16", "Scout: new sport/market/bookmaker"),
    "stream:directed": ("1d76db", "Owner-requested work"),
    "stream:capability": ("5319e7", "Adopt a new skill / MCP"),
}

STATUS_LABELS: dict[str, tuple[str, str]] = {
    "status:claimed": ("fbca04", "An agent is working this"),
    "status:in-review": ("0052cc", "PR open, awaiting review"),
}

ALL_LABELS: dict[str, tuple[str, str]] = {**STREAM_LABELS, **STATUS_LABELS}


def ensure_labels(gh: GhRunner) -> list[str]:
    """Create any missing stream:*/status:* labels. Idempotent. Returns the
    names that were created (empty when everything already exists)."""
    existing = set(gh.list_labels())
    created: list[str] = []
    for name, (color, description) in ALL_LABELS.items():
        if name in existing:
            continue
        gh.create_label(name, color=color, description=description)
        created.append(name)
    return created
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_labels.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration tests/orchestration`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/orchestration/labels.py tests/orchestration/test_labels.py
git commit -m "feat(orchestration): label taxonomy + idempotent ensure_labels

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `workitem.py` — `WorkItem` + `render_body` / `parse_meta`

**Files:**
- Create: `src/bookieskit/orchestration/workitem.py`
- Create: `tests/orchestration/test_workitem.py`

**Interfaces:**
- Consumes: `dataclasses`, `re` (stdlib only — NO PyYAML).
- Produces: `WorkItem(signature, stream, title, summary, meta={})` dataclass; `render_body(item) -> str`; `parse_meta(body) -> dict`. Consumed by `Queue` (Task 4) and `maintenance` (Task 5).

Design notes (encoded from the spec's `workitem.py` section):
- `WorkItem` dataclass fields: `signature: str`, `stream: str`, `title: str`, `summary: str`, `meta: dict[str, Any] = field(default_factory=dict)`.
- `render_body(item)`: a fenced ` ```yaml ` block holding `signature: <sig>`, `stream: <stream>`, then each `meta` key as a flat `key: value` line — then a blank line and the `summary` prose below the closing fence. **Hand-rolled flat `key: value` serialization**: values are coerced to `str`; no nesting, no lists, no quoting beyond what a flat scalar needs. The order inside the block is `signature`, `stream`, then meta keys in insertion order — deterministic so re-renders are byte-stable.
- `parse_meta(body)`: extract the FIRST fenced ` ```yaml ` … ` ``` ` block and parse its `key: value` lines into a dict (split on the first `": "`; key and value `.strip()`ed). Returns `{}` if there is no yaml block or it is malformed (no `key: value` lines). Robust to a body with no block (a non-ours / hand-filed issue) — returns `{}` rather than raising.
- Round-trip must be **lossless for the fields used**: `parse_meta(render_body(item))` recovers `signature`, `stream`, and every string-valued `meta` entry. (Values are strings end-to-end; a caller passing an int in `meta` gets back its `str` — acceptable, the queue only stores string scalars.)
- The fence is exactly ` ```yaml ` open / ` ``` ` close; the regex matches with `re.DOTALL` so the block can span lines. Use a non-greedy capture so only the first block is taken.

- [ ] **Step 1: Write the failing test**

Create `tests/orchestration/test_workitem.py`:

```python
from bookieskit.orchestration.workitem import (
    WorkItem,
    parse_meta,
    render_body,
)


def test_render_body_has_yaml_block_with_signature_and_stream():
    item = WorkItem(
        signature="canary:betika:structure",
        stream="stream:maintenance",
        title="betika structure drift",
        summary="The betika payload shape changed.",
    )
    body = render_body(item)
    assert "```yaml" in body
    assert "signature: canary:betika:structure" in body
    assert "stream: stream:maintenance" in body
    assert "The betika payload shape changed." in body
    # The prose sits below the closing fence.
    assert body.index("```yaml") < body.index("The betika payload shape")


def test_render_body_includes_meta_scalars():
    item = WorkItem(
        signature="canary:betika:missing:1x2_ft",
        stream="stream:maintenance",
        title="betika missing 1x2_ft",
        summary="Core market stopped resolving.",
        meta={"platform": "betika", "canonical": "1x2_ft"},
    )
    body = render_body(item)
    assert "platform: betika" in body
    assert "canonical: 1x2_ft" in body


def test_parse_meta_round_trips_signature_stream_and_meta():
    item = WorkItem(
        signature="canary:betika:missing:1x2_ft",
        stream="stream:maintenance",
        title="t",
        summary="s",
        meta={"platform": "betika", "canonical": "1x2_ft"},
    )
    meta = parse_meta(render_body(item))
    assert meta["signature"] == "canary:betika:missing:1x2_ft"
    assert meta["stream"] == "stream:maintenance"
    assert meta["platform"] == "betika"
    assert meta["canonical"] == "1x2_ft"


def test_parse_meta_returns_empty_when_no_yaml_block():
    assert parse_meta("Just a hand-filed issue with no meta block.") == {}


def test_parse_meta_returns_empty_on_malformed_block():
    # A yaml fence with no key: value lines -> {}.
    body = "```yaml\njust prose, no colon pairs\n```\n"
    assert parse_meta(body) == {}


def test_parse_meta_takes_only_the_first_block():
    body = (
        "```yaml\nsignature: a\nstream: stream:maintenance\n```\n"
        "noise\n"
        "```yaml\nsignature: b\n```\n"
    )
    assert parse_meta(body)["signature"] == "a"
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_workitem.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bookieskit.orchestration.workitem'`.

- [ ] **Step 3: Implement `workitem.py`**

Create `src/bookieskit/orchestration/workitem.py`:

```python
"""WorkItem model + the issue-body format.

A work item is rendered as a fenced ``yaml`` meta block (the machine-readable
dedup contract: ``signature`` + ``stream`` + flat ``meta`` scalars) followed by
human prose. The block is serialized/parsed by a tiny hand-rolled flat
``key: value`` codec — no PyYAML (runtime dep stays ``httpx``-only). Round-trip
is lossless for the string scalars the queue stores.
"""

import re
from dataclasses import dataclass, field
from typing import Any

_YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)


@dataclass
class WorkItem:
    """A unit of queued work: a dedup signature, its stream, and prose."""

    signature: str
    stream: str
    title: str
    summary: str
    meta: dict[str, Any] = field(default_factory=dict)


def render_body(item: WorkItem) -> str:
    """Render the issue body: a fenced ``yaml`` meta block then the summary.

    The block holds ``signature`` and ``stream`` first, then each ``meta`` key
    as a flat ``key: value`` scalar (values coerced to ``str``). The order is
    deterministic so re-renders are byte-stable.
    """
    lines = [
        f"signature: {item.signature}",
        f"stream: {item.stream}",
    ]
    for key, value in item.meta.items():
        lines.append(f"{key}: {value}")
    block = "\n".join(lines)
    return f"```yaml\n{block}\n```\n\n{item.summary}"


def parse_meta(body: str) -> dict[str, Any]:
    """Extract the first fenced ``yaml`` meta block as a flat dict.

    Returns ``{}`` when there is no block or it contains no ``key: value``
    lines (a hand-filed / non-ours issue is simply not matched, never a crash).
    """
    match = _YAML_BLOCK_RE.search(body)
    if match is None:
        return {}
    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        meta[key.strip()] = value.strip()
    return meta
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_workitem.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration tests/orchestration`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/orchestration/workitem.py tests/orchestration/test_workitem.py
git commit -m "feat(orchestration): WorkItem + hand-rolled yaml meta render/parse

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `queue.py` — `Queue` (find / open-or-update / close / list by signature)

**Files:**
- Create: `src/bookieskit/orchestration/queue.py`
- Create: `tests/orchestration/test_queue.py`

**Interfaces:**
- Consumes: `GhRunner` (Task 1), `ensure_labels` (Task 2), `WorkItem` + `render_body` + `parse_meta` (Task 3).
- Produces: `Queue(gh, *, ensure=True)` with `find_open_by_signature(signature) -> dict | None`, `open_or_update(item, *, note) -> tuple[int, str]`, `close_by_signature(signature, *, reason) -> int | None`, `list_open(*, stream=None) -> list[dict]`. Consumed by `maintenance.sync_canary` (Task 5) and the CLI (Task 6).

Design notes (encoded from the spec's `queue.py` section):
- `__init__(gh, *, ensure=True)`: store `gh`; when `ensure` is True call `ensure_labels(gh)` once (so the labels exist before the first issue is filed). Tests pass `ensure=False` (or a fake whose `list_labels` returns everything) to keep label setup out of the assertion surface where not relevant.
- `find_open_by_signature(signature)`: `gh.list_issues(state="open")`, `parse_meta(issue["body"])` each, return the first whose parsed `signature` equals the argument (else `None`). An issue with no/garbled meta simply doesn't match (its `parse_meta` is `{}`).
- `open_or_update(item, *, note)`: if `find_open_by_signature(item.signature)` returns an existing issue → `gh.comment_issue(number, note)` and return `(number, "updated")`. Else `gh.create_issue(title=item.title, body=render_body(item), labels=(item.stream,))` and return `(number, "opened")`. (Only the stream label is applied at creation; status labels are added later by 5b.)
- `close_by_signature(signature, *, reason)`: if an open issue matches → `gh.close_issue(number, comment=reason)` and return its number; else return `None`.
- `list_open(*, stream=None)`: `gh.list_issues(state="open", labels=(stream,) if stream else ())` and return the raw list of issue dicts.

- [ ] **Step 1: Write the failing test**

Create `tests/orchestration/test_queue.py`:

```python
from bookieskit.orchestration.queue import Queue
from bookieskit.orchestration.workitem import WorkItem, render_body


class _FakeGh:
    """In-memory GhRunner fake: tracks open issues + records mutations."""

    def __init__(self):
        self.issues: list[dict] = []
        self._next = 1
        self.comments: list[tuple[int, str]] = []
        self.closed: list[tuple[int, str | None]] = []
        # Pretend every label already exists so ensure_labels is a no-op.
        self._labels = [
            "stream:maintenance", "stream:expansion", "stream:directed",
            "stream:capability", "status:claimed", "status:in-review",
        ]

    def list_labels(self):
        return list(self._labels)

    def create_label(self, name, *, color, description):
        self._labels.append(name)

    def list_issues(self, *, labels=(), state="open"):
        out = [i for i in self.issues if i["state"] == state]
        for label in labels:
            out = [
                i for i in out
                if label in [l["name"] for l in i["labels"]]
            ]
        return out

    def create_issue(self, *, title, body, labels):
        number = self._next
        self._next += 1
        self.issues.append({
            "number": number, "title": title, "body": body,
            "labels": [{"name": l} for l in labels], "state": "open",
        })
        return number

    def comment_issue(self, number, body):
        self.comments.append((number, body))

    def close_issue(self, number, *, comment=None):
        for i in self.issues:
            if i["number"] == number:
                i["state"] = "closed"
        self.closed.append((number, comment))


def _item(sig="canary:betika:structure"):
    return WorkItem(
        signature=sig, stream="stream:maintenance",
        title="t", summary="s", meta={"platform": "betika"},
    )


def test_open_or_update_creates_when_absent():
    gh = _FakeGh()
    q = Queue(gh)
    number, action = q.open_or_update(_item(), note="opened")
    assert action == "opened"
    assert number == 1
    assert gh.issues[0]["labels"] == [{"name": "stream:maintenance"}]


def test_open_or_update_comments_when_present():
    gh = _FakeGh()
    q = Queue(gh)
    n1, _ = q.open_or_update(_item(), note="first")
    n2, action = q.open_or_update(_item(), note="still drifting")
    assert action == "updated"
    assert n2 == n1
    assert gh.comments == [(n1, "still drifting")]
    assert len(gh.issues) == 1  # no duplicate


def test_find_open_by_signature_matches_via_parsed_meta():
    gh = _FakeGh()
    gh.create_issue(
        title="t", body=render_body(_item("canary:msport:structure")),
        labels=["stream:maintenance"],
    )
    q = Queue(gh, ensure=False)
    found = q.find_open_by_signature("canary:msport:structure")
    assert found is not None and found["number"] == 1
    assert q.find_open_by_signature("canary:nope:structure") is None


def test_find_open_ignores_issue_without_meta_block():
    gh = _FakeGh()
    gh.create_issue(title="hand-filed", body="no meta here", labels=[])
    q = Queue(gh, ensure=False)
    assert q.find_open_by_signature("canary:betika:structure") is None


def test_close_by_signature_closes_and_returns_number():
    gh = _FakeGh()
    q = Queue(gh)
    n, _ = q.open_or_update(_item(), note="opened")
    closed = q.close_by_signature(_item().signature, reason="recovered")
    assert closed == n
    assert gh.closed == [(n, "recovered")]
    assert gh.issues[0]["state"] == "closed"


def test_close_by_signature_returns_none_when_absent():
    gh = _FakeGh()
    q = Queue(gh)
    assert q.close_by_signature("canary:ghost:structure", reason="x") is None


def test_list_open_filters_by_stream():
    gh = _FakeGh()
    q = Queue(gh)
    q.open_or_update(_item(), note="opened")
    assert len(q.list_open()) == 1
    assert len(q.list_open(stream="stream:maintenance")) == 1
    assert q.list_open(stream="stream:expansion") == []


def test_constructor_ensure_true_creates_missing_labels():
    gh = _FakeGh()
    gh._labels = ["bug"]  # nothing of ours exists yet
    Queue(gh)  # ensure=True by default
    assert "stream:maintenance" in gh._labels
    assert "status:claimed" in gh._labels
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_queue.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bookieskit.orchestration.queue'`.

- [ ] **Step 3: Implement `queue.py`**

Create `src/bookieskit/orchestration/queue.py`:

```python
"""Queue: the durable work queue over GitHub Issues.

Dedup is by the ``signature`` stored in each issue's yaml meta block: a re-run
that finds an open issue with the same signature *updates* (comments) rather
than duplicating, and closes one whose work is done. Labels are ensured on
first use so the stream label always exists before an issue is filed.
"""

from bookieskit.orchestration.gh import GhRunner
from bookieskit.orchestration.labels import ensure_labels
from bookieskit.orchestration.workitem import WorkItem, parse_meta, render_body


class Queue:
    """Read/write the work queue (GitHub Issues), deduped by signature."""

    def __init__(self, gh: GhRunner, *, ensure: bool = True):
        self.gh = gh
        if ensure:
            ensure_labels(gh)

    def find_open_by_signature(self, signature: str) -> dict | None:
        for issue in self.gh.list_issues(state="open"):
            if parse_meta(issue.get("body", "")).get("signature") == signature:
                return issue
        return None

    def open_or_update(
        self, item: WorkItem, *, note: str
    ) -> tuple[int, str]:
        existing = self.find_open_by_signature(item.signature)
        if existing is not None:
            number = existing["number"]
            self.gh.comment_issue(number, note)
            return number, "updated"
        number = self.gh.create_issue(
            title=item.title,
            body=render_body(item),
            labels=(item.stream,),
        )
        return number, "opened"

    def close_by_signature(
        self, signature: str, *, reason: str
    ) -> int | None:
        existing = self.find_open_by_signature(signature)
        if existing is None:
            return None
        number = existing["number"]
        self.gh.close_issue(number, comment=reason)
        return number

    def list_open(self, *, stream: str | None = None) -> list[dict]:
        labels = (stream,) if stream else ()
        return self.gh.list_issues(state="open", labels=labels)
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_queue.py -q`
Expected: `8 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration tests/orchestration`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/orchestration/queue.py tests/orchestration/test_queue.py
git commit -m "feat(orchestration): Queue — signature-deduped GitHub-Issues work queue

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `maintenance.py` — `canary_signatures` + `sync_canary` (canary → Issue bridge)

**Files:**
- Create: `src/bookieskit/orchestration/maintenance.py`
- Create: `tests/orchestration/test_maintenance.py`

**Interfaces:**
- Consumes: `CanaryReport` + `BookCheck` (from `bookieskit.devtools.canary`), `WorkItem` (Task 3), `Queue` (Task 4).
- Produces: `canary_signatures(report) -> list[tuple[str, str]]` (`(signature, title)` per drift), `SyncResult(opened, updated, closed, errors)` dataclass, `sync_canary(report, queue) -> SyncResult`. Consumed by the CLI `sync-canary` (Task 6).

Design notes (encoded from the spec's `maintenance.py` section + the verified `CanaryReport`/`BookCheck` shapes):
- `CanaryReport` fields (verified in `src/bookieskit/devtools/canary.py`): `sport`, `seed: str | None`, `sr_numeric`, `checks: list[BookCheck]`, `drifted: bool`. `BookCheck` fields: `platform`, `status` (`"ok"|"drift"|"unreachable"|"skipped"`), `reason`, `expected_canonicals`, `resolved_canonicals`, `missing_canonicals`, `structure_ok`.
- `canary_signatures(report)`: derive `(signature, title)` pairs from drift in the report:
  - For each `BookCheck` with `status == "drift"`: if `structure_ok is False` → `("canary:<platform>:structure", "<platform> structure drift")`. Then for each canonical in `missing_canonicals` → `("canary:<platform>:missing:<canonical>", "<platform> missing core market <canonical>")`. (A structure-drift check has `missing_canonicals == list(expected)`, so a broken-structure book yields its structure signature PLUS one missing signature per expected core canonical — both are real, actionable drifts; the recovery rule closes them together when the book goes ok again.)
  - When `report.seed is None` → add `("canary:seed-discovery", "canary seed discovery failed")` (the discovery-failure signal — geo-block / churn, owner-actionable).
  - Returns a list in a deterministic order: per-check (in `report.checks` order) structure-then-missing, with the seed-discovery pair appended last when applicable.
- `SyncResult` dataclass: `opened: list[str]`, `updated: list[str]`, `closed: list[str]`, `errors: list[str]` — all signatures (errors are `"<signature>: <exc>"` strings). `--json`-serializable via `asdict`.
- `sync_canary(report, queue)`: reconcile. Build `current = canary_signatures(report)` and `current_sigs = {sig for sig, _ in current}`.
  1. **Open/update** each current drift: `WorkItem(signature, stream="stream:maintenance", title, summary=<derived>, meta=<derived>)` → `queue.open_or_update(item, note=...)`; record the signature in `opened` or `updated` per the returned action. A `gh` error on one item is caught, recorded in `errors`, and the loop continues (per-operation isolation — mirrors the canary/resolver pattern).
  2. **Recovery close**: for each `BookCheck` with `status == "ok"`, compute its platform's possible signatures (`canary:<p>:structure` and `canary:<p>:missing:<canonical>` for every `canonical in expected_canonicals`); for each such signature **not** in `current_sigs`, `queue.close_by_signature(signature, reason=...)`; if it returned a number, record it in `closed`. Skipped/unreachable platforms are **never** closed (recovery can't be confirmed). Per-signature `gh` errors are isolated into `errors`.
  - The recovery rule is precise: an open `canary:<p>:...` issue is closed ONLY when this run has a `BookCheck` for `<p>` with `status == "ok"` AND that signature is absent from the current drift set. Because `close_by_signature` returns `None` when no open issue matches, closing a never-opened signature is a harmless no-op (not recorded).
  - Seed-discovery recovery: there is no platform "ok" that clears `canary:seed-discovery`; it is closed implicitly only on a run where `report.seed is not None` is handled separately — close `canary:seed-discovery` when `report.seed is not None` and it's not in `current_sigs` (it never is when seed is present). Record in `closed` if a number came back.

- [ ] **Step 1: Write the failing test**

Create `tests/orchestration/test_maintenance.py`:

```python
from dataclasses import asdict

from bookieskit.devtools.canary import BookCheck, CanaryReport
from bookieskit.orchestration.maintenance import (
    SyncResult,
    canary_signatures,
    sync_canary,
)


def _check(platform, status, *, missing=(), structure_ok=True, expected=()):
    expected = list(expected) or ["1x2_ft", "over_under_ft"]
    return BookCheck(
        platform=platform, status=status, reason="",
        expected_canonicals=expected,
        resolved_canonicals=[c for c in expected if c not in missing],
        missing_canonicals=list(missing), structure_ok=structure_ok,
    )


def _report(checks, *, seed="555"):
    return CanaryReport(
        sport="soccer", seed=seed, sr_numeric="777",
        checks=list(checks), drifted=any(c.status == "drift" for c in checks),
    )


class _FakeQueue:
    """Records open_or_update / close_by_signature; configurable presence."""

    def __init__(self, present: set[str] | None = None):
        self._present = set(present or set())
        self.opened: list[str] = []
        self.updated: list[str] = []
        self.closed: list[str] = []
        self._n = 100

    def open_or_update(self, item, *, note):
        self._n += 1
        if item.signature in self._present:
            self.updated.append(item.signature)
            return self._n, "updated"
        self._present.add(item.signature)
        self.opened.append(item.signature)
        return self._n, "opened"

    def close_by_signature(self, signature, *, reason):
        if signature in self._present:
            self._present.discard(signature)
            self.closed.append(signature)
            self._n += 1
            return self._n
        return None


def test_canary_signatures_structure_drift_collapses_to_one():
    # A structure break is ONE root-cause signature, not one per missing core.
    rep = _report([_check("betika", "drift", structure_ok=False,
                          missing=["1x2_ft", "over_under_ft"])])
    sigs = dict(canary_signatures(rep))
    assert sigs == {"canary:betika:structure": "betika structure drift"}


def test_canary_signatures_missing_core_only():
    rep = _report([_check("msport", "drift", missing=["btts_ft"],
                          structure_ok=True, expected=["btts_ft", "1x2_ft"])])
    sigs = dict(canary_signatures(rep))
    assert sigs == {
        "canary:msport:missing:btts_ft": "msport missing core market btts_ft"
    }


def test_canary_signatures_seed_none():
    rep = _report([], seed=None)
    sigs = dict(canary_signatures(rep))
    assert "canary:seed-discovery" in sigs


def test_canary_signatures_no_drift_is_empty():
    rep = _report([_check("betpawa", "ok")])
    assert canary_signatures(rep) == []


def test_sync_opens_new_drift():
    rep = _report([_check("betika", "drift", structure_ok=False,
                          missing=["1x2_ft"], expected=["1x2_ft"])])
    q = _FakeQueue()
    result = sync_canary(rep, q)
    assert result.opened == ["canary:betika:structure"]  # collapses to one
    assert result.updated == []
    assert isinstance(result, SyncResult)


def test_sync_updates_persisting_drift():
    rep = _report([_check("betika", "drift", structure_ok=False,
                          missing=["1x2_ft"], expected=["1x2_ft"])])
    q = _FakeQueue(present={"canary:betika:structure"})
    result = sync_canary(rep, q)
    assert result.updated == ["canary:betika:structure"]
    assert result.opened == []


def test_sync_closes_recovered_check():
    # betika was drifting (issues open) and is OK this run -> close both.
    rep = _report([_check("betika", "ok", expected=["1x2_ft"])])
    q = _FakeQueue(present={"canary:betika:structure",
                            "canary:betika:missing:1x2_ft"})
    result = sync_canary(rep, q)
    assert set(result.closed) == {
        "canary:betika:structure", "canary:betika:missing:1x2_ft"
    }


def test_sync_does_not_close_skipped_or_unreachable():
    # An open structure issue for a platform that is unreachable/skipped this
    # run must NOT be closed (recovery can't be confirmed).
    rep = _report([
        _check("bet9ja", "unreachable", expected=["1x2_ft"]),
        _check("sportpesa", "skipped", expected=["1x2_ft"]),
    ])
    q = _FakeQueue(present={"canary:bet9ja:structure",
                            "canary:sportpesa:structure"})
    result = sync_canary(rep, q)
    assert result.closed == []


def test_sync_closes_seed_discovery_when_seed_recovered():
    rep = _report([_check("betpawa", "ok", expected=["1x2_ft"])], seed="555")
    q = _FakeQueue(present={"canary:seed-discovery"})
    result = sync_canary(rep, q)
    assert "canary:seed-discovery" in result.closed


def test_sync_isolates_per_item_gh_errors():
    class _BoomQueue(_FakeQueue):
        def open_or_update(self, item, *, note):
            raise RuntimeError("gh boom")

    rep = _report([_check("betika", "drift", structure_ok=False,
                          missing=["1x2_ft"], expected=["1x2_ft"])])
    result = sync_canary(rep, _BoomQueue())
    assert result.opened == []
    assert any("gh boom" in e for e in result.errors)


def test_sync_result_serializes_for_json():
    rep = _report([_check("betika", "drift", structure_ok=False,
                          missing=["1x2_ft"], expected=["1x2_ft"])])
    d = asdict(sync_canary(rep, _FakeQueue()))
    assert set(d) == {"opened", "updated", "closed", "errors"}
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_maintenance.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bookieskit.orchestration.maintenance'`.

- [ ] **Step 3: Implement `maintenance.py`**

Create `src/bookieskit/orchestration/maintenance.py`:

```python
"""Maintenance stream: reconcile a CanaryReport into the work queue.

Each current drift -> a deduped ``stream:maintenance`` Issue (open on first
sight, comment on persistence). A check that is OK this run closes its open
issues (recovery), but a skipped/unreachable platform is left untouched because
recovery can't be confirmed. Per-issue gh errors are isolated so one failure
doesn't abort the reconciliation.
"""

from dataclasses import dataclass, field

from bookieskit.devtools.canary import BookCheck, CanaryReport
from bookieskit.orchestration.queue import Queue
from bookieskit.orchestration.workitem import WorkItem

_STREAM = "stream:maintenance"
_SEED_SIGNATURE = "canary:seed-discovery"


@dataclass
class SyncResult:
    """Outcome of a sync_canary run, all lists of signatures."""

    opened: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    closed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _check_signatures(check: BookCheck) -> list[tuple[str, str]]:
    """The drift signatures a single BookCheck contributes.

    A structure break is ONE root-cause signature — the missing canonicals are
    a *consequence* of the broken structure, not separate problems (a
    structure-broken check has ``missing_canonicals == expected``). Only when
    structure is intact but specific core markets stopped resolving do we emit
    one signature per missing canonical.
    """
    if not check.structure_ok:
        return [(
            f"canary:{check.platform}:structure",
            f"{check.platform} structure drift",
        )]
    return [
        (
            f"canary:{check.platform}:missing:{canonical}",
            f"{check.platform} missing core market {canonical}",
        )
        for canonical in check.missing_canonicals
    ]


def canary_signatures(report: CanaryReport) -> list[tuple[str, str]]:
    """(signature, human title) for each drift in the report.

    Kinds: ``canary:<platform>:structure``,
    ``canary:<platform>:missing:<canonical>``, and ``canary:seed-discovery``
    when ``report.seed is None``.
    """
    out: list[tuple[str, str]] = []
    for check in report.checks:
        if check.status == "drift":
            out += _check_signatures(check)
    if report.seed is None:
        out.append((_SEED_SIGNATURE, "canary seed discovery failed"))
    return out


def _possible_signatures(check: BookCheck) -> list[str]:
    """Every signature a platform *could* have, used to find recoveries."""
    sigs = [f"canary:{check.platform}:structure"]
    sigs += [
        f"canary:{check.platform}:missing:{c}"
        for c in check.expected_canonicals
    ]
    return sigs


def sync_canary(report: CanaryReport, queue: Queue) -> SyncResult:
    """Reconcile a CanaryReport into the maintenance stream."""
    result = SyncResult()
    current = canary_signatures(report)
    current_sigs = {sig for sig, _ in current}
    titles = dict(current)

    # 1. Open or update each current drift.
    for signature in current_sigs:
        title = titles[signature]
        item = WorkItem(
            signature=signature,
            stream=_STREAM,
            title=title,
            summary=f"Canary drift detected: {title}.",
            meta={"source": "canary"},
        )
        try:
            _, action = queue.open_or_update(
                item, note=f"Still drifting: {title}."
            )
        except Exception as exc:  # per-operation isolation
            result.errors.append(f"{signature}: {exc}")
            continue
        (result.opened if action == "opened" else result.updated).append(
            signature
        )

    # 2. Recovery: close issues for platforms that are OK this run.
    for check in report.checks:
        if check.status != "ok":
            continue  # never close for skipped/unreachable
        for signature in _possible_signatures(check):
            if signature in current_sigs:
                continue
            try:
                number = queue.close_by_signature(
                    signature, reason=f"Recovered: {check.platform} is OK."
                )
            except Exception as exc:
                result.errors.append(f"{signature}: {exc}")
                continue
            if number is not None:
                result.closed.append(signature)

    # 3. Seed-discovery recovery: a run with a seed clears the discovery issue.
    if report.seed is not None and _SEED_SIGNATURE not in current_sigs:
        try:
            number = queue.close_by_signature(
                _SEED_SIGNATURE, reason="Recovered: seed discovery succeeded."
            )
        except Exception as exc:
            result.errors.append(f"{_SEED_SIGNATURE}: {exc}")
        else:
            if number is not None:
                result.closed.append(_SEED_SIGNATURE)

    return result
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_maintenance.py -q`
Expected: `12 passed`.

- [ ] **Step 5: Lint**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration tests/orchestration`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/orchestration/maintenance.py tests/orchestration/test_maintenance.py
git commit -m "feat(orchestration): canary->Issue maintenance bridge (canary_signatures + sync_canary)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `cli.py` + `__main__.py` — the orchestration CLI

**Files:**
- Create: `src/bookieskit/orchestration/cli.py`
- Create: `src/bookieskit/orchestration/__main__.py`
- Create: `tests/orchestration/test_cli.py`

**Interfaces:**
- Consumes: `GhRunner` (Task 1), `ensure_labels` (Task 2), `Queue` (Task 4), `sync_canary` + `SyncResult` (Task 5), and `run_canary` + `CanaryReport` (from `bookieskit.devtools.canary`).
- Produces: `python -m bookieskit.orchestration sync-canary [--sport soccer] [--json]`, `ensure-labels [--json]`, `queue list [--stream <s>] [--json]`. Exit code **0 on successful reconciliation**; **non-zero on an operational `gh`/canary error**.

Design notes — mirror `devtools/cli.py`'s patterns (argparse subparsers, `--json` via an `_emit`-style helper, injected seams, exit codes), but this is a SEPARATE CLI for the new subpackage:
- `run_canary` is **async** (verified — `async def run_canary(...)`), so the `sync-canary` branch must `asyncio.run(runner(args.sport, clients=...))` to get the report. To keep the CLI's `run` itself simple and synchronous, run the canary inside the branch with `asyncio.run`; the injected test `runner` is supplied as an **async** callable matching `run_canary`'s signature (the tests define `async def _runner_ok(sport, *, ...)`), so `asyncio.run(runner(...))` works for both the real and the fake.
- `_emit(obj, as_json, text_lines)`: identical helper to `devtools/cli.py` — `print(json.dumps(obj, default=str))` when `as_json` else `print("\n".join(text_lines))`.
- Injected seams on `run(args, *, runner=run_canary, gh=None)`: `runner` defaults to `run_canary`; `gh` defaults to `None` and is lazily constructed as `GhRunner()` inside `run` when needed (so importing the module never spawns a process, and tests inject a fake `gh`). The `Queue` is built from `gh` inside the relevant branches.
- `sync-canary`: `report = asyncio.run(runner(args.sport))`; `queue = Queue(gh)`; `result = sync_canary(report, queue)`; `_emit(asdict(result), args.as_json, [...])`. Exit **0** on success (drift recorded is success). A `gh`/canary operational error (`subprocess.CalledProcessError` from `GhRunner`, or any exception escaping `runner`/`Queue` construction) is caught at the top of the branch → print the message → return **1**. (Per-item gh errors inside `sync_canary` are already isolated into `result.errors` and do NOT fail the command; only an error that aborts the whole reconciliation — e.g. the initial `list_issues`/`ensure_labels` failing — returns non-zero.)
- `ensure-labels`: `created = ensure_labels(gh)`; `_emit({"created": created}, args.as_json, [...])`; return **0** (a `CalledProcessError` propagates to a non-zero exit via the `main`-level try, see below).
- `queue list`: `issues = Queue(gh, ensure=False).list_open(stream=args.stream)`; emit a compact view (number, title, signature parsed from the body). Return **0**.
- Operational-error mapping: wrap the dispatch so a `subprocess.CalledProcessError` (gh not authed / network) becomes exit **1** with the gh stderr printed — do this in `main` (catch `CalledProcessError`, print `exc.stderr or exc`, return 1) so all three subcommands inherit it. The `sync-canary` branch additionally catches broadly to map a canary/runner failure to 1 while still printing.
- `argparse`: a top-level `cmd` subparser; `queue` is a sub-subparser group with a `list` action (so `queue list` parses), OR — simpler and sufficient here — a single `queue-list` is avoided in favor of the spec's literal `queue list`: add a `queue` subparser whose own `add_subparsers(dest="queue_cmd")` has a `list` parser. Tests assert `parse_args(["queue", "list"]).cmd == "queue"` and `.queue_cmd == "list"`.
- `__main__.py`: mirror `devtools/__main__.py` — force UTF-8 stdout/stderr (Windows cp1252 safety for the `->`/arrow-free output, still harmless), then `sys.exit(main())`.

- [ ] **Step 1: Write the failing test**

Create `tests/orchestration/test_cli.py`:

```python
import json

import pytest

from bookieskit.devtools.canary import BookCheck, CanaryReport
from bookieskit.orchestration import cli


class _FakeGh:
    """In-memory gh fake reused for the CLI (labels pre-populated)."""

    def __init__(self, issues=None):
        self.issues = list(issues or [])
        self._next = len(self.issues) + 1
        self.comments = []
        self.closed = []
        self._labels = [
            "stream:maintenance", "stream:expansion", "stream:directed",
            "stream:capability", "status:claimed", "status:in-review",
        ]

    def list_labels(self):
        return list(self._labels)

    def create_label(self, name, *, color, description):
        self._labels.append(name)

    def list_issues(self, *, labels=(), state="open"):
        out = [i for i in self.issues if i.get("state", "open") == state]
        for label in labels:
            out = [
                i for i in out
                if label in [l["name"] for l in i.get("labels", [])]
            ]
        return out

    def create_issue(self, *, title, body, labels):
        number = self._next
        self._next += 1
        self.issues.append({
            "number": number, "title": title, "body": body,
            "labels": [{"name": l} for l in labels], "state": "open",
        })
        return number

    def comment_issue(self, number, body):
        self.comments.append((number, body))

    def close_issue(self, number, *, comment=None):
        for i in self.issues:
            if i["number"] == number:
                i["state"] = "closed"
        self.closed.append((number, comment))


async def _runner_drift(sport, *, seed=None, max_candidates=3, clients=None):
    return CanaryReport(
        sport=sport, seed="555", sr_numeric="777",
        checks=[BookCheck(
            platform="betika", status="drift", reason="structure",
            expected_canonicals=["1x2_ft"], resolved_canonicals=[],
            missing_canonicals=["1x2_ft"], structure_ok=False,
        )],
        drifted=True,
    )


async def _runner_ok(sport, *, seed=None, max_candidates=3, clients=None):
    return CanaryReport(
        sport=sport, seed="555", sr_numeric="777",
        checks=[BookCheck(
            platform="betika", status="ok", reason="",
            expected_canonicals=["1x2_ft"], resolved_canonicals=["1x2_ft"],
            missing_canonicals=[], structure_ok=True,
        )],
        drifted=False,
    )


def test_build_parser_has_three_subcommands():
    p = cli.build_parser()
    assert p.parse_args(["sync-canary"]).cmd == "sync-canary"
    assert p.parse_args(["ensure-labels"]).cmd == "ensure-labels"
    qargs = p.parse_args(["queue", "list"])
    assert qargs.cmd == "queue" and qargs.queue_cmd == "list"


def test_sync_canary_json_opens_issue_and_exits_zero(capsys):
    gh = _FakeGh()
    code = cli.run(
        cli.build_parser().parse_args(["sync-canary", "--json"]),
        runner=_runner_drift, gh=gh,
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert "canary:betika:structure" in out["opened"]
    assert "canary:betika:missing:1x2_ft" in out["opened"]
    # The issue was actually filed on the fake.
    assert any(i["title"] for i in gh.issues)


def test_sync_canary_recovery_closes_issue(capsys):
    from bookieskit.orchestration.workitem import WorkItem, render_body
    body = render_body(WorkItem(
        signature="canary:betika:structure", stream="stream:maintenance",
        title="t", summary="s",
    ))
    gh = _FakeGh(issues=[{
        "number": 1, "title": "t", "body": body,
        "labels": [{"name": "stream:maintenance"}], "state": "open",
    }])
    code = cli.run(
        cli.build_parser().parse_args(["sync-canary", "--json"]),
        runner=_runner_ok, gh=gh,
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert "canary:betika:structure" in out["closed"]


def test_ensure_labels_json_reports_created(capsys):
    gh = _FakeGh()
    gh._labels = ["bug"]  # nothing of ours exists
    code = cli.run(
        cli.build_parser().parse_args(["ensure-labels", "--json"]), gh=gh
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert "stream:maintenance" in out["created"]


def test_queue_list_json_lists_open(capsys):
    from bookieskit.orchestration.workitem import WorkItem, render_body
    body = render_body(WorkItem(
        signature="canary:msport:structure", stream="stream:maintenance",
        title="msport structure drift", summary="s",
    ))
    gh = _FakeGh(issues=[{
        "number": 5, "title": "msport structure drift", "body": body,
        "labels": [{"name": "stream:maintenance"}], "state": "open",
    }])
    code = cli.run(
        cli.build_parser().parse_args(
            ["queue", "list", "--stream", "stream:maintenance", "--json"]
        ),
        gh=gh,
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["items"][0]["number"] == 5
    assert out["items"][0]["signature"] == "canary:msport:structure"


def test_sync_canary_maps_canary_error_to_exit_one(capsys):
    async def _boom(sport, *, seed=None, max_candidates=3, clients=None):
        raise RuntimeError("canary blew up")

    code = cli.run(
        cli.build_parser().parse_args(["sync-canary"]),
        runner=_boom, gh=_FakeGh(),
    )
    assert code == 1
```

- [ ] **Step 2: Run to confirm RED**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bookieskit.orchestration.cli'`.

- [ ] **Step 3: Implement `cli.py` + `__main__.py`**

Create `src/bookieskit/orchestration/cli.py`:

```python
"""argparse CLI for the orchestration work queue.

Three subcommands — sync-canary, ensure-labels, queue list — each
non-interactive, each supporting --json. Exit 0 on successful reconciliation;
non-zero only on an operational gh/canary error. Injected seams (``runner`` for
the canary, ``gh`` for the GhRunner) keep every test offline.
"""

import argparse
import asyncio
import json
import subprocess
from dataclasses import asdict
from typing import Any, Awaitable, Callable

from bookieskit.devtools.canary import CanaryReport, run_canary
from bookieskit.orchestration.gh import GhRunner
from bookieskit.orchestration.labels import ensure_labels
from bookieskit.orchestration.maintenance import sync_canary
from bookieskit.orchestration.queue import Queue
from bookieskit.orchestration.workitem import parse_meta

CanaryRunner = Callable[..., Awaitable[CanaryReport]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bookieskit.orchestration",
        description="Work queue: sync-canary / ensure-labels / queue list.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync-canary")
    p_sync.add_argument("--sport", default="soccer")
    p_sync.add_argument("--json", action="store_true", dest="as_json")

    p_labels = sub.add_parser("ensure-labels")
    p_labels.add_argument("--json", action="store_true", dest="as_json")

    p_queue = sub.add_parser("queue")
    qsub = p_queue.add_subparsers(dest="queue_cmd", required=True)
    p_list = qsub.add_parser("list")
    p_list.add_argument("--stream", default=None)
    p_list.add_argument("--json", action="store_true", dest="as_json")

    return parser


def _emit(obj: Any, as_json: bool, text_lines: list[str]) -> None:
    if as_json:
        print(json.dumps(obj, default=str))
    else:
        print("\n".join(text_lines))


def _sync_canary(args: argparse.Namespace, runner: CanaryRunner,
                 gh: GhRunner) -> int:
    try:
        report = asyncio.run(runner(args.sport))
        result = sync_canary(report, Queue(gh))
    except Exception as exc:  # canary/gh operational failure -> exit 1
        print(f"sync-canary failed: {exc}")
        return 1
    _emit(
        asdict(result),
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


def _ensure_labels(args: argparse.Namespace, gh: GhRunner) -> int:
    created = ensure_labels(gh)
    _emit(
        {"created": created},
        args.as_json,
        [f"ensure-labels created={len(created)}"]
        + [f"  {name}" for name in created],
    )
    return 0


def _queue_list(args: argparse.Namespace, gh: GhRunner) -> int:
    issues = Queue(gh, ensure=False).list_open(stream=args.stream)
    items = [
        {
            "number": i["number"],
            "title": i.get("title", ""),
            "signature": parse_meta(i.get("body", "")).get("signature", ""),
        }
        for i in issues
    ]
    _emit(
        {"items": items},
        args.as_json,
        [f"queue list ({len(items)} open)"]
        + [f"  #{it['number']} [{it['signature']}] {it['title']}"
           for it in items],
    )
    return 0


def run(
    args: argparse.Namespace,
    *,
    runner: CanaryRunner = run_canary,
    gh: GhRunner | None = None,
) -> int:
    if gh is None:
        gh = GhRunner()
    if args.cmd == "sync-canary":
        return _sync_canary(args, runner, gh)
    if args.cmd == "ensure-labels":
        return _ensure_labels(args, gh)
    if args.cmd == "queue" and args.queue_cmd == "list":
        return _queue_list(args, gh)
    raise SystemExit(f"unknown command {args.cmd!r}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except subprocess.CalledProcessError as exc:
        print(f"gh error: {exc.stderr or exc}")
        return 1
```

Create `src/bookieskit/orchestration/__main__.py`:

```python
"""Entrypoint: python -m bookieskit.orchestration <cmd>."""

import sys

from bookieskit.orchestration.cli import main


def _force_utf8_output() -> None:
    """Make stdout/stderr UTF-8 so non-ASCII output doesn't crash on a Windows
    cp1252 console. No-op where unavailable."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


if __name__ == "__main__":
    _force_utf8_output()
    sys.exit(main())
```

- [ ] **Step 4: Run to confirm GREEN**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration/test_cli.py -q`
Expected: `7 passed`.

- [ ] **Step 5: Run the full orchestration suite + smoke-test the entrypoint `--help`**

Run: `.venv/Scripts/python.exe -m pytest tests/orchestration -q`
Expected: all pass, 0 failed (Tasks 1–6: gh, labels, workitem, queue, maintenance, cli).

Run: `.venv/Scripts/python.exe -m bookieskit.orchestration --help`
Expected: usage text whose subcommand list includes `sync-canary`, `ensure-labels`, `queue`; exit 0.

Run: `.venv/Scripts/python.exe -m bookieskit.orchestration sync-canary --help`
Expected: usage text showing `--sport` and `--json`; exit 0.

(Do NOT run a bare `sync-canary` / `ensure-labels` / `queue list` against the real `gh` here: those spawn the `gh` process and reach GitHub. The offline behavior is fully covered by the injected-fake tests; a real run is the owner-verified follow-up below.)

- [ ] **Step 6: Lint the whole tree (final green gate)**

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/orchestration tests/orchestration`
Expected: `All checks passed!`

Run: `.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: full suite green, 0 failed (the new `tests/orchestration/` suite plus the existing devtools suite; no existing test touched).

- [ ] **Step 7: Commit**

```bash
git add src/bookieskit/orchestration/cli.py src/bookieskit/orchestration/__main__.py tests/orchestration/test_cli.py
git commit -m "feat(orchestration): sync-canary/ensure-labels/queue-list CLI (--json + exit codes)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 8: (Deferred — owner-triggered) Verify the live path against the real repo**

Once merged and run from an in-region environment with `gh` authenticated, the owner runs one real `sync-canary` end-to-end and confirms it files a deduped `stream:maintenance` Issue per drift, a re-run *updates* (comments) rather than duplicates, a recovered check *closes* its Issue, and seed-None opens a `canary:seed-discovery` Issue. Do not block plan completion on this step; record it as the post-remote follow-up.

---

## Notes for the executor

- Run commands with the project venv: `.venv/Scripts/python.exe -m <tool>` (Windows). On CI (Ubuntu) the gates use plain `pytest` / `ruff` after `pip install`.
- The orchestration logic reaches the network only through `gh` (a side effect) and `run_canary` (in-region, geo-restricted). Every test injects a fake `GhRunner` and an injected canary `runner` — no `gh` process, no network. Never run a bare `sync-canary` / `ensure-labels` against the real repo during the plan; it would mutate live Issues/labels.
- Karpathy: focused single-responsibility modules (one file per concern), smallest surgical CLI (three subparsers + injected seams), no speculative extension points — no orchestrator loop, no Slack, no scout (5b/5c/5d), and the maintenance stream is the only intake wired in 5a.
- NO new dependencies: the meta block is a hand-rolled flat `key: value` codec (`workitem.py`), NOT PyYAML. `GhRunner` is stdlib `subprocess` + `json`. `httpx` stays the only runtime dep.

## Controller self-review notes (verified against source; address during execution)

- `run_canary` is `async def run_canary(sport="soccer", *, seed=None, max_candidates=3, books=ALL_BOOKS, clients=None) -> CanaryReport` (verified in `src/bookieskit/devtools/canary.py`). The CLI's `sync-canary` branch calls it via `asyncio.run(runner(args.sport))`; the injected test `runner` is an async callable with the same signature (matching the `test_canary.py` `_runner_*` fakes), so `asyncio.run` works for real and fake alike.
- `CanaryReport` / `BookCheck` field names used by `maintenance.py` (`status`, `structure_ok`, `missing_canonicals`, `expected_canonicals`, `platform`, `seed`) are verified against the dataclasses in `canary.py` and the fixtures in `tests/devtools/test_canary.py`.
- `GhRunner._run` mirrors `GitRunner._run` in `devtools/release.py` (`subprocess.run([...], check=True, capture_output=True, text=True)`) but **omits `cwd`** — `gh` infers the repo from the working directory, and the tests monkeypatch `subprocess.run` so no real process spawns. A non-zero `gh` exit raises `CalledProcessError`, surfaced as exit 1 by `main`.
- `gh issue create` prints the new issue URL to stdout; `_ISSUE_NUMBER_RE = re.compile(r"/(\d+)\s*$")` extracts the trailing number. A malformed response (no number) raises `ValueError` rather than returning a wrong number.
- The hand-rolled yaml codec is line-based `key: value` (split on the first `": "`), fenced ` ```yaml ` / ` ``` ` matched with `re.DOTALL` + non-greedy so only the first block is parsed; round-trip is lossless for the string scalars the queue stores. No PyYAML — runtime dep stays `httpx`-only.
- `devtools/cli.py` is the structural template (argparse subparsers, `_emit(asdict(...), args.as_json, [...])`, injected seams, `__main__.py` with UTF-8 forcing). The orchestration CLI is a SEPARATE module (`bookieskit.orchestration.cli` + `__main__`) following the same patterns, NOT an addition to `devtools/cli.py`.

## Spec ambiguities resolved

1. **`SyncResult` shape — the spec lists `opened, updated, closed` but the error-handling section says "the `SyncResult` carries any per-signature errors."** Resolved by adding a fourth field `errors: list[str]` (signature-prefixed messages), keeping the three the spec names. Per-item `gh` failures are isolated into `errors` and do NOT fail the CLI; only an error that aborts the whole reconciliation (e.g. the initial `list_issues`/`ensure_labels`) returns a non-zero exit. This matches the spec's "drift is recorded, not a CLI failure" + "per-operation isolation" rules.
2. **Structure-drift signatures vs. missing signatures — a structure-broken `BookCheck` has `missing_canonicals == list(expected)`.** Resolved: such a check yields BOTH its `canary:<p>:structure` signature AND one `canary:<p>:missing:<c>` per expected canonical (all are real, actionable drifts). The recovery rule (`_possible_signatures` covers structure + every expected missing) closes them together when the book goes `ok`, so there's no orphan. Documented in Task 5's design notes.
3. **Seed-discovery recovery — the spec defines closing on platform recovery but `canary:seed-discovery` has no platform.** Resolved with an explicit rule: close `canary:seed-discovery` when `report.seed is not None` (and it isn't in the current drift set, which it never is when a seed is present). This is the natural recovery condition and is tested.
4. **`queue list` parsing — the spec writes the literal `queue list`.** Resolved as a `queue` subparser with its own `add_subparsers(dest="queue_cmd")` and a `list` action (so `parse_args(["queue", "list"])` works), rather than a single `queue-list` token — staying faithful to the spec's literal command form.
5. **`GhRunner` list-param defaults — the spec's signature shows `labels: list[str] = ()`.** Resolved by typing them as `tuple[str, ...] = ()` (an immutable default; a `[]` default is a ruff/B mutable-default smell). Callers pass tuples (`(item.stream,)`); behavior is identical.
