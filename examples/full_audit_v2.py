"""Full audit v2: Same structure for all 4 bookmakers (prematch + live)."""

import asyncio

from bookieskit import BetPawa, SportyBet, Bet9ja, Betway
from bookieskit.markets import parse_markets
from bookieskit.matching import extract_sportradar_id


async def audit_bookmaker(name, get_data_fn):
    """Run audit for a single bookmaker."""
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")

    data = await get_data_fn()

    # PREMATCH
    print(f"\n  --- PREMATCH ---")
    print(f"  Sports: {data['prematch']['sports_count']}")
    for s in data["prematch"]["sports"]:
        print(f"    {s['name']} - {s['events']} events")

    print(f"\n  Football Regions: {data['prematch']['regions_count']}")
    print(f"  Football Tournaments: {data['prematch']['tournaments_count']}")
    for t in data["prematch"]["sample_tournaments"][:8]:
        print(f"    {t}")
    if data["prematch"]["regions_count"] > 8:
        print(f"    ... +{data['prematch']['regions_count'] - 8} more regions")

    print(f"\n  Premier League Events: {data['prematch']['pl_events_count']}")
    for ev in data["prematch"]["pl_events"][:5]:
        print(f"    {ev}")

    # LIVE
    print(f"\n  --- LIVE ---")
    print(f"  Live Sports: {data['live']['sports_count']}")
    for s in data["live"]["sports"]:
        print(f"    {s['name']} - {s['events']} live")

    print(f"\n  Live Football Events: {data['live']['football_events_count']}")
    for ev in data["live"]["football_events"][:5]:
        print(f"    {ev}")
    if data["live"]["football_events_count"] > 5:
        print(f"    ... +{data['live']['football_events_count'] - 5} more")


async def get_betpawa_data():
    data = {"prematch": {}, "live": {}}

    async with BetPawa(country="ng") as bp:
        # PREMATCH - Sports
        sports = await bp.get_sports()
        sport_list = sports.get("onlyMeta", [])
        data["prematch"]["sports_count"] = len(sport_list)
        data["prematch"]["sports"] = [
            {"name": s["category"]["name"], "events": s.get("eventCounts", {}).get("upcoming", 0)}
            for s in sport_list
        ]

        # PREMATCH - Regions/Tournaments
        countries = await bp.get_countries(sport_id="2")
        regions = countries.get("withRegions", [{}])[0].get("regions", [])
        data["prematch"]["regions_count"] = len(regions)
        total_comps = sum(len(r.get("competitions", [])) for r in regions)
        data["prematch"]["tournaments_count"] = total_comps
        data["prematch"]["sample_tournaments"] = []
        for r in regions[:8]:
            ri = r.get("region", {})
            comps = r.get("competitions", [])
            for c in comps[:2]:
                ci = c.get("competition", {})
                data["prematch"]["sample_tournaments"].append(
                    f"{ri.get('name')}/{ci.get('name')}"
                )

        # PREMATCH - PL Events
        events = await bp.get_events(tournament_id="11965")
        responses = events.get("responses", [])
        ev_list = responses[0].get("responses", []) if responses else []
        data["prematch"]["pl_events_count"] = len(ev_list)
        data["prematch"]["pl_events"] = []
        for ev in ev_list[:5]:
            parts = ev.get("participants", [])
            if len(parts) >= 2:
                data["prematch"]["pl_events"].append(
                    f"{parts[0]['name']} vs {parts[1]['name']}"
                )

        # LIVE - Sports
        live_sports = []
        for s in sport_list:
            cat = s["category"]
            live = s.get("eventCounts", {}).get("live", 0)
            if live > 0:
                live_sports.append({"name": cat["name"], "events": live})
        data["live"]["sports_count"] = len(live_sports)
        data["live"]["sports"] = live_sports

        # LIVE - Football events
        events = await bp.get_events(event_type="LIVE", sport_id="2")
        responses = events.get("responses", [])
        ev_list = responses[0].get("responses", []) if responses else []
        data["live"]["football_events_count"] = len(ev_list)
        data["live"]["football_events"] = []
        for ev in ev_list[:5]:
            parts = ev.get("participants", [])
            comp = ev.get("competition", {}).get("name", "?")
            if len(parts) >= 2:
                data["live"]["football_events"].append(
                    f"{parts[0]['name']} vs {parts[1]['name']} ({comp})"
                )

    return data


async def get_sportybet_data():
    data = {"prematch": {}, "live": {}}

    async with SportyBet(country="ng") as sb:
        # PREMATCH - Sports
        sports_raw = await sb.get_sports(live=False)
        sport_list = sports_raw.get("data", {}).get("sportList", [])
        data["prematch"]["sports_count"] = len(sport_list)
        data["prematch"]["sports"] = [
            {"name": s["name"], "events": s.get("eventSize", 0)}
            for s in sport_list
        ]

        # PREMATCH - Regions/Tournaments
        countries_raw = await sb.get_countries(sport_id="sr:sport:1", live=False)
        cats = countries_raw.get("data", {}).get("sportList", [{}])[0].get("categories", [])
        total_t = sum(len(c.get("tournaments", [])) for c in cats)
        data["prematch"]["regions_count"] = len(cats)
        data["prematch"]["tournaments_count"] = total_t
        data["prematch"]["sample_tournaments"] = []
        for c in cats[:8]:
            for t in c.get("tournaments", [])[:2]:
                data["prematch"]["sample_tournaments"].append(
                    f"{c['name']}/{t['name']}"
                )

        # PREMATCH - PL Events
        events = await sb.get_events(tournament_id="sr:tournament:17")
        ev_data = events.get("data", [{}])
        ev_list = ev_data[0].get("events", []) if ev_data else []
        data["prematch"]["pl_events_count"] = len(ev_list)
        data["prematch"]["pl_events"] = [
            f"{ev.get('homeTeamName')} vs {ev.get('awayTeamName')}"
            for ev in ev_list[:5]
        ]

        # LIVE - Sports
        sports_raw = await sb.get_sports(live=True)
        sport_list = sports_raw.get("data", {}).get("sportList", [])
        live_sports = [
            {"name": s["name"], "events": s.get("eventSize", 0)}
            for s in sport_list if s.get("eventSize", 0) > 0
        ]
        data["live"]["sports_count"] = len(live_sports)
        data["live"]["sports"] = live_sports

        # LIVE - Football events
        countries_raw = await sb.get_countries(sport_id="sr:sport:1", live=True)
        cats = countries_raw.get("data", {}).get("sportList", [{}])[0].get("categories", [])
        live_football = []
        for c in cats[:10]:
            for t in c.get("tournaments", [])[:2]:
                events = await sb.get_events(tournament_id=t["id"])
                ev_data = events.get("data", [{}])
                ev_list = ev_data[0].get("events", []) if ev_data else []
                for ev in ev_list[:2]:
                    live_football.append(
                        f"{ev.get('homeTeamName')} vs {ev.get('awayTeamName')} ({t['name']})"
                    )
                if len(live_football) >= 5:
                    break
            if len(live_football) >= 5:
                break
        data["live"]["football_events_count"] = sum(
            s["events"] for s in live_sports if s["name"] == "Football"
        )
        data["live"]["football_events"] = live_football[:5]

    return data


async def get_bet9ja_data():
    data = {"prematch": {}, "live": {}}

    async with Bet9ja(country="ng") as b9:
        # PREMATCH - Sports
        sports_raw = await b9.get_sports(live=False)
        pal = sports_raw.get("D", {}).get("PAL", {})
        regular = {k: v for k, v in pal.items()
                   if "Antepost" not in v.get("S_DESC", "")
                   and "Players" not in v.get("S_DESC", "")
                   and "Zoom" not in v.get("S_DESC", "")
                   and "Specials" not in v.get("S_DESC", "")}
        data["prematch"]["sports_count"] = len(regular)
        data["prematch"]["sports"] = [
            {"name": v["S_DESC"], "events": v.get("NUM", 0)}
            for v in regular.values() if v.get("NUM", 0) > 0
        ]

        # PREMATCH - Regions/Tournaments
        soccer = pal.get("1", {})
        sg = soccer.get("SG", {})
        total_t = sum(len(g.get("G", {})) for g in sg.values())
        data["prematch"]["regions_count"] = len(sg)
        data["prematch"]["tournaments_count"] = total_t
        data["prematch"]["sample_tournaments"] = []
        for gid in list(sg.keys())[:8]:
            group = sg[gid]
            lang = group.get("SG_LANG", {})
            name = lang.get("en", "?")
            sub = group.get("G", {})
            for t in list(sub.values())[:2]:
                data["prematch"]["sample_tournaments"].append(
                    f"{name}/{t.get('G_DESC', '?')}"
                )

        # PREMATCH - PL Events
        events = await b9.get_events(tournament_id="170880")
        ev_list = events.get("D", {}).get("E", [])
        data["prematch"]["pl_events_count"] = len(ev_list)
        data["prematch"]["pl_events"] = [
            ev.get("DS", "?") for ev in ev_list[:5]
        ]

        # LIVE - Sports
        sports_raw = await b9.get_sports(live=True)
        pal = sports_raw.get("D", {}).get("PAL", {})
        live_sports = [
            {"name": v["S_DESC"], "events": v.get("NUM", 0)}
            for v in pal.values()
            if v.get("NUM", 0) > 0
            and "Players" not in v.get("S_DESC", "")
            and "Zoom" not in v.get("S_DESC", "")
            and "Specials" not in v.get("S_DESC", "")
        ]
        data["live"]["sports_count"] = len(live_sports)
        data["live"]["sports"] = live_sports

        # LIVE - Football events
        soccer = pal.get("1", {})
        sg = soccer.get("SG", {})
        live_football = []
        total_live_football = soccer.get("NUM", 0)
        for gid, group in list(sg.items())[:10]:
            sub = group.get("G", {})
            for tid, t in sub.items():
                if t.get("NUM", 0) > 0:
                    events = await b9.get_events(tournament_id=tid)
                    ev_list = events.get("D", {}).get("E", [])
                    for ev in ev_list[:2]:
                        live_football.append(
                            f"{ev.get('DS', '?')} ({t.get('G_DESC', '?')})"
                        )
                    if len(live_football) >= 5:
                        break
            if len(live_football) >= 5:
                break
        data["live"]["football_events_count"] = total_live_football
        data["live"]["football_events"] = live_football[:5]

    return data


async def get_betway_data():
    data = {"prematch": {}, "live": {}}

    async with Betway(country="ng") as bw:
        # PREMATCH - Sports
        sports = await bw.get_sports()
        sport_list = [s for s in sports.get("sports", []) if s.get("sportType") == "Sport"]
        data["prematch"]["sports_count"] = len(sport_list)
        data["prematch"]["sports"] = [
            {"name": s["name"], "events": "yes" if s.get("hasUpcomingEvents") else "no"}
            for s in sport_list
        ]

        # PREMATCH - Regions/Tournaments
        countries = await bw.get_countries(sport_id="soccer")
        regions = countries.get("regions", [])
        total_leagues = sum(len(r.get("leagues", [])) for r in regions)
        data["prematch"]["regions_count"] = len(regions)
        data["prematch"]["tournaments_count"] = total_leagues
        data["prematch"]["sample_tournaments"] = []
        for r in regions[:8]:
            for l in r.get("leagues", [])[:2]:
                data["prematch"]["sample_tournaments"].append(
                    f"{r['name']}/{l['name']}"
                )

        # PREMATCH - PL Events
        events = await bw.get_events(region_id="england", league_id="premier-league")
        ev_list = events.get("events", [])
        data["prematch"]["pl_events_count"] = len(ev_list)
        data["prematch"]["pl_events"] = [
            f"{ev.get('homeTeam')} vs {ev.get('awayTeam')}"
            for ev in ev_list[:5]
        ]

        # LIVE - Sports
        live_sports = [
            {"name": s["name"], "events": s.get("liveInPlayCount", 0)}
            for s in sport_list if s.get("liveInPlayCount", 0) > 0
        ]
        data["live"]["sports_count"] = len(live_sports)
        data["live"]["sports"] = live_sports

        # LIVE - Football events
        # Betway doesn't have a direct live-only filter via Filtered endpoint
        # Use highlights and filter isLive
        events = await bw.get_events()
        all_events = events.get("events", [])
        live_events = [e for e in all_events if e.get("isLive")]
        data["live"]["football_events_count"] = next(
            (s["events"] for s in live_sports if s["name"] == "Soccer"), 0
        )
        data["live"]["football_events"] = [
            f"{ev.get('homeTeam')} vs {ev.get('awayTeam')} ({ev.get('league', '?')})"
            for ev in live_events[:5]
        ]

    return data


async def main():
    print("*" * 60)
    print("*  BOOKIESKIT v0.3.0 - FULL 4-BOOKMAKER AUDIT             *")
    print("*  Sports -> Tournaments -> Events (Prematch + Live)       *")
    print("*" * 60)

    await audit_bookmaker("BETPAWA", get_betpawa_data)
    await audit_bookmaker("SPORTYBET", get_sportybet_data)
    await audit_bookmaker("BET9JA", get_bet9ja_data)
    await audit_bookmaker("BETWAY", get_betway_data)

    print("\n\n" + "*" * 60)
    print("*  AUDIT COMPLETE                                         *")
    print("*" * 60)


if __name__ == "__main__":
    asyncio.run(main())
