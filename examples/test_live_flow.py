"""Full live flow test: Sports -> Countries -> Events -> Markets for all 3 bookmakers."""  # noqa: E501

import asyncio

from bookieskit import Bet9ja, BetPawa, SportyBet
from bookieskit.markets import parse_markets
from bookieskit.matching import extract_sportradar_id


async def main():
    print("=" * 60)
    print("FULL LIVE FLOW: Sports -> Countries -> Events -> Markets")
    print("=" * 60)

    # === BETPAWA ===
    print("\n\n=== BETPAWA LIVE ===")
    async with BetPawa(country="ng") as bp:
        # 1. Sports
        sports = await bp.get_sports()
        sport_list = sports.get("onlyMeta", [])
        print("\n[1] Live Sports:")
        for s in sport_list:
            cat = s["category"]
            live = s.get("eventCounts", {}).get("live", 0)
            if live > 0:
                print(f"    {cat['name']} (id: {cat['id']}) - {live} live")

        # 2. Live events (all football)
        events = await bp.get_events(event_type="LIVE", sport_id="2")
        responses = events.get("responses", [])
        ev_list = responses[0].get("responses", []) if responses else []
        print(f"\n[2] Live Football Events: {len(ev_list)}")

        # 3. Group by country/competition
        comps = {}
        for ev in ev_list:
            comp_name = ev.get("competition", {}).get("name", "Unknown")
            country = ev.get("region", {}).get("name", "?")
            key = f"{country}/{comp_name}"
            if key not in comps:
                comps[key] = []
            comps[key].append(ev)

        print("\n[3] Countries/Tournaments:")
        for comp, evts in list(comps.items())[:8]:
            print(f"    {comp} ({len(evts)} events)")

        # 4. First event -> detail -> markets
        if ev_list:
            ev = ev_list[0]
            ev_id = str(ev.get("id"))
            parts = ev.get("participants", [])
            home = parts[0]["name"] if len(parts) > 0 else "?"
            away = parts[1]["name"] if len(parts) > 1 else "?"
            print(f"\n[4] Event: {home} vs {away} (id: {ev_id})")

            detail = await bp.get_event_detail(event_id=ev_id)
            sr_id = extract_sportradar_id(detail, platform="betpawa")
            print(f"    SportRadar ID: {sr_id}")

            markets = parse_markets(detail, platform="betpawa")
            print(f"    Normalized Markets: {len(markets)}")
            for m in markets:
                if m.lines:
                    lines_list = sorted(m.lines.keys())[:3]
                    for line in lines_list:
                        odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[line])  # noqa: E501
                        print(f"      {m.name} [{line}]: {odds}")
                else:
                    odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
                    print(f"      {m.name}: {odds}")

    # === SPORTYBET ===
    print("\n\n=== SPORTYBET LIVE ===")
    async with SportyBet(country="ng") as sb:
        # 1. Live sports
        sports_raw = await sb.get_sports(live=True)
        sport_list = sports_raw.get("data", {}).get("sportList", [])
        print("\n[1] Live Sports:")
        for s in sport_list[:8]:
            print(f"    {s['name']} (id: {s['id']}) - {s.get('eventSize', 0)} live")

        # 2-3. Live football countries/tournaments
        countries_raw = await sb.get_countries(sport_id="sr:sport:1", live=True)
        cats = countries_raw.get("data", {}).get("sportList", [{}])[0].get("categories", [])  # noqa: E501
        print(f"\n[2] Live Football Countries: {len(cats)}")
        print("\n[3] Countries/Tournaments:")
        for c in cats[:8]:
            for t in c.get("tournaments", []):
                print(f"    {c['name']}/{t['name']} (id: {t['id']})")

        # 4. First event -> detail -> markets
        picked_event = None
        for c in cats:
            for t in c.get("tournaments", []):
                events = await sb.get_events(tournament_id=t.get("id"))
                ev_data = events.get("data", [{}])
                ev_list = ev_data[0].get("events", []) if ev_data else []
                if ev_list:
                    picked_event = ev_list[0]
                    break
            if picked_event:
                break

        if picked_event:
            ev_id = picked_event.get("eventId")
            print(f"\n[4] Event: {picked_event.get('homeTeamName')} vs {picked_event.get('awayTeamName')} (id: {ev_id})")  # noqa: E501

            detail = await sb.get_event_detail(event_id=ev_id)
            sr_id = extract_sportradar_id(detail, platform="sportybet")
            print(f"    SportRadar ID: {sr_id}")

            markets = parse_markets(detail, platform="sportybet")
            print(f"    Normalized Markets: {len(markets)}")
            for m in markets:
                if m.lines:
                    lines_list = sorted(m.lines.keys())[:3]
                    for line in lines_list:
                        odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[line])  # noqa: E501
                        print(f"      {m.name} [{line}]: {odds}")
                else:
                    odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
                    print(f"      {m.name}: {odds}")

    # === BET9JA ===
    print("\n\n=== BET9JA LIVE ===")
    async with Bet9ja(country="ng") as b9:
        # 1. Live sports
        sports_raw = await b9.get_sports(live=True)
        pal = sports_raw.get("D", {}).get("PAL", {})
        print("\n[1] Live Sports:")
        for key, item in pal.items():
            num = item.get("NUM", 0)
            if num > 0:
                print(f"    {item['S_DESC']} (id: {key}) - {num} live")

        # 2-3. Soccer countries/tournaments
        soccer = pal.get("1", {})
        sg = soccer.get("SG", {})
        print(f"\n[2] Live Soccer Countries: {len(sg)}")
        print("\n[3] Countries/Tournaments:")
        for gid in list(sg.keys())[:8]:
            group = sg[gid]
            lang = group.get("SG_LANG", {})
            name = lang.get("en", "?")
            sub = group.get("G", {})
            for tid, t in sub.items():
                if t.get("NUM", 0) > 0:
                    print(f"    {name}/{t.get('G_DESC', '?')} (id: {tid}) - {t.get('NUM', 0)} events")  # noqa: E501

        # 4. First live event -> detail -> markets
        found = False
        for gid, group in sg.items():
            sub = group.get("G", {})
            for tid, t in sub.items():
                if t.get("NUM", 0) > 0:
                    events = await b9.get_events(tournament_id=tid)
                    ev_list = events.get("D", {}).get("E", [])
                    if ev_list:
                        ev = ev_list[0]
                        ev_id = str(ev.get("ID", ""))
                        print(f"\n[4] Event: {ev.get('DS', '?')} (id: {ev_id})")

                        detail = await b9.get_event_detail(event_id=ev_id)
                        sr_id = extract_sportradar_id(detail, platform="bet9ja")
                        print(f"    SportRadar ID: {sr_id}")

                        markets = parse_markets(detail, platform="bet9ja")
                        print(f"    Normalized Markets: {len(markets)}")
                        for m in markets:
                            if m.lines:
                                lines_list = sorted(m.lines.keys())[:3]
                                for line in lines_list:
                                    odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[line])  # noqa: E501
                                    print(f"      {m.name} [{line}]: {odds}")
                            else:
                                odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)  # noqa: E501
                                print(f"      {m.name}: {odds}")
                        found = True
                        break
            if found:
                break

    print("\n\n" + "=" * 60)
    print("FULL LIVE FLOW COMPLETE - ALL 3 PLATFORMS")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
