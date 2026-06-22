"""Live canary: probe real bookmaker payloads on a schedule and detect drift.

Drift = a reachable payload whose parser-critical structure changed, or a
core market that stopped resolving via parse_markets. Distinguished from
transient unreachability (network blip -> soft warning). Reuses the harness
core: resolve_event (fan-out), ADAPTERS (fetch), verify (resolution check).

All checker logic is offline-unit-testable; the only networked path is the
scheduled workflow (.github/workflows/canary.yml). The CanaryReport JSON is
the stable contract the orchestrator (sub-project 5) turns into alerts.
"""

from dataclasses import dataclass
from typing import Any, Callable

from bookieskit.devtools.adapters import ADAPTERS
from bookieskit.devtools.resolver import ALL_BOOKS, resolve_event
from bookieskit.devtools.sports import sport_id as _sport_id
from bookieskit.devtools.types import Handle
from bookieskit.devtools.verify import verify
from bookieskit.markets.registry import MarketRegistry
from bookieskit.matching import extract_sportradar_id

CORE_CANONICALS: tuple[str, ...] = (
    "1x2_ft",
    "over_under_ft",
    "btts_ft",
    "double_chance_ft",
)

# Per-platform id attribute on MarketMapping (verified in markets/types.py).
_ID_ATTR: dict[str, str] = {
    "betpawa": "betpawa_id",
    "sportybet": "sportybet_id",
    "msport": "msport_id",
    "bet9ja": "bet9ja_key",
    "betway": "betway_id",
    "betika": "betika_id",
    "sportpesa": "sportpesa_id",
}


@dataclass
class BookCheck:
    """The drift verdict for one bookmaker on one canary run."""

    platform: str
    status: str  # "ok" | "drift" | "unreachable" | "skipped"
    reason: str  # human explanation (empty when ok)
    expected_canonicals: list[str]  # the core subset this book should resolve
    resolved_canonicals: list[str]  # what actually resolved
    missing_canonicals: list[str]  # expected - resolved (drift driver)
    structure_ok: bool


@dataclass
class CanaryReport:
    """The full canary run: per-book checks + the run-level drift flag."""

    sport: str
    seed: str | None  # the BetPawa event id used (None if discovery failed)
    sr_numeric: str | None
    checks: list[BookCheck]
    drifted: bool  # any check.status == "drift"


# ---- Structure predicates -------------------------------------------------
# One per book; each asserts the parser-critical shape, derived from the
# matching _candidates_* reader in search.py so it matches the real parser.


def _struct_betpawa(payload: dict) -> bool:
    return isinstance(payload.get("markets"), list)


def _struct_data_markets(payload: dict) -> bool:
    # sportybet / msport: data.markets is a list.
    data = payload.get("data")
    if not isinstance(data, dict):
        return False
    return isinstance(data.get("markets"), list)


def _struct_betway(payload: dict) -> bool:
    return all(
        isinstance(payload.get(k), list)
        for k in ("marketsInGroup", "outcomes", "prices")
    )


def _struct_bet9ja(payload: dict) -> bool:
    return isinstance((payload.get("D") or {}).get("O"), dict)


def _struct_betika(payload: dict) -> bool:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return False
    first = data[0]
    return isinstance(first, dict) and isinstance(first.get("odds"), list)


def _struct_sportpesa(payload: dict) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    first = next(iter(payload.values()), None)
    return isinstance(first, list)


STRUCTURE_PREDICATES: dict[str, Callable[[dict], bool]] = {
    "betpawa": _struct_betpawa,
    "sportybet": _struct_data_markets,
    "msport": _struct_data_markets,
    "betway": _struct_betway,
    "bet9ja": _struct_bet9ja,
    "betika": _struct_betika,
    "sportpesa": _struct_sportpesa,
}


def expected_core(
    platform: str, sport: str, registry: MarketRegistry
) -> list[str]:
    """CORE_CANONICALS intersected with what the registry maps for this book.

    A canonical counts as mapped for ``platform`` iff its MarketMapping has a
    non-None platform id attribute. For soccer every CORE canonical maps all
    seven books, so this returns the full list; for a narrower sport or a
    future registry edit it narrows automatically.
    """
    attr = _ID_ATTR.get(platform)
    if attr is None:
        return []
    out: list[str] = []
    for canonical in CORE_CANONICALS:
        mapping = registry.get_by_canonical(canonical)
        if mapping is None:
            continue
        if getattr(mapping, attr, None) is not None:
            out.append(canonical)
    return out


def check_book(
    payload: dict[str, Any],
    platform: str,
    sport: str,
    registry: MarketRegistry | None = None,
) -> BookCheck:
    """Structure predicate + core resolution -> a per-book drift verdict.

    Reachable-but-broken (structure False OR any expected core canonical did
    not resolve) -> status "drift". All good -> "ok". When the registry maps
    none of the core for this book -> "skipped".
    """
    if registry is None:
        registry = MarketRegistry()
    expected = expected_core(platform, sport, registry)
    if not expected:
        return BookCheck(
            platform=platform,
            status="skipped",
            reason="no core markets mapped",
            expected_canonicals=[],
            resolved_canonicals=[],
            missing_canonicals=[],
            structure_ok=False,
        )

    predicate = STRUCTURE_PREDICATES.get(platform)
    if predicate is None:
        structure_ok = False
    else:
        structure_ok = bool(predicate(payload))

    if not structure_ok:
        return BookCheck(
            platform=platform,
            status="drift",
            reason="structure predicate failed",
            expected_canonicals=expected,
            resolved_canonicals=[],
            missing_canonicals=list(expected),
            structure_ok=False,
        )

    result = verify(payload, platform, sport, canonical_ids=expected)
    missing = list(result.missing)
    resolved = [c for c in expected if c not in missing]

    if missing:
        return BookCheck(
            platform=platform,
            status="drift",
            reason=f"missing core canonicals: {', '.join(missing)}",
            expected_canonicals=expected,
            resolved_canonicals=resolved,
            missing_canonicals=missing,
            structure_ok=True,
        )
    return BookCheck(
        platform=platform,
        status="ok",
        reason="",
        expected_canonicals=expected,
        resolved_canonicals=resolved,
        missing_canonicals=[],
        structure_ok=True,
    )


def _list_betpawa_events(payload: dict) -> list[dict]:
    """Flatten BetPawa get_events responses[].responses[] into one list."""
    out: list[dict] = []
    for group in payload.get("responses") or []:
        if not isinstance(group, dict):
            continue
        for event in group.get("responses") or []:
            if isinstance(event, dict):
                out.append(event)
    return out


async def _discover_seed(
    bp_client: Any, sport_id: str, max_candidates: int
) -> str | None:
    """Return a current top BetPawa event id that carries a SportRadar id.

    Lists UPCOMING events for the sport, ranks by marketsCount desc, then
    fetches detail for up to ``max_candidates`` and returns the first whose
    detail yields a SportRadar id. Returns None if none qualify, the listing
    is unreachable, or every candidate's detail fetch fails — a clean
    "no seed" signal, never a crash. (BetPawa is geo-restricted: from a
    network it does not serve, ``get_events`` returns a 403, which surfaces
    here as None. Run the canary from an in-region environment.)
    """
    try:
        payload = await bp_client.get_events(
            sport_id=sport_id, event_type="UPCOMING"
        )
    except Exception:
        # Listing unreachable/blocked (e.g. geo-restricted 403) -> no seed.
        return None
    events = _list_betpawa_events(payload)
    # marketsCount is a soft dependency: if BetPawa renames it, all events
    # sort as 0 and discovery degrades gracefully to insertion order.
    events.sort(key=lambda e: e.get("marketsCount") or 0, reverse=True)
    for event in events[:max_candidates]:
        event_id = event.get("id")
        if event_id is None:
            continue
        event_id = str(event_id)
        try:
            detail = await bp_client.get_event_detail(event_id=event_id)
        except Exception:
            continue  # this candidate unreachable; try the next
        if extract_sportradar_id(detail, platform="betpawa") is not None:
            return event_id
    return None


_FETCH_RETRIES = 2  # 1 try + 2 retries before a book is "unreachable"


async def _fetch_with_retries(
    adapter: Any, client: Any, handle: Handle, *, retries: int = _FETCH_RETRIES
) -> dict:
    """Fetch raw markets, retrying transient errors; re-raise on the last."""
    last: Exception | None = None
    for _ in range(1 + retries):
        try:
            return await adapter.fetch_raw_markets(client, handle, live=False)
        except Exception as exc:  # transient until proven persistent
            last = exc
    assert last is not None
    raise last


async def _fetch_for_book(
    book: str, handle: Handle, clients: dict[str, Any] | None
) -> dict:
    """Resolve the client for ``book`` (injected or constructed) and fetch."""
    adapter = ADAPTERS[book]
    injected = (clients or {}).get(book)
    if injected is not None:
        return await _fetch_with_retries(adapter, injected, handle)
    from bookieskit.devtools.resolver import _CLIENT_CLASSES, _COUNTRY

    async with _CLIENT_CLASSES[book](country=_COUNTRY[book]) as client:
        return await _fetch_with_retries(adapter, client, handle)


async def run_canary(
    sport: str = "soccer",
    *,
    seed: str | None = None,
    max_candidates: int = 3,
    books: tuple[str, ...] = ALL_BOOKS,
    clients: dict[str, Any] | None = None,
) -> CanaryReport:
    """Discover a seed, resolve across books, check each reachable book.

    Args:
        sport: Canonical sport (v1 = "soccer").
        seed: BetPawa internal event id; discovered dynamically when None.
        max_candidates: Top-N BetPawa events to try during discovery.
        books: Subset of ALL_BOOKS to fan out to (defaults to all). Narrowed
            by tests so only books with injected clients are fetched — keeps
            the suite offline. BetPawa is always checked (added explicitly).
        clients: Optional pre-entered client instances keyed by platform
            (test injection). When None, clients are constructed per book.

    Returns:
        CanaryReport. ``drifted`` is True iff any check is "drift".
        ``seed`` is None when discovery failed (no checks).
    """
    registry = MarketRegistry()

    # 1. Seed discovery.
    if seed is None:
        bp_sport_id = _sport_id("betpawa", sport) or "2"
        bp = (clients or {}).get("betpawa")
        if bp is not None:
            seed = await _discover_seed(bp, bp_sport_id, max_candidates)
        else:
            from bookieskit import BetPawa

            async with BetPawa(country="ng") as bp_client:
                seed = await _discover_seed(
                    bp_client, bp_sport_id, max_candidates
                )
    if seed is None:
        return CanaryReport(
            sport=sport, seed=None, sr_numeric=None, checks=[], drifted=False
        )

    # 2. Resolve across books from the BetPawa seed.
    resolved = await resolve_event(
        seed, sport, books=books, betpawa_seed=True, clients=clients
    )

    # 3. Check set = resolved handles + explicit BetPawa handle.
    handles: dict[str, Handle] = dict(resolved.handles)
    handles["betpawa"] = Handle(platform="betpawa", event_id=seed)

    checks: list[BookCheck] = []

    # 4. Reachable books: fetch (with retries) + check_book.
    for book, handle in handles.items():
        expected = expected_core(book, sport, registry)
        if not expected:
            checks.append(BookCheck(
                platform=book, status="skipped",
                reason="no core markets mapped",
                expected_canonicals=[], resolved_canonicals=[],
                missing_canonicals=[], structure_ok=False,
            ))
            continue
        try:
            raw = await _fetch_for_book(book, handle, clients)
        except Exception as exc:
            checks.append(BookCheck(
                platform=book, status="unreachable",
                reason=f"fetch failed: {exc!r}",
                expected_canonicals=expected,
                resolved_canonicals=[], missing_canonicals=[],
                structure_ok=False,
            ))
            continue
        try:
            checks.append(check_book(raw, book, sport, registry))
        except Exception as exc:
            checks.append(BookCheck(
                platform=book, status="drift",
                reason=f"parse error: {exc!r}",
                expected_canonicals=expected,
                resolved_canonicals=[], missing_canonicals=[],
                structure_ok=False,
            ))

    # 5. Resolver-skipped books (not in the check set) -> skipped.
    for book, reason in resolved.skipped.items():
        if book in handles:
            continue  # checked via the explicit/resolved handle
        checks.append(BookCheck(
            platform=book, status="skipped", reason=reason,
            expected_canonicals=[], resolved_canonicals=[],
            missing_canonicals=[], structure_ok=False,
        ))

    drifted = any(c.status == "drift" for c in checks)
    return CanaryReport(
        sport=sport, seed=seed, sr_numeric=resolved.sr_numeric,
        checks=checks, drifted=drifted,
    )
