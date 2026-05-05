"""Final audit: Sports, Tournaments, Events (prematch + live) for all 4 bookmakers."""

import asyncio

from bookieskit import Bet9ja, BetPawa, Betway, SportyBet


async def main():
    print("*" * 60)
    print("*  BOOKIESKIT v0.3.0 - FINAL AUDIT                        *")
    print("*" * 60)

    # ================================================================
    # BETPAWA
    # ================================================================
    print(f"\n{'=' * 60}")
    print("  BETPAWA")
    print(f"{'=' * 60}")

    async with BetPawa(country="ng") as bp:
        sports = await bp.get_sports()
        sport_list = sports.get("onlyMeta", [])

        print("\n  PREMATCH")
        print(f"  Sports: {len(sport_list)}")
        total_prematch = 0
        for s in sport_list:
            cat = s["category"]
            n = s.get("eventCounts", {}).get("upcoming", 0)
            total_prematch += n
            print(f"    {cat['name']} - {n} events")

        countries = await bp.get_countries(sport_id="2")
        regions = countries.get("withRegions", [{}])[0].get("regions", [])
        total_t = sum(len(r.get("competitions", [])) for r in regions)
        print(f"  Football: {len(regions)} regions, {total_t} tournaments")

        events = await bp.get_events(tournament_id="11965")
        responses = events.get("responses", [])
        pl = responses[0].get("responses", []) if responses else []
        print(f"  Premier League: {len(pl)} events")
        for ev in pl[:3]:
            p = ev.get("participants", [])
            if len(p) >= 2:
                print(f"    {p[0]['name']} vs {p[1]['name']}")

        print("\n  LIVE")
        total_live = 0
        for s in sport_list:
            cat = s["category"]
            n = s.get("eventCounts", {}).get("live", 0)
            if n > 0:
                total_live += n
                print(f"    {cat['name']} - {n} live")
        if total_live == 0:
            print("    No live events")

        print(f"\n  TOTALS: {total_prematch} prematch, {total_live} live")

    # ================================================================
    # SPORTYBET
    # ================================================================
    print(f"\n{'=' * 60}")
    print("  SPORTYBET")
    print(f"{'=' * 60}")

    async with SportyBet(country="ng") as sb:
        sports_raw = await sb.get_sports(live=False)
        sport_list = sports_raw.get("data", {}).get("sportList", [])

        print("\n  PREMATCH")
        print(f"  Sports: {len(sport_list)}")
        total_prematch = 0
        for s in sport_list:
            n = s.get("eventSize", 0)
            total_prematch += n
            print(f"    {s['name']} - {n} events")

        countries_raw = await sb.get_countries(sport_id="sr:sport:1", live=False)
        cats = countries_raw.get("data", {}).get("sportList", [{}])[0].get("categories", [])  # noqa: E501
        total_t = sum(len(c.get("tournaments", [])) for c in cats)
        print(f"  Football: {len(cats)} regions, {total_t} tournaments")

        events = await sb.get_events(tournament_id="sr:tournament:17")
        ev_data = events.get("data", [{}])
        ev_list = ev_data[0].get("events", []) if ev_data else []
        print(f"  Premier League: {len(ev_list)} events")
        for ev in ev_list[:3]:
            print(f"    {ev.get('homeTeamName')} vs {ev.get('awayTeamName')}")

        print("\n  LIVE")
        sports_raw = await sb.get_sports(live=True)
        sport_list_live = sports_raw.get("data", {}).get("sportList", [])
        total_live = 0
        for s in sport_list_live:
            n = s.get("eventSize", 0)
            if n > 0:
                total_live += n
                print(f"    {s['name']} - {n} live")

        print(f"\n  TOTALS: {total_prematch} prematch, {total_live} live")

    # ================================================================
    # BET9JA
    # ================================================================
    print(f"\n{'=' * 60}")
    print("  BET9JA")
    print(f"{'=' * 60}")

    async with Bet9ja(country="ng") as b9:
        exclude = ["Antepost", "Players", "Zoom", "Specials", "Round Specials"]

        sports_raw = await b9.get_sports()
        pal = sports_raw.get("D", {}).get("PAL", {})

        print("\n  PREMATCH")
        real_sports = {k: v for k, v in pal.items()
                       if not any(x in v.get("S_DESC", "") for x in exclude)
                       and v.get("NUM", 0) > 0}
        print(f"  Sports: {len(real_sports)}")
        total_prematch = 0
        for v in real_sports.values():
            total_prematch += v.get("NUM", 0)
            print(f"    {v['S_DESC']} - {v.get('NUM', 0)} events")

        soccer = pal.get("1", {})
        sg = soccer.get("SG", {})
        total_t = sum(len(g.get("G", {})) for g in sg.values())
        print(f"  Soccer: {len(sg)} regions, {total_t} tournaments")

        events = await b9.get_events(tournament_id="170880")
        ev_list = events.get("D", {}).get("E", [])
        print(f"  Premier League: {len(ev_list)} events")
        for ev in ev_list[:3]:
            print(f"    {ev.get('DS')}")

        print("\n  LIVE")
        live_raw = await b9.get_live_events()
        live_d = live_raw.get("D", {})
        live_sports = live_d.get("S", {})
        live_events = live_d.get("E", {})

        sport_counts = {}
        for ev in live_events.values():
            sid = str(ev.get("SID", ""))
            name = live_sports.get(sid, {}).get("S_DESC", f"id:{sid}")
            sport_counts[name] = sport_counts.get(name, 0) + 1

        total_live = len(live_events)
        for name, count in sorted(sport_counts.items(), key=lambda x: -x[1]):
            print(f"    {name} - {count} live")
        if not sport_counts:
            print("    No live events")

        print(f"\n  TOTALS: {total_prematch} prematch, {total_live} live")

    # ================================================================
    # BETWAY
    # ================================================================
    print(f"\n{'=' * 60}")
    print("  BETWAY")
    print(f"{'=' * 60}")

    async with Betway(country="ng") as bw:
        sports = await bw.get_sports()
        sport_list = [s for s in sports.get("sports", [])
                      if s.get("sportType") == "Sport"]

        print("\n  PREMATCH")
        print(f"  Sports: {len(sport_list)}")
        for s in sport_list:
            has = "yes" if s.get("hasUpcomingEvents") else "no"
            print(f"    {s['name']} - upcoming: {has}")

        countries = await bw.get_countries(sport_id="soccer")
        regions = countries.get("regions", [])
        total_leagues = sum(len(r.get("leagues", [])) for r in regions)
        print(f"  Soccer: {len(regions)} regions, {total_leagues} tournaments")

        events = await bw.get_events(
            region_id="england", league_id="premier-league"
        )
        ev_list = events.get("events", [])
        print(f"  Premier League: {len(ev_list)} events")
        for ev in ev_list[:3]:
            print(f"    {ev.get('homeTeam')} vs {ev.get('awayTeam')}")

        print("\n  LIVE")
        total_live = 0
        for s in sport_list:
            n = s.get("liveInPlayCount", 0)
            if n > 0:
                total_live += n
                print(f"    {s['name']} - {n} live")
        if total_live == 0:
            print("    No live events")

        print(f"\n  TOTALS: prematch N/A (no count), {total_live} live")

    # ================================================================
    # SUMMARY
    # ================================================================
    print(f"\n{'*' * 60}")
    print("*  AUDIT COMPLETE                                         *")
    print(f"{'*' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
