# Orchestration 5a — Work Queue + Maintenance Stream — Design

**Date:** 2026-06-23
**Status:** Approved (pending written-spec review)
**Sub-project:** 5a of the orchestration capstone (sub-project 5 of the project-workflow track). Umbrella: `2026-06-22-agent-company-north-star.md`. The capstone decomposes into: **5a** work queue + maintenance stream (this), 5b orchestrator + autonomous execution, 5c Slack cockpit, 5d scout.

## Problem

The four loop pieces exist (CI, harness, canary, release) but nothing **converges them into a durable work queue** or turns the canary's *signal* into a *work item*. The agent company needs a queue it can read/write, and a first intake stream feeding it. 5a builds that foundation: GitHub Issues as the durable queue, and the **maintenance stream** (canary drift → Issue). No autonomous agents and no Slack yet — those are 5b/5c.

## Goals

- A durable, queryable **work queue on GitHub Issues** with a stream/status taxonomy that both humans and agents can route on.
- The **maintenance stream**: run the canary in-region → reconcile drift into deduped, labeled Issues (open on drift, update on persistence, close on recovery).
- **Agent-runnable**: `--json`, non-interactive, meaningful exit codes; all logic offline-testable behind an injectable `gh` runner.
- Establish the taxonomy the other streams (expansion/directed/capability) and 5b/5c/5d plug into.

## Non-goals

- The orchestrator loop / autonomous agent execution (5b) — 5a delivers the `sync-canary` *command*; *scheduling* it is 5b.
- Slack (5c), the scout/expansion stream (5d), the capability-review *task* (5b) — but 5a establishes the `stream:capability` label so the skill-growth stream has a home.
- A GitHub Actions schedule for `sync-canary` — it runs the canary, which is geo-restricted to in-region networks (see the canary spec's "Run environment"); it runs in-region, scheduled by 5b.

## Cross-cutting standards (carried from the north-star)

This subpackage is part of the agent company and inherits the standing operating standards: agents use the superpowers discipline (brainstorm → plan → subagent-driven → systematic-debugging → verification → review) plus **graphify** (structural memory), **llm-council** (stakes/tradeoff decisions), **Karpathy principles** (all code, reviewer-enforced), and **continuous capability review**. 5a's contribution to skill-growth is establishing the `stream:capability` label; the discovery task and the operating-contract enforcement live in 5b.

## Decisions

| Decision | Choice |
|---|---|
| Location | New `src/bookieskit/orchestration/` subpackage; `python -m bookieskit.orchestration` |
| Work-item representation | Stream/status **labels** + a fenced ` ```yaml ` **meta block** (signature, stream, …) + human prose |
| Dedup | Stable **signature** per `(platform, drift-kind)`, stored in the issue meta; re-runs reconcile by signature |
| Labels | Idempotent `ensure_labels` (auto-created on first queue use) |
| `gh` access | Injectable `GhRunner` (subprocess wrapper); faked in tests |
| `sync-canary` exit code | 0 on successful reconciliation (drift is *recorded*, not a CLI failure); non-zero only on operational error |

## Architecture

New subpackage `src/bookieskit/orchestration/`:

### `gh.py` — `GhRunner`

Thin injectable wrapper over the `gh` subprocess calls the queue needs. Every method runs `gh` with `check=True` (non-zero exit raises `CalledProcessError`). Tests inject a fake.

```python
class GhRunner:
    def list_issues(self, *, labels: list[str] = (), state: str = "open") -> list[dict]: ...
        # gh issue list --json number,title,body,labels,state --state <state> [--label ...]
    def create_issue(self, *, title: str, body: str, labels: list[str]) -> int: ...
        # gh issue create --title --body --label ... ; returns the new issue number
    def comment_issue(self, number: int, body: str) -> None: ...
    def edit_issue(self, number: int, *, body: str | None = None,
                   add_labels: list[str] = (), remove_labels: list[str] = ()) -> None: ...
    def close_issue(self, number: int, *, comment: str | None = None) -> None: ...
    def list_labels(self) -> list[str]: ...          # gh label list --json name
    def create_label(self, name: str, *, color: str, description: str) -> None: ...
```

### `labels.py` — taxonomy + idempotent ensure

```python
STREAM_LABELS = {
    "stream:maintenance": ("d73a4a", "Canary drift / keep-it-working"),
    "stream:expansion":   ("0e8a16", "Scout: new sport/market/bookmaker"),
    "stream:directed":    ("1d76db", "Owner-requested work"),
    "stream:capability":  ("5319e7", "Adopt a new skill / MCP"),
}
STATUS_LABELS = {
    "status:claimed":   ("fbca04", "An agent is working this"),
    "status:in-review": ("0052cc", "PR open, awaiting review"),
}

def ensure_labels(gh: GhRunner) -> list[str]:
    """Create any missing stream:*/status:* labels. Idempotent. Returns created."""
```

(open/closed are native issue state; `status:claimed`/`status:in-review` and assignee + linked PR carry the in-flight states.)

### `workitem.py` — model + body format

```python
@dataclass
class WorkItem:
    signature: str           # stable dedup key, e.g. "canary:betika:structure"
    stream: str              # a stream label value, e.g. "stream:maintenance"
    title: str               # human title (no signature prefix needed)
    summary: str             # human-readable prose body
    meta: dict[str, Any] = field(default_factory=dict)  # extra structured fields

def render_body(item: WorkItem) -> str:
    """Body = a fenced ```yaml meta block (signature, stream, + meta) then the
    summary prose. The yaml block is the machine-readable contract."""

def parse_meta(body: str) -> dict[str, Any]:
    """Extract the yaml meta block from an issue body. {} if absent/malformed."""
```

The yaml block is rendered/parsed with a tiny hand-rolled serializer for the flat string→scalar fields we use (no PyYAML dependency — runtime dep stays `httpx`-only). `signature` and `stream` are always present.

### `queue.py` — `Queue`

```python
class Queue:
    def __init__(self, gh: GhRunner, *, ensure: bool = True): ...   # ensure_labels on first use
    def find_open_by_signature(self, signature: str) -> dict | None: ...
        # list open issues, parse_meta, match signature
    def open_or_update(self, item: WorkItem, *, note: str) -> tuple[int, str]: ...
        # existing -> comment(note), return (n, "updated"); else create, return (n, "opened")
    def close_by_signature(self, signature: str, *, reason: str) -> int | None: ...
        # find open -> close_issue(comment=reason); return number or None
    def list_open(self, *, stream: str | None = None) -> list[dict]: ...
```

### `maintenance.py` — canary → Issue bridge

```python
def canary_signatures(report: CanaryReport) -> list[tuple[str, str]]:
    """(signature, human title) for each drift in the report. Drift kinds:
       canary:<platform>:structure ; canary:<platform>:missing:<canonical> ;
       and canary:seed-discovery when report.seed is None."""

def sync_canary(report: CanaryReport, queue: Queue) -> SyncResult:
    """Reconcile a CanaryReport into the maintenance stream:
       - each current drift -> queue.open_or_update(... stream='stream:maintenance')
       - an open canary maintenance issue whose platform is OK this run AND whose
         signature is not in the current drift set -> close_by_signature (recovered)
       - platforms that were skipped/unreachable this run are left untouched
         (recovery can't be confirmed). Returns SyncResult(opened, updated, closed)."""

@dataclass
class SyncResult:
    opened: list[str]; updated: list[str]; closed: list[str]   # signatures
```

Recovery rule (precise): an open issue with signature `canary:<p>:<...>` is closed only when this run has a `BookCheck` for `<p>` with `status == "ok"` and that signature is absent from the current drift set. Skipped/unreachable platforms never trigger a close.

### `cli.py` + `__main__.py`

`python -m bookieskit.orchestration <cmd>`:
- `sync-canary [--sport soccer] [--json]` — run the canary in-region (reuse `run_canary`), `sync_canary` the report into the queue, print/`--json` the `SyncResult`. Exit 0 on successful reconciliation; non-zero on a `gh`/canary operational error. Injection seams (`runner=run_canary`, `gh=`) keep it offline-testable.
- `ensure-labels [--json]` — idempotent label setup (also auto-run by `Queue`).
- `queue list [--stream <s>] [--json]` — list open work items.

## Error handling

- **Per-operation isolation in `sync_canary`**: a `gh` failure on one issue is recorded and the reconciliation continues for the others (mirrors the resolver/canary pattern); the `SyncResult` carries any per-signature errors.
- **`gh` not authenticated / network**: surfaces as a `CalledProcessError` from `GhRunner` → non-zero CLI exit with the `gh` stderr. (`gh` Issue calls are not geo-restricted.)
- **Malformed issue body** (missing/garbled meta): `parse_meta` returns `{}`; such an issue simply doesn't match any signature (treated as not-ours) rather than crashing.

## Testing approach

Offline unit tests under `tests/orchestration/` (a new test dir; add `tests/orchestration/__init__.py`), all behind an injected fake `GhRunner` — no `gh` process, no network:
- `labels`: `ensure_labels` creates only the missing labels (idempotent on a fake whose `list_labels` already has some).
- `workitem`: `render_body`/`parse_meta` round-trip; `parse_meta` returns `{}` on a body with no yaml block.
- `queue`: `find_open_by_signature` matches via parsed meta; `open_or_update` creates when absent / comments when present; `close_by_signature`.
- `maintenance`: `canary_signatures` for structure-drift, missing-core-drift, and seed-None; `sync_canary` against mocked `CanaryReport`s (drift → opened; same drift again → updated; recovered ok → closed; skipped/unreachable → untouched) with a fake queue.
- `cli`: `sync-canary --json` with injected `runner` (returns a canned `CanaryReport`) + fake `gh` → expected `SyncResult` + exit code; `ensure-labels`; `queue list`.
- No live network in any test. A real `sync-canary` against the live repo + in-region canary is an owner-verified follow-up.

## Success criteria

- `ensure-labels` creates the 4 stream + 2 status labels idempotently (re-run is a no-op).
- `sync-canary` (injected report + fake gh): opens a deduped `stream:maintenance` Issue per drift; a re-run with the same drift **updates** (comments) rather than duplicates; a recovered check **closes** its Issue; seed-None opens a `canary:seed-discovery` Issue.
- New `tests/orchestration/` suite passes; full suite + `ruff check .` green in CI.
- Owner-verified once (deferred): a real in-region `sync-canary` files/updates/closes real Issues against the repo.

## Reuse hooks for 5b/5c/5d

- **5b orchestrator**: `Queue.list_open()` is how it picks work; it labels `status:claimed`/`status:in-review` and links PRs via the same `GhRunner`. The capability-review task files `stream:capability` items through `Queue`.
- **5c Slack cockpit**: mirrors `Queue` state to channels; tickets typed in Slack become `stream:directed` `WorkItem`s via `Queue`.
- **5d scout**: files `stream:expansion` `WorkItem`s (new sport/market/bookmaker) via `Queue`, reusing the harness adapters for discovery.
