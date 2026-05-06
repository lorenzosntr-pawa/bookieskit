"""
Monitor odds across 4 bookmakers (BetPawa, SportyBet, Bet9ja, Betway) for two
specific BetPawa competitions, ticking every 10 minutes.

WHAT THIS SCRIPT DOES
    On each tick, for every event in BetPawa competitions 13344 and 12385:
      1. Reads the event's BetPawa detail (gets BetPawa id, SR id, BetPawa odds).
      2. Detects whether the event is currently in-play. If it is, fetches LIVE
         odds from SportyBet / Bet9ja / Betway. If not, fetches PREMATCH odds.
      3. Filters down to the markets we care about: 1X2, BTTS, Over/Under (only
         the 2.5 line), 1X2 1Up, 1X2 2Up. Skips Double Chance entirely.
      4. Appends one CSV row per (event, market, line, outcome) with a UTC
         timestamp, BetPawa id, and SR id.

    The script then sleeps 10 minutes and repeats. Output CSV grows over time —
    each tick is a snapshot, suitable for time-series analysis.

WHY MSPORT IS SKIPPED
    Per request — MSport excluded from this monitoring run.

WHY DOUBLE CHANCE IS SKIPPED
    Per request — DC excluded from this monitoring run.

USAGE
    python examples/monitor_competitions.py
        Run forever, ticking every 10 minutes, appending to monitor_odds.csv.

    python examples/monitor_competitions.py --once
        Single tick, useful for testing without the 10-minute wait.

    python examples/monitor_competitions.py --csv my_run.csv
        Override the output CSV path.

STOPPING
    Ctrl-C cleanly stops the loop after the current tick finishes.
"""

# Standard library only — keeps the script obvious.
import argparse
import asyncio
import csv
import os
from collections import defaultdict
from datetime import datetime, timezone

# Public surface of the library — only what we need.
from bookieskit import Bet9ja, BetPawa, Betway, SportyBet
from bookieskit.markets import parse_markets
from bookieskit.matching import extract_sportradar_id


# ----------------------------------------------------------------------
# Configuration. All hard-coded values are here at the top so changes
# are easy to find.
# ----------------------------------------------------------------------

# BetPawa competition ids to monitor.
COMPETITIONS = ["13344", "12385"]

# Interval between ticks in seconds. 10 minutes.
INTERVAL_SECONDS = 600

# Markets to include in the CSV. Names are the canonical ids from the
# library's MarketRegistry (see docs/markets.md). Note: double_chance_ft
# is intentionally absent.
ALLOWED_MARKETS = {
    "1x2_ft",
    "btts_ft",
    "over_under_ft",
    "1x2_1up_ft",
    "1x2_2up_ft",
}

# For Over/Under, only the 2.5 line is kept. All other lines (0.5, 1.5,
# 3.5, etc.) are dropped at row-flatten time.
OU_ALLOWED_LINES = {2.5}

# Bookmakers (in column order). MSport is intentionally absent.
BOOKMAKERS = ["BetPawa", "SportyBet", "Bet9ja", "Betway"]


# ----------------------------------------------------------------------
# Step 1: List events in a BetPawa competition.
# ----------------------------------------------------------------------
async def list_competition_events(bp: BetPawa, competition_id: str) -> list[dict]:
    """Return [{betpawa_id, home, away}, ...] for one BetPawa competition."""
    raw = await bp.get_events(tournament_id=competition_id)
    responses = raw.get("responses", [])
    events = responses[0].get("responses", []) if responses else []
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
# Step 2: Per-event BetPawa fetch — gets BetPawa odds, SR id, and a
# heuristic for live vs prematch state.
#
# We can't tell live state from the event-list response alone, but the
# event-detail response has it. Strategy: fetch detail, parse markets,
# extract SR id. If the detail's `status` (or any of several flag
# fields) indicates LIVE, mark this event as live. Otherwise treat as
# prematch.
# ----------------------------------------------------------------------
async def fetch_betpawa_event(bp: BetPawa, betpawa_id: str) -> dict:
    """Return {markets, sr_id, is_live}.  Empty markets / None sr_id are OK."""
    detail = await bp.get_event_detail(event_id=betpawa_id)
    markets = parse_markets(detail, platform="betpawa")
    sr_id = extract_sportradar_id(detail, platform="betpawa")
    is_live = _is_live_betpawa(detail)
    return {"markets": markets, "sr_id": sr_id, "is_live": is_live}


def _is_live_betpawa(detail: dict) -> bool:
    """Heuristic: detect whether a BetPawa event detail is currently in-play.

    BetPawa exposes the state under several possible fields depending on
    the response variant. We check a few common ones; if any says LIVE,
    we treat it as live.
    """
    for key in ("status", "state", "matchStatus"):
        v = str(detail.get(key, "")).upper()
        if v in {"LIVE", "INPLAY", "IN_PLAY"}:
            return True
    if detail.get("isLive") is True or detail.get("inPlay") is True:
        return True
    return False


# ----------------------------------------------------------------------
# Step 3: Other bookmakers, given the SR id and the live/prematch mode.
#
# Each helper opens its own client per call. That's a fresh httpx
# connection per event per tick — fine at our scale (a few events per
# competition, ticking every 10 minutes).
# ----------------------------------------------------------------------
async def fetch_sportybet(sr_prefixed: str, *, live: bool) -> list:
    async with SportyBet(country="ng") as sb:
        try:
            d = await sb.get_event_detail(event_id=sr_prefixed, live=live)
            return parse_markets(d, platform="sportybet")
        except Exception:
            return []


async def fetch_betway(sr_numeric: str) -> list:
    """Betway uses a separate markets endpoint via get_markets(); the same
    response shape covers both live and prematch."""
    async with Betway(country="ng") as bw:
        try:
            return await bw.get_markets(event_id=sr_numeric)
        except Exception:
            return []


async def fetch_bet9ja(
    sr_numeric: str, *, live: bool, lookup: dict[str, str]
) -> list:
    """Bet9ja needs a SR-id -> internal-id translation. The caller passes
    the right pre-built lookup dict (live or prematch). If the SR id
    isn't in the lookup, the event isn't on Bet9ja right now."""
    internal = lookup.get(sr_numeric)
    if internal is None:
        return []
    async with Bet9ja(country="ng") as b9:
        try:
            if live:
                d = await b9.get_live_event_detail(event_id=internal)
            else:
                d = await b9.get_event_detail(event_id=internal)
            return parse_markets(d, platform="bet9ja")
        except Exception:
            return []


# ----------------------------------------------------------------------
# Step 4: Build Bet9ja's two SR-id -> internal-id maps once per tick.
#
# Live: cheap, single API call.
# Prematch: walks every soccer tournament — takes a few seconds. We
# build it lazily and only if at least one prematch event needs it.
# ----------------------------------------------------------------------
async def build_bet9ja_maps(b9: Bet9ja, *, need_prematch: bool) -> dict[str, dict[str, str]]:
    """Returns {'live': dict, 'prematch': dict}. Prematch is empty if
    need_prematch is False — saves a slow walk when all events are live."""
    out: dict[str, dict[str, str]] = {"live": {}, "prematch": {}}

    # Live: one call.
    resp = await b9.get_live_events(sport_id="3000001")
    events = (resp.get("D") or {}).get("E") or {}
    out["live"] = {
        str(ev.get("EXTID", "") or ""): str(internal_id)
        for internal_id, ev in events.items()
        if ev.get("EXTID")
    }

    # Prematch: only if needed.
    if need_prematch:
        out["prematch"] = await b9.build_prematch_event_map(sport_id="1")

    return out


# ----------------------------------------------------------------------
# Step 5: Filter markets to the allowed set + only the 2.5 OU line.
#
# We don't reconstruct NormalizedMarket objects — instead we work
# directly on the per-bookmaker market list and apply the filter when
# building rows. Keeping it in build_rows means one place to enforce
# the rules.
# ----------------------------------------------------------------------
def _outcomes_to_emit(market) -> list[tuple[str, str, float]]:
    """Yield (line_str, canonical_outcome, odds) tuples for one market,
    filtered per the script's rules.

    - Skip markets not in ALLOWED_MARKETS.
    - For over_under_ft, only the lines in OU_ALLOWED_LINES.
    """
    if market.canonical_id not in ALLOWED_MARKETS:
        return []

    out: list[tuple[str, str, float]] = []
    if market.lines is not None:
        # Parameterized market.
        for line, outcomes in market.lines.items():
            if market.canonical_id == "over_under_ft" and line not in OU_ALLOWED_LINES:
                continue
            for o in outcomes:
                out.append((str(line), o.canonical_name, o.odds))
    else:
        # Simple market — empty line.
        for o in market.outcomes:
            out.append(("", o.canonical_name, o.odds))
    return out


# ----------------------------------------------------------------------
# Step 6: Flatten one event's per-bookmaker markets into rows.
# ----------------------------------------------------------------------
def event_rows(
    timestamp: str,
    event_meta: dict,
    sr_numeric: str,
    mode: str,
    per_bookmaker: dict[str, list],
) -> list[dict]:
    """Build CSV rows for one event."""
    # Nested grid: (canonical_id, market_name, line, outcome) -> {bookie: odds}
    grid: dict[tuple, dict[str, float]] = defaultdict(dict)

    for bookie, markets in per_bookmaker.items():
        for m in markets:
            for line, outcome, odds in _outcomes_to_emit(m):
                key = (m.canonical_id, m.name, line, outcome)
                grid[key][bookie] = odds

    # Sort: market name, then numeric line (empty first), then outcome.
    def sort_key(item):
        _cid, name, line, outcome = item[0]
        line_key = (1, float(line)) if line != "" else (0, 0.0)
        return (name, line_key, outcome)

    rows: list[dict] = []
    for (_cid, name, line, outcome), per_bookie in sorted(grid.items(), key=sort_key):
        rows.append({
            "timestamp": timestamp,
            "mode": mode,
            "betpawa_id": event_meta["betpawa_id"],
            "sr_id": sr_numeric,
            "home": event_meta["home"],
            "away": event_meta["away"],
            "market": name,
            "line": line,
            "outcome": outcome,
            **{b: per_bookie.get(b, "") for b in BOOKMAKERS},
        })
    return rows


# ----------------------------------------------------------------------
# Step 7: CSV append.
#
# Each tick appends to the same file. If the file is empty / new, write
# the header row first.
# ----------------------------------------------------------------------
def append_csv(rows: list[dict], path: str) -> None:
    fieldnames = [
        "timestamp", "mode", "betpawa_id", "sr_id", "home", "away",
        "market", "line", "outcome",
    ] + BOOKMAKERS
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


# ----------------------------------------------------------------------
# Step 8: One full tick — list events, fetch all data, write rows.
# ----------------------------------------------------------------------
async def run_tick(csv_path: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"\n[{timestamp}] tick start")

    all_rows: list[dict] = []
    total_events = 0

    async with BetPawa(country="ng") as bp, Bet9ja(country="ng") as b9:
        # --- Phase A: list every event, fetch BetPawa detail to learn
        # SR id and live state. We do this BEFORE building the Bet9ja
        # prematch map so we know whether we actually need it. ---
        per_event_payload: list[tuple[dict, dict]] = []
        for comp_id in COMPETITIONS:
            try:
                events = await list_competition_events(bp, comp_id)
            except Exception as e:
                print(f"  competition {comp_id}: ERROR {e}")
                continue
            print(f"  competition {comp_id}: {len(events)} events")
            for ev in events:
                try:
                    bp_data = await fetch_betpawa_event(bp, ev["betpawa_id"])
                except Exception as e:
                    print(f"    {ev['home']} vs {ev['away']}: BetPawa ERROR {e}")
                    continue
                per_event_payload.append((ev, bp_data))
        total_events = len(per_event_payload)

        # Decide whether we need the (slow) prematch Bet9ja walk.
        need_prematch = any(not bp_data["is_live"] for _ev, bp_data in per_event_payload)
        bet9ja_maps = await build_bet9ja_maps(b9, need_prematch=need_prematch)
        print(f"  Bet9ja lookups: live={len(bet9ja_maps['live'])}, "
              f"prematch={len(bet9ja_maps['prematch'])}")

        # --- Phase B: per-event, fetch other 3 bookmakers in parallel. ---
        for ev, bp_data in per_event_payload:
            sr_numeric = bp_data["sr_id"]
            mode = "live" if bp_data["is_live"] else "prematch"

            if sr_numeric is None:
                # No SR id — record BetPawa-only rows.
                per_bookmaker = {
                    "BetPawa": bp_data["markets"],
                    "SportyBet": [], "Bet9ja": [], "Betway": [],
                }
                all_rows.extend(event_rows(
                    timestamp, ev, sr_numeric or "", mode, per_bookmaker,
                ))
                continue

            sr_prefixed = f"sr:match:{sr_numeric}"
            live = bp_data["is_live"]
            lookup = bet9ja_maps["live" if live else "prematch"]

            sb_markets, bw_markets, b9_markets = await asyncio.gather(
                fetch_sportybet(sr_prefixed, live=live),
                fetch_betway(sr_numeric),
                fetch_bet9ja(sr_numeric, live=live, lookup=lookup),
            )

            per_bookmaker = {
                "BetPawa": bp_data["markets"],
                "SportyBet": sb_markets,
                "Bet9ja": b9_markets,
                "Betway": bw_markets,
            }
            counts = " ".join(
                f"{name[:2]}={len(per_bookmaker[name])}" for name in BOOKMAKERS
            )
            # Deduplicate the BetPawa/Betway leading-letter clash for clarity.
            counts = counts.replace("Be=", "BP=", 1).replace("Be=", "BW=", 1)
            print(f"    [{mode}] {ev['home']} vs {ev['away']}: {counts}")

            all_rows.extend(event_rows(
                timestamp, ev, sr_numeric, mode, per_bookmaker,
            ))

    append_csv(all_rows, csv_path)
    print(f"[{timestamp}] tick end — {total_events} events, "
          f"{len(all_rows)} rows appended to {csv_path}")


# ----------------------------------------------------------------------
# Step 9: The outer loop.
# ----------------------------------------------------------------------
async def run_forever(csv_path: str) -> None:
    while True:
        try:
            await run_tick(csv_path)
        except Exception as e:
            # Don't let one bad tick kill the loop.
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            print(f"[{now}] tick failed: {e}")
        # Sleep until the next tick.
        await asyncio.sleep(INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Monitor odds across BetPawa/SportyBet/Bet9ja/Betway for two "
                     "BetPawa competitions, ticking every 10 minutes."),
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single tick and exit (useful for testing).",
    )
    parser.add_argument(
        "--csv", default="monitor_odds.csv",
        help="Output CSV path (default: monitor_odds.csv). Appended to.",
    )
    args = parser.parse_args()

    if args.once:
        asyncio.run(run_tick(args.csv))
    else:
        try:
            asyncio.run(run_forever(args.csv))
        except KeyboardInterrupt:
            print("\nstopped (Ctrl-C)")


if __name__ == "__main__":
    main()
