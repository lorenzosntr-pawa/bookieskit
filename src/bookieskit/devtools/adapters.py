"""Per-bookmaker adapters: resolve a SR id to a fetch Handle, and fetch the
raw markets payload for a Handle.

Each adapter isolates one bookmaker's resolve/fetch quirks behind the same
two-method interface so the resolver, the later canary, and the scout all
reuse it. A parallel ``catalog_fetch`` method can be added alongside without
touching the markets path.
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from bookieskit.devtools.types import Handle

_BETIKA_SCAN_PAGES = 9  # mirrors the old probe/smoke scripts


@dataclass
class Adapter:
    """Two-method adapter for one bookmaker."""

    platform: str
    resolve: Callable[..., Awaitable[Handle | None]]
    fetch_raw_markets: Callable[..., Awaitable[dict]]


# ---- SportyBet ------------------------------------------------------------


async def _sportybet_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    return Handle(platform="sportybet", event_id=f"sr:match:{sr_numeric}")


async def _sportybet_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    return await client.get_event_detail(event_id=handle.event_id, live=live)


# ---- MSport ---------------------------------------------------------------


async def _msport_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    return Handle(platform="msport", event_id=f"sr:match:{sr_numeric}")


async def _msport_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    return await client.get_event_detail(event_id=handle.event_id, live=live)


# ---- Betway ---------------------------------------------------------------


async def _betway_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    # Betway's eventId IS the bare numeric SR id.
    return Handle(platform="betway", event_id=sr_numeric)


async def _betway_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    return await client.get_event_markets_all(event_id=handle.event_id)


# ---- Bet9ja ---------------------------------------------------------------


async def _bet9ja_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    from bookieskit.devtools.sports import sport_id

    if live:
        internal = await client.find_event_id_by_sr_id(sr_numeric)
    else:
        sid = sport_id("bet9ja", sport) or "1"
        event_map = await client.build_prematch_event_map(sport_id=sid)
        internal = event_map.get(sr_numeric)
    if internal is None:
        return None
    return Handle(platform="bet9ja", event_id=str(internal))


async def _bet9ja_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    if live:
        return await client.get_live_event_detail(event_id=handle.event_id)
    return await client.get_event_detail(event_id=handle.event_id)


# ---- Betika ---------------------------------------------------------------


async def _betika_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    from bookieskit.devtools.sports import sport_id

    sid = sport_id("betika", sport) or "14"
    for page in range(1, _BETIKA_SCAN_PAGES + 1):
        listing = await client.get_matches(
            sport_id=int(sid), page=page, limit=100
        )
        data = listing.get("data") or []
        if not data:
            break
        for row in data:
            if str(row.get("parent_match_id", "")) == sr_numeric:
                comp = row.get("competition_id")
                extra = {}
                if comp is not None:
                    extra["competition_id"] = str(comp)
                return Handle(
                    platform="betika",
                    event_id=str(row.get("match_id")),
                    extra=extra,
                )
    return None


async def _betika_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    comp = handle.extra.get("competition_id")
    return await client.get_event_markets(
        event_id=handle.event_id, live=live, competition_id=comp
    )


# ---- BetPawa --------------------------------------------------------------


async def _betpawa_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    # BetPawa has no SR->internal reverse lookup; it is the seed source.
    # The resolver handles a BetPawa-internal seed directly.
    return None


async def _betpawa_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    # handle.event_id is a BetPawa internal id (used when the seed is one).
    return await client.get_event_detail(event_id=handle.event_id)


# ---- SportPesa ------------------------------------------------------------


async def _sportpesa_resolve(
    client: Any, sr_numeric: str, sport: str, *, live: bool = False
) -> Handle | None:
    # No cheap SR->game-id reverse lookup in v1 (that is the scout's index
    # builder). Resolver records a skip. fetch_raw_markets still works when
    # a game id is supplied directly.
    return None


async def _sportpesa_fetch(
    client: Any, handle: Handle, *, live: bool = False
) -> dict:
    return await client.get_event_markets(event_id=handle.event_id)


ADAPTERS: dict[str, Adapter] = {
    "betpawa": Adapter("betpawa", _betpawa_resolve, _betpawa_fetch),
    "sportybet": Adapter("sportybet", _sportybet_resolve, _sportybet_fetch),
    "msport": Adapter("msport", _msport_resolve, _msport_fetch),
    "bet9ja": Adapter("bet9ja", _bet9ja_resolve, _bet9ja_fetch),
    "betway": Adapter("betway", _betway_resolve, _betway_fetch),
    "betika": Adapter("betika", _betika_resolve, _betika_fetch),
    "sportpesa": Adapter("sportpesa", _sportpesa_resolve, _sportpesa_fetch),
}
