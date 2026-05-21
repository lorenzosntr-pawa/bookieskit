"""Smoke test for the 3 new soccer markets (next_goal_ft +
home/away_over_under_ft) starting from a BetPawa internal event id.

Mirrors the `examples/odds_from_betpawa_id.py` lookup flow:
  1. Fetch BetPawa event → extract SR id from SPORTRADAR widget.
  2. Fan out to SportyBet / MSport / Betway / Bet9ja via SR id.
  3. Look up Betika via `parent_match_id` listing scan.
  4. SportPesa skipped (no Akamai cookie at probe time).

Prints odds for ONLY the 3 new canonical IDs per bookmaker.

Usage:
    python scripts/smoke_new_markets.py <betpawa_id> [--live]
"""

import asyncio
import sys

from bookieskit import (
    Bet9ja,
    Betika,
    BetPawa,
    Betway,
    MSport,
    SportyBet,
)
from bookieskit.markets import parse_markets
from bookieskit.matching import extract_sportradar_id

NEW_CANONICALS = {"next_goal_ft", "home_over_under_ft", "away_over_under_ft"}


def _print_new_markets(label: str, home: str, away: str, markets, extra: str = ""):
    print(f"\n=== {label} ===")
    print(f"  Event: {home} vs {away}{extra}")
    relevant = [m for m in markets if m.canonical_id in NEW_CANONICALS]
    if not relevant:
        print("  (none of the 3 new markets found)")
        return
    for m in relevant:
        if m.lines:
            for line in sorted(m.lines.keys()):
                odds = ", ".join(
                    f"{o.canonical_name}={o.odds}" for o in m.lines[line]
                )
                print(f"  [{m.canonical_id}] line={line}: {odds}")
        else:
            odds = ", ".join(
                f"{o.canonical_name}={o.odds}" for o in m.outcomes
            )
            print(f"  [{m.canonical_id}] {odds}")


async def fetch_betpawa(betpawa_id: str):
    async with BetPawa(country="ng") as bp:
        detail = await bp.get_event_detail(event_id=betpawa_id)
        participants = detail.get("participants", [])
        home = participants[0]["name"] if len(participants) > 0 else "?"
        away = participants[1]["name"] if len(participants) > 1 else "?"
        markets = parse_markets(detail, platform="betpawa")
        sr_id = extract_sportradar_id(detail, platform="betpawa")
        return home, away, markets, sr_id


async def fetch_sportybet(sr_prefixed: str, live: bool):
    async with SportyBet(country="ng") as sb:
        detail = await sb.get_event_detail(event_id=sr_prefixed, live=live)
        return parse_markets(detail, platform="sportybet")


async def fetch_msport(sr_prefixed: str, live: bool):
    async with MSport(country="ng") as ms:
        detail = await ms.get_event_detail(event_id=sr_prefixed, live=live)
        return parse_markets(detail, platform="msport")


async def fetch_betway(sr_numeric: str):
    async with Betway(country="ng") as bw:
        detail = await bw.get_event_detail(event_id=sr_numeric)
        sport_event = detail.get("sportEvent") or {}
        home = sport_event.get("homeTeam") or "?"
        away = sport_event.get("awayTeam") or "?"
        # Paginate — Betway returns 100 entries per page and the new markets
        # (1st Goal, <Team> Total) often land past index 100. Library bug:
        # Betway.get_event_markets()/get_markets() default to take=100 with
        # no auto-pagination, so callers silently lose markets.
        all_mig, all_outs, all_prices = [], [], []
        for skip in range(0, 600, 100):
            r = await bw.get_event_markets(
                event_id=sr_numeric, skip=skip, take=100
            )
            mig = r.get("marketsInGroup") or []
            if not mig:
                break
            all_mig.extend(mig)
            all_outs.extend(r.get("outcomes") or [])
            all_prices.extend(r.get("prices") or [])
        merged = {
            "marketsInGroup": all_mig,
            "outcomes": all_outs,
            "prices": all_prices,
            "sportEvent": sport_event,
        }
        return home, away, parse_markets(merged, platform="betway")


async def fetch_bet9ja(sr_numeric: str, live: bool):
    async with Bet9ja(country="ng") as b9:
        if live:
            internal = await b9.find_event_id_by_sr_id(sr_numeric)
        else:
            event_map = await b9.build_prematch_event_map(sport_id="1")
            internal = event_map.get(sr_numeric)
        if internal is None:
            return None, None
        if live:
            detail = await b9.get_live_event_detail(event_id=internal)
        else:
            detail = await b9.get_event_detail(event_id=internal)
        return internal, parse_markets(detail, platform="bet9ja")


async def fetch_betika(sr_numeric: str):
    """Look up Betika match by SR id (parent_match_id) via listing scan.

    Betika's get_matches doesn't accept a parent_match_id filter so we
    walk pages until we find a row whose parent_match_id matches. We
    bail after a reasonable number of pages — if not found, return None.
    """
    async with Betika(country="ke") as bk:
        match_id = None
        comp_id = None
        home = away = "?"
        for page in range(1, 10):
            listing = await bk.get_matches(sport_id=14, page=page, limit=100)
            data = listing.get("data") or []
            if not data:
                break
            for m in data:
                if str(m.get("parent_match_id", "")) == sr_numeric:
                    match_id = m.get("match_id")
                    comp_id = m.get("competition_id")
                    home = m.get("home_team") or "?"
                    away = m.get("away_team") or "?"
                    break
            if match_id is not None:
                break
        if match_id is None:
            return None, None, "?", "?"
        # Fetch the 3 sub_type_ids via get_matches (the underlying lib's
        # get_event_markets only fans out the 4 universal ids). Each call
        # returns a single match-shaped row; we merge their odds groups.
        merged_odds = []
        for sti in ("8", "19", "20"):
            r = await bk.get_matches(
                sport_id=14,
                match_id=str(match_id),
                competition_id=str(comp_id) if comp_id else None,
                sub_type_id=sti,
                limit=1,
            )
            for entry in (r.get("data") or []):
                if str(entry.get("match_id")) == str(match_id):
                    merged_odds.extend(entry.get("odds") or [])
                    break
        payload = {"data": [{
            "match_id": match_id,
            "competition_id": comp_id,
            "home_team": home,
            "away_team": away,
            "odds": merged_odds,
        }]}
        return match_id, parse_markets(payload, platform="betika"), home, away


async def main(betpawa_id: str, live: bool):
    mode = "LIVE" if live else "PREMATCH"
    print(f"Smoke test: BetPawa event {betpawa_id}  mode: {mode}")
    print(f"Checking canonicals: {sorted(NEW_CANONICALS)}")

    # Step 1: BetPawa — also gives us the SR id
    try:
        bp_home, bp_away, bp_markets, sr_numeric = await fetch_betpawa(betpawa_id)
        _print_new_markets("BetPawa", bp_home, bp_away, bp_markets)
        if sr_numeric is None:
            print("\nERROR: no SPORTRADAR widget on this BetPawa event — cannot resolve other bookmakers")
            return
        sr_prefixed = f"sr:match:{sr_numeric}"
        print(f"\n[resolved SR id: {sr_prefixed}]")
    except Exception as exc:
        print(f"\n=== BetPawa === error: {exc!r}")
        return

    # Step 2: Fan-out to the other 5 bookmakers (skipping SportPesa)
    async def safe(fn, label):
        try:
            await fn()
        except Exception as exc:
            print(f"\n=== {label} === error: {exc!r}")

    async def run_sportybet():
        markets = await fetch_sportybet(sr_prefixed, live)
        _print_new_markets("SportyBet", bp_home, bp_away, markets)

    async def run_msport():
        markets = await fetch_msport(sr_prefixed, live)
        _print_new_markets("MSport", bp_home, bp_away, markets)

    async def run_betway():
        home, away, markets = await fetch_betway(sr_numeric)
        _print_new_markets("Betway", home, away, markets)

    async def run_bet9ja():
        internal, markets = await fetch_bet9ja(sr_numeric, live)
        if markets is None:
            print(f"\n=== Bet9ja === SR id not found in {'live' if live else 'prematch'}")
            return
        _print_new_markets(
            "Bet9ja", bp_home, bp_away, markets, extra=f" (internal={internal})"
        )

    async def run_betika():
        match_id, markets, home, away = await fetch_betika(sr_numeric)
        if markets is None:
            print(f"\n=== Betika === SR id {sr_numeric} not found in first 9 listing pages")
            return
        _print_new_markets(
            "Betika", home, away, markets, extra=f" (match_id={match_id})"
        )

    await safe(run_sportybet, "SportyBet")
    await safe(run_msport, "MSport")
    await safe(run_betway, "Betway")
    await safe(run_bet9ja, "Bet9ja")
    await safe(run_betika, "Betika")
    print("\n=== SportPesa === skipped (requires Akamai cookie)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python scripts/smoke_new_markets.py <betpawa_id> [--live]")
        sys.exit(1)
    betpawa_id = sys.argv[1]
    live = "--live" in sys.argv
    asyncio.run(main(betpawa_id, live))
