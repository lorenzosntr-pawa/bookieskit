"""
Monitor odds across 4 bookmakers (BetPawa, SportyBet, Bet9ja, Betway) for a
fixed list of BetPawa event ids, ticking every 10 minutes.

WHAT THIS SCRIPT DOES
    On each tick, for every BetPawa event id in BETPAWA_EVENT_IDS below:
      1. (First tick only) resolves the event's SR id, home/away names, and
         kickoff time from BetPawa. These are cached for the rest of the run.
      2. Compares kickoff time to current UTC time to pick mode:
           - now < kickoff   -> prematch
           - now >= kickoff  -> live
      3. Dispatches ALL 4 bookmakers in parallel via asyncio.gather, so the
         odds snapshot from each provider is taken at (essentially) the same
         instant.
      4. From the BetPawa response, extracts live match info when available:
         current minute, period name, and home/away score.
      5. Filters markets down to: 1X2, BTTS, Over/Under (only the 2.5 line),
         1X2 1Up, 1X2 2Up. Skips Double Chance entirely.
      6. Appends one CSV row per (event, market, line, outcome) with a UTC
         timestamp, BetPawa id, SR id, and the live-match-info columns
         (empty during prematch).

    The script sleeps 10 minutes and repeats. Output CSV grows over time —
    each tick is a snapshot, suitable for time-series analysis.

    To switch to a different event set, edit BETPAWA_EVENT_IDS below.

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
from bookieskit import (
    Bet9ja,
    BetPawa,
    Betway,
    LiveInfo,
    SportyBet,
    extract_kickoff,
    extract_live_info,
    extract_participants,
    is_live_now,
)
from bookieskit.markets import parse_markets
from bookieskit.matching import extract_sportradar_id

# ----------------------------------------------------------------------
# Configuration. All hard-coded values are here at the top so changes
# are easy to find.
# ----------------------------------------------------------------------

# BetPawa event ids to monitor. Each id corresponds to a single match;
# the script will fetch live or prematch odds per event automatically
# based on each event's current state.
BETPAWA_EVENT_IDS = ["33289995", "33248210"]
# BETPAWA_EVENT_IDS = ["33204225"]

# Interval between ticks. We monitor more aggressively during live
# (live odds move quickly) and back off during prematch (odds drift
# slowly when no match is in progress).
INTERVAL_SECONDS_PREMATCH = 600  # 10 minutes when all events are prematch
INTERVAL_SECONDS_LIVE = 120      # 2 minutes when at least one event is live

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
# Step 1: Per-event cache.
#
# For each BetPawa event id we monitor, we resolve once and cache:
#   - sr_numeric:  the SportRadar id (from the SPORTRADAR widget)
#   - home / away: team names (from participants[])
#   - kickoff_utc: tz-aware datetime parsed from BetPawa's startTime
#                  (ISO 8601, ends with Z)
#
# These don't change for the duration of an event, so we resolve them
# the first time we see the event and reuse forever. This lets every
# subsequent tick fire all 4 bookmaker fetches in parallel — including
# BetPawa — because the SR id and mode decision don't depend on a
# fresh BetPawa call.
# ----------------------------------------------------------------------
EVENT_CACHE: dict[str, dict] = {}


async def resolve_event(bp: BetPawa, betpawa_id: str) -> dict | None:
    """One-shot resolve of static event metadata. Returns None on failure."""
    if betpawa_id in EVENT_CACHE:
        return EVENT_CACHE[betpawa_id]
    try:
        detail = await bp.get_event_detail(event_id=betpawa_id)
    except Exception as e:
        print(f"  resolve {betpawa_id}: ERROR {e}")
        return None
    parts = extract_participants(detail, platform="betpawa")
    sr_numeric = extract_sportradar_id(detail, platform="betpawa")
    kickoff = extract_kickoff(detail, platform="betpawa")
    EVENT_CACHE[betpawa_id] = {
        "sr_numeric": sr_numeric,
        "home": parts.home or "?",
        "away": parts.away or "?",
        "kickoff_utc": kickoff,
    }
    return EVENT_CACHE[betpawa_id]


# ----------------------------------------------------------------------
# Step 2: Per-tick BetPawa fetch — markets + live info (minute, period,
# scores). Returns the markets list AND the live-info dataclass.
# ----------------------------------------------------------------------
async def fetch_betpawa_tick(bp: BetPawa, betpawa_id: str) -> dict:
    """Fetch fresh BetPawa data for one tick. Returns {markets, live_info}."""
    try:
        detail = await bp.get_event_detail(event_id=betpawa_id)
    except Exception:
        return {"markets": [], "live_info": LiveInfo()}
    markets = parse_markets(detail, platform="betpawa")
    live_info = extract_live_info(detail, platform="betpawa")
    return {"markets": markets, "live_info": live_info}


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
async def build_bet9ja_maps(
    b9: Bet9ja, *, need_prematch: bool
) -> dict[str, dict[str, str]]:
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
    live_info: LiveInfo,
    per_bookmaker: dict[str, list],
) -> list[dict]:
    """Build CSV rows for one event."""
    grid: dict[tuple, dict[str, float]] = defaultdict(dict)

    for bookie, markets in per_bookmaker.items():
        for m in markets:
            for line, outcome, odds in _outcomes_to_emit(m):
                key = (m.canonical_id, m.name, line, outcome)
                grid[key][bookie] = odds

    def sort_key(item):
        _cid, name, line, outcome = item[0]
        line_key = (1, float(line)) if line != "" else (0, 0.0)
        return (name, line_key, outcome)

    def _s(v: object) -> str:
        return "" if v is None else str(v)

    rows: list[dict] = []
    for (_cid, name, line, outcome), per_bookie in sorted(grid.items(), key=sort_key):
        rows.append({
            "timestamp": timestamp,
            "mode": mode,
            "betpawa_id": event_meta["betpawa_id"],
            "sr_id": sr_numeric,
            "home": event_meta["home"],
            "away": event_meta["away"],
            "minute": _s(live_info.minute),
            "period": _s(live_info.period),
            "score_home": _s(live_info.score_home),
            "score_away": _s(live_info.score_away),
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
        "minute", "period", "score_home", "score_away",
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
    print(f"\n[{timestamp}] tick start ({len(BETPAWA_EVENT_IDS)} events)")

    all_rows: list[dict] = []
    short = {"BetPawa": "BP", "SportyBet": "SB", "Bet9ja": "B9", "Betway": "BW"}

    async with BetPawa(country="ng") as bp, Bet9ja(country="ng") as b9:
        # --- Phase A: ensure cache is populated (one-shot per event id).
        # Subsequent ticks skip this — the cache stays warm for the run. ---
        cached: list[tuple[str, dict]] = []
        for bp_id in BETPAWA_EVENT_IDS:
            entry = await resolve_event(bp, bp_id)
            if entry is None:
                continue
            cached.append((bp_id, entry))
            kickoff_str = (
                entry["kickoff_utc"].isoformat(timespec="seconds")
                if entry["kickoff_utc"] else "?"
            )
            mode = "live" if is_live_now(entry["kickoff_utc"]) else "prematch"
            print(f"  {bp_id}  {entry['home']} vs {entry['away']}  "
                  f"sr={entry['sr_numeric']}  kickoff={kickoff_str}  mode={mode}")

        # --- Phase B: build Bet9ja's SR-id -> internal-id maps.
        # Live: cheap, always. Prematch: slow walk; only if any event needs it. ---
        need_prematch = any(
            not is_live_now(entry["kickoff_utc"]) for _, entry in cached
        )
        bet9ja_maps = await build_bet9ja_maps(b9, need_prematch=need_prematch)
        print(f"  Bet9ja lookups: live={len(bet9ja_maps['live'])}, "
              f"prematch={len(bet9ja_maps['prematch'])}")

        # --- Phase C: per event, fire ALL 4 bookmaker fetches in parallel.
        # BetPawa is in the gather alongside SportyBet/Bet9ja/Betway, so
        # the four snapshots are taken at (essentially) the same instant. ---
        for bp_id, entry in cached:
            sr_numeric = entry["sr_numeric"]
            live = is_live_now(entry["kickoff_utc"])
            mode = "live" if live else "prematch"
            ev_meta = {
                "betpawa_id": bp_id,
                "home": entry["home"],
                "away": entry["away"],
            }

            # All four fetches dispatched together. If we have no SR id,
            # the other three return [] without an API call.
            sr_prefixed = f"sr:match:{sr_numeric}" if sr_numeric else None
            lookup = bet9ja_maps["live" if live else "prematch"]

            async def _empty_markets() -> list:
                return []

            tasks = [
                fetch_betpawa_tick(bp, bp_id),
                fetch_sportybet(sr_prefixed, live=live)
                if sr_prefixed else _empty_markets(),
                fetch_betway(sr_numeric) if sr_numeric else _empty_markets(),
                fetch_bet9ja(sr_numeric, live=live, lookup=lookup)
                if sr_numeric else _empty_markets(),
            ]
            bp_result, sb_markets, bw_markets, b9_markets = await asyncio.gather(*tasks)

            per_bookmaker = {
                "BetPawa": bp_result["markets"],
                "SportyBet": sb_markets,
                "Bet9ja": b9_markets,
                "Betway": bw_markets,
            }
            live_info = bp_result["live_info"] if live else LiveInfo()

            counts = " ".join(
                f"{short[name]}={len(per_bookmaker[name])}" for name in BOOKMAKERS
            )
            extra = ""
            if live and live_info.minute is not None:
                extra = (f"  [{live_info.period or ''} {live_info.minute}'  "
                         f"{live_info.score_home}-{live_info.score_away}]")
            print(f"    [{mode}] {entry['home']} vs {entry['away']}: {counts}{extra}")

            all_rows.extend(event_rows(
                timestamp, ev_meta, sr_numeric or "", mode, live_info, per_bookmaker,
            ))

    append_csv(all_rows, csv_path)
    print(f"[{timestamp}] tick end — {len(cached)} events, "
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
        # Pick the next-tick interval based on current live state. As
        # soon as any monitored event has kicked off, we drop to the
        # tighter cadence; once all events are over (in practice: when
        # they go to settled / scrubbed off), this naturally returns to
        # the relaxed cadence.
        any_live = any(
            is_live_now((EVENT_CACHE.get(bp_id) or {}).get("kickoff_utc"))
            for bp_id in BETPAWA_EVENT_IDS
        )
        sleep_s = INTERVAL_SECONDS_LIVE if any_live else INTERVAL_SECONDS_PREMATCH
        cadence = "live" if any_live else "prematch"
        print(f"  next tick in {sleep_s}s ({cadence} cadence)")
        await asyncio.sleep(sleep_s)


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
