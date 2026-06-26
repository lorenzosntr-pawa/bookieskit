"""Live odds audit: probe every mapped market across all books on a set of
fixtures and classify each market x book as MAPPED+PRICED / NOT OFFERED, plus a
per-book MIS-MAP review surface (raw market groups the registry does not map).

All classification/report logic here is pure and offline-testable. The only
networked path is ``run_audit`` (the in-region live probe), which reuses the
harness resolve/fetch/discover machinery.

Betway caveat: ``search.unmapped`` over-reports for Betway (the registry
indexes Betway by NAME but candidates carry numeric ids -- see search.py).
Betway's ``unmapped_groups`` is therefore always empty; Betway odds still
appear in the matrix via ``verify``.
"""

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from bookieskit.devtools.adapters import ADAPTERS
from bookieskit.devtools.coverage import PLATFORMS
from bookieskit.devtools.resolver import ALL_BOOKS, resolve_event
from bookieskit.devtools.search import unmapped
from bookieskit.devtools.types import Handle
from bookieskit.devtools.verify import verify
from bookieskit.markets.registry import MarketRegistry

# Per-platform id attribute on MarketMapping (mirrors canary._ID_ATTR).
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
class MarketAudit:
    """One canonical market's verdict for one book on one fixture."""

    canonical_id: str
    status: str  # "mapped_priced" | "not_offered"
    odds: dict | None  # verify() odds dict when priced, else None


@dataclass
class UnmappedGroup:
    """A raw market group present on the payload but not mapped by the registry."""

    market_id: str | None
    name: str
    outcomes: list[str]


@dataclass
class BookAudit:
    """Per-book audit: market verdicts + MIS-MAP review surface."""

    platform: str
    status: str  # "ok" | "unreachable" | "skipped"
    reason: str
    markets: list[MarketAudit] = field(default_factory=list)
    unmapped_groups: list[UnmappedGroup] = field(default_factory=list)


@dataclass
class FixtureAudit:
    """All per-book audits for one fixture."""

    label: str
    sr_numeric: str | None
    books: list[BookAudit] = field(default_factory=list)


@dataclass
class AuditReport:
    """The full audit run: fixtures + roll-up summary."""

    sport: str
    mode: str  # "prematch" | "live"
    fixtures: list[FixtureAudit] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


def expected_canonicals(
    platform: str,
    sport: str = "soccer",
    registry: MarketRegistry | None = None,
) -> list[str]:
    """Canonicals (sorted) the registry maps for ``platform`` in ``sport``.

    A canonical counts as mapped iff its MarketMapping has a non-None
    platform id attribute and its ``sport`` matches -- so a football audit
    never expects basketball/tennis markets.
    """
    if registry is None:
        registry = MarketRegistry()
    attr = _ID_ATTR.get(platform)
    if attr is None:
        return []
    return sorted(
        m.canonical_id
        for m in registry.list_markets()
        if m.sport == sport and getattr(m, attr, None) is not None
    )


def classify_book(
    raw: Any,
    platform: str,
    sport: str,
    *,
    registry: MarketRegistry | None = None,
) -> BookAudit:
    """Classify each expected canonical for one reachable book payload."""
    if registry is None:
        registry = MarketRegistry()
    expected = expected_canonicals(platform, sport, registry)
    vr = verify(raw, platform, sport, canonical_ids=expected)
    markets = [
        MarketAudit(
            canonical_id=c,
            status="mapped_priced" if c in vr.resolved else "not_offered",
            odds=vr.resolved.get(c),
        )
        for c in expected
    ]
    # MIS-MAP review surface: raw groups the registry doesn't map. Betway's
    # unmapped() is unreliable (see module docstring) -> always empty.
    groups: list[UnmappedGroup] = []
    if platform != "betway":
        groups = [
            UnmappedGroup(
                market_id=c.market_id, name=c.name, outcomes=list(c.outcomes)
            )
            for c in unmapped(raw, platform, sport, registry)
        ]
    return BookAudit(
        platform=platform,
        status="ok",
        reason="",
        markets=markets,
        unmapped_groups=groups,
    )


def audit_fixture(
    label: str,
    sr_numeric: str | None,
    raws: dict[str, dict],
    skipped: dict[str, str],
    sport: str,
    *,
    registry: MarketRegistry | None = None,
) -> FixtureAudit:
    """Classify every book for one fixture (present -> classify, else skipped)."""
    if registry is None:
        registry = MarketRegistry()
    books: list[BookAudit] = []
    for platform in PLATFORMS:
        if platform in raws:
            books.append(
                classify_book(raws[platform], platform, sport, registry=registry)
            )
            continue
        reason = skipped.get(platform, "not probed")
        status = "unreachable" if reason.startswith("fetch") else "skipped"
        books.append(BookAudit(platform=platform, status=status, reason=reason))
    return FixtureAudit(label=label, sr_numeric=sr_numeric, books=books)


def build_report(
    fixtures: list[FixtureAudit], *, sport: str, mode: str
) -> AuditReport:
    """Aggregate fixtures into a report with summary counts."""
    summary = {
        "mapped_priced": 0,
        "not_offered": 0,
        "unmapped_groups": 0,
        "books_ok": 0,
        "books_skipped": 0,
        "books_unreachable": 0,
    }
    for fa in fixtures:
        for ba in fa.books:
            key = f"books_{ba.status}"
            summary[key] = summary.get(key, 0) + 1
            summary["unmapped_groups"] += len(ba.unmapped_groups)
            for m in ba.markets:
                summary[m.status] = summary.get(m.status, 0) + 1
    return AuditReport(sport=sport, mode=mode, fixtures=fixtures, summary=summary)


def _odds_cell(market: MarketAudit) -> str:
    """One matrix cell: compact priced summary, or a not-offered placeholder."""
    if market.status != "mapped_priced" or market.odds is None:
        return "—"
    odds = market.odds
    if "outcomes" in odds:
        return "/".join(str(v) for v in odds["outcomes"].values()) or "✓"
    lines = odds.get("lines") or {}
    if not lines:
        return "✓"
    first = next(iter(lines.values()))
    return "/".join(str(v) for v in first.values()) or "✓"


def render_markdown(report: AuditReport) -> str:
    """Render an AuditReport as a human-readable markdown report."""
    s = report.summary
    lines = [
        f"# bookieskit — Live Odds Audit ({report.mode}, {report.sport})",
        "",
        f"_Summary: {s.get('mapped_priced', 0)} priced, "
        f"{s.get('not_offered', 0)} not-offered, "
        f"{s.get('unmapped_groups', 0)} unmapped groups across "
        f"{len(report.fixtures)} fixture(s)._",
        "",
    ]
    for fa in report.fixtures:
        title = f"## {fa.label}"
        if fa.sr_numeric:
            title += f" (sr:{fa.sr_numeric})"
        lines += [title, ""]
        ok_books = [b for b in fa.books if b.status == "ok"]
        canonicals = sorted(
            {m.canonical_id for b in ok_books for m in b.markets}
        )
        header = "| market | " + " | ".join(b.platform for b in ok_books) + " |"
        sep = "| --- | " + " | ".join("---" for _ in ok_books) + " |"
        lines += [header, sep]
        for canonical in canonicals:
            cells = []
            for b in ok_books:
                m = next(
                    (x for x in b.markets if x.canonical_id == canonical), None
                )
                cells.append(_odds_cell(m) if m else "·")
            lines.append(f"| {canonical} | " + " | ".join(cells) + " |")
        for b in fa.books:
            if b.status != "ok":
                lines.append(f"- _{b.platform}: {b.status} — {b.reason}_")
        lines += ["", "### MIS-MAP review (raw groups we don't map)", ""]
        any_unmapped = False
        for b in ok_books:
            if not b.unmapped_groups:
                continue
            any_unmapped = True
            lines.append(f"- **{b.platform}**:")
            for g in b.unmapped_groups:
                lines.append(
                    f"  - `{g.market_id}` {g.name} "
                    f"[{', '.join(g.outcomes)}]"
                )
        if not any_unmapped:
            lines.append("_None._")
        lines.append("")
    lines.append("_Generated by `python -m bookieskit.devtools audit`._")
    return "\n".join(lines)


# ---- Networked runner (in-region only) ------------------------------------


async def _fetch_book(
    book: str,
    handle: Handle,
    clients: dict[str, Any] | None,
    *,
    live: bool,
    sportpesa_cookie: str | None = None,
    betika_cookie: str | None = None,
) -> dict:
    """Fetch raw markets for one book via its adapter (injected or built).

    Cookie-gated books (SportPesa, Betika) need their session cookie threaded
    into client construction or the live fetch hits an unauthenticated
    challenge -- mirrors cli._fetch_raw.
    """
    adapter = ADAPTERS[book]
    injected = (clients or {}).get(book)
    if injected is not None:
        return await adapter.fetch_raw_markets(injected, handle, live=live)
    from bookieskit.devtools.resolver import _CLIENT_CLASSES, _COUNTRY

    cookie = None
    if book == "sportpesa":
        cookie = sportpesa_cookie
    elif book == "betika":
        cookie = betika_cookie
    kwargs: dict[str, Any] = {"country": _COUNTRY[book]}
    if cookie is not None:
        kwargs["cookie"] = cookie
    async with _CLIENT_CLASSES[book](**kwargs) as client:
        return await adapter.fetch_raw_markets(client, handle, live=live)


async def _audit_one_seed(
    seed: str,
    sport: str,
    books: tuple[str, ...],
    *,
    live: bool,
    betpawa_seed: bool,
    sportpesa_cookie: str | None,
    betika_cookie: str | None,
    clients: dict[str, Any] | None,
    registry: MarketRegistry,
) -> FixtureAudit:
    """Resolve + fetch one seed across books, then classify the fixture."""
    ev = await resolve_event(
        seed,
        sport,
        books,
        live=live,
        betpawa_seed=betpawa_seed,
        sportpesa_cookie=sportpesa_cookie,
        betika_cookie=betika_cookie,
        clients=clients,
    )
    raws: dict[str, dict] = {}
    skipped = dict(ev.skipped)
    for book, handle in ev.handles.items():
        try:
            raws[book] = await _fetch_book(
                book, handle, clients, live=live,
                sportpesa_cookie=sportpesa_cookie, betika_cookie=betika_cookie,
            )
        except Exception as exc:  # per-book isolation
            skipped[book] = f"fetch error: {exc!r}"
    label = f"{ev.home} vs {ev.away}".strip()
    if label == "vs":
        label = seed
    return audit_fixture(
        label, ev.sr_numeric, raws, skipped, sport, registry=registry
    )


async def run_audit(
    mode: str,
    *,
    seeds: list[str] | None = None,
    sport: str = "soccer",
    books: tuple[str, ...] = ALL_BOOKS,
    max_live: int = 4,
    betpawa_seed: bool = False,
    sportpesa_cookie: str | None = None,
    betika_cookie: str | None = None,
    clients: dict[str, Any] | None = None,
    discover: Callable[..., Awaitable[list[str]]] | None = None,
) -> AuditReport:
    """Probe all books across fixtures and build an AuditReport.

    mode="prematch": requires ``seeds``; prematch path (live=False).
    mode="live": auto-discovers up to ``max_live`` in-play betpawa events
    (via ``discover``) and probes the live path (live=True).
    """
    registry = MarketRegistry()
    live = mode == "live"

    if mode == "prematch":
        if not seeds:
            raise ValueError("prematch mode requires at least one seed")
        seed_list = list(seeds)
        bp_seed = betpawa_seed
    elif mode == "live":
        if discover is None:
            discover = _discover_live
        seed_list = await discover(sport, max_live, clients)
        bp_seed = True  # live discovery yields betpawa event ids
    else:
        raise ValueError(f"unknown audit mode: {mode!r}")

    fixtures: list[FixtureAudit] = []
    for seed in seed_list:
        fixtures.append(
            await _audit_one_seed(
                seed,
                sport,
                books,
                live=live,
                betpawa_seed=bp_seed,
                sportpesa_cookie=sportpesa_cookie,
                betika_cookie=betika_cookie,
                clients=clients,
                registry=registry,
            )
        )
    return build_report(fixtures, sport=sport, mode=mode)


async def _discover_live(
    sport: str, max_live: int, clients: dict[str, Any] | None
) -> list[str]:
    """Return up to ``max_live`` in-play betpawa event ids (in-region only).

    Lists LIVE betpawa events for the sport, ranked by marketsCount desc, and
    returns their ids. Returns [] when the listing is unreachable (e.g. a
    geo-blocked 403 from out of region) -- a clean "no live events" signal.
    """
    from bookieskit.devtools.sports import sport_id as _sport_id

    bp_sport_id = _sport_id("betpawa", sport) or "2"
    bp = (clients or {}).get("betpawa")
    if bp is None:
        from bookieskit import BetPawa

        async with BetPawa(country="ng") as bp_client:
            return await _list_live_seeds(bp_client, bp_sport_id, max_live)
    return await _list_live_seeds(bp, bp_sport_id, max_live)


async def _list_live_seeds(
    bp_client: Any, sport_id: str, max_live: int
) -> list[str]:
    """Pull LIVE betpawa events and return up to ``max_live`` ids."""
    from bookieskit.devtools.canary import _list_betpawa_events

    try:
        payload = await bp_client.get_events(sport_id=sport_id, event_type="LIVE")
    except Exception:
        return []
    events = _list_betpawa_events(payload)
    events.sort(key=lambda e: e.get("marketsCount") or 0, reverse=True)
    out: list[str] = []
    for event in events[:max_live]:
        eid = event.get("id")
        if eid is not None:
            out.append(str(eid))
    return out
