"""Quick totals audit: sports / tournaments / events for all 6 bookmakers.

Strategy: single API call per (bookmaker, prematch/live) where possible.
Event totals come from per-sport counts in the sports response; tournament
totals iterate over sports (for soccer only — full enumeration would be many
calls per bookmaker).

SportPesa requires warmed Akamai cookies — set the SPORTPESA_COOKIE env var
to a full Cookie: header from a browser session. When unset, the SportPesa
block reports a clean failure rather than crashing.

The file name (count_5bookies.py) is kept for backwards-compatibility with
external references; the script now iterates 6 bookmakers.
"""

import asyncio
import os

from bookieskit import (
    Bet9ja,
    Betika,
    BetPawa,
    Betway,
    MSport,
    SportPesa,
    SportyBet,
)


async def count_betpawa() -> dict:
    out = {"name": "BetPawa", "country": "ng"}
    async with BetPawa(country="ng") as bp:
        sports = (await bp.get_sports()).get("onlyMeta", [])
        out["sports_total"] = len(sports)
        out["sports_with_prematch"] = sum(
            1 for s in sports if s.get("eventCounts", {}).get("upcoming", 0) > 0
        )
        out["sports_with_live"] = sum(
            1 for s in sports if s.get("eventCounts", {}).get("live", 0) > 0
        )
        out["events_prematch"] = sum(
            s.get("eventCounts", {}).get("upcoming", 0) for s in sports
        )
        out["events_live"] = sum(
            s.get("eventCounts", {}).get("live", 0) for s in sports
        )
        # Tournament total: iterate ALL sports for prematch.
        # Live tournaments: BetPawa has no dedicated "live competitions" endpoint,
        # but every live event carries `competition.id` — derive by paginating
        # get_events(event_type="LIVE") per sport and collecting distinct ids.
        # BetPawa caps take at 100.
        prematch_tournaments = 0
        live_competition_ids: set = set()
        for s in sports:
            sid = str(s["category"]["id"])
            try:
                regs = (await bp.get_countries(sport_id=sid)).get("withRegions", [])
                comp_count = sum(
                    len(r.get("competitions", []))
                    for entry in regs
                    for r in entry.get("regions", [])
                )
                prematch_tournaments += comp_count
            except Exception:
                pass
            # Only walk live-events when the sport has live activity (avoids
            # an extra call per empty sport).
            if s.get("eventCounts", {}).get("live", 0) == 0:
                continue
            skip = 0
            while True:
                try:
                    page = await bp.get_events(
                        event_type="LIVE", sport_id=sid, take=100, skip=skip
                    )
                except Exception:
                    break
                inner = (page.get("responses") or [{}])[0].get("responses") or []
                if not inner:
                    break
                for e in inner:
                    if not isinstance(e, dict):
                        continue
                    comp = e.get("competition") or {}
                    cid = comp.get("id")
                    if cid:
                        live_competition_ids.add((sid, cid))
                if len(inner) < 100:
                    break
                skip += 100
        out["tournaments_prematch"] = prematch_tournaments
        out["tournaments_live"] = len(live_competition_ids)
    return out


async def count_sportybet() -> dict:
    out = {"name": "SportyBet", "country": "ng"}
    async with SportyBet(country="ng") as sb:
        prematch_sports = (await sb.get_sports(live=False)).get("data", {}).get("sportList", [])  # noqa: E501
        live_sports = (await sb.get_sports(live=True)).get("data", {}).get("sportList", [])  # noqa: E501
        out["sports_total"] = len(prematch_sports)
        out["sports_with_prematch"] = sum(1 for s in prematch_sports if s.get("eventSize", 0) > 0)  # noqa: E501
        out["sports_with_live"] = sum(1 for s in live_sports if s.get("eventSize", 0) > 0)  # noqa: E501
        out["events_prematch"] = sum(s.get("eventSize", 0) for s in prematch_sports)
        out["events_live"] = sum(s.get("eventSize", 0) for s in live_sports)
        # Tournaments: iterate all sports
        prematch_tournaments = 0
        live_tournaments = 0
        for s in prematch_sports:
            sid = s["id"]
            try:
                cats = (
                    (await sb.get_countries(sport_id=sid, live=False))
                    .get("data", {}).get("sportList", [{}])[0].get("categories", [])
                )
                prematch_tournaments += sum(len(c.get("tournaments", [])) for c in cats)
            except Exception:
                pass
        for s in live_sports:
            sid = s["id"]
            try:
                cats = (
                    (await sb.get_countries(sport_id=sid, live=True))
                    .get("data", {}).get("sportList", [{}])[0].get("categories", [])
                )
                live_tournaments += sum(len(c.get("tournaments", [])) for c in cats)
            except Exception:
                pass
        out["tournaments_prematch"] = prematch_tournaments
        out["tournaments_live"] = live_tournaments
    return out


async def count_bet9ja() -> dict:
    out = {"name": "Bet9ja", "country": "ng"}
    async with Bet9ja(country="ng") as b9:
        prematch = (await b9.get_sports()).get("D", {}).get("PAL", {})
        # Filter out non-regular books
        regular = {
            k: v for k, v in prematch.items()
            if "Antepost" not in v.get("S_DESC", "")
            and "Players" not in v.get("S_DESC", "")
            and "Zoom" not in v.get("S_DESC", "")
        }
        out["sports_total"] = len(regular)
        out["sports_with_prematch"] = sum(1 for v in regular.values() if v.get("NUM", 0) > 0)  # noqa: E501
        out["events_prematch"] = sum(v.get("NUM", 0) for v in regular.values())

        # Tournaments: count by walking SG (countries) -> G (tournaments) per sport
        prematch_tournaments = 0
        for v in regular.values():
            sg = v.get("SG", {}) or {}
            prematch_tournaments += sum(len(g.get("G", {}) or {}) for g in sg.values())
        out["tournaments_prematch"] = prematch_tournaments

        # Live — get_live_events returns D.E (events dict) AND D.G (groups
        # dict). D.G is the live-tournaments grouping keyed by group id; each
        # entry has a `DS` description (e.g. "Eredivisie-Zoom"). Count both.
        live = (await b9.get_live_sports()).get("D", {}).get("S", {}) or {}
        out["sports_with_live"] = len(live)
        live_events = 0
        live_tournaments = 0
        for sid in live.keys():
            try:
                D = (await b9.get_live_events(sport_id=str(sid))).get("D", {}) or {}
                live_events += len(D.get("E") or {})
                live_tournaments += len(D.get("G") or {})
            except Exception:
                pass
        out["events_live"] = live_events
        out["tournaments_live"] = live_tournaments
    return out


async def count_betway() -> dict:
    """Betway totals via the iter_all_prematch_events catalogue iterator.

    Static metadata (sports / live counts) comes from the sports list.
    Prematch enumeration delegates to the client's iterator which fans
    out per-league concurrently under MAX_CONCURRENT=50. Live tournament
    derivation still walks LiveInPlay per sport (no library iterator for
    live events yet).
    """
    out = {"name": "Betway", "country": "ng"}
    async with Betway(country="ng") as bw:
        sports = [
            s for s in (await bw.get_sports()).get("sports", [])
            if s.get("sportType") == "Sport"
        ]
        out["sports_total"] = len(sports)
        out["sports_with_prematch"] = sum(
            1 for s in sports if s.get("hasUpcomingEvents", False)
        )
        out["sports_with_live"] = sum(
            1 for s in sports if s.get("liveInPlayCount", 0) > 0
        )
        out["events_live"] = sum(s.get("liveInPlayCount", 0) for s in sports)

        event_ids: set = set()
        league_pairs: set = set()
        async for ev in bw.iter_all_prematch_events():
            event_ids.add(ev.event_id)
            league_pairs.add((ev.sport_id, ev.league_id))
        out["events_prematch"] = len(event_ids)
        out["tournaments_prematch"] = len(league_pairs)

        # Live tournaments: walk LiveInPlay per sport with live activity.
        live_league_ids: set = set()
        for s in sports:
            if s.get("liveInPlayCount", 0) == 0:
                continue
            sid = s.get("sportId")
            if not sid:
                continue
            skip = 0
            while True:
                try:
                    page = await bw.get_live_events(
                        sport_id=sid, skip=skip, take=100
                    )
                except Exception:
                    break
                evs = page.get("events", []) or []
                for e in evs:
                    if not isinstance(e, dict):
                        continue
                    lid = e.get("leagueId")
                    if lid:
                        live_league_ids.add((sid, lid))
                if page.get("isFinalPage", True) or len(evs) < 100:
                    break
                skip += 100
        out["tournaments_live"] = len(live_league_ids)
    return out


async def count_msport() -> dict:
    """MSport totals via the iter_all_prematch_events catalogue iterator."""
    out = {"name": "MSport", "country": "ng"}
    async with MSport(country="ng") as ms:
        prematch = (await ms.get_sports()).get("data", {}).get("sports", [])
        live = (await ms.get_live_sports()).get("data", {}).get("sports", [])
        out["sports_total"] = len(prematch)
        out["sports_with_live"] = sum(1 for s in live if s.get("count", 0) > 0)
        out["events_live"] = sum(s.get("count", 0) for s in live)

        event_ids: set = set()
        sport_event_counts: dict = {}
        league_pairs: set = set()
        async for ev in ms.iter_all_prematch_events():
            event_ids.add(ev.event_id)
            league_pairs.add((ev.sport_id, ev.league_id))
            sport_event_counts[ev.sport_id] = (
                sport_event_counts.get(ev.sport_id, 0) + 1
            )
        out["sports_with_prematch"] = len(sport_event_counts)
        out["events_prematch"] = len(event_ids)
        out["tournaments_prematch"] = len(league_pairs)

        # Live: the live-matches/list endpoint already returns everything
        # (no cursor pagination needed). Walk per live sport.
        live_tournaments = 0
        for s in live:
            sid = s.get("sportId")
            if not sid:
                continue
            try:
                tours = (
                    (await ms.get_live_events(sport_id=sid))
                    .get("data", {})
                    .get("tournaments", [])
                )
                live_tournaments += len(tours)
            except Exception:
                pass
        out["tournaments_live"] = live_tournaments
    return out


async def count_sportpesa() -> dict:
    """SportPesa totals via the iter_all_prematch_events catalogue iterator.

    Prematch enumeration delegates to the navigation-tree + per-league
    fan-out inside ``SportPesa.iter_all_prematch_events``. Live counts
    come from ``/api/live/sports/{sid}/events/started`` per sport (the
    ``eventNumber`` counter on ``/api/live/sports`` is unreliable —
    observed returning all zeros even when sports clearly have in-play
    events). ``sports_total`` comes from the navigation tree (13 sports
    at writing) rather than the live-sports endpoint (9), because the
    navigation tree is the authoritative full-catalogue view.
    """
    out = {"name": "SportPesa", "country": "ke"}
    cookie = os.environ.get("SPORTPESA_COOKIE")
    if not cookie:
        return {"name": "SportPesa", "error": "SPORTPESA_COOKIE env var not set"}
    async with SportPesa(country="ke", cookie=cookie) as sp:
        # Navigation tree is the source of truth for the sport catalogue.
        try:
            nav = await sp.get_navigation()
        except Exception as e:
            return {"name": "SportPesa", "error": f"get_navigation failed: {e!r}"}
        out["sports_total"] = len(nav)

        # Prematch: delegate to the iterator.
        prematch_event_ids: set = set()
        league_pairs: set = set()
        sport_event_counts: dict = {}
        async for ev in sp.iter_all_prematch_events():
            prematch_event_ids.add(ev.event_id)
            league_pairs.add((ev.sport_id, ev.league_id))
            sport_event_counts[ev.sport_id] = (
                sport_event_counts.get(ev.sport_id, 0) + 1
            )
        out["sports_with_prematch"] = len(sport_event_counts)
        out["tournaments_prematch"] = len(league_pairs)
        out["events_prematch"] = len(prematch_event_ids)

        # Live: walk /api/live/sports/{sid}/events/started per live sport.
        try:
            live_sports = (await sp.get_sports()).get("sports", []) or []
        except Exception:
            live_sports = []

        async def _live_started(sid: str) -> list:
            try:
                resp = await sp.get_live_events_started(sport_id=sid)
                return resp.get("events", []) or []
            except Exception:
                return []

        live_walks = await asyncio.gather(
            *[_live_started(str(s.get("id"))) for s in live_sports]
        )
        live_event_ids: set = set()
        live_tournament_ids: set = set()
        sports_with_live = 0
        for evs in live_walks:
            if evs:
                sports_with_live += 1
            for e in evs:
                eid = e.get("id")
                if eid is not None:
                    live_event_ids.add(eid)
                tour = e.get("tournament") or {}
                tid = tour.get("id")
                if tid is not None:
                    live_tournament_ids.add(tid)
        out["sports_with_live"] = sports_with_live
        out["events_live"] = len(live_event_ids)
        out["tournaments_live"] = len(live_tournament_ids)
    return out


async def count_betika() -> dict:
    """Betika totals via iter_all_prematch_events plus get_live_matches.

    Betika is country-agnostic at the API layer; pick any supported code.
    No warmed cookies are needed — the API is open.
    """
    out = {"name": "Betika", "country": "ke"}
    async with Betika(country="ke") as bk:
        try:
            sports = (await bk.get_sports()).get("data", []) or []
        except Exception:
            sports = []
        out["sports_total"] = len(sports)

        prematch_event_ids: set = set()
        league_ids: set = set()
        async for ev in bk.iter_all_prematch_events():
            prematch_event_ids.add(ev.event_id)
            if ev.league_id:
                league_ids.add(ev.league_id)
        out["tournaments_prematch"] = len(league_ids)
        out["events_prematch"] = len(prematch_event_ids)

        live_event_ids: set = set()
        live_competition_ids: set = set()
        page = 1
        while True:
            try:
                resp = await bk.get_live_matches(page=page, limit=100)
            except Exception:
                break
            data = (resp.get("data") or []) if isinstance(resp, dict) else []
            for ev in data:
                mid = ev.get("match_id")
                if mid is not None:
                    live_event_ids.add(str(mid))
                cid = ev.get("competition_id")
                if cid is not None:
                    live_competition_ids.add(str(cid))
            meta = resp.get("meta") if isinstance(resp, dict) else None
            total = meta.get("total") if isinstance(meta, dict) else 0
            if not isinstance(total, int) or page * 100 >= total:
                break
            page += 1
        out["events_live"] = len(live_event_ids)
        out["tournaments_live"] = len(live_competition_ids)
    return out


async def main():
    results = []
    for fn in (
        count_betpawa, count_sportybet, count_bet9ja,
        count_betway, count_msport, count_sportpesa, count_betika,
    ):
        try:
            r = await fn()
            results.append(r)
            print(f"[ok] {r['name']} done")
        except Exception as e:
            print(f"[err] {fn.__name__}: {e}")
            results.append({"name": fn.__name__.replace("count_", ""), "error": str(e)})

    print("\n" + "=" * 90)
    print(f"{'Bookmaker':<12} {'Sports':>7} {'Tour(P)':>8} {'Tour(L)':>8} {'Events(P)':>10} {'Events(L)':>10}")  # noqa: E501
    print("-" * 90)
    for r in results:
        if "error" in r:
            print(f"{r['name']:<12} ERROR: {r['error']}")
            continue
        sp = r.get("sports_total", "?")
        tp = r.get("tournaments_prematch", "?")
        tl = r.get("tournaments_live", "?")
        ep = r.get("events_prematch")
        el = r.get("events_live", "?")
        ep_str = "n/a" if ep is None else str(ep)
        print(f"{r['name']:<12} {sp:>7} {tp:>8} {tl:>8} {ep_str:>10} {el:>10}")
    print("=" * 90)
    print(
        "\nLegend: Tour(P)=prematch tournaments, Tour(L)=live tournaments, "
        "Events(P/L)=events totals"
    )


if __name__ == "__main__":
    asyncio.run(main())
