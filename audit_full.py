"""Full audit: 1 match per sport for both prematch and live across all 3 bookmakers."""

import asyncio

from bookieskit import BetPawa, SportyBet, Bet9ja
from bookieskit.markets import parse_markets
from bookieskit.matching import extract_sportradar_id


async def audit_betpawa():
    print("\n" + "=" * 60)
    print("BETPAWA - FULL AUDIT")
    print("=" * 60)

    async with BetPawa(country="ng") as bp:
        sports = await bp.get_sports()
        sport_list = sports.get("onlyMeta", [])

        # --- PREMATCH ---
        print("\n--- PREMATCH ---")
        for s in sport_list:
            cat = s["category"]
            sport_id = str(cat["id"])
            sport_name = cat["name"]
            upcoming = s.get("eventCounts", {}).get("upcoming", 0)
            if upcoming == 0:
                continue

            # Get events for this sport
            events = await bp.get_events(sport_id=sport_id, event_type="UPCOMING")
            responses = events.get("responses", [])
            ev_list = responses[0].get("responses", []) if responses else []

            if not ev_list:
                print(f"\n  [{sport_name}] No events found")
                continue

            ev = ev_list[0]
            ev_id = str(ev.get("id"))
            parts = ev.get("participants", [])
            home = parts[0]["name"] if len(parts) > 0 else "?"
            away = parts[1]["name"] if len(parts) > 1 else "?"
            comp = ev.get("competition", {}).get("name", "?")

            print(f"\n  [{sport_name}] {home} vs {away}")
            print(f"    Competition: {comp}")

            detail = await bp.get_event_detail(event_id=ev_id)
            sr_id = extract_sportradar_id(detail, platform="betpawa")
            markets = parse_markets(detail, platform="betpawa")

            print(f"    SR ID: {sr_id}")
            print(f"    Markets: {len(markets)}")
            for m in markets:
                if m.lines:
                    lines_sorted = sorted(m.lines.keys())
                    mid_line = lines_sorted[len(lines_sorted) // 2] if lines_sorted else None
                    if mid_line:
                        odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[mid_line])
                        print(f"      {m.name} [{mid_line}]: {odds}")
                else:
                    odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
                    print(f"      {m.name}: {odds}")

        # --- LIVE ---
        print("\n\n--- LIVE ---")
        for s in sport_list:
            cat = s["category"]
            sport_id = str(cat["id"])
            sport_name = cat["name"]
            live_count = s.get("eventCounts", {}).get("live", 0)
            if live_count == 0:
                continue

            events = await bp.get_events(sport_id=sport_id, event_type="LIVE")
            responses = events.get("responses", [])
            ev_list = responses[0].get("responses", []) if responses else []

            if not ev_list:
                print(f"\n  [{sport_name}] No live events found")
                continue

            ev = ev_list[0]
            ev_id = str(ev.get("id"))
            parts = ev.get("participants", [])
            home = parts[0]["name"] if len(parts) > 0 else "?"
            away = parts[1]["name"] if len(parts) > 1 else "?"
            comp = ev.get("competition", {}).get("name", "?")

            print(f"\n  [{sport_name}] {home} vs {away}")
            print(f"    Competition: {comp}")

            detail = await bp.get_event_detail(event_id=ev_id)
            sr_id = extract_sportradar_id(detail, platform="betpawa")
            markets = parse_markets(detail, platform="betpawa")

            print(f"    SR ID: {sr_id}")
            print(f"    Markets: {len(markets)}")
            for m in markets:
                if m.lines:
                    lines_sorted = sorted(m.lines.keys())
                    mid_line = lines_sorted[len(lines_sorted) // 2] if lines_sorted else None
                    if mid_line:
                        odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[mid_line])
                        print(f"      {m.name} [{mid_line}]: {odds}")
                else:
                    odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
                    print(f"      {m.name}: {odds}")


async def audit_sportybet():
    print("\n" + "=" * 60)
    print("SPORTYBET - FULL AUDIT")
    print("=" * 60)

    async with SportyBet(country="ng") as sb:
        # --- PREMATCH ---
        print("\n--- PREMATCH ---")
        sports_raw = await sb.get_sports(live=False)
        sport_list = sports_raw.get("data", {}).get("sportList", [])

        for s in sport_list:
            sport_id = s["id"]
            sport_name = s["name"]
            event_size = s.get("eventSize", 0)
            if event_size == 0:
                continue

            # Get countries for this sport to find a tournament
            countries_raw = await sb.get_countries(sport_id=sport_id, live=False)
            cats = countries_raw.get("data", {}).get("sportList", [{}])[0].get("categories", [])

            # Find first tournament with events
            found = False
            for c in cats[:5]:
                for t in c.get("tournaments", [])[:3]:
                    t_id = t.get("id")
                    events = await sb.get_events(tournament_id=t_id, sport_id=sport_id)
                    ev_data = events.get("data", [{}])
                    ev_list = ev_data[0].get("events", []) if ev_data else []

                    if ev_list:
                        ev = ev_list[0]
                        ev_id = ev.get("eventId")
                        home = ev.get("homeTeamName", "?")
                        away = ev.get("awayTeamName", "?")
                        tourney = t.get("name", "?")

                        print(f"\n  [{sport_name}] {home} vs {away}")
                        print(f"    Tournament: {c.get('name', '?')}/{tourney}")

                        detail = await sb.get_event_detail(event_id=ev_id)
                        sr_id = extract_sportradar_id(detail, platform="sportybet")
                        markets = parse_markets(detail, platform="sportybet")

                        print(f"    SR ID: {sr_id}")
                        print(f"    Markets: {len(markets)}")
                        for m in markets:
                            if m.lines:
                                lines_sorted = sorted(m.lines.keys())
                                mid_line = lines_sorted[len(lines_sorted) // 2] if lines_sorted else None
                                if mid_line:
                                    odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[mid_line])
                                    print(f"      {m.name} [{mid_line}]: {odds}")
                            else:
                                odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
                                print(f"      {m.name}: {odds}")
                        found = True
                        break
                if found:
                    break

            if not found:
                print(f"\n  [{sport_name}] No events found in first tournaments")

        # --- LIVE ---
        print("\n\n--- LIVE ---")
        sports_raw = await sb.get_sports(live=True)
        sport_list = sports_raw.get("data", {}).get("sportList", [])

        for s in sport_list:
            sport_id = s["id"]
            sport_name = s["name"]
            event_size = s.get("eventSize", 0)
            if event_size == 0:
                continue

            countries_raw = await sb.get_countries(sport_id=sport_id, live=True)
            cats = countries_raw.get("data", {}).get("sportList", [{}])[0].get("categories", [])

            found = False
            for c in cats[:5]:
                for t in c.get("tournaments", [])[:3]:
                    t_id = t.get("id")
                    events = await sb.get_events(tournament_id=t_id, sport_id=sport_id)
                    ev_data = events.get("data", [{}])
                    ev_list = ev_data[0].get("events", []) if ev_data else []

                    if ev_list:
                        ev = ev_list[0]
                        ev_id = ev.get("eventId")
                        home = ev.get("homeTeamName", "?")
                        away = ev.get("awayTeamName", "?")

                        print(f"\n  [{sport_name}] {home} vs {away}")
                        print(f"    Tournament: {c.get('name', '?')}/{t.get('name', '?')}")

                        detail = await sb.get_event_detail(event_id=ev_id)
                        sr_id = extract_sportradar_id(detail, platform="sportybet")
                        markets = parse_markets(detail, platform="sportybet")

                        print(f"    SR ID: {sr_id}")
                        print(f"    Markets: {len(markets)}")
                        for m in markets:
                            if m.lines:
                                lines_sorted = sorted(m.lines.keys())
                                mid_line = lines_sorted[len(lines_sorted) // 2] if lines_sorted else None
                                if mid_line:
                                    odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[mid_line])
                                    print(f"      {m.name} [{mid_line}]: {odds}")
                            else:
                                odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
                                print(f"      {m.name}: {odds}")
                        found = True
                        break
                if found:
                    break

            if not found:
                print(f"\n  [{sport_name}] No live events accessible")


async def audit_bet9ja():
    print("\n" + "=" * 60)
    print("BET9JA - FULL AUDIT")
    print("=" * 60)

    async with Bet9ja(country="ng") as b9:
        # --- PREMATCH ---
        print("\n--- PREMATCH ---")
        sports_raw = await b9.get_sports(live=False)
        pal = sports_raw.get("D", {}).get("PAL", {})

        for key, item in pal.items():
            sport_name = item.get("S_DESC", "?")
            num = item.get("NUM", 0)
            if num == 0 or "Antepost" in sport_name or "Players" in sport_name or "Zoom" in sport_name:
                continue

            sg = item.get("SG", {})
            found = False
            for gid, group in list(sg.items())[:5]:
                sub = group.get("G", {})
                for tid, t in list(sub.items())[:3]:
                    if t.get("NUM", 0) > 0:
                        events = await b9.get_events(tournament_id=tid)
                        ev_list = events.get("D", {}).get("E", [])
                        if ev_list:
                            ev = ev_list[0]
                            ev_id = str(ev.get("ID", ""))
                            match_name = ev.get("DS", "?")
                            tourney = t.get("G_DESC", "?")
                            lang = group.get("SG_LANG", {})
                            country = lang.get("en", "?")

                            print(f"\n  [{sport_name}] {match_name}")
                            print(f"    Tournament: {country}/{tourney}")

                            detail = await b9.get_event_detail(event_id=ev_id)
                            sr_id = extract_sportradar_id(detail, platform="bet9ja")
                            markets = parse_markets(detail, platform="bet9ja")

                            print(f"    SR ID: {sr_id}")
                            print(f"    Markets: {len(markets)}")
                            for m in markets:
                                if m.lines:
                                    lines_sorted = sorted(m.lines.keys())
                                    mid_line = lines_sorted[len(lines_sorted) // 2] if lines_sorted else None
                                    if mid_line:
                                        odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[mid_line])
                                        print(f"      {m.name} [{mid_line}]: {odds}")
                                else:
                                    odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
                                    print(f"      {m.name}: {odds}")
                            found = True
                            break
                if found:
                    break

            if not found:
                print(f"\n  [{sport_name}] No events accessible")

        # --- LIVE ---
        print("\n\n--- LIVE ---")
        sports_raw = await b9.get_sports(live=True)
        pal = sports_raw.get("D", {}).get("PAL", {})

        for key, item in pal.items():
            sport_name = item.get("S_DESC", "?")
            num = item.get("NUM", 0)
            if num == 0 or "Players" in sport_name or "Zoom" in sport_name or "Specials" in sport_name:
                continue

            sg = item.get("SG", {})
            found = False
            for gid, group in list(sg.items())[:5]:
                sub = group.get("G", {})
                for tid, t in list(sub.items())[:3]:
                    if t.get("NUM", 0) > 0:
                        events = await b9.get_events(tournament_id=tid)
                        ev_list = events.get("D", {}).get("E", [])
                        if ev_list:
                            ev = ev_list[0]
                            ev_id = str(ev.get("ID", ""))
                            match_name = ev.get("DS", "?")

                            print(f"\n  [{sport_name}] {match_name}")
                            print(f"    Tournament: {t.get('G_DESC', '?')}")

                            detail = await b9.get_event_detail(event_id=ev_id)
                            sr_id = extract_sportradar_id(detail, platform="bet9ja")
                            markets = parse_markets(detail, platform="bet9ja")

                            print(f"    SR ID: {sr_id}")
                            print(f"    Markets: {len(markets)}")
                            for m in markets:
                                if m.lines:
                                    lines_sorted = sorted(m.lines.keys())
                                    mid_line = lines_sorted[len(lines_sorted) // 2] if lines_sorted else None
                                    if mid_line:
                                        odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[mid_line])
                                        print(f"      {m.name} [{mid_line}]: {odds}")
                                else:
                                    odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
                                    print(f"      {m.name}: {odds}")
                            found = True
                            break
                if found:
                    break

            if not found:
                print(f"\n  [{sport_name}] No live events accessible")


async def main():
    print("*" * 60)
    print("*  BOOKIESKIT - FULL AUDIT                                *")
    print("*  1 match per sport, PREMATCH + LIVE, all 3 bookmakers   *")
    print("*" * 60)

    await audit_betpawa()
    await audit_sportybet()
    await audit_bet9ja()

    print("\n\n" + "*" * 60)
    print("*  AUDIT COMPLETE                                         *")
    print("*" * 60)


if __name__ == "__main__":
    asyncio.run(main())
