# Slice B — Respond to questions & change-requests on open PRs

**Date:** 2026-06-25
**Status:** design — approved in brainstorming, pending spec review
**Stream:** capability (loop UX gap)

## Problem

The loop converses with the owner only on `status:designing` Issues (the gate
wakes on a design thread whose newest message is human). Once work becomes a PR
(`status:in-review`), the loop stops listening: an owner question or change
request **on the open PR goes unanswered** — the gap hit live on #19, where the
owner asked "I see some missing bookmakers… why, and how do we take it all?" on
the PR and nothing responded.

## Goal

When the owner comments on an open loop PR, the loop wakes and **responds**:
answers questions, and for change requests actually **makes the change** (push a
commit to the PR branch, re-run tests) and replies — all without merging.

## Decisions (from brainstorming)

- **Channel: the GitHub PR** (review comments + review bodies). The natural
  code-review surface and where #19's question lived.
- **Scope: answer + implement.** Questions → a reply comment. Change requests →
  edit on the PR branch via the subagent/TDD pipeline, push **as the App**,
  re-test, reply with the commit + CI.
- **Preempt:** an owner waiting on an open PR outranks starting new queue work —
  the cycle handles a PR-reply *before* picking a fresh queue item.
- **v1 surface:** PR **conversation comments + review bodies**. Inline diff-line
  comments are a documented fast-follow.

## Detection — stateless, mirrors the design-thread mechanism

The gate already treats a `status:designing` thread as "owes a reply" when its
**newest message is human (no `bot_id`)**. The PR analog:

1. List open PRs and their `closingIssuesReferences` (one `gh pr list` call).
2. Keep PRs whose closing Issue is `status:in-review` (a loop PR).
3. For each, fetch **conversation comments** (`issues/{n}/comments`) + **reviews**
   (`pulls/{n}/reviews`). Build a timeline of "human-actionable events":
   - every conversation comment;
   - every review whose `state == "CHANGES_REQUESTED"` **or** whose body is
     non-empty (an `APPROVED`/`COMMENTED` review with an empty body is **not**
     actionable — a bare approval must not trigger a reply).
4. If the **newest** such event was authored by a non-bot user
   (`user.type != "Bot"`), the loop owes a response → `pr_reply_waiting` true.

No watermark file: the App's own reply comment is the newest event afterward
(authored by the App ⇒ `type == "Bot"`), which flips the state off — exactly how
the design threads self-resolve.

## Architecture

```
gate (cheap, every tick)                 responder (one cycle, preempts queue)
─────────────────────────                ───────────────────────────────────────
open PRs whose closing issue             pr-review pending --json -> {pr, issue,
 is status:in-review                       comments[], reviews[]}  (highest pri)
   └ fetch comments + reviews                       │
   └ pr_reply_waiting(...) ──► wake ──► cycle reads the thread, per human comment:
                                          • question      -> gh pr comment (answer)
                                          • change request -> checkout PR branch,
                                              edit (subagent/TDD), push as App,
                                              re-test, gh pr comment (summary)
                                          ends with a consolidated reply
                                          (newest event now the App's -> resolved)
```

## Components

### `src/bookieskit/orchestration/gate.py`

Add a pure predicate alongside `thread_reply_waiting`:

- `pr_reply_waiting(comments: list[dict], reviews: list[dict]) -> bool` —
  builds the actionable timeline per the rule above (all comments; reviews where
  `state == "CHANGES_REQUESTED"` or `body` is non-empty), sorts by timestamp
  (`created_at` for comments, `submitted_at` for reviews), and returns
  `True` iff the newest event's `user.type != "Bot"`. Empty timeline → `False`.

`should_run` gains a `pr_reply: bool` parameter (OR-ed in).

### `src/bookieskit/orchestration/gh.py`

- `list_open_prs() -> list[dict]` — `gh pr list --state open --json
  number,closingIssuesReferences,headRefName`.
- `pr_comments(pr: int) -> list[dict]` — `gh api repos/:owner/:repo/issues/{pr}/comments`
  (PR conversation comments are issue comments).
- `pr_reviews(pr: int) -> list[dict]` — `gh api repos/:owner/:repo/pulls/{pr}/reviews`.
- `comment_pr(pr: int, body: str) -> None` — `gh pr comment {pr} --body <body>`.

(These use the ambient identity = the App when run inside a cycle, consistent
with slice A. No token threading needed — commenting/pushing as the App is fine;
only merge is gated.)

### `src/bookieskit/orchestration/cli.py`

- Extend `_gate`: after the designing-thread loop, iterate `list_open_prs()`,
  map closing issues to the set of `status:in-review` numbers, and for each
  matching PR call `pr_comments`/`pr_reviews` → `gate.pr_reply_waiting`. Set
  `pr_reply` and remember the first PR number that owes a reply. Fold `pr_reply`
  into `should_run`; add `"pr-reply"` to the reason ladder; include
  `pr_awaiting` (the PR number, or null) in the JSON. Degrade silently to the
  existing signals if gh/Slack calls fail.
- New subcommand `pr-review pending [--json]` — returns the highest-priority PR
  that owes a reply as `{pr, issue, head, comments, reviews}` (or `null`). The
  orchestrate cycle calls this, reads the thread, acts, and replies. "Highest
  priority" = lowest PR number (oldest) for determinism.

### `.claude/skills/orchestrate/SKILL.md`

Add a **Step 0: PR review-response** before the queue pick:

> Run `pr-review pending --json`. If non-null, this cycle answers it instead of
> picking new queue work (an owner waiting on a PR preempts new work):
> read the comments/reviews; for each unaddressed human comment, if it is a
> question post an answer with `gh pr comment`; if it requests a change, check
> out `head`, make the change (subagent-driven / TDD), push (as the App — never
> merge), let CI re-run, and `gh pr comment` a summary. Finish with one
> consolidated reply so the newest event is the loop's. Then STOP (one item per
> cycle). Best-effort post `pr-reply` note to `#agent-activity`.

The hard rules are unchanged: one item per cycle, **never merge**, surface
assumptions.

### Slack (best-effort)

A `notify`-style line is optional; v1 can post a plain `#agent-activity` note
("responded to your comment on PR #N") only if the Slack MCP is available —
never on the critical path.

## Testing

Pure-logic unit tests (offline) carry the weight:

- `pr_reply_waiting`:
  - newest event is a human comment → `True`.
  - newest event is a bot (App) comment → `False`.
  - newest is a human `CHANGES_REQUESTED` review (empty body) → `True`.
  - an `APPROVED` review with empty body is ignored (a lone bare approval →
    `False`).
  - human comment older than a later bot reply → `False`.
  - empty comments+reviews → `False`.
  - comments and reviews interleaved by timestamp → newest wins regardless of
    which list it came from.
- `should_run` includes `pr_reply`.
- `gh.py` argv tests (extend `_RecordingRun`): `list_open_prs` requests the right
  `--json` fields; `pr_comments`/`pr_reviews` hit the right `gh api` paths;
  `comment_pr` builds `gh pr comment <pr> --body <body>`.
- `cli.py` `_gate`: with a fake gh returning an in-review Issue + an open PR
  closing it whose newest comment is human, `gate --json` reports
  `run=true, reason="pr-reply", pr_awaiting=<n>`; with the newest comment a bot,
  `pr_awaiting=null` and the reason falls through. `pr-review pending --json`
  returns the expected `{pr, issue, ...}` (and `null` when none).

## Out of scope / fast-follow

- Inline diff-line review comments (`pulls/{n}/comments`) — v1 reads conversation
  comments + review bodies; add inline support next if owner reviews inline.
- Auto-detecting "this comment is just chit-chat" — v1 lets the cycle's agent
  judge per comment (a thank-you needs no code change, just a brief ack or none).

## Files

- Modify: `src/bookieskit/orchestration/gate.py`
- Modify: `src/bookieskit/orchestration/gh.py`
- Modify: `src/bookieskit/orchestration/cli.py`
- Modify: `tests/orchestration/test_gate.py`, `test_gh.py`, `test_cli.py`
- Modify: `.claude/skills/orchestrate/SKILL.md`
- Modify: `CHANGELOG.md` (`[Unreleased]` — loop UX)
