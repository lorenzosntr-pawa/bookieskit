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

from bookieskit import Bet9ja, BetPawa, Betway, MSport, SportPesa, SportyBet


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
    """Betway has no per-sport upcoming count and its Highlights endpoint
    caps at 29 events and ignores `skip`. The only way to get an accurate
    prematch event total is to fan out (region, league) calls per sport
    (the BetBook/Filtered endpoint, which paginates honestly per league).

    The fan-out is bounded by Betway's MAX_CONCURRENT=50 semaphore, so this
    runs in a handful of seconds even though it issues hundreds of HTTP
    calls. Live tournaments are derived the same way: collect distinct
    `league` ids from live events surfaced by Highlights/Filtered.
    """
    out = {"name": "Betway", "country": "ng"}
    async with Betway(country="ng") as bw:
        sports = [s for s in (await bw.get_sports()).get("sports", []) if s.get("sportType") == "Sport"]  # noqa: E501
        out["sports_total"] = len(sports)
        out["sports_with_prematch"] = sum(1 for s in sports if s.get("hasUpcomingEvents", False))  # noqa: E501
        out["sports_with_live"] = sum(1 for s in sports if s.get("liveInPlayCount", 0) > 0)  # noqa: E501
        out["events_live"] = sum(s.get("liveInPlayCount", 0) for s in sports)

        # Walk each sport's regions/leagues once. We use the result for
        # both tournaments_prematch (count of leagues) and events_prematch
        # (fan out get_events per league).
        prematch_tournaments = 0
        # (sport_id, region_id, league_id) tuples for per-league fan-out
        league_calls: list[tuple[str, str, str]] = []
        for s in sports:
            sid = s.get("sportId")
            if not sid:
                continue
            try:
                regions = (await bw.get_countries(sport_id=sid)).get("regions", [])
            except Exception:
                continue
            for r in regions:
                rid = r.get("regionId")
                if not rid:
                    continue
                leagues = r.get("leagues", []) or []
                prematch_tournaments += len(leagues)
                for lg in leagues:
                    lid = lg.get("leagueId")
                    if lid:
                        league_calls.append((sid, rid, lid))
        out["tournaments_prematch"] = prematch_tournaments

        async def _league_event_count(sid: str, rid: str, lid: str) -> int:
            try:
                r = await bw.get_events(
                    region_id=rid, league_id=lid, sport_id=sid, take=100
                )
                return len(r.get("events", []) or [])
            except Exception:
                return 0

        # Run all per-league calls concurrently; the client's semaphore
        # (MAX_CONCURRENT=50) gates in-flight requests automatically.
        if league_calls:
            counts = await asyncio.gather(
                *[_league_event_count(*c) for c in league_calls]
            )
            out["events_prematch"] = sum(counts)
        else:
            out["events_prematch"] = 0

        # Live tournaments: walk get_live_events per sport with live activity,
        # collect distinct leagueIds. The LiveInPlay endpoint paginates honestly
        # and requires `sportId` + `marketTypes`.
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
    """MSport totals via cursor-paginated sports-matches-list walk.

    MSport's `/sports-matches-list?sportId=N` returns ~50 events / ~12
    tournaments per page by default and exposes a `lastEventId` cursor for
    pagination (the `count` field on `/sports` is misleadingly zero for
    every sport, hence the per-sport walk).

    To get accurate totals we paginate per sport: pass `last_event_id`
    plus `limit=100` until the next call adds no new events. Without
    pagination the script reported only ~131 tournaments / ~668 events —
    in reality MSport carries ~1000+ events for soccer alone.
    """
    out = {"name": "MSport", "country": "ng"}
    async with MSport(country="ng") as ms:
        prematch = (await ms.get_sports()).get("data", {}).get("sports", [])
        live = (await ms.get_live_sports()).get("data", {}).get("sports", [])
        out["sports_total"] = len(prematch)
        out["sports_with_live"] = sum(1 for s in live if s.get("count", 0) > 0)
        out["events_live"] = sum(s.get("count", 0) for s in live)

        async def _walk_sport(sport_id: str) -> tuple[set, set]:
            """Walk all pages for one sport; returns (event_ids, tournament_ids)."""
            event_ids: set = set()
            tournament_ids: set = set()
            last_id: str | None = None
            for _ in range(100):  # safety
                try:
                    resp = await ms.get_events(
                        sport_id=sport_id, last_event_id=last_id, limit=100
                    )
                except Exception:
                    break
                data = resp.get("data") or {}
                tours = data.get("tournaments") or []
                new_event_count = 0
                for t in tours:
                    tid = t.get("tournamentId")
                    if tid is not None:
                        tournament_ids.add(tid)
                    for e in t.get("events") or []:
                        eid = e.get("eventId")
                        if eid and eid not in event_ids:
                            event_ids.add(eid)
                            new_event_count += 1
                next_cursor = data.get("lastEventId")
                # Terminate when no progress is made or no cursor returned.
                if not tours or new_event_count == 0 or next_cursor == last_id:
                    break
                last_id = next_cursor
            return event_ids, tournament_ids

        # Fan out the per-sport walks concurrently. MSport's MAX_CONCURRENT=50
        # caps in-flight requests.
        walks = await asyncio.gather(
            *[_walk_sport(s.get("sportId")) for s in prematch if s.get("sportId")]
        )
        prematch_event_ids: set = set()
        prematch_tournament_ids: set = set()
        sports_with_prematch = 0
        for evs, tours in walks:
            if evs:
                sports_with_prematch += 1
            prematch_event_ids |= evs
            prematch_tournament_ids |= tours
        out["sports_with_prematch"] = sports_with_prematch
        out["events_prematch"] = len(prematch_event_ids)
        out["tournaments_prematch"] = len(prematch_tournament_ids)

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
    """SportPesa totals via navigation-tree walk.

    Strategy:
    - ``/api/navigation`` returns the full sport → country → league tree.
      Use that to enumerate every league SportPesa exposes (302 across
      13 sports as of writing).
    - For each league, ``get_events(sport_id=S, league_id=L)`` returns
      the full league catalogue. The ``leagueId`` filter walks past the
      rolling-100-event window that limits per-sport calls (verified
      empirically — ``competitionId`` does NOT, it is silently ignored).
    - Run all per-league calls concurrently. SportPesa's
      ``MAX_CONCURRENT=15`` semaphore caps in-flight requests.
    - ``/api/live/sports`` is used for live counts (it carries per-sport
      ``eventNumber`` plus the live-tournaments grouping derivation).

    This is the only known path to the complete SportPesa prematch
    catalogue. The rolling-window cap discussion in earlier versions of
    this docstring still applies to the per-sport ``/api/upcoming/games``
    call, but ``leagueId``-filtered calls bypass it cleanly.
    """
    out = {"name": "SportPesa", "country": "ke"}
    cookie = os.environ.get("SPORTPESA_COOKIE")
    if not cookie:
        return {"name": "SportPesa", "error": "SPORTPESA_COOKIE env var not set"}
    async with SportPesa(country="ke") as sp:
        sp._http_client.headers["cookie"] = cookie

        # Navigation tree drives the catalogue enumeration.
        try:
            nav = await sp.get_navigation()
        except Exception as e:
            return {"name": "SportPesa", "error": f"get_navigation failed: {e!r}"}
        out["sports_total"] = len(nav)

        # Live: /api/live/sports lists the sports, then for each sport we
        # call /api/live/sports/{sid}/events/started for the authoritative
        # in-play event list. The `eventNumber` field on /api/live/sports
        # is a separately-cached counter that is unreliable (observed
        # returning all zeros even when sports clearly have in-play events).
        try:
            live_resp = await sp.get_sports()
            live_sports = live_resp.get("sports", []) or []
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

        # Build the per-league call list from navigation.
        league_calls: list[tuple[str, str]] = []  # (sport_id, league_id)
        sports_with_leagues = set()
        for sport in nav:
            sid = str(sport.get("id"))
            if not sport.get("has_matches"):
                continue
            for country in sport.get("countries", []) or []:
                for league in country.get("leagues", []) or []:
                    lid = league.get("id")
                    if lid is not None:
                        league_calls.append((sid, str(lid)))
                        sports_with_leagues.add(sid)

        out["tournaments_prematch"] = len(league_calls)

        async def _fetch_league(sid: str, lid: str) -> tuple[str, str, list]:
            try:
                events = await sp.get_events(
                    sport_id=sid, league_id=lid, pag_count=100
                )
                return sid, lid, events if isinstance(events, list) else []
            except Exception:
                return sid, lid, []

        # Concurrent per-league fan-out (semaphore-bounded).
        results = await asyncio.gather(
            *[_fetch_league(sid, lid) for sid, lid in league_calls]
        )

        prematch_event_ids: set = set()
        sports_with_prematch = set()
        for sid, lid, events in results:
            for g in events:
                gid = g.get("id")
                if gid is not None:
                    prematch_event_ids.add(gid)
            if events:
                sports_with_prematch.add(sid)

        out["sports_with_prematch"] = len(sports_with_prematch)
        out["events_prematch"] = len(prematch_event_ids)

        # Live tournaments come from the same started-events walk above.
        # Using `/api/live/sports/{sid}/events/started` is authoritative
        # (vs the older /api/highlights/{sid}?live=true which mixed
        # in-play with about-to-start "highlight" events and had no
        # `started`/`live` flag to filter on).
        out["tournaments_live"] = len(live_tournament_ids)
    return out


async def main():
    results = []
    for fn in (
        count_betpawa, count_sportybet, count_bet9ja,
        count_betway, count_msport, count_sportpesa,
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
