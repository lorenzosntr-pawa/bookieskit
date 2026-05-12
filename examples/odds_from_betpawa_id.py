"""
Compare odds across all 6 bookmakers, starting from a BetPawa event id.

WHY START FROM BETPAWA?
    Four of the others (SportyBet, MSport, Betway, Bet9ja) either use
    the SportRadar id directly as their event id (SportyBet/MSport/Betway)
    or expose the SR id alongside their internal id (Bet9ja's `EXTID`),
    so given a SR id we can look them up cheaply.

    BetPawa is one odd one out: its event id is internal, and the API
    doesn't (yet, in this lib) expose a SR-id -> BetPawa-id search. But
    BetPawa DOES embed the SR id inside the event-detail response (under
    `widgets[].id` for the SPORTRADAR widget), so once we have the BetPawa
    id, we can read out the SR id and use it to query the SR-keyed four.

    SportPesa is the *other* odd one out: same lack of SR-id reverse
    search, AND its endpoints are gated by Akamai Bot Manager. This
    script shows it as a placeholder column populated with empty values;
    populate it manually once a reverse-search path exists.

USAGE
    python examples/odds_from_betpawa_id.py <betpawa_id> [--prematch] [--csv path.csv]

    Defaults to live (matches the most recent in-play state on each
    bookmaker). Pass --prematch for upcoming events. CSV defaults to
    odds_comparison.csv in the current working directory.
"""

# Standard library only here — keeps the script obvious.
import argparse
import asyncio
import csv
from collections import defaultdict

# Public surface of the library — these are the 6 client classes plus
# the two helpers we need: a parser (raw response -> NormalizedMarket
# list) and an extractor (raw response -> SportRadar id).
from bookieskit import Bet9ja, BetPawa, Betway, MSport, SportyBet
from bookieskit.markets import parse_markets
from bookieskit.matching import extract_sportradar_id

# SportPesa kept as an explicit import even though it's not wired into
# the fan-out below — see the module docstring for why.
from bookieskit import SportPesa  # noqa: F401


# --- Step 1: Fetch BetPawa event + extract SR id ---
#
# Why this is its own function: BetPawa is both the *input* (caller
# gives us its internal id) and one of the bookmakers we're collecting
# odds for. So this single call does double duty:
#   1. Parses BetPawa's normalized markets (so we can fill its column
#      in the CSV).
#   2. Pulls the SR id out of the SPORTRADAR widget so we can reuse it
#      for the other four bookmakers.
async def fetch_betpawa(betpawa_id: str) -> dict:
    async with BetPawa(country="ng") as bp:
        # `get_event_detail` returns the raw JSON. We need the raw response
        # for two reasons: (a) feed it to `parse_markets`, and (b) feed it
        # to `extract_sportradar_id` to find the widget. Calling
        # `get_markets` (the convenience helper) would parse the markets
        # but throw the raw response away.
        detail = await bp.get_event_detail(event_id=betpawa_id)

        # The participants list gives us the home/away team names for the
        # CSV header — BetPawa returns these as `[{name: ...}, {name: ...}]`.
        participants = detail.get("participants", [])
        home = participants[0]["name"] if len(participants) > 0 else "?"
        away = participants[1]["name"] if len(participants) > 1 else "?"

        # `parse_markets(raw, platform=...)` walks the raw response and
        # returns a list of `NormalizedMarket` objects — one per market
        # the registry recognises (1X2, O/U, BTTS, DC by default).
        markets = parse_markets(detail, platform="betpawa")

        # `extract_sportradar_id` looks at `widgets[]` for the
        # `type == "SPORTRADAR"` entry and returns its `.id` (stripping
        # the `sr:match:` prefix). Returns None if no widget is present.
        sr_id = extract_sportradar_id(detail, platform="betpawa")

    return {"home": home, "away": away, "markets": markets, "sr_id": sr_id}


# --- Step 2: Fetch the other 4 bookmakers using the SR id ---
#
# Each helper below is intentionally written the same way:
#   1. Open the bookmaker's async context.
#   2. Use the right method to fetch markets given the SR id.
#   3. Hand the raw response to `parse_markets` (or, for Betway, use
#      `get_markets` because Betway has a separate markets endpoint).
#   4. Return {"markets": [...]} — empty list on failure.
#
# All four are dispatched in parallel via `asyncio.gather` in main().


async def fetch_sportybet(sr_prefixed: str, *, live: bool) -> dict:
    async with SportyBet(country="ng") as sb:
        # SportyBet's eventId IS the SR id (e.g. "sr:match:69339436"),
        # so we pass it through directly. The `live=True` flag switches
        # the endpoint's `productId` from 3 (prematch) to 1 (live) —
        # productId=3 returns only player-prop markets for in-play games.
        detail = await sb.get_event_detail(event_id=sr_prefixed, live=live)
        return {"markets": parse_markets(detail, platform="sportybet")}


async def fetch_msport(sr_prefixed: str, *, live: bool) -> dict:
    async with MSport(country="ng") as ms:
        # Same shape as SportyBet — SR id direct lookup, productId switch.
        detail = await ms.get_event_detail(event_id=sr_prefixed, live=live)
        return {"markets": parse_markets(detail, platform="msport")}


async def fetch_betway(sr_numeric: str) -> dict:
    async with Betway(country="ng") as bw:
        # Betway is special: it splits "event metadata" and "markets/odds"
        # across two endpoints. `get_event_detail` returns scoreboard
        # info but no markets. The convenience method `get_markets`
        # internally calls Betway's `get_event_markets` (the markets
        # endpoint) and runs the parser. Betway's eventId is the bare
        # numeric SR id, no prefix.
        return {"markets": await bw.get_markets(event_id=sr_numeric)}


async def fetch_bet9ja(sr_numeric: str, *, live: bool) -> dict:
    async with Bet9ja(country="ng") as b9:
        # Bet9ja uses internal ids, so first translate SR -> internal.
        # `find_event_id_by_sr_id` scans the live events list for a
        # matching `EXTID` and returns Bet9ja's numeric id. Returns None
        # if the event isn't currently live (this implementation only
        # searches live events for now).
        internal = await b9.find_event_id_by_sr_id(sr_numeric)
        if internal is None:
            return {"markets": []}

        # Live and prematch use *different* endpoints on Bet9ja:
        #   - live:    /PalimpsestLiveAjax/GetLiveEvent (param: EVENTID)
        #   - prematch: /PalimpsestAjax/GetEvent       (param: ID)
        # The parser handles the live `LIVES_*` key prefix and the
        # `{"v": <float>}` odds wrapper transparently — no extra work
        # here besides choosing the right method.
        if live:
            detail = await b9.get_live_event_detail(event_id=internal)
        else:
            detail = await b9.get_event_detail(event_id=internal)
        return {"markets": parse_markets(detail, platform="bet9ja")}


# --- Step 3: Flatten markets into CSV rows ---
#
# Each `NormalizedMarket` has a canonical_id (e.g. "1x2_ft") plus either:
#   - a flat `outcomes` list (for non-parameterized markets like 1X2,
#     BTTS, DC), or
#   - a `lines` dict {line_value: [outcomes]} (for parameterized markets
#     like Over/Under).
#
# We want one CSV row per (market, line, outcome) triple, with one column
# per bookmaker. We build a nested dict keyed by that triple, then flatten
# it. The dict structure is:
#   rows[(canonical_market_id, market_name, line, canonical_outcome)] = {
#       bookmaker_name: odds, ...
#   }
def build_rows(per_bookmaker: dict) -> list[dict]:
    # `defaultdict(dict)` so we can write `rows[key][bookie] = odds`
    # without first checking if the key exists.
    rows: dict[tuple, dict] = defaultdict(dict)

    for bookie_name, payload in per_bookmaker.items():
        for m in payload.get("markets", []):
            if m.lines is not None:
                # Parameterized market — one logical row per (line, outcome).
                for line, outcomes in m.lines.items():
                    for o in outcomes:
                        key = (m.canonical_id, m.name, line, o.canonical_name)
                        rows[key][bookie_name] = o.odds
            else:
                # Simple market — one logical row per outcome, line is "".
                for o in m.outcomes:
                    key = (m.canonical_id, m.name, "", o.canonical_name)
                    rows[key][bookie_name] = o.odds

    # Sort for stable, readable output: by market name, then by line value
    # (numeric where present), then by outcome name. The empty-string line
    # for non-parameterized markets sorts before the numeric ones via the
    # `(0, "")` vs `(1, line)` tuple — keeps 1X2 above O/U lines.
    def sort_key(item):
        canonical_id, name, line, outcome = item[0]
        line_key = (1, float(line)) if line != "" else (0, 0.0)
        return (name, line_key, outcome)

    sorted_rows = sorted(rows.items(), key=sort_key)

    # Build dict-rows ready for csv.DictWriter. The bookmaker columns are
    # filled with the empty string when a bookmaker didn't have that market
    # / line / outcome — keeps the CSV grid rectangular.
    bookies = list(per_bookmaker.keys())
    return [
        {
            "market": name,
            "line": line if line != "" else "",
            "outcome": outcome,
            **{b: odds_by_bookie.get(b, "") for b in bookies},
        }
        for (canonical_id, name, line, outcome), odds_by_bookie in sorted_rows
    ]


# --- Step 4: Write CSV ---
#
# `csv.DictWriter` is the simplest way to get a header row + rectangular
# CSV. `newline=""` is required on Windows to avoid double line endings.
def write_csv(rows: list[dict], path: str, bookies: list[str]) -> None:
    fieldnames = ["market", "line", "outcome"] + bookies
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# --- Step 5: Putting it together ---
async def main(betpawa_id: str, live: bool, csv_path: str) -> None:
    print(f"Looking up BetPawa event id: {betpawa_id}  mode: {'LIVE' if live else 'PREMATCH'}")  # noqa: E501

    # First call: BetPawa. We need its result before we can dispatch the
    # other four (we need the SR id from the widget).
    bp = await fetch_betpawa(betpawa_id)
    sr_numeric = bp["sr_id"]
    if sr_numeric is None:
        print("ERROR: BetPawa event has no SPORTRADAR widget — cannot resolve.")
        return
    sr_prefixed = f"sr:match:{sr_numeric}"
    print(f"Match: {bp['home']} vs {bp['away']}")
    print(f"SportRadar id: {sr_prefixed}")

    # Now dispatch the other four in parallel — they're independent.
    sb_res, ms_res, bw_res, b9_res = await asyncio.gather(
        fetch_sportybet(sr_prefixed, live=live),
        fetch_msport(sr_prefixed, live=live),
        fetch_betway(sr_numeric),
        fetch_bet9ja(sr_numeric, live=live),
    )

    # Bundle results keyed by display name. Order here is the column
    # order in the CSV. SportPesa is included as an empty placeholder
    # column — no SR-id reverse search yet, and the API needs warmed
    # Akamai cookies anyway.
    per_bookmaker = {
        "BetPawa": {"markets": bp["markets"]},
        "SportyBet": sb_res,
        "MSport": ms_res,
        "Betway": bw_res,
        "Bet9ja": b9_res,
        "SportPesa": {"markets": []},
    }

    # Quick console summary so the user can see at a glance whether each
    # bookmaker actually returned data, before opening the CSV.
    print("\nMatched markets per bookmaker:")
    for name, payload in per_bookmaker.items():
        print(f"  {name:<10} {len(payload.get('markets', []))} markets")

    rows = build_rows(per_bookmaker)
    write_csv(rows, csv_path, list(per_bookmaker.keys()))
    print(f"\nWrote {len(rows)} rows to {csv_path}")


if __name__ == "__main__":
    # `argparse` keeps the CLI surface tiny but discoverable.
    parser = argparse.ArgumentParser(
        description="Compare odds across 6 bookmakers, starting from a BetPawa event id."  # noqa: E501
    )
    parser.add_argument("betpawa_id", help="BetPawa internal event id (e.g. 32299257)")
    parser.add_argument(
        "--prematch", action="store_true",
        help="Use prematch endpoints instead of live (default: live).",
    )
    parser.add_argument(
        "--csv", default="odds_comparison.csv",
        help="Output CSV path (default: odds_comparison.csv).",
    )
    args = parser.parse_args()

    # `asyncio.run` is the right entry-point for a top-level async main.
    asyncio.run(main(args.betpawa_id, live=not args.prematch, csv_path=args.csv))
