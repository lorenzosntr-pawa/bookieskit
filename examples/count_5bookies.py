"""Quick totals audit: sports / tournaments / events for all 5 bookmakers.

Strategy: single API call per (bookmaker, prematch/live) where possible.
Event totals come from per-sport counts in the sports response; tournament
totals iterate over sports (for soccer only — full enumeration would be many
calls per bookmaker).
"""

import asyncio

from bookieskit import Bet9ja, BetPawa, Betway, MSport, SportyBet


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
        # Tournament total: iterate ALL sports
        prematch_tournaments = 0
        live_tournaments = 0
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
        out["tournaments_prematch"] = prematch_tournaments
        out["tournaments_live"] = live_tournaments  # BetPawa doesn't expose live tournaments distinctly
    return out


async def count_sportybet() -> dict:
    out = {"name": "SportyBet", "country": "ng"}
    async with SportyBet(country="ng") as sb:
        prematch_sports = (await sb.get_sports(live=False)).get("data", {}).get("sportList", [])
        live_sports = (await sb.get_sports(live=True)).get("data", {}).get("sportList", [])
        out["sports_total"] = len(prematch_sports)
        out["sports_with_prematch"] = sum(1 for s in prematch_sports if s.get("eventSize", 0) > 0)
        out["sports_with_live"] = sum(1 for s in live_sports if s.get("eventSize", 0) > 0)
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
        out["sports_with_prematch"] = sum(1 for v in regular.values() if v.get("NUM", 0) > 0)
        out["events_prematch"] = sum(v.get("NUM", 0) for v in regular.values())

        # Tournaments: count by walking SG (countries) -> G (tournaments) per sport
        prematch_tournaments = 0
        for v in regular.values():
            sg = v.get("SG", {}) or {}
            prematch_tournaments += sum(len(g.get("G", {}) or {}) for g in sg.values())
        out["tournaments_prematch"] = prematch_tournaments

        # Live
        live = (await b9.get_live_sports()).get("D", {}).get("S", {}) or {}
        out["sports_with_live"] = len(live)
        # Bet9ja live: fetch events per live sport and count D.E entries
        live_events = 0
        for sid in live.keys():
            try:
                ev = (await b9.get_live_events(sport_id=str(sid))).get("D", {}).get("E", {}) or {}
                live_events += len(ev)
            except Exception:
                pass
        out["events_live"] = live_events
        out["tournaments_live"] = 0  # Bet9ja live shape doesn't expose tournament counts here
    return out


async def count_betway() -> dict:
    out = {"name": "Betway", "country": "ng"}
    async with Betway(country="ng") as bw:
        sports = [s for s in (await bw.get_sports()).get("sports", []) if s.get("sportType") == "Sport"]
        out["sports_total"] = len(sports)
        out["sports_with_prematch"] = sum(1 for s in sports if s.get("hasUpcomingEvents", False))
        out["sports_with_live"] = sum(1 for s in sports if s.get("liveInPlayCount", 0) > 0)
        out["events_live"] = sum(s.get("liveInPlayCount", 0) for s in sports)
        # Betway doesn't surface a per-sport upcoming count — leave None
        out["events_prematch"] = None

        # Tournaments: iterate each sport's regions/leagues
        prematch_tournaments = 0
        for s in sports:
            sid = s.get("sportId")
            if not sid:
                continue
            try:
                regions = (await bw.get_countries(sport_id=sid)).get("regions", [])
                prematch_tournaments += sum(len(r.get("leagues", [])) for r in regions)
            except Exception:
                pass
        out["tournaments_prematch"] = prematch_tournaments
        out["tournaments_live"] = 0
    return out


async def count_msport() -> dict:
    out = {"name": "MSport", "country": "ng"}
    async with MSport(country="ng") as ms:
        prematch = (await ms.get_sports()).get("data", {}).get("sports", [])
        live = (await ms.get_live_sports()).get("data", {}).get("sports", [])
        out["sports_total"] = len(prematch)
        out["sports_with_prematch"] = sum(1 for s in prematch if s.get("count", 0) > 0)
        out["sports_with_live"] = sum(1 for s in live if s.get("count", 0) > 0)
        out["events_prematch"] = sum(s.get("count", 0) for s in prematch)
        out["events_live"] = sum(s.get("count", 0) for s in live)

        # MSport bundles tournaments+events per sport call — iterate sports
        # The /sports endpoint returns count=0 universally; real counts are inside
        # the per-sport sports-matches-list payload.
        prematch_tournaments = 0
        prematch_events = 0
        for s in prematch:
            sid = s.get("sportId")
            if not sid:
                continue
            try:
                tours = (await ms.get_events(sport_id=sid)).get("data", {}).get("tournaments", [])
                prematch_tournaments += len(tours)
                prematch_events += sum(len(t.get("events", []) or []) for t in tours)
            except Exception:
                pass
        live_tournaments = 0
        for s in live:
            sid = s.get("sportId")
            if not sid:
                continue
            try:
                tours = (await ms.get_live_events(sport_id=sid)).get("data", {}).get("tournaments", [])
                live_tournaments += len(tours)
            except Exception:
                pass
        out["tournaments_prematch"] = prematch_tournaments
        out["tournaments_live"] = live_tournaments
        out["events_prematch"] = prematch_events  # override the meaningless 0
    return out


async def main():
    results = []
    for fn in (count_betpawa, count_sportybet, count_bet9ja, count_betway, count_msport):
        try:
            r = await fn()
            results.append(r)
            print(f"[ok] {r['name']} done")
        except Exception as e:
            print(f"[err] {fn.__name__}: {e}")
            results.append({"name": fn.__name__.replace("count_", ""), "error": str(e)})

    print("\n" + "=" * 90)
    print(f"{'Bookmaker':<12} {'Sports':>7} {'Tour(P)':>8} {'Tour(L)':>8} {'Events(P)':>10} {'Events(L)':>10}")
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
    print("\nLegend: Tour(P)=prematch tournaments, Tour(L)=live tournaments, Events(P/L)=events totals")


if __name__ == "__main__":
    asyncio.run(main())
