"""Cross-bookmaker fan-out: seed + sport -> ResolvedEvent.

Each book is resolved independently; an exception, a not-found, or a
missing cookie records a per-book skip and never aborts the others.
"""

from typing import Any

from bookieskit import (
    Bet9ja,
    Betika,
    BetPawa,
    Betway,
    MSport,
    SportPesa,
    SportyBet,
)
from bookieskit.devtools.adapters import ADAPTERS
from bookieskit.devtools.types import Handle, ResolvedEvent
from bookieskit.matching import extract_sportradar_id

ALL_BOOKS: tuple[str, ...] = (
    "betpawa", "sportybet", "msport", "bet9ja",
    "betway", "betika", "sportpesa",
)

# Cookie-gated books: resolution is skipped when no cookie is supplied.
_COOKIE_GATED = {"sportpesa"}

_CLIENT_CLASSES: dict[str, type] = {
    "betpawa": BetPawa,
    "sportybet": SportyBet,
    "msport": MSport,
    "bet9ja": Bet9ja,
    "betway": Betway,
    "betika": Betika,
    "sportpesa": SportPesa,
}

# Country variant per book (ng where it operates, ke proxy for ke-only books).
_COUNTRY: dict[str, str] = {
    "betpawa": "ng",
    "sportybet": "ng",
    "msport": "ng",
    "bet9ja": "ng",
    "betway": "ng",
    "betika": "ke",
    "sportpesa": "ke",
}


def _normalize_sr(seed: str) -> str:
    """Return the bare numeric SR id from a seed (strips sr:match: prefix)."""
    if seed.startswith("sr:match:"):
        return seed[len("sr:match:"):]
    return seed


async def resolve_event(
    seed: str,
    sport: str,
    books: tuple[str, ...] = ALL_BOOKS,
    *,
    live: bool = False,
    betpawa_seed: bool = False,
    sportpesa_cookie: str | None = None,
    betika_cookie: str | None = None,
    clients: dict[str, Any] | None = None,
) -> ResolvedEvent:
    """Resolve a seed across the requested bookmakers.

    Args:
        seed: Raw SR id ("sr:match:N" or bare "N"), or a BetPawa internal
            event id when ``betpawa_seed=True``.
        sport: Canonical sport name ("soccer", "basketball", "tennis").
        books: Subset of ALL_BOOKS to resolve.
        live: Resolve/fetch live markets where the book distinguishes.
        betpawa_seed: Treat ``seed`` as a BetPawa internal id; fetch its
            detail and extract the SR id from there.
        sportpesa_cookie / betika_cookie: Warmed cookies for gated books.
        clients: Optional pre-entered client instances keyed by platform
            (test injection). When None, clients are constructed here.

    Returns:
        ResolvedEvent with per-book handles and skip reasons.
    """
    home = away = "?"
    sr_numeric: str | None = None

    # Resolve the SR id (and home/away) up front.
    if betpawa_seed:
        bp = (clients or {}).get("betpawa")
        if bp is not None:
            sr_numeric, home, away = await _betpawa_seed_lookup(bp, seed)
        else:
            async with BetPawa(country="ng") as bp_client:
                sr_numeric, home, away = await _betpawa_seed_lookup(
                    bp_client, seed
                )
    else:
        sr_numeric = _normalize_sr(seed)

    handles: dict[str, Handle] = {}
    skipped: dict[str, str] = {}

    for book in books:
        if book == "betpawa":
            # BetPawa has no SR->internal reverse lookup.
            skipped["betpawa"] = "no SR reverse lookup (use --betpawa-seed)"
            continue
        if book in _COOKIE_GATED and sportpesa_cookie is None:
            skipped[book] = "cookie missing"
            continue
        if sr_numeric is None:
            skipped[book] = "no SR id"
            continue
        adapter = ADAPTERS.get(book)
        if adapter is None:
            skipped[book] = "no adapter"
            continue
        try:
            client = (clients or {}).get(book)
            if client is not None:
                handle = await adapter.resolve(
                    client, sr_numeric, sport, live=live
                )
            else:
                cookie = sportpesa_cookie if book == "sportpesa" else (
                    betika_cookie if book == "betika" else None
                )
                cls = _CLIENT_CLASSES[book]
                kwargs = {"country": _COUNTRY[book]}
                if cookie is not None:
                    kwargs["cookie"] = cookie
                async with cls(**kwargs) as constructed:
                    handle = await adapter.resolve(
                        constructed, sr_numeric, sport, live=live
                    )
            if handle is None:
                skipped[book] = "not found"
            else:
                handles[book] = handle
        except Exception as exc:  # per-book isolation
            skipped[book] = f"error: {exc!r}"

    return ResolvedEvent(
        seed=seed,
        sport=sport,
        sr_numeric=sr_numeric,
        home=home,
        away=away,
        handles=handles,
        skipped=skipped,
    )


async def _betpawa_seed_lookup(bp: Any, seed: str) -> tuple[str | None, str, str]:
    """Fetch a BetPawa event by internal id; return (sr_numeric, home, away)."""
    detail = await bp.get_event_detail(event_id=seed)
    sr_numeric = extract_sportradar_id(detail, platform="betpawa")
    parts = detail.get("participants") or []
    home = parts[0]["name"] if len(parts) > 0 else "?"
    away = parts[1]["name"] if len(parts) > 1 else "?"
    return sr_numeric, home, away
