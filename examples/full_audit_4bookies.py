"""Full audit: Sports, Tournaments, Events for all 4 bookmakers (prematch + live)."""

import asyncio

from bookieskit import BetPawa, SportyBet, Bet9ja, Betway


async def audit_betpawa():
    print("\n" + "=" * 60)
    print("  BETPAWA")
    print("=" * 60)

    async with BetPawa(country="ng") as bp:
        # PREMATCH
        print("\n  --- PREMATCH ---")
        sports = await bp.get_sports()
        sport_list = sports.get("onlyMeta", [])
        print(f"  Sports: {len(sport_list)}")
        for s in sport_list:
            cat = s["category"]
            upcoming = s.get("eventCounts", {}).get("upcoming", 0)
            live = s.get("eventCounts", {}).get("live", 0)
            print(f"    {cat['name']} (id: {cat['id']}) - {upcoming} prematch, {live} live")

        # Football tournaments
        countries = await bp.get_countries(sport_id="2")
        regions = countries.get("withRegions", [{}])[0].get("regions", [])
        print(f"\n  Football Regions: {len(regions)}")
        total_comps = sum(len(r.get("competitions", [])) for r in regions)
        print(f"  Total Tournaments: {total_comps}")
        for r in regions[:5]:
            region_info = r.get("region", {})
            comps = r.get("competitions", [])
            comp_names = ", ".join(c.get("competition", {}).get("name", "?") for c in comps[:3])
            print(f"    {region_info.get('name')} ({len(comps)}): {comp_names}")
        if len(regions) > 5:
            print(f"    ... +{len(regions)-5} more regions")

        # Sample events
        events = await bp.get_events(tournament_id="11965")
        responses = events.get("responses", [])
        ev_list = responses[0].get("responses", []) if responses else []
        print(f"\n  Premier League Events: {len(ev_list)}")
        for ev in ev_list[:3]:
            parts = ev.get("participants", [])
            if len(parts) >= 2:
                print(f"    {parts[0]['name']} vs {parts[1]['name']}")

        # LIVE
        print("\n  --- LIVE ---")
        events = await bp.get_events(event_type="LIVE", sport_id="2")
        responses = events.get("responses", [])
        ev_list = responses[0].get("responses", []) if responses else []
        print(f"  Live Football Events: {len(ev_list)}")
        for ev in ev_list[:3]:
            parts = ev.get("participants", [])
            comp = ev.get("competition", {}).get("name", "?")
            if len(parts) >= 2:
                print(f"    {parts[0]['name']} vs {parts[1]['name']} ({comp})")


async def audit_sportybet():
    print("\n" + "=" * 60)
    print("  SPORTYBET")
    print("=" * 60)

    async with SportyBet(country="ng") as sb:
        # PREMATCH
        print("\n  --- PREMATCH ---")
        sports_raw = await sb.get_sports(live=False)
        sport_list = sports_raw.get("data", {}).get("sportList", [])
        print(f"  Sports: {len(sport_list)}")
        for s in sport_list[:10]:
            print(f"    {s['name']} (id: {s['id']}) - {s.get('eventSize', 0)} events")
        if len(sport_list) > 10:
            print(f"    ... +{len(sport_list)-10} more")

        # Football tournaments
        countries_raw = await sb.get_countries(sport_id="sr:sport:1", live=False)
        cats = countries_raw.get("data", {}).get("sportList", [{}])[0].get("categories", [])
        total_tournaments = sum(len(c.get("tournaments", [])) for c in cats)
        print(f"\n  Football Countries: {len(cats)}")
        print(f"  Total Tournaments: {total_tournaments}")
        for c in cats[:5]:
            tournaments = c.get("tournaments", [])
            t_names = ", ".join(t.get("name", "?") for t in tournaments[:3])
            print(f"    {c['name']} ({len(tournaments)}): {t_names}")
        if len(cats) > 5:
            print(f"    ... +{len(cats)-5} more countries")

        # Sample events
        events = await sb.get_events(tournament_id="sr:tournament:17")
        ev_data = events.get("data", [{}])
        ev_list = ev_data[0].get("events", []) if ev_data else []
        print(f"\n  Premier League Events: {len(ev_list)}")
        for ev in ev_list[:3]:
            print(f"    {ev.get('homeTeamName')} vs {ev.get('awayTeamName')}")

        # LIVE
        print("\n  --- LIVE ---")
        sports_raw = await sb.get_sports(live=True)
        sport_list = sports_raw.get("data", {}).get("sportList", [])
        print(f"  Live Sports: {len(sport_list)}")
        for s in sport_list[:8]:
            print(f"    {s['name']} - {s.get('eventSize', 0)} live events")
        if len(sport_list) > 8:
            print(f"    ... +{len(sport_list)-8} more")

        # Live football countries
        countries_raw = await sb.get_countries(sport_id="sr:sport:1", live=True)
        cats = countries_raw.get("data", {}).get("sportList", [{}])[0].get("categories", [])
        print(f"  Live Football Countries: {len(cats)}")
        for c in cats[:5]:
            for t in c.get("tournaments", []):
                print(f"    {c['name']}/{t['name']}")


async def audit_bet9ja():
    print("\n" + "=" * 60)
    print("  BET9JA")
    print("=" * 60)

    async with Bet9ja(country="ng") as b9:
        # PREMATCH
        print("\n  --- PREMATCH ---")
        sports_raw = await b9.get_sports(live=False)
        pal = sports_raw.get("D", {}).get("PAL", {})
        regular = {k: v for k, v in pal.items()
                   if "Antepost" not in v.get("S_DESC", "")
                   and "Players" not in v.get("S_DESC", "")
                   and "Zoom" not in v.get("S_DESC", "")}
        print(f"  Sports: {len(regular)} (excluding Antepost/Players/Zoom)")
        for key, item in list(regular.items())[:10]:
            print(f"    {item['S_DESC']} (id: {key}) - {item.get('NUM', 0)} events")
        if len(regular) > 10:
            print(f"    ... +{len(regular)-10} more")

        # Soccer tournaments
        soccer = pal.get("1", {})
        sg = soccer.get("SG", {})
        total_tournaments = sum(len(g.get("G", {})) for g in sg.values())
        print(f"\n  Soccer Countries: {len(sg)}")
        print(f"  Total Tournaments: {total_tournaments}")
        for gid in list(sg.keys())[:5]:
            group = sg[gid]
            lang = group.get("SG_LANG", {})
            name = lang.get("en", "?")
            sub = group.get("G", {})
            t_names = ", ".join(t.get("G_DESC", "?") for t in list(sub.values())[:3])
            print(f"    {name} ({len(sub)}): {t_names}")
        if len(sg) > 5:
            print(f"    ... +{len(sg)-5} more countries")

        # Sample events (Premier League)
        events = await b9.get_events(tournament_id="170880")
        ev_list = events.get("D", {}).get("E", [])
        print(f"\n  Premier League Events: {len(ev_list)}")
        for ev in ev_list[:3]:
            print(f"    {ev.get('DS', '?')}")

        # LIVE
        print("\n  --- LIVE ---")
        sports_raw = await b9.get_sports(live=True)
        pal = sports_raw.get("D", {}).get("PAL", {})
        live_sports = {k: v for k, v in pal.items()
                       if v.get("NUM", 0) > 0
                       and "Players" not in v.get("S_DESC", "")
                       and "Zoom" not in v.get("S_DESC", "")}
        print(f"  Live Sports: {len(live_sports)}")
        for key, item in list(live_sports.items())[:8]:
            print(f"    {item['S_DESC']} - {item.get('NUM', 0)} live events")
        if len(live_sports) > 8:
            print(f"    ... +{len(live_sports)-8} more")


async def audit_betway():
    print("\n" + "=" * 60)
    print("  BETWAY")
    print("=" * 60)

    async with Betway(country="ng") as bw:
        # PREMATCH
        print("\n  --- PREMATCH ---")
        sports = await bw.get_sports()
        sport_list = [s for s in sports.get("sports", []) if s.get("sportType") == "Sport"]
        print(f"  Sports: {len(sport_list)}")
        for s in sport_list[:10]:
            live = s.get("liveInPlayCount", 0)
            has_upcoming = s.get("hasUpcomingEvents", False)
            print(f"    {s['name']} (id: {s['sportId']}) - live: {live}, upcoming: {has_upcoming}")
        if len(sport_list) > 10:
            print(f"    ... +{len(sport_list)-10} more")

        # Soccer regions/leagues
        countries = await bw.get_countries(sport_id="soccer")
        regions = countries.get("regions", [])
        total_leagues = sum(len(r.get("leagues", [])) for r in regions)
        print(f"\n  Soccer Regions: {len(regions)}")
        print(f"  Total Leagues: {total_leagues}")
        for r in regions[:5]:
            leagues = r.get("leagues", [])
            l_names = ", ".join(l.get("name", "?") for l in leagues[:3])
            print(f"    {r['name']} ({len(leagues)}): {l_names}")
        if len(regions) > 5:
            print(f"    ... +{len(regions)-5} more regions")

        # Sample events (UCL)
        events = await bw.get_events(league_id="international-clubs_uefa-champions-league")
        ev_list = events.get("events", [])
        print(f"\n  UCL Events: {len(ev_list)}")
        for ev in ev_list[:3]:
            print(f"    {ev.get('homeTeam')} vs {ev.get('awayTeam')}")

        # LIVE
        print("\n  --- LIVE ---")
        events = await bw.get_events(sport_id="soccer", market_types="[Win/Draw/Win]")
        all_events = events.get("events", [])
        live_events = [e for e in all_events if e.get("isLive")]
        print(f"  Live Soccer Events (from highlights): {len(live_events)}")
        for ev in live_events[:5]:
            print(f"    {ev.get('homeTeam')} vs {ev.get('awayTeam')} ({ev.get('league', '?')})")

        # Live sports counts from config
        print(f"\n  Live Sports (from config):")
        for s in sport_list[:10]:
            live = s.get("liveInPlayCount", 0)
            if live > 0:
                print(f"    {s['name']} - {live} live")


async def main():
    print("*" * 60)
    print("*  BOOKIESKIT v0.3.0 - FULL 4-BOOKMAKER AUDIT             *")
    print("*  Sports -> Tournaments -> Events (Prematch + Live)       *")
    print("*" * 60)

    await audit_betpawa()
    await audit_sportybet()
    await audit_bet9ja()
    await audit_betway()

    print("\n\n" + "*" * 60)
    print("*  AUDIT COMPLETE                                         *")
    print("*" * 60)


if __name__ == "__main__":
    asyncio.run(main())
