"""
For every event in a BetPawa competition (tournament), fetch the mapped
odds from all 5 bookmakers and write a single CSV comparing them.

WHY START FROM A BETPAWA COMPETITION ID?
    Same reason as the single-event script: BetPawa's API doesn't (yet,
    in this lib) expose a SR-id -> BetPawa-id search, but it DOES embed
    the SR id inside each event detail (under the SPORTRADAR widget).
    Given a BetPawa competition id we can:
        1. List that competition's events (BetPawa internal ids).
        2. For each event, hit BetPawa to get its markets AND extract
           the SR id from the widget.
        3. Use that SR id to query the other four bookmakers.

USAGE
    python examples/odds_for_betpawa_competition.py <competition_id> [--live] [--csv path.csv]

    Defaults to PREMATCH (productId=3 / prematch endpoints) since
    competition listings are mostly upcoming events. Pass --live to
    switch every bookmaker to its live-market book.
"""

# Standard library only — keeps the script obvious.
import argparse
import asyncio
import csv
from collections import defaultdict
from typing import Any

# Public surface of the library: the 5 client classes plus the parser
# (raw response -> NormalizedMarket list) and extractor (raw response
# -> SportRadar id).
from bookieskit import Bet9ja, BetPawa, Betway, MSport, SportyBet
from bookieskit.markets import parse_markets
from bookieskit.matching import extract_sportradar_id


# ----------------------------------------------------------------------
# Step 1: List events in a BetPawa competition.
#
# BetPawa returns events under a nested structure:
#   { "responses": [ { "responses": [ <event>, <event>, ... ] } ] }
# Each event has at minimum `id` (BetPawa internal id) and a
# `participants` list with `[{name: home}, {name: away}]`.
# ----------------------------------------------------------------------
async def list_competition_events(bp: BetPawa, competition_id: str) -> list[dict]:
    raw = await bp.get_events(tournament_id=competition_id)
    responses = raw.get("responses", [])
    events = responses[0].get("responses", []) if responses else []
    # Normalize to a small dict per event — that's all downstream code needs.
    out: list[dict] = []
    for ev in events:
        parts = ev.get("participants", [])
        out.append({
            "betpawa_id": str(ev.get("id", "")),
            "home": parts[0]["name"] if len(parts) > 0 else "?",
            "away": parts[1]["name"] if len(parts) > 1 else "?",
        })
    return out


# ----------------------------------------------------------------------
# Step 2: Per-event odds collection.
#
# For each event we run six logical operations:
#   1. BetPawa: detail -> markets + SR id (single call, used for two
#      things at once).
#   2-5. SportyBet / MSport / Betway / Bet9ja: each given the SR id,
#      return their normalized markets.
#
# We dispatch 2-5 in parallel via asyncio.gather. Each helper opens its
# own bookmaker context per event, which is simple but does mean a fresh
# httpx connection per event — fine at this scale (tens of events).
# ----------------------------------------------------------------------
async def fetch_betpawa_event(bp: BetPawa, betpawa_id: str) -> dict:
    """Step 1 (per event). Pull BetPawa markets and SR id in one call."""
    detail = await bp.get_event_detail(event_id=betpawa_id)
    markets = parse_markets(detail, platform="betpawa")
    sr_id = extract_sportradar_id(detail, platform="betpawa")
    return {"markets": markets, "sr_id": sr_id}


async def fetch_sportybet(sr_prefixed: str, *, live: bool) -> list:
    # SportyBet's eventId IS the SR id. The `live` flag flips
    # productId between 3 (prematch) and 1 (live).
    async with SportyBet(country="ng") as sb:
        try:
            d = await sb.get_event_detail(event_id=sr_prefixed, live=live)
            return parse_markets(d, platform="sportybet")
        except Exception:
            return []


async def fetch_msport(sr_prefixed: str, *, live: bool) -> list:
    # Same shape as SportyBet — SR id direct lookup, productId switch.
    async with MSport(country="ng") as ms:
        try:
            d = await ms.get_event_detail(event_id=sr_prefixed, live=live)
            return parse_markets(d, platform="msport")
        except Exception:
            return []


async def fetch_betway(sr_numeric: str) -> list:
    # Betway splits metadata and markets across two endpoints. The
    # convenience method `get_markets` calls the right one (markets
    # endpoint) and runs the parser.
    async with Betway(country="ng") as bw:
        try:
            return await bw.get_markets(event_id=sr_numeric)
        except Exception:
            return []


async def fetch_bet9ja(
    sr_numeric: str,
    *,
    live: bool,
    bet9ja_lookup: dict[str, str],
) -> list:
    # Bet9ja uses internal ids. Instead of calling
    # `find_event_id_by_sr_id` per event (which hits the live-events
    # endpoint each time), we pre-fetched once into `bet9ja_lookup`
    # — a SR-numeric -> internal-id map.
    internal = bet9ja_lookup.get(sr_numeric)
    if internal is None:
        return []
    async with Bet9ja(country="ng") as b9:
        try:
            if live:
                d = await b9.get_live_event_detail(event_id=internal)
            else:
                # Prematch endpoint takes Bet9ja's internal id directly;
                # the parser handles both `S_*` and `LIVES_*` keys.
                d = await b9.get_event_detail(event_id=internal)
            return parse_markets(d, platform="bet9ja")
        except Exception:
            return []


# ----------------------------------------------------------------------
# One-shot Bet9ja optimisation: build a SR-id -> internal-id map.
#
# Bet9ja stores events in TWO disjoint buckets:
#   - Live: a single flat dict (D.E) on get_live_events. Cheap — one call.
#   - Prematch: scoped per-tournament. There is no flat global endpoint,
#     so a full prematch map requires walking every tournament under the
#     sport and concatenating their event lists. The lib's
#     `build_prematch_event_map` does this concurrently under the
#     client's rate limit (15 concurrent / 25ms delay).
#
# We pick the right one based on `live`. The map shape is the same
# either way: SR numeric id -> Bet9ja internal id.
# ----------------------------------------------------------------------
async def build_bet9ja_lookup(b9: Bet9ja, *, live: bool) -> dict[str, str]:
    if live:
        # Live: cheap. One call, all live soccer events at list level.
        resp = await b9.get_live_events(sport_id="3000001")  # 3000001 = Live Soccer
        events = (resp.get("D") or {}).get("E") or {}
        return {
            str(ev.get("EXTID", "") or ""): str(internal_id)
            for internal_id, ev in events.items()
            if ev.get("EXTID")
        }
    # Prematch: walks every soccer tournament. Slower (a few seconds for
    # the full Bet9ja prematch soccer list), but covers all upcoming
    # events. sport_id="1" is prematch Soccer.
    return await b9.build_prematch_event_map(sport_id="1")


# ----------------------------------------------------------------------
# Step 3: Flatten one event's per-bookmaker markets into rows.
#
# Output shape (one row per (market, line, outcome) within the event):
#   event_id, home, away, market, line, outcome, BetPawa, SportyBet,
#   MSport, Betway, Bet9ja
#
# Empty bookmaker cells mean "this bookmaker didn't have that
# market/line/outcome" — keeps the CSV grid rectangular.
# ----------------------------------------------------------------------
def event_rows(
    event_meta: dict,
    per_bookmaker: dict[str, list],
    bookies: list[str],
) -> list[dict]:
    # Same nested-dict-then-flatten approach used in the single-event
    # script. Key is (canonical_market_id, market_name, line, outcome);
    # value is {bookmaker_name: odds, ...}.
    odds_grid: dict[tuple, dict[str, float]] = defaultdict(dict)

    for bookie, markets in per_bookmaker.items():
        for m in markets:
            if m.lines is not None:
                # Parameterized: one row per (line, outcome).
                for line, outcomes in m.lines.items():
                    for o in outcomes:
                        key = (m.canonical_id, m.name, line, o.canonical_name)
                        odds_grid[key][bookie] = o.odds
            else:
                # Simple: one row per outcome, line is "".
                for o in m.outcomes:
                    key = (m.canonical_id, m.name, "", o.canonical_name)
                    odds_grid[key][bookie] = o.odds

    # Stable order: by market name, then numeric line (empty line first
    # so non-parameterized markets sit above O/U lines), then outcome.
    def sort_key(item):
        _canonical_id, name, line, outcome = item[0]
        line_key = (1, float(line)) if line != "" else (0, 0.0)
        return (name, line_key, outcome)

    rows: list[dict] = []
    for (_canonical_id, name, line, outcome), per_bookie in sorted(
        odds_grid.items(), key=sort_key
    ):
        rows.append({
            "event_id": event_meta["betpawa_id"],
            "home": event_meta["home"],
            "away": event_meta["away"],
            "market": name,
            "line": line,
            "outcome": outcome,
            **{b: per_bookie.get(b, "") for b in bookies},
        })
    return rows


# ----------------------------------------------------------------------
# Step 4: CSV writer. csv.DictWriter handles the header + rectangular
# rows. `newline=""` avoids double line endings on Windows.
# ----------------------------------------------------------------------
def write_csv(rows: list[dict], path: str, bookies: list[str]) -> None:
    fieldnames = ["event_id", "home", "away", "market", "line", "outcome"] + bookies
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ----------------------------------------------------------------------
# Step 5: Putting it together.
#
# Flow:
#   1. Open BetPawa context. List events in the competition.
#   2. Open Bet9ja context. Build the SR -> internal lookup table once.
#   3. For each event:
#        a. Pull BetPawa markets + SR id.
#        b. Dispatch the other 4 bookmakers in parallel via gather.
#        c. Flatten into rows.
#   4. Write the CSV.
#
# We process events sequentially (not in parallel) to keep API load
# moderate and to make the per-event log line readable. The 4
# non-BetPawa fetches per event ARE parallel — that's the only
# concurrency we want here.
# ----------------------------------------------------------------------
async def main(competition_id: str, live: bool, csv_path: str) -> None:
    mode = "LIVE" if live else "PREMATCH"
    print(f"BetPawa competition: {competition_id}  mode: {mode}")

    bookies_order = ["BetPawa", "SportyBet", "MSport", "Betway", "Bet9ja"]
    all_rows: list[dict] = []

    async with BetPawa(country="ng") as bp, Bet9ja(country="ng") as b9_lookup:
        events = await list_competition_events(bp, competition_id)
        print(f"Events in competition: {len(events)}")
        if not events:
            print("Nothing to do.")
            return

        # One-shot Bet9ja lookup table — built once, reused per event.
        # Live mode: cheap (one call). Prematch mode: walks every soccer
        # tournament — takes a few seconds; printed before so the user
        # knows what the pause is.
        if not live:
            print("Building Bet9ja prematch event map (walking soccer tournaments)...")
        bet9ja_lookup = await build_bet9ja_lookup(b9_lookup, live=live)
        print(f"Bet9ja {'live' if live else 'prematch'} lookup: {len(bet9ja_lookup)} entries")

        for i, ev in enumerate(events, start=1):
            label = f"{ev['home']} vs {ev['away']}"
            try:
                # 1. BetPawa first (we need its SR id to dispatch the rest).
                bp_data = await fetch_betpawa_event(bp, ev["betpawa_id"])
                sr_numeric = bp_data["sr_id"]
                if sr_numeric is None:
                    # No SPORTRADAR widget — record BetPawa odds only.
                    print(f"  [{i}/{len(events)}] {label}: no SR id (BetPawa only)")
                    per_bookmaker = {
                        "BetPawa": bp_data["markets"],
                        "SportyBet": [], "MSport": [], "Betway": [], "Bet9ja": [],
                    }
                else:
                    sr_prefixed = f"sr:match:{sr_numeric}"

                    # 2. The other 4 in parallel.
                    sb, ms, bw, b9 = await asyncio.gather(
                        fetch_sportybet(sr_prefixed, live=live),
                        fetch_msport(sr_prefixed, live=live),
                        fetch_betway(sr_numeric),
                        fetch_bet9ja(sr_numeric, live=live, bet9ja_lookup=bet9ja_lookup),
                    )
                    per_bookmaker = {
                        "BetPawa": bp_data["markets"],
                        "SportyBet": sb, "MSport": ms, "Betway": bw, "Bet9ja": b9,
                    }

                    # Per-event progress line: lets you see at a glance
                    # whether each bookmaker found the event. Short labels
                    # are unique even though some bookmakers share a prefix
                    # (BetPawa vs Betway, Bet9ja).
                    short = {
                        "BetPawa": "BP", "SportyBet": "SB", "MSport": "MS",
                        "Betway": "BW", "Bet9ja": "B9",
                    }
                    counts = " ".join(
                        f"{short[name]}={len(per_bookmaker[name])}"
                        for name in bookies_order
                    )
                    print(f"  [{i}/{len(events)}] {label}: {counts}")

                # 3. Flatten and accumulate.
                all_rows.extend(event_rows(ev, per_bookmaker, bookies_order))

            except Exception as e:
                # Don't let one broken event kill the whole run.
                print(f"  [{i}/{len(events)}] {label}: ERROR {e}")

    write_csv(all_rows, csv_path, bookies_order)
    print(f"\nWrote {len(all_rows)} rows across {len(events)} events to {csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare odds across 5 bookmakers for every event in a BetPawa competition.",
    )
    parser.add_argument(
        "competition_id",
        help="BetPawa competition (tournament) id, e.g. 12546.",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Use live endpoints (default: prematch).",
    )
    parser.add_argument(
        "--csv", default="competition_odds.csv",
        help="Output CSV path (default: competition_odds.csv).",
    )
    args = parser.parse_args()

    asyncio.run(main(args.competition_id, live=args.live, csv_path=args.csv))
