#!/usr/bin/env python3
"""One-shot BetPawa 2-event market-availability monitor -> SQLite.

A standalone, portable monitor the owner drops on an in-region server to track
market availability for **two** BetPawa events across their whole lifecycle, then
diff the two. It is **stdlib-only** (Python 3.8+) and does **not** import the
``bookieskit`` library — copy this single file to a server and run it.

Usage
-----
Monitor two events (poll ~10 min while upcoming, ~2 min while live, stop each
event when it ends; the whole run ends once both events have ended, bounded by
``--max-hours``)::

    python betpawa_availability_monitor.py --country ng \
        --events 35429065 33289995 --db run.sqlite \
        [--prematch-interval 600] [--live-interval 120] [--max-hours 8]

Diff the captured availability between the two fixtures afterwards::

    python betpawa_availability_monitor.py --summarize run.sqlite

Each scrape records, per market (mapped or not), its presence plus breadth
(number of lines and outcomes) into SQLite tables ``meta``, ``scrape`` and
``market_sample``. ``--summarize`` prints which markets appeared on event A vs B
vs both, with peak line/outcome counts — surfacing the markets added to only one
fixture.

In-region requirement
---------------------
BetPawa geo-blocks US/cloud IPs (HTTP 403), so the host MUST sit on an
in-region / Africa-reachable IP, exactly like the live canary. Run it
backgrounded (``nohup ... &``, ``screen``/``tmux``, or a ``systemd`` unit) so it
survives logout, then ``--summarize`` the DB.

Ended-detection (decide-and-document)
-------------------------------------
An event is treated as *ended* when any of: the event payload reports a finished
period slug (``FINISHED_SLUGS``); the event-detail fetch returns HTTP 404 (the
event was removed post-match); or the event has been *live* for longer than
``max_live_hours`` (default 4h). These layered backstops — plus the global
``--max-hours`` cap — guarantee the run always terminates even if BetPawa's exact
finished-slug strings differ from those guessed here (no ended-state fixture was
available to verify them).
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# --- Inlined BetPawa endpoint config (mirrors src/bookieskit/bookmakers/betpawa.py) ---

DOMAINS = {
    "ng": "https://www.betpawa.ng",
    "gh": "https://www.betpawa.com.gh",
    "ke": "https://www.betpawa.co.ke",
    "ug": "https://www.betpawa.co.ug",
    "tz": "https://www.betpawa.co.tz",
    "zm": "https://www.betpawa.co.zm",
    "rw": "https://www.betpawa.rw",
    "cm": "https://www.betpawa.cm",
    "sl": "https://www.betpawa.sl",
    "bj": "https://www.betpawa.bj",
    "cg": "https://cg.betpawa.com",
    "cd": "https://www.betpawa.cd",
    "ls": "https://ls.betpawa.com",
    "mw": "https://www.betpawa.mw",
    "mz": "https://www.betpawa.co.mz",
}

BRAND_MAP = {
    "ng": "betpawa-nigeria",
    "gh": "betpawa-ghana",
    "ke": "betpawa-kenya",
    "ug": "betpawa-uganda",
    "tz": "betpawa-tanzania",
    "zm": "betpawa-zambia",
    "rw": "betpawa-rwanda",
    "cm": "betpawa-cameroon",
    "sl": "betpawa-sierraleone",
    "bj": "betpawa-benin",
    "cg": "betpawa-congobrazzaville",
    "cd": "betpawa-drc",
    "ls": "betpawa-lesotho",
    "mw": "betpawa-malawi",
    "mz": "betpawa-mozambique",
}

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)

# Best-effort finished-period slugs (no ended-state fixture exists to verify
# these exactly; the 404 + max_live_hours backstops guarantee termination).
FINISHED_SLUGS = {
    "MATCH_FINISHED",
    "ENDED",
    "FINISHED",
    "AFTER_EXTRA_TIME",
    "AFTER_PENALTIES",
    "MATCH_ABOUT_TO_END",
}


class NotFound(Exception):
    """The event-detail endpoint returned HTTP 404 (event removed/ended)."""


# --- Pure logic --------------------------------------------------------------


def _parse_iso(value):
    """Parse an ISO-8601 timestamp (trailing ``Z`` allowed) to tz-aware UTC."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def detect_phase(payload, now):
    """Return the event phase: ``"upcoming"``, ``"live"`` or ``"ended"``.

    ``now`` is a tz-aware UTC ``datetime``. When ``results`` is absent the event
    has not started: it is *upcoming* before kickoff and *live* once kickoff has
    passed (results lag the whistle). When ``results`` is present the event is
    *live*, or *ended* if the current period slug is a finished marker.
    """
    results = payload.get("results")
    if results is None:
        start = payload.get("startTime")
        if start:
            try:
                if now < _parse_iso(start):
                    return "upcoming"
            except ValueError:
                pass
        return "live"
    slug = (
        (results.get("display") or {}).get("currentPeriod") or {}
    ).get("slug")
    if slug in FINISHED_SLUGS:
        return "ended"
    return "live"


def extract_event_meta(payload):
    """Pull stable identity/metadata fields out of an event payload."""
    return {
        "id": str(payload.get("id", "")),
        "name": payload.get("name", ""),
        "participants": [p.get("name", "") for p in payload.get("participants") or []],
        "start_time": payload.get("startTime", ""),
        "total_market_count": payload.get("totalMarketCount", 0),
    }


def extract_market_samples(payload):
    """One presence+breadth record per market in the payload.

    ``num_lines`` = handicap lines (``row`` entries); ``num_outcomes`` = total
    selectable prices across lines; ``num_active`` = outcomes not suspended.
    """
    samples = []
    for market in payload.get("markets") or []:
        mtype = market.get("marketType") or {}
        rows = market.get("row") or []
        num_outcomes = 0
        num_active = 0
        for row in rows:
            for price in row.get("prices") or []:
                num_outcomes += 1
                if not price.get("suspended", False):
                    num_active += 1
        samples.append(
            {
                "market_id": str(mtype.get("id", "")),
                "market_name": mtype.get("name", ""),
                "display_name": mtype.get("displayName", ""),
                "num_lines": len(rows),
                "num_outcomes": num_outcomes,
                "num_active": num_active,
            }
        )
    return samples


# --- Persistence -------------------------------------------------------------


def init_db(path):
    """Open ``path`` and create the schema if missing; return the connection."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS scrape (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            ts REAL NOT NULL,
            iso TEXT NOT NULL,
            phase TEXT NOT NULL,
            ok INTEGER NOT NULL,
            total_market_count INTEGER,
            error TEXT
        );
        CREATE TABLE IF NOT EXISTS market_sample (
            scrape_id INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            market_id TEXT NOT NULL,
            market_name TEXT,
            display_name TEXT,
            num_lines INTEGER,
            num_outcomes INTEGER,
            num_active INTEGER
        );
        CREATE INDEX IF NOT EXISTS ix_sample_scrape ON market_sample(scrape_id);
        CREATE INDEX IF NOT EXISTS ix_scrape_event ON scrape(event_id);
        """
    )
    conn.commit()
    return conn


def record_meta(conn, items):
    """Upsert run-config key/value strings into ``meta``."""
    conn.executemany(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        [(str(k), str(v)) for k, v in items.items()],
    )
    conn.commit()


def record_scrape(conn, event_id, ts, phase, ok, payload, error):
    """Insert one scrape row (+ its market samples when ``ok``); return its id.

    Commits immediately so a crash mid-run preserves everything captured so far.
    """
    iso = datetime.fromtimestamp(ts, timezone.utc).isoformat()
    total = payload.get("totalMarketCount") if (ok and payload) else None
    cur = conn.execute(
        "INSERT INTO scrape(event_id, ts, iso, phase, ok, total_market_count, error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(event_id), ts, iso, phase, 1 if ok else 0, total, error),
    )
    scrape_id = cur.lastrowid
    if ok and payload:
        samples = extract_market_samples(payload)
        conn.executemany(
            "INSERT INTO market_sample(scrape_id, event_id, market_id, market_name, "
            "display_name, num_lines, num_outcomes, num_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    scrape_id,
                    str(event_id),
                    s["market_id"],
                    s["market_name"],
                    s["display_name"],
                    s["num_lines"],
                    s["num_outcomes"],
                    s["num_active"],
                )
                for s in samples
            ],
        )
    conn.commit()
    return scrape_id


# --- Network -----------------------------------------------------------------


def fetch_event(country, event_id, timeout=30):
    """Fetch full event detail (all markets) from BetPawa. Raises on failure."""
    domain = DOMAINS.get(country)
    if domain is None:
        raise ValueError(
            f"unknown country code: {country!r} (one of {sorted(DOMAINS)})"
        )
    url = f"{domain}/api/sportsbook/v3/events/{event_id}"
    headers = {
        "accept": "*/*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "devicetype": "web",
        "user-agent": _USER_AGENT,
        "x-pawa-brand": BRAND_MAP.get(country, f"betpawa-{country}"),
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise NotFound(f"event {event_id} not found (404)") from exc
        raise


# --- Monitor loop ------------------------------------------------------------


def run_monitor(
    db_path,
    country,
    event_ids,
    *,
    fetch_fn,
    now_fn,
    sleep_fn,
    prematch_interval,
    live_interval,
    max_hours,
    max_live_hours=4.0,
):
    """Poll each event on a phase-aware cadence until all end or ``max_hours``.

    Seams (``fetch_fn(country, event_id)``, ``now_fn() -> epoch``,
    ``sleep_fn(seconds)``) are injected so the lifecycle is testable offline.
    A fetch exception is recorded (``ok=0``) and retried next cycle; a
    :class:`NotFound` drops the event (removed == ended). An event also stops on
    a finished phase or after ``max_live_hours`` live.
    """
    conn = init_db(db_path)
    start_wall = now_fn()
    record_meta(
        conn,
        {
            "country": country,
            "event_ids": ",".join(event_ids),
            "prematch_interval": prematch_interval,
            "live_interval": live_interval,
            "max_hours": max_hours,
            "started_at": datetime.fromtimestamp(start_wall, timezone.utc).isoformat(),
        },
    )
    # Per-event state: next due time and the epoch we first saw it live.
    next_due = {eid: start_wall for eid in event_ids}
    live_since = {eid: None for eid in event_ids}
    named = set()  # events whose display name is already stored in meta
    active = set(event_ids)
    deadline = start_wall + max_hours * 3600.0

    while active:
        now = now_fn()
        if now >= deadline:
            break
        due = [eid for eid in active if next_due[eid] <= now]
        if not due:
            soonest = min(next_due[eid] for eid in active)
            sleep_fn(max(0.0, min(soonest, deadline) - now))
            continue
        for eid in due:
            tick = now_fn()
            try:
                payload = fetch_fn(country, eid)
            except NotFound as exc:
                record_scrape(conn, eid, tick, "ended", False, None, str(exc))
                active.discard(eid)
                continue
            except Exception as exc:  # noqa: BLE001 - any fetch error: log + retry
                record_scrape(conn, eid, tick, "unknown", False, None, repr(exc))
                next_due[eid] = tick + live_interval
                continue
            if eid not in named:
                meta = extract_event_meta(payload)
                record_meta(conn, {f"event_name:{eid}": meta["name"] or eid})
                named.add(eid)
            phase = detect_phase(payload, datetime.fromtimestamp(tick, timezone.utc))
            if phase == "live" and live_since[eid] is None:
                live_since[eid] = tick
            # Backstop: an event stuck "live" past max_live_hours is declared
            # ended so the run always terminates (slug-detection may miss).
            if (
                phase != "ended"
                and live_since[eid] is not None
                and (tick - live_since[eid]) >= max_live_hours * 3600.0
            ):
                phase = "ended"
            record_scrape(conn, eid, tick, phase, True, payload, None)
            if phase == "ended":
                active.discard(eid)
            else:
                interval = prematch_interval if phase == "upcoming" else live_interval
                next_due[eid] = tick + interval

    conn.close()


# --- Summarize / diff --------------------------------------------------------


def summarize(db_path):
    """Build a human-readable availability diff between the monitored events."""
    conn = sqlite3.connect(db_path)
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    event_ids = [e for e in (meta.get("event_ids", "").split(",")) if e]
    if not event_ids:
        event_ids = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT event_id FROM scrape ORDER BY event_id"
            )
        ]

    # Friendly per-event display name (team names), recorded on first scrape.
    ev_names = {eid: meta.get(f"event_name:{eid}", eid) for eid in event_ids}

    # Peak breadth per (event, market) + a friendly market name.
    rows = conn.execute(
        """
        SELECT event_id, market_id,
               MAX(market_name) AS name,
               MAX(num_lines) AS peak_lines,
               MAX(num_outcomes) AS peak_outcomes
        FROM market_sample
        GROUP BY event_id, market_id
        """
    ).fetchall()

    per_event = {eid: {} for eid in event_ids}
    names = {}
    for event_id, market_id, name, peak_lines, peak_outcomes in rows:
        per_event.setdefault(event_id, {})[market_id] = (peak_lines, peak_outcomes)
        if name:
            names[market_id] = name

    lines = []
    lines.append("BetPawa market-availability summary")
    lines.append("=" * 38)
    started = meta.get("started_at")
    if started:
        lines.append(f"run started: {started}")
    for eid in event_ids:
        scrapes = conn.execute(
            "SELECT COUNT(*) FROM scrape WHERE event_id=? AND ok=1", (eid,)
        ).fetchone()[0]
        fails = conn.execute(
            "SELECT COUNT(*) FROM scrape WHERE event_id=? AND ok=0", (eid,)
        ).fetchone()[0]
        lines.append(
            f"event {eid} ({ev_names[eid]}): {len(per_event.get(eid, {}))} "
            f"distinct markets over {scrapes} scrapes ({fails} failed)"
        )
    lines.append("")

    all_market_ids = sorted({mid for markets in per_event.values() for mid in markets})
    header = ["market", "name"] + [f"ev{eid}(lines/outcomes)" for eid in event_ids]
    lines.append(" | ".join(header))
    lines.append("-" * (len(" | ".join(header))))
    for mid in all_market_ids:
        cells = [mid, names.get(mid, "?")]
        for eid in event_ids:
            peak = per_event.get(eid, {}).get(mid)
            cells.append(f"{peak[0]}/{peak[1]}" if peak else "-")
        lines.append(" | ".join(cells))

    # Difference lists (the headline: markets added to only one fixture).
    lines.append("")
    lines.append("Difference (markets present on only one event)")
    lines.append("-" * 46)
    if len(event_ids) == 2:
        a, b = event_ids
        a_ids = set(per_event.get(a, {}))
        b_ids = set(per_event.get(b, {}))
        only_a = sorted(a_ids - b_ids)
        only_b = sorted(b_ids - a_ids)
        shared = a_ids & b_ids
        lines.append(f"shared by both: {len(shared)} markets")
        lines.append(f"only on event {a} ({ev_names[a]}) - {len(only_a)}:")
        for mid in only_a:
            lines.append(f"  - {mid} {names.get(mid, '?')}")
        lines.append(f"only on event {b} ({ev_names[b]}) - {len(only_b)}:")
        for mid in only_b:
            lines.append(f"  - {mid} {names.get(mid, '?')}")
    else:
        lines.append("(need exactly 2 events for a pairwise diff)")

    conn.close()
    return "\n".join(lines)


# --- CLI ---------------------------------------------------------------------


def build_arg_parser():
    """Construct the argparse parser for monitor and summarize modes."""
    parser = argparse.ArgumentParser(
        description="Monitor BetPawa market availability for two events -> SQLite.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--summarize", metavar="DB", help="print the diff for an existing DB and exit"
    )
    parser.add_argument("--country", help="BetPawa country code (e.g. ng, ke, gh)")
    parser.add_argument(
        "--events", nargs="+", metavar="EVENT_ID", help="two BetPawa numeric event IDs"
    )
    parser.add_argument(
        "--db", default="run.sqlite", help="SQLite output path (default: run.sqlite)"
    )
    parser.add_argument(
        "--prematch-interval",
        type=int,
        default=600,
        help="prematch poll seconds (default: 600)",
    )
    parser.add_argument(
        "--live-interval",
        type=int,
        default=120,
        help="live poll seconds (default: 120)",
    )
    parser.add_argument(
        "--max-hours",
        type=float,
        default=8.0,
        help="hard run cap in hours (default: 8)",
    )
    parser.add_argument(
        "--max-live-hours",
        type=float,
        default=4.0,
        help="stop an event after this many hours live (default: 4)",
    )
    return parser


def main(argv=None):
    """Entry point: dispatch summarize vs monitor mode."""
    args = build_arg_parser().parse_args(argv)

    if args.summarize:
        print(summarize(args.summarize))
        return 0

    if not args.country or not args.events:
        print("error: --country and --events are required to monitor", file=sys.stderr)
        return 2
    if args.country not in DOMAINS:
        print(
            f"error: unknown country {args.country!r}; one of {sorted(DOMAINS)}",
            file=sys.stderr,
        )
        return 2
    if len(args.events) != 2:
        print("error: provide exactly two --events IDs", file=sys.stderr)
        return 2

    print(
        f"monitoring BetPawa {args.country} events {args.events} -> {args.db} "
        f"(prematch {args.prematch_interval}s / live {args.live_interval}s, "
        f"cap {args.max_hours}h). In-region IP required.",
        file=sys.stderr,
    )
    run_monitor(
        args.db,
        args.country,
        list(args.events),
        fetch_fn=fetch_event,
        now_fn=time.time,
        sleep_fn=time.sleep,
        prematch_interval=args.prematch_interval,
        live_interval=args.live_interval,
        max_hours=args.max_hours,
        max_live_hours=args.max_live_hours,
    )
    print(
        f"done - summarize with: python {sys.argv[0]} --summarize {args.db}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
