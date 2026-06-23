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
    if args.cmd == "next":
        return _next(args, gh)
    if args.cmd == "claim":
        return _claim(args, gh)
    if args.cmd == "mark-in-review":
        return _mark_in_review(args, gh)
    if args.cmd == "mark-blocked":
        return _mark_blocked(args, gh)
    raise SystemExit(f"unknown command {args.cmd!r}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except subprocess.CalledProcessError as exc:
        print(f"gh error: {exc.stderr or exc}")
        return 1
