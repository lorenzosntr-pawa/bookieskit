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
    return isinstance((payload.get("data") or {}).get("markets"), list)


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

    result = verify(payload, platform, sport, canonical_ids=expected)
    missing = list(result.missing)
    resolved = [c for c in expected if c not in missing]

    if not structure_ok:
        return BookCheck(
            platform=platform,
            status="drift",
            reason="structure predicate failed",
            expected_canonicals=expected,
            resolved_canonicals=resolved,
            missing_canonicals=missing,
            structure_ok=False,
        )
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
    detail yields a SportRadar id. None if none qualify (a signal that the
    BetPawa listing itself may have drifted).
    """
    payload = await bp_client.get_events(
        sport_id=sport_id, event_type="UPCOMING"
    )
    events = _list_betpawa_events(payload)
    events.sort(key=lambda e: e.get("marketsCount") or 0, reverse=True)
    for event in events[:max_candidates]:
        event_id = event.get("id")
        if event_id is None:
            continue
        event_id = str(event_id)
        detail = await bp_client.get_event_detail(event_id=event_id)
        if extract_sportradar_id(detail, platform="betpawa") is not None:
            return event_id
    return None
