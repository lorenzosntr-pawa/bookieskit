"""Capture raw event payloads from each book as test fixtures.

Writes tests/fixtures/event_info/<book>/<name>.json using the same fetch call
each client's ``get_markets`` parses. Run from an in-region network (books
geo-block US/cloud IPs).

Usage:
    python -X utf8 scripts/capture_fixtures.py --name my_event \
        --betpawa 123 --sportybet sr:match:1 [--sport soccer] [--country ng]
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
from pathlib import Path
from typing import Any

from bookieskit import (
    Bet9ja,
    Betika,
    BetPawa,
    Betway,
    ElephantBet,
    MSport,
    SportPesa,
    SportyBet,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "event_info"

CLIENTS: dict[str, type] = {
    cls.PLATFORM_KEY: cls
    for cls in (
        BetPawa,
        SportyBet,
        Bet9ja,
        Betway,
        MSport,
        SportPesa,
        Betika,
        ElephantBet,
    )
}

# The call each client's get_markets parses.
FETCH_METHOD: dict[str, str] = {
    book: "get_event_detail" for book in CLIENTS
} | {
    "betika": "get_event_markets",
    "betway": "get_event_markets_all",
    "sportpesa": "get_event_markets",
}


async def capture(
    clients: dict[str, Any],
    ids: dict[str, str],
    name: str,
    out_dir: Path,
) -> dict[str, str]:
    """Fetch and write ``out_dir/<book>/<name>.json`` for every book with an id."""
    results: dict[str, str] = {}
    for book, event_id in ids.items():
        if not event_id or book not in clients:
            continue
        try:
            payload = await getattr(clients[book], FETCH_METHOD[book])(
                event_id=event_id
            )
            path = out_dir / book / f"{name}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, indent=1, ensure_ascii=False),
                encoding="utf-8",
            )
            results[book] = "ok"
        except Exception as exc:  # one book failing must not stop the rest
            results[book] = f"{type(exc).__name__}: {exc}"
    return results


async def _run(args: argparse.Namespace) -> dict[str, str]:
    ids = {b: v for b in CLIENTS if (v := getattr(args, b))}
    name = args.name
    if args.sport != "soccer" and not name.startswith(args.sport):
        name = f"{args.sport}_{name}"  # golden tests derive sport from the prefix
    results: dict[str, str] = {}
    async with contextlib.AsyncExitStack() as stack:
        clients: dict[str, Any] = {}
        for book in ids:
            try:
                clients[book] = await stack.enter_async_context(
                    CLIENTS[book](country=args.country)
                )
            except Exception as exc:
                results[book] = f"{type(exc).__name__}: {exc}"
        results.update(await capture(clients, ids, name, FIXTURES_DIR))
    return results


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--name", required=True, help="fixture file stem")
    p.add_argument(
        "--sport", default="soccer", choices=["soccer", "basketball", "tennis"]
    )
    p.add_argument("--country", default="ng")
    for book in CLIENTS:
        p.add_argument(f"--{book}", metavar="EVENT_ID")
    args = p.parse_args()
    for book, status in asyncio.run(_run(args)).items():
        print(f"{book}: {status}")


if __name__ == "__main__":
    main()
