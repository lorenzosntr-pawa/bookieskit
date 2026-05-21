"""One-off probe: discovers Next Goal / Home O/U / Away O/U market ids
and outcome strings for the 5 bookmakers we haven't already captured
(Bet9ja, MSport, SportPesa, Betika, Betway).

Outputs:
  - JSON fixtures under tests/fixtures/event_info/<bookmaker>/next_goal_and_team_ou.json
  - A printed candidate table per bookmaker (market id, name, outcome strings)

Usage:
  python scripts/probe_next_goal_and_team_ou.py SPORTRADAR_MATCH_ID

The SR id should be a live (or near-live) soccer match so all bookmakers
have markets populated. Find one with e.g.:

  python examples/find_betgenius_matches.py
"""
import asyncio
import json
import re
import sys
from pathlib import Path

from bookieskit import Bet9ja, Betika, Betway, MSport, SportPesa
from bookieskit import SportyBet  # for the SR-id translator probe

FIXTURE_DIR = Path(__file__).parent.parent / "tests/fixtures/event_info"

CANDIDATE_PATTERNS = {
    "next_goal": re.compile(
        r"next\s*goal|1st\s*goal|first\s*goal|goal\s*\#1|nth\s*goal",
        re.IGNORECASE,
    ),
    "home_over_under": re.compile(
        r"home.*(o/?u|over[/\s]?under|total[\s_]?goals?)",
        re.IGNORECASE,
    ),
    "away_over_under": re.compile(
        r"away.*(o/?u|over[/\s]?under|total[\s_]?goals?)",
        re.IGNORECASE,
    ),
}


def find_candidates(label: str, name: str) -> list[str]:
    """Return list of canonical labels whose pattern matches the market name."""
    hits = []
    for canonical, pattern in CANDIDATE_PATTERNS.items():
        if pattern.search(name):
            hits.append(canonical)
    return hits


async def probe_bet9ja(sr_id: str) -> dict:
    """Fetch Bet9ja markets; print candidate keys; return raw response."""
    async with Bet9ja(country="ng") as b:
        match_map = await b.build_prematch_event_map(sport_id="1")
        internal_id = match_map.get(sr_id)
        if internal_id is None:
            print(f"[bet9ja] SR id {sr_id} not in prematch map; trying live")
            response = await b.get_live_event_markets(sr_id)
        else:
            response = await b.get_event_detail(internal_id)

        odds_dict = response.get("D", {}).get("O", {})
        # Bet9ja keys are flat: S_*/B_*/T_*/LIVES_*; extract market-key
        # candidates (the prefix-and-key portion before @ or _outcome).
        keys = {k for k in odds_dict.keys() if k.startswith(("S_", "LIVES_"))}
        market_keys = set()
        for k in keys:
            if "@" in k:
                market_keys.add(k.split("@")[0])
            else:
                # MARKET_OUTCOME split
                last_us = k.rfind("_")
                if last_us > 0:
                    market_keys.add(k[:last_us])
        # Try to correlate keys to market names via the M# dictionary
        meta = response.get("D", {})
        print(f"\n=== bet9ja markets for SR {sr_id} ===")
        for mk in sorted(market_keys):
            meta_key = f"M#{mk}"
            name = ""
            if isinstance(meta.get(meta_key), dict):
                name = meta[meta_key].get("NAME", "")
            hits = find_candidates(mk, mk + " " + name)
            if hits:
                print(f"  {mk}  ({name}) -> {hits}")
        return response


async def probe_msport(sr_id: str) -> dict:
    async with MSport(country="ng") as m:
        response = await m.get_event_detail(event_id=f"sr:match:{sr_id}", live=False)
        markets = response.get("data", {}).get("markets", [])
        if not markets:
            response = await m.get_event_detail(event_id=f"sr:match:{sr_id}", live=True)
            markets = response.get("data", {}).get("markets", [])
        print(f"\n=== msport markets for SR {sr_id} ({len(markets)} entries) ===")
        for md in markets:
            mid = md.get("id", "")
            name = md.get("name", "") or md.get("description", "")
            hits = find_candidates(mid, str(mid) + " " + str(name))
            if hits:
                outs = [o.get("description") for o in md.get("outcomes", [])]
                spec = md.get("specifiers", "")
                print(f"  id={mid}  name={name!r}  spec={spec!r}  outs={outs}  -> {hits}")
        return response


async def probe_sportpesa(sr_id: str) -> dict:
    # SportPesa needs an Akamai cookie; this probe assumes it's set in env.
    import os
    cookie = os.environ.get("SPORTPESA_COOKIE", "")
    async with SportPesa(country="ke", cookie=cookie) as sp:
        # SR id -> SportPesa game id requires the index walker
        nav = await sp.get_navigation(sport_id=14)
        # Walk leagues to find the SR id; abbreviated for brevity — real
        # probe should be more thorough. The test fixture only needs one
        # captured event so any soccer event will do.
        game_id = None
        for cat in nav.get("data", []):
            for comp in cat.get("competitions", []):
                events = await sp.get_events(
                    sport_id=14, competition_id=comp.get("id")
                )
                for ev in events.get("data", []):
                    if str(ev.get("betradarId", "")) == sr_id:
                        game_id = ev.get("id")
                        break
                if game_id:
                    break
            if game_id:
                break
        if game_id is None:
            # Fall back to the first soccer event with a sufficient market count
            print("[sportpesa] SR id not found in nav walk; using first soccer event")
            events = await sp.get_events(sport_id=14)
            game_id = events["data"][0]["id"]
        response = await sp.get_event_markets(game_id)
        first_value = next(iter(response.values()), [])
        print(f"\n=== sportpesa markets for game {game_id} ({len(first_value)} entries) ===")
        for md in first_value:
            mid = md.get("id", "")
            name = md.get("name", "")
            spec = md.get("specValue", "")
            hits = find_candidates(mid, str(mid) + " " + str(name))
            if hits:
                outs = [s.get("shortName") for s in md.get("selections", [])]
                print(f"  id={mid}  name={name!r}  spec={spec!r}  outs={outs}  -> {hits}")
        return response


async def probe_betika(sr_id: str) -> dict:
    async with Betika(country="ke") as bk:
        # Look up by parent_match_id (SR id)
        listing = await bk.get_events(sport_id="14", parent_match_id=sr_id)
        data = listing.get("data", [])
        if not data:
            print(f"[betika] no match for parent_match_id={sr_id}; falling back to first soccer event")
            listing = await bk.get_events(sport_id="14", limit=1)
            data = listing.get("data", [])
        match_id = data[0].get("match_id")
        comp_id = data[0].get("competition_id")
        # Fetch all market groups (no sub_type_id filter)
        response = await bk.get_event_markets(match_id, competition_id=comp_id)
        match = response.get("data", [{}])[0]
        groups = match.get("odds", [])
        print(f"\n=== betika markets for match {match_id} ({len(groups)} groups) ===")
        for grp in groups:
            sub_type_id = grp.get("sub_type_id", "")
            name = grp.get("name", "")
            hits = find_candidates(sub_type_id, str(sub_type_id) + " " + str(name))
            if hits:
                outs = [s.get("display") for s in grp.get("odds", [])]
                print(f"  sub_type_id={sub_type_id}  name={name!r}  outs={outs}  -> {hits}")
        return response


async def probe_betway(sr_id: str) -> dict:
    async with Betway(country="ng") as bw:
        # Betway accepts SR ids directly on get_event_markets when prefixed
        response = await bw.get_event_markets(f"sr:match:{sr_id}")
        markets_in_group = response.get("marketsInGroup", [])
        home_team = response.get("sportEvent", {}).get("homeTeam", "")
        away_team = response.get("sportEvent", {}).get("awayTeam", "")
        print(f"\n=== betway markets for SR {sr_id} (home={home_team!r}, away={away_team!r}) ===")
        for md in markets_in_group:
            name = md.get("name", "")
            hits = find_candidates(name, name)
            # Also check for the placeholder shape: name contains the actual home/away team
            if home_team and home_team in name and "total" in name.lower():
                hits.append("home_over_under (team-name shape)")
            if away_team and away_team in name and "total" in name.lower():
                hits.append("away_over_under (team-name shape)")
            if hits:
                print(f"  name={name!r}  -> {hits}")
        return response


async def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sr_id = sys.argv[1]
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    # Run sequentially so output is readable; each probe handles its own errors.
    captures = {}
    for name, fn in [
        ("bet9ja", probe_bet9ja),
        ("msport", probe_msport),
        ("sportpesa", probe_sportpesa),
        ("betika", probe_betika),
        ("betway", probe_betway),
    ]:
        try:
            captures[name] = await fn(sr_id)
        except Exception as exc:
            print(f"[{name}] probe failed: {exc!r}")
            captures[name] = None

    # Write each capture to its fixture file
    for name, capture in captures.items():
        if capture is None:
            continue
        path = FIXTURE_DIR / name / "next_goal_and_team_ou.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(capture, indent=2), encoding="utf-8")
        print(f"[{name}] wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
