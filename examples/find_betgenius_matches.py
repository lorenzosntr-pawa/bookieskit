"""Find SportyBet BetGenius events that match BetPawa events.

WHAT THIS DOES
    1. Walks every BetPawa event for one sport (default soccer), both
       UPCOMING (prematch) and LIVE. Fetches event-detail per event.
    2. Keeps only events that have BOTH widgets — SPORTRADAR (the SR
       id is BetPawa's only stable cross-bookmaker key) AND GENIUSSPORTS
       (the marker that BetPawa is routing the event through Genius).
    3. Looks up each event on SportyBet via the SR id, in both phases
       (``live=False`` and ``live=True``).
    4. Confirms the match only when SportyBet's
       ``data.eventSource.{preMatchSource,liveSource}.sourceType`` is
       ``BET_GENIUS`` — i.e. SportyBet is also routing the event via
       BetGenius rather than SportRadar.
    5. Prints a table of confirmed two-bookmaker BetGenius matches.

WHY LOOK UP BY SR ID, NOT THE SYNTHETIC 11111111 ENCODING
    SportyBet's ``data.eventId`` always carries the SportRadar id, even
    for BetGenius events (e.g. ``sr:match:71453928`` for an event whose
    sourceType is BET_GENIUS). The synthetic ``1111111<id>`` form is on
    ``eventSource.*Source.sourceId``, not on ``eventId``, so direct
    lookup by SR id is the cleaner path. The Genius source-type read
    after the lookup is what confirms it as BetGenius on both sides.

USAGE
    python examples/find_betgenius_matches.py            # soccer (sport_id=2)
    python examples/find_betgenius_matches.py 3          # basketball
"""

import asyncio
import sys

from bookieskit import BetPawa, SportyBet
from bookieskit.matching import extract_event_ids

DEFAULT_SPORT_ID = "2"
PAGE_SIZE = 100


async def walk_betpawa_event_ids(bp, event_type: str, sport_id: str) -> set[str]:
    """Walk the paginated BetPawa events list for one sport + phase.

    Returns a set of event ids. Pages until a short page (< PAGE_SIZE)
    signals the end.
    """
    ids: set[str] = set()
    skip = 0
    while True:
        page = await bp.get_events(
            event_type=event_type, sport_id=sport_id,
            take=PAGE_SIZE, skip=skip,
        )
        inner = (page.get("responses") or [{}])[0].get("responses") or []
        for ev in inner:
            eid = ev.get("id")
            if eid:
                ids.add(str(eid))
        if len(inner) < PAGE_SIZE:
            return ids
        skip += PAGE_SIZE


async def fetch_betpawa_event(bp, eid: str):
    """Returns (eid, sr_id, genius_id, home, away) when BetPawa lists a
    Genius widget on the event; None otherwise.

    Only events that have BOTH a SPORTRADAR widget (so we can look up
    SportyBet by SR id) AND a GENIUSSPORTS widget (so we know BetPawa
    routes via Genius) are kept.
    """
    try:
        d = await bp.get_event_detail(event_id=eid)
    except Exception:
        return None
    ids = extract_event_ids(d, platform="betpawa")
    if ids.genius is None or ids.sportradar is None:
        return None
    parts = d.get("participants") or []
    home = (
        parts[0].get("name") if len(parts) > 0 and isinstance(parts[0], dict) else None
    )
    away = (
        parts[1].get("name") if len(parts) > 1 and isinstance(parts[1], dict) else None
    )
    return eid, ids.sportradar, ids.genius, home or "?", away or "?"


def _sportybet_genius_phases(data: dict) -> list[str]:
    """Return ['prematch'], ['live'], ['prematch','live'], or []."""
    source = data.get("eventSource") or {}
    phases: list[str] = []
    for key, phase in (("preMatchSource", "prematch"), ("liveSource", "live")):
        s = source.get(key) or {}
        if isinstance(s, dict) and s.get("sourceType") == "BET_GENIUS":
            phases.append(phase)
    return phases


async def sportybet_lookup(sb, sr_id: str):
    """Look up the SR id on SportyBet (one call, prematch endpoint).

    SportyBet's eventDetail response carries BOTH ``preMatchSource`` and
    ``liveSource`` regardless of which phase the endpoint hit — we only
    need one call to learn whether each phase routes via BetGenius.
    """
    try:
        d = await sb.get_event_detail(event_id=f"sr:match:{sr_id}", live=False)
    except Exception:
        return None
    data = d.get("data") if isinstance(d, dict) else None
    if not isinstance(data, dict) or not data.get("eventId"):
        return None
    phases = _sportybet_genius_phases(data)
    if not phases:
        return None
    return {
        "event_id": str(data.get("eventId")),
        "home": str(data.get("homeTeamName") or "?"),
        "away": str(data.get("awayTeamName") or "?"),
        "phases": phases,
    }


async def main(sport_id: str) -> None:
    async with BetPawa(country="ng") as bp, SportyBet(country="ng") as sb:
        # 1. Enumerate BetPawa event ids (prematch + live, dedup'd).
        eids: set[str] = set()
        for et in ("UPCOMING", "LIVE"):
            page_ids = await walk_betpawa_event_ids(bp, et, sport_id)
            eids |= page_ids
            print(f"BetPawa {et:<8}: {len(page_ids):>5} events")
        print(f"BetPawa total : {len(eids):>5} unique events")

        # 2. Fetch BetPawa detail concurrently; only keep events that
        #    have BOTH a SPORTRADAR (for SR lookup on SportyBet) AND
        #    a GENIUSSPORTS widget (so BetPawa is routing via Genius).
        bp_results = await asyncio.gather(
            *(fetch_betpawa_event(bp, eid) for eid in eids)
        )
        bp_genius_events = [r for r in bp_results if r is not None]
        print(
            f"BetPawa events with both SPORTRADAR + GENIUSSPORTS widgets: "
            f"{len(bp_genius_events)}"
        )

        # 3. Look up each on SportyBet by SR id; keep only those where
        #    SportyBet routes via BET_GENIUS for at least one phase.
        sb_results = await asyncio.gather(
            *(sportybet_lookup(sb, e[1]) for e in bp_genius_events)
        )

    matches: list[tuple] = []
    for bp_event, sb_match in zip(bp_genius_events, sb_results):
        if sb_match is None:
            continue
        bp_eid, sr_id, gid, bp_home, bp_away = bp_event
        for phase in sb_match["phases"]:
            matches.append((
                phase, sr_id, gid,
                bp_eid, bp_home, bp_away,
                sb_match["event_id"], sb_match["home"], sb_match["away"],
            ))

    print()
    print("=" * 90)
    print(f"Confirmed BetPawa <-> SportyBet BetGenius matches: {len(matches)}")
    print("=" * 90)
    if not matches:
        print("(no overlap)")
        return
    for m in matches:
        phase, sr_id, gid = m[0], m[1], m[2]
        bp_eid, bp_home, bp_away = m[3], m[4], m[5]
        sb_eid, sb_home, sb_away = m[6], m[7], m[8]
        print(f"  [{phase:8}] sr:{sr_id}  genius:{gid}")
        print(f"             BP {bp_eid:<12} {bp_home} v {bp_away}")
        print(f"             SB {sb_eid:<24} {sb_home} v {sb_away}")


if __name__ == "__main__":
    sport = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SPORT_ID
    asyncio.run(main(sport))
