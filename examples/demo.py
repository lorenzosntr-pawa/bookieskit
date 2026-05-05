"""Quick demo — test bookieskit against real APIs."""

import asyncio

from bookieskit import BetPawa, SportyBet, Bet9ja
from bookieskit.markets import MarketRegistry
from bookieskit.matching import extract_sportradar_id


async def main():
    print("=" * 60)
    print("BOOKIESKIT LIVE DEMO")
    print("=" * 60)

    # --- BetPawa ---
    print("\n--- BetPawa (Nigeria) ---")
    async with BetPawa(country="ng") as bp:
        # Get sports
        sports = await bp.get_sports()
        categories = sports.get("categories", [])
        print(f"Sports found: {len(categories)}")
        for cat in categories[:5]:
            print(f"  - {cat.get('name', '?')} (id: {cat.get('id', '?')})")

        # Get events from a football competition
        # First, get football regions
        football = await bp.get_countries(sport_id="2")
        regions = football.get("regions", [])
        print(f"\nFootball regions: {len(regions)}")

        # Find a competition with events
        event_id = None
        for region in regions[:5]:
            competitions = region.get("competitions", [])
            if competitions:
                comp = competitions[0]
                print(f"\nFetching events from: {region['name']} / {comp['name']}")
                events = await bp.get_events(tournament_id=str(comp["id"]))
                results = events.get("results", [])
                print(f"  Events found: {len(results)}")
                if results:
                    event_id = str(results[0]["id"])
                    print(f"  First event: {results[0].get('homeTeam', '?')} vs {results[0].get('awayTeam', '?')}")
                    break

        # Get markets for an event
        if event_id:
            print(f"\nFetching normalized markets for event {event_id}...")
            markets = await bp.get_markets(event_id=event_id)
            print(f"  Normalized markets found: {len(markets)}")
            for m in markets:
                if m.lines:
                    lines_str = ", ".join(f"{l}" for l in list(m.lines.keys())[:3])
                    print(f"  - {m.name} (lines: {lines_str})")
                else:
                    odds_str = ", ".join(
                        f"{o.canonical_name}={o.odds}" for o in m.outcomes
                    )
                    print(f"  - {m.name}: {odds_str}")

            # Get SportRadar ID
            sr_id = await bp.get_sportradar_id(event_id=event_id)
            print(f"\n  SportRadar ID: {sr_id}")

    # --- SportyBet ---
    print("\n\n--- SportyBet (Nigeria) ---")
    async with SportyBet(country="ng") as sb:
        sports = await sb.get_sports()
        sport_list = sports.get("data", {}).get("sportList", [])
        print(f"Sports found: {len(sport_list)}")

        # Get Premier League events
        events = await sb.get_events(tournament_id="sr:tournament:17")
        event_data = events.get("data", [{}])
        if event_data:
            event_list = event_data[0].get("events", [])
            print(f"Premier League events: {len(event_list)}")
            if event_list:
                ev = event_list[0]
                print(f"  First: {ev.get('homeTeamName', '?')} vs {ev.get('awayTeamName', '?')}")
                ev_id = ev.get("eventId", "")
                print(f"  EventId (SR ID): {ev_id}")

                # Get full detail + markets
                detail = await sb.get_event_detail(event_id=ev_id)
                markets = await sb.get_markets(event_id=ev_id)
                print(f"  Normalized markets: {len(markets)}")
                for m in markets:
                    if m.lines:
                        print(f"    - {m.name} ({len(m.lines)} lines)")
                    else:
                        print(f"    - {m.name} ({len(m.outcomes)} outcomes)")

    # --- Bet9ja ---
    print("\n\n--- Bet9ja (Nigeria) ---")
    async with Bet9ja(country="ng") as b9:
        sports = await b9.get_sports()
        status = sports.get("R", "?")
        print(f"API status: {status}")
        if status == "OK":
            print("  Sports hierarchy loaded successfully")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
