"""argparse CLI for the market-add harness.

Four subcommands — resolve, discover, capture, verify — each non-interactive,
each supporting --json (serialized dataclasses). Exit code 0 when the seed
resolved on >=1 book, 1 when resolution failed entirely.
"""

import argparse
import asyncio
import json
from dataclasses import asdict
from typing import Any, Awaitable, Callable

from bookieskit.devtools.adapters import ADAPTERS
from bookieskit.devtools.fixtures import capture as capture_fixture
from bookieskit.devtools.resolver import ALL_BOOKS, resolve_event
from bookieskit.devtools.search import discover, unmapped
from bookieskit.devtools.types import ResolvedEvent
from bookieskit.devtools.verify import verify as verify_payload

Resolver = Callable[..., Awaitable[ResolvedEvent]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bookieskit.devtools",
        description="Market-add harness: resolve/discover/capture/verify.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument("seed", help="SR id (sr:match:N or N) or BetPawa id")
        p.add_argument("--sport", default="soccer")
        p.add_argument("--book", default=None, help="CSV of books (default all)")
        p.add_argument("--json", action="store_true", dest="as_json")
        p.add_argument("--live", action="store_true")
        p.add_argument("--betpawa-seed", action="store_true", dest="betpawa_seed")
        p.add_argument("--sportpesa-cookie", default=None, dest="sportpesa_cookie")
        p.add_argument("--betika-cookie", default=None, dest="betika_cookie")

    p_resolve = sub.add_parser("resolve")
    _common(p_resolve)

    p_discover = sub.add_parser("discover")
    _common(p_discover)
    mode = p_discover.add_mutually_exclusive_group(required=True)
    mode.add_argument("--term", default=None)
    mode.add_argument("--unmapped", action="store_true")

    p_capture = sub.add_parser("capture")
    _common(p_capture)
    p_capture.add_argument("--name", required=True)

    p_verify = sub.add_parser("verify")
    _common(p_verify)
    p_verify.add_argument(
        "--canonical", default=None, help="CSV of canonical_ids to require"
    )

    return parser


def _books_arg(args: argparse.Namespace) -> tuple[str, ...]:
    if args.book:
        return tuple(b.strip() for b in args.book.split(",") if b.strip())
    return ALL_BOOKS


def _emit(obj: Any, as_json: bool, text_lines: list[str]) -> None:
    if as_json:
        print(json.dumps(obj, default=str))
    else:
        print("\n".join(text_lines))


async def _fetch_raw(
    book: str,
    handle: Any,
    args: argparse.Namespace,
    clients: dict[str, Any] | None,
) -> dict:
    """Fetch raw markets for one resolved book via its adapter."""
    adapter = ADAPTERS[book]
    injected = (clients or {}).get(book)
    if injected is not None:
        return await adapter.fetch_raw_markets(injected, handle, live=args.live)
    # Lazy import of client classes to keep module import cheap/offline.
    from bookieskit.devtools.resolver import _CLIENT_CLASSES, _COUNTRY

    cookie = None
    if book == "sportpesa":
        cookie = args.sportpesa_cookie
    elif book == "betika":
        cookie = args.betika_cookie
    kwargs: dict[str, Any] = {"country": _COUNTRY[book]}
    if cookie is not None:
        kwargs["cookie"] = cookie
    async with _CLIENT_CLASSES[book](**kwargs) as client:
        return await adapter.fetch_raw_markets(client, handle, live=args.live)


async def run(
    args: argparse.Namespace,
    *,
    resolver: Resolver = resolve_event,
    clients: dict[str, Any] | None = None,
) -> int:
    books = _books_arg(args)
    ev = await resolver(
        args.seed,
        args.sport,
        books,
        live=args.live,
        betpawa_seed=args.betpawa_seed,
        sportpesa_cookie=args.sportpesa_cookie,
        betika_cookie=args.betika_cookie,
        clients=clients,
    )
    exit_code = 0 if ev.handles else 1

    if args.cmd == "resolve":
        _emit(
            asdict(ev),
            args.as_json,
            [f"seed={ev.seed} sr={ev.sr_numeric} {ev.home} vs {ev.away}"]
            + [f"  {b}: {h.event_id}" for b, h in ev.handles.items()]
            + [f"  SKIP {b}: {r}" for b, r in ev.skipped.items()],
        )
        return exit_code

    # discover / capture / verify all fetch raw markets per resolved book.
    per_book: dict[str, Any] = {}
    for book, handle in ev.handles.items():
        try:
            raw = await _fetch_raw(book, handle, args, clients)
        except Exception as exc:  # per-book isolation
            ev.skipped[book] = f"fetch error: {exc!r}"
            continue
        if args.cmd == "discover":
            if args.unmapped:
                cands = unmapped(raw, book, args.sport)
            else:
                cands = discover(raw, book, args.term)
            per_book[book] = [asdict(c) for c in cands]
        elif args.cmd == "capture":
            path = capture_fixture(raw, book, args.name)
            per_book[book] = str(path)
        elif args.cmd == "verify":
            canon = (
                [c.strip() for c in args.canonical.split(",") if c.strip()]
                if args.canonical else None
            )
            per_book[book] = asdict(
                verify_payload(raw, book, args.sport, canonical_ids=canon)
            )

    exit_code = 0 if per_book else 1
    payload = {
        "seed": ev.seed,
        "sport": ev.sport,
        "sr_numeric": ev.sr_numeric,
        "results": per_book,
        "skipped": ev.skipped,
    }
    _emit(
        payload,
        args.as_json,
        [f"{args.cmd} seed={ev.seed} sr={ev.sr_numeric}"]
        + [f"  {b}: {v}" for b, v in per_book.items()]
        + [f"  SKIP {b}: {r}" for b, r in ev.skipped.items()],
    )
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(run(args))
