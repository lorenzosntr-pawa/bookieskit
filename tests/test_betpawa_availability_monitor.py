"""Offline tests for the portable BetPawa availability monitor script.

The script lives in ``scripts/`` (outside the package, stdlib-only) so it can be
copied to a server as a single file. Tests load it by path and exercise the
pure logic + the full upcoming->live->ended lifecycle against committed BetPawa
event fixtures, with the network/clock/sleep replaced by injected seams (no live
calls — BetPawa geo-blocks CI).
"""

import importlib.util
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_MOD_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "betpawa_availability_monitor.py"
)
_spec = importlib.util.spec_from_file_location("betpawa_availability_monitor", _MOD_PATH)
mon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mon)

FIX = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "event_info" / "betpawa"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


# --- Task 1: phase detection -------------------------------------------------


def test_detect_phase_upcoming():
    p = _load("prematch.json")  # startTime 2026-05-06T11:00:00Z, results null
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    assert mon.detect_phase(p, now) == "upcoming"


def test_detect_phase_live_results_present():
    p = _load("live.json")  # results present, currentPeriod SECOND_HALF
    now = datetime(2026, 5, 6, 7, tzinfo=timezone.utc)
    assert mon.detect_phase(p, now) == "live"


def test_detect_phase_live_kickoff_passed_no_results():
    p = _load("prematch.json")
    now = datetime(2026, 5, 6, 12, tzinfo=timezone.utc)  # past startTime, results null
    assert mon.detect_phase(p, now) == "live"


def test_detect_phase_ended_finished_slug():
    p = _load("live.json")
    p["results"]["display"]["currentPeriod"]["slug"] = "MATCH_FINISHED"
    now = datetime(2026, 5, 6, 8, tzinfo=timezone.utc)
    assert mon.detect_phase(p, now) == "ended"


# --- Task 2: extraction ------------------------------------------------------


def test_extract_event_meta():
    m = mon.extract_event_meta(_load("wc_nf.json"))
    assert m["id"] == "35429065"
    assert m["name"] == "Norway - France (n)"
    assert m["participants"] == ["Norway", "France"]
    assert m["total_market_count"] == 173


def test_extract_market_samples_counts():
    samples = mon.extract_market_samples(_load("wc_nf.json"))
    by_id = {s["market_id"]: s for s in samples}
    assert len(samples) == 113
    ou = by_id["5000"]  # Total Score Over/Under - FT, 6 lines x 2 outcomes
    assert ou["num_lines"] == 6
    assert ou["num_outcomes"] == 12


def test_extract_market_samples_active_count():
    # live.json market 3743 row[0] price "1" is suspended:true
    samples = mon.extract_market_samples(_load("live.json"))
    by_id = {s["market_id"]: s for s in samples}
    assert by_id["3743"]["num_active"] < by_id["3743"]["num_outcomes"]


def test_extract_market_samples_handles_missing_rows():
    samples = mon.extract_market_samples({"markets": [{"marketType": {"id": "X", "name": "n"}}]})
    assert samples == [
        {
            "market_id": "X",
            "market_name": "n",
            "display_name": "",
            "num_lines": 0,
            "num_outcomes": 0,
            "num_active": 0,
        }
    ]


# --- Task 3: schema + recording ---------------------------------------------


def test_init_and_record_scrape_inserts_samples():
    conn = mon.init_db(":memory:")
    sid = mon.record_scrape(
        conn, "35429065", 1700000000.0, "upcoming", True, _load("wc_nf.json"), None
    )
    n = conn.execute(
        "select count(*) from market_sample where scrape_id=?", (sid,)
    ).fetchone()[0]
    assert n == 113
    row = conn.execute(
        "select event_id, phase, ok, total_market_count from scrape where id=?", (sid,)
    ).fetchone()
    assert row == ("35429065", "upcoming", 1, 173)


def test_record_failed_scrape_has_no_samples():
    conn = mon.init_db(":memory:")
    sid = mon.record_scrape(conn, "1", 1700000000.0, "live", False, None, "timeout")
    assert (
        conn.execute(
            "select count(*) from market_sample where scrape_id=?", (sid,)
        ).fetchone()[0]
        == 0
    )
    assert conn.execute("select error from scrape where id=?", (sid,)).fetchone()[0] == "timeout"


# --- Task 4: monitor loop ----------------------------------------------------


def test_run_monitor_lifecycle(tmp_path):
    pre = _load("prematch.json")
    pre["id"] = "100"
    live = _load("live.json")
    live["id"] = "100"
    ended = _load("live.json")
    ended["id"] = "100"
    ended["results"]["display"]["currentPeriod"]["slug"] = "MATCH_FINISHED"
    seq = {"100": [pre, pre, live, ended], "200": [pre, ended]}
    calls = {"100": 0, "200": 0}

    def fetch_fn(country, eid):
        i = calls[eid]
        calls[eid] = min(i + 1, len(seq[eid]) - 1)
        return seq[eid][i]

    t = {"now": 1_700_000_000.0}

    def now_fn():
        return t["now"]

    def sleep_fn(s):
        t["now"] += s

    db = str(tmp_path / "run.sqlite")
    mon.run_monitor(
        db,
        "ng",
        ["100", "200"],
        fetch_fn=fetch_fn,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
        prematch_interval=600,
        live_interval=120,
        max_hours=24,
    )
    conn = sqlite3.connect(db)
    phases = [r[0] for r in conn.execute("select phase from scrape where event_id='100' order by id")]
    assert "upcoming" in phases and "live" in phases and "ended" in phases
    assert (
        conn.execute(
            "select count(*) from scrape where event_id='200' and phase='ended'"
        ).fetchone()[0]
        >= 1
    )


def test_run_monitor_terminates_on_max_hours(tmp_path):
    """A never-ending event (always upcoming) must still stop at max_hours."""
    pre = _load("prematch.json")
    pre["id"] = "100"
    pre["results"] = None

    def fetch_fn(country, eid):
        return pre

    t = {"now": 1_700_000_000.0}

    def now_fn():
        return t["now"]

    def sleep_fn(s):
        t["now"] += s

    db = str(tmp_path / "run.sqlite")
    mon.run_monitor(
        db,
        "ng",
        ["100"],
        fetch_fn=fetch_fn,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
        prematch_interval=600,
        live_interval=120,
        max_hours=2,
    )
    conn = sqlite3.connect(db)
    # ~2h / 600s ≈ 12 scrapes, bounded — not infinite
    n = conn.execute("select count(*) from scrape").fetchone()[0]
    assert 0 < n < 100


def test_run_monitor_records_fetch_failure_and_continues(tmp_path):
    pre = _load("prematch.json")
    pre["id"] = "100"
    ended = _load("live.json")
    ended["id"] = "100"
    ended["results"]["display"]["currentPeriod"]["slug"] = "MATCH_FINISHED"
    state = {"n": 0}

    def fetch_fn(country, eid):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("boom")
        return ended

    t = {"now": 1_700_000_000.0}

    def now_fn():
        return t["now"]

    def sleep_fn(s):
        t["now"] += s

    db = str(tmp_path / "run.sqlite")
    mon.run_monitor(
        db,
        "ng",
        ["100"],
        fetch_fn=fetch_fn,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
        prematch_interval=600,
        live_interval=120,
        max_hours=24,
    )
    conn = sqlite3.connect(db)
    assert conn.execute("select count(*) from scrape where ok=0").fetchone()[0] == 1
    assert conn.execute("select count(*) from scrape where phase='ended'").fetchone()[0] >= 1


def test_run_monitor_stale_live_backstop_records_ended(tmp_path):
    """An event stuck 'live' past max_live_hours is force-ended (terminates)."""
    live = _load("live.json")
    live["id"] = "100"  # currentPeriod SECOND_HALF -> always 'live'

    def fetch_fn(country, eid):
        return live

    t = {"now": 1_700_000_000.0}

    def now_fn():
        return t["now"]

    def sleep_fn(s):
        t["now"] += s

    db = str(tmp_path / "run.sqlite")
    mon.run_monitor(
        db,
        "ng",
        ["100"],
        fetch_fn=fetch_fn,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
        prematch_interval=600,
        live_interval=120,
        max_hours=24,
        max_live_hours=1.0,
    )
    conn = sqlite3.connect(db)
    # the backstop wrote an explicit 'ended' row, not just a dangling 'live'
    assert conn.execute("select count(*) from scrape where phase='ended'").fetchone()[0] >= 1


def test_run_monitor_records_event_name_in_meta(tmp_path):
    live = _load("live.json")
    live["id"] = "100"
    live["name"] = "Team A - Team B"
    ended = _load("live.json")
    ended["id"] = "100"
    ended["name"] = "Team A - Team B"
    ended["results"]["display"]["currentPeriod"]["slug"] = "MATCH_FINISHED"
    seq = [live, ended]
    state = {"n": 0}

    def fetch_fn(country, eid):
        i = min(state["n"], len(seq) - 1)
        state["n"] += 1
        return seq[i]

    t = {"now": 1_700_000_000.0}

    def now_fn():
        return t["now"]

    def sleep_fn(s):
        t["now"] += s

    db = str(tmp_path / "run.sqlite")
    mon.run_monitor(
        db,
        "ng",
        ["100"],
        fetch_fn=fetch_fn,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
        prematch_interval=600,
        live_interval=120,
        max_hours=24,
    )
    conn = sqlite3.connect(db)
    name = conn.execute(
        "select value from meta where key='event_name:100'"
    ).fetchone()[0]
    assert name == "Team A - Team B"


def test_run_monitor_stops_event_on_notfound(tmp_path):
    def fetch_fn(country, eid):
        raise mon.NotFound("404")

    t = {"now": 1_700_000_000.0}

    def now_fn():
        return t["now"]

    def sleep_fn(s):
        t["now"] += s

    db = str(tmp_path / "run.sqlite")
    mon.run_monitor(
        db,
        "ng",
        ["100"],
        fetch_fn=fetch_fn,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
        prematch_interval=600,
        live_interval=120,
        max_hours=24,
    )
    conn = sqlite3.connect(db)
    # one failed scrape recorded, then the event is dropped (NotFound == removed/ended)
    assert conn.execute("select count(*) from scrape").fetchone()[0] == 1


# --- Task 5: summarize -------------------------------------------------------


def test_summarize_reports_diff(tmp_path):
    db = str(tmp_path / "s.sqlite")
    conn = mon.init_db(db)
    mon.record_meta(conn, {"event_ids": "100,200"})
    mon.record_scrape(
        conn,
        "100",
        1.0,
        "live",
        True,
        {
            "id": "100",
            "markets": [
                {"marketType": {"id": "M1", "name": "1X2"}, "row": [{"prices": [{}, {}, {}]}]},
                {"marketType": {"id": "M2", "name": "Corners"}, "row": [{"prices": [{}, {}]}]},
            ],
        },
        None,
    )
    mon.record_scrape(
        conn,
        "200",
        1.0,
        "live",
        True,
        {
            "id": "200",
            "markets": [
                {"marketType": {"id": "M1", "name": "1X2"}, "row": [{"prices": [{}, {}, {}]}]},
                {"marketType": {"id": "M3", "name": "Cards"}, "row": [{"prices": [{}, {}]}]},
            ],
        },
        None,
    )
    report = mon.summarize(db)
    assert "Corners" in report  # only on 100
    assert "Cards" in report  # only on 200
    assert "1X2" in report  # shared


# --- Task 6: CLI -------------------------------------------------------------


def test_cli_parses_monitor_args():
    args = mon.build_arg_parser().parse_args(
        ["--country", "ng", "--events", "100", "200", "--db", "x.sqlite"]
    )
    assert args.country == "ng" and args.events == ["100", "200"]


def test_cli_summarize_flag():
    args = mon.build_arg_parser().parse_args(["--summarize", "run.sqlite"])
    assert args.summarize == "run.sqlite"
