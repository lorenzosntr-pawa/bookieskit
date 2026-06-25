"""argparse CLI for the orchestration work queue.

Three subcommands — sync-canary, ensure-labels, queue list — each
non-interactive, each supporting --json. Exit 0 on successful reconciliation;
non-zero only on an operational gh/canary error. Injected seams (``runner`` for
the canary, ``gh`` for the GhRunner) keep every test offline.
"""

import argparse
import asyncio
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict
from typing import Any, Awaitable, Callable

from bookieskit.devtools.canary import CanaryReport, run_canary
from bookieskit.orchestration import appauth, chatops, control
from bookieskit.orchestration import notify as notify_fmt
from bookieskit.orchestration import runner as tick_runner
from bookieskit.orchestration import status as status_mod
from bookieskit.orchestration.gh import GhRunner
from bookieskit.orchestration.labels import ensure_labels
from bookieskit.orchestration.maintenance import sync_canary
from bookieskit.orchestration.priority import next_work_item
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

    p_status = sub.add_parser("status")
    ssub = p_status.add_subparsers(dest="status_cmd", required=True)
    p_board = ssub.add_parser("board")
    p_board.add_argument("--config", default=".chatops.json")
    p_board.add_argument(
        "--state-file", default=".orchestrator/status-board.json", dest="state_file"
    )
    p_board.add_argument("--json", action="store_true", dest="as_json")

    p_chatops = sub.add_parser("chatops")
    chsub = p_chatops.add_subparsers(dest="chatops_cmd", required=True)

    p_intake = chsub.add_parser("intake")
    p_intake.add_argument("--author", required=True)
    p_intake.add_argument("--ts", required=True)
    p_intake.add_argument("--title", required=True)
    p_intake.add_argument("--summary", required=True)
    p_intake.add_argument("--json", action="store_true", dest="as_json")

    p_approve = chsub.add_parser("approve")
    p_approve.add_argument("--pr", type=int, required=True)
    p_approve.add_argument("--author", required=True)
    p_approve.add_argument("--config", default=".chatops.json")
    p_approve.add_argument("--json", action="store_true", dest="as_json")

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

    p_cstatus = chsub.add_parser("status")
    p_cstatus.add_argument("--json", action="store_true", dest="as_json")

    p_lock = sub.add_parser("lock")
    lsub = p_lock.add_subparsers(dest="lock_cmd", required=True)
    p_lacq = lsub.add_parser("acquire")
    p_lacq.add_argument("--path", required=True)
    p_lacq.add_argument("--stale-after", type=float, default=7200.0, dest="stale_after")
    p_lacq.add_argument("--json", action="store_true", dest="as_json")
    p_lrel = lsub.add_parser("release")
    p_lrel.add_argument("--path", required=True)
    p_lrel.add_argument("--json", action="store_true", dest="as_json")

    p_gate = sub.add_parser("gate")
    p_gate.add_argument("--config", default=".chatops.json")
    p_gate.add_argument("--watermark", default=".orchestrator/slack-watermark")
    p_gate.add_argument("--json", action="store_true", dest="as_json")

    p_token = sub.add_parser("token")
    p_token.add_argument("--identity", default=".orchestrator/identity.json")
    p_token.add_argument("--key", default=".orchestrator/app.pem")
    p_token.add_argument("--cache", default=".orchestrator/app-token.json")

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

    return parser


def _emit(obj: Any, as_json: bool, text_lines: list[str]) -> None:
    if as_json:
        print(json.dumps(obj, default=str))
    else:
        print("\n".join(text_lines))


def _lock(args: argparse.Namespace) -> int:
    if args.lock_cmd == "acquire":
        ok = tick_runner.acquire_lock(
            args.path, stale_after_s=args.stale_after,
            now=time.time(), pid=os.getpid(),
        )
        _emit({"acquired": ok}, args.as_json,
              ["acquired" if ok else "busy"])
        return 0 if ok else 3
    tick_runner.release_lock(args.path)
    _emit({"released": True}, args.as_json, ["released"])
    return 0


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


def _sync_canary(args: argparse.Namespace, runner: CanaryRunner,
                 gh: GhRunner) -> int:
    try:
        report = asyncio.run(runner(args.sport))
        result = sync_canary(report, Queue(gh))
    except Exception as exc:  # canary/gh operational failure -> exit 1
        print(f"sync-canary failed: {exc}")
        return 1
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


def _chatops_intake(args: argparse.Namespace, gh: GhRunner) -> int:
    signature = chatops.ticket_signature(args.ts)
    queue = Queue(gh)
    existing = queue.find_any_by_signature(signature)  # open OR closed
    if existing is not None:
        number = existing["number"]
        _emit(
            {"status": "duplicate", "number": number, "slack_text": ""},
            args.as_json,
            [f"duplicate #{number}"],
        )
        return 0
    item = chatops.build_ticket(args.author, args.ts, args.title, args.summary)
    # File directed tickets as status:designing so they are NOT buildable until
    # the owner's `design ok` — the buildability gate is enforced here in code,
    # not by a follow-up prose step.
    number, _ = queue.open_or_update(
        item, note="(filed from Slack #tickets)",
        extra_labels=("status:designing",),
    )
    _emit(
        {
            "status": "opened",
            "number": number,
            "slack_text": chatops.queued(number, args.title),
        },
        args.as_json,
        [f"opened #{number}", chatops.queued(number, args.title)],
    )
    return 0


def _chatops_reject(args: argparse.Namespace, reason: str) -> int:
    _emit(
        {"status": "rejected", "pr": args.pr, "reason": reason,
         "slack_text": chatops.rejected(args.pr, reason)},
        args.as_json,
        [f"rejected PR #{args.pr}: {reason}"],
    )
    return 0  # a rejection is a normal handled outcome, not an error


def _chatops_approve(args: argparse.Namespace, gh: GhRunner) -> int:
    config = chatops.load_config(args.config)
    approvers = tuple(config.get("approvers", []))
    if not chatops.is_authorized(args.author, approvers):
        return _chatops_reject(args, "not authorized")
    view = gh.pr_view(args.pr)
    if view.get("state") != "OPEN":
        return _chatops_reject(args, "PR is not open")
    if not chatops.checks_pass(view.get("statusCheckRollup") or []):
        return _chatops_reject(args, "CI not green")
    closes = chatops.closing_issue_numbers(view)
    in_review = {
        i["number"]
        for i in gh.list_issues(state="open", labels=("status:in-review",))
    }
    matched = next((n for n in closes if n in in_review), None)
    if matched is None:
        return _chatops_reject(args, "not a loop PR")
    gh.merge_pr(args.pr, method="squash")
    _emit(
        {"status": "merged", "pr": args.pr, "issue": matched,
         "slack_text": chatops.merged(args.pr, matched)},
        args.as_json,
        [f"merged PR #{args.pr} (closes #{matched})"],
    )
    return 0


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


def _chatops_design_ok(args: argparse.Namespace, gh: GhRunner) -> int:
    approvers = tuple(chatops.load_config(args.config).get("approvers", []))
    if not chatops.is_authorized(args.author, approvers):
        slack_text = chatops.rejected(
            args.issue, "not authorized to approve a design"
        )
        _emit({"status": "rejected", "reason": "not authorized",
               "slack_text": slack_text},
              args.as_json, [f"rejected design-ok #{args.issue}"])
        return 0
    gh.edit_issue(
        args.issue,
        add_labels=["status:ready"],
        remove_labels=["status:designing"],
    )
    gh.comment_issue(args.issue, f"Design approved by {args.author} -> status:ready.")
    _emit(
        {"status": "ready", "issue": args.issue,
         "slack_text": chatops.design_ready(args.issue)},
        args.as_json, [f"design-ok #{args.issue} -> ready"],
    )
    return 0


def _chatops_design_no(args: argparse.Namespace, gh: GhRunner) -> int:
    approvers = tuple(chatops.load_config(args.config).get("approvers", []))
    if not chatops.is_authorized(args.author, approvers):
        _emit({"status": "rejected", "reason": "not authorized",
               "slack_text": chatops.rejected(args.issue, "not authorized")},
              args.as_json, [f"rejected design-no #{args.issue}"])
        return 0
    gh.comment_issue(
        args.issue, f"Design change requested by {args.author}: {args.notes}"
    )
    _emit({"status": "changes", "issue": args.issue,
           "slack_text": chatops.design_changes_ack(args.issue)},
          args.as_json, [f"design-no #{args.issue}: {args.notes}"])
    return 0


def _chatops_council(args: argparse.Namespace, gh: GhRunner) -> int:
    approvers = tuple(chatops.load_config(args.config).get("approvers", []))
    if not chatops.is_authorized(args.author, approvers):
        _emit({"status": "rejected", "reason": "not authorized",
               "slack_text": chatops.rejected(args.issue, "not authorized")},
              args.as_json, [f"rejected council #{args.issue}"])
        return 0
    gh.comment_issue(args.issue, f"llm-council pass requested by {args.author}.")
    _emit({"status": "council-requested", "issue": args.issue}, args.as_json,
          [f"council requested #{args.issue}"])
    return 0


def _status_board(args: argparse.Namespace, gh: GhRunner) -> int:
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
        now = datetime.datetime.now().strftime("%H:%M")
        text = status_mod.render_board(st, now=now)
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
                r = _slack_post(
                    "chat.postMessage", token=token, channel=channel, text=text
                )
        else:
            r = _slack_post("chat.postMessage", token=token, channel=channel, text=text)
        if r.get("ok") and r.get("ts"):
            os.makedirs(os.path.dirname(args.state_file) or ".", exist_ok=True)
            with open(args.state_file, "w", encoding="utf-8") as f:
                json.dump({"channel": r.get("channel", channel), "ts": r["ts"]}, f)
        _emit({"posted": bool(r.get("ok"))}, args.as_json, ["status board updated"])
    except Exception as exc:  # best-effort: never break the tick
        _emit(
            {"posted": False, "error": str(exc)},
            args.as_json,
            [f"status board error: {exc}"],
        )
    return 0


def _chatops_status(args: argparse.Namespace, gh: GhRunner) -> int:
    now = datetime.datetime.now().strftime("%H:%M")
    st = status_mod.gather_state(gh, paused=control.is_paused(gh))
    text = status_mod.render_board(st, now=now)
    _emit({"slack_text": text}, args.as_json, [text])
    return 0


def _slack_get(method: str, *, token: str, **params) -> dict:
    url = "https://slack.com/api/" + method + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def _slack_post(method: str, *, token: str, **params) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        "https://slack.com/api/" + method, data=data,
        headers={"Authorization": "Bearer " + token},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def _read_token() -> str | None:
    try:
        with open(".mcp.json", encoding="utf-8") as handle:
            data = json.load(handle)
        return data["mcpServers"]["slack"]["env"]["SLACK_MCP_XOXB_TOKEN"]
    except (OSError, KeyError, ValueError):
        return None


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


def _gate(args: argparse.Namespace, gh: GhRunner) -> int:
    from bookieskit.orchestration import gate
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
            hist = _slack_get(
                "conversations.history", token=token, channel=channel, limit=20
            )
            humans = [m for m in hist.get("messages", [])
                      if m.get("type") == "message" and not m.get("bot_id")]
            newest_ts = humans[0]["ts"] if humans else None  # history is newest-first
            wm = None
            try:
                with open(args.watermark, encoding="utf-8") as handle:
                    wm = handle.read().strip() or None
            except OSError:
                wm = None
            new_ticket = gate.new_ticket_waiting(newest_ts, wm)
            # designing items: any thread whose last message is human?
            for issue in Queue(gh, ensure=False).list_open(stream="stream:directed"):
                labels = {lb["name"] for lb in issue.get("labels", [])}
                if "status:designing" not in labels:
                    continue
                thread_ts = parse_meta(issue.get("body", "")).get("slack_ts")
                if not thread_ts:
                    continue
                rep = _slack_get(
                    "conversations.replies", token=token, channel=channel, ts=thread_ts
                )
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


def run(
    args: argparse.Namespace,
    *,
    runner: CanaryRunner = run_canary,
    gh: GhRunner | None = None,
) -> int:
    if args.cmd == "notify":
        return _notify(args)
    if args.cmd == "lock":
        return _lock(args)
    if args.cmd == "token":
        return _token(args)
    if gh is None:
        gh = GhRunner()
    if args.cmd == "gate":
        return _gate(args, gh)
    if args.cmd == "status":
        return _status_board(args, gh)
    if args.cmd == "sync-canary":
        return _sync_canary(args, runner, gh)
    if args.cmd == "ensure-labels":
        return _ensure_labels(args, gh)
    if args.cmd == "queue" and args.queue_cmd == "list":
        return _queue_list(args, gh)
    if args.cmd == "next":
        return _next(args, gh)
    if args.cmd == "claim":
        return _claim(args, gh)
    if args.cmd == "mark-in-review":
        return _mark_in_review(args, gh)
    if args.cmd == "mark-blocked":
        return _mark_blocked(args, gh)
    if args.cmd == "chatops" and args.chatops_cmd == "intake":
        return _chatops_intake(args, gh)
    if args.cmd == "chatops" and args.chatops_cmd == "approve":
        return _chatops_approve(args, gh)
    if args.cmd == "chatops" and args.chatops_cmd == "pause":
        return _chatops_pause(args, gh)
    if args.cmd == "chatops" and args.chatops_cmd == "resume":
        return _chatops_resume(args, gh)
    if args.cmd == "chatops" and args.chatops_cmd == "paused":
        return _chatops_paused(args, gh)
    if args.cmd == "chatops" and args.chatops_cmd == "design-ok":
        return _chatops_design_ok(args, gh)
    if args.cmd == "chatops" and args.chatops_cmd == "design-no":
        return _chatops_design_no(args, gh)
    if args.cmd == "chatops" and args.chatops_cmd == "council":
        return _chatops_council(args, gh)
    if args.cmd == "chatops" and args.chatops_cmd == "status":
        return _chatops_status(args, gh)
    raise SystemExit(f"unknown command {args.cmd!r}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except subprocess.CalledProcessError as exc:
        print(f"gh error: {exc.stderr or exc}")
        return 1
