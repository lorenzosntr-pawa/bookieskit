# BetPawa 2-Event Market-Availability Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A single, portable, stdlib-only script the owner drops on an in-region server to monitor market availability for two BetPawa events over their lifecycle, writing a small SQLite DB, plus a `--summarize` mode that diffs market availability between the two fixtures.

**Architecture:** One self-contained file `scripts/betpawa_availability_monitor.py` (Python 3.8+, stdlib only — no pip, no library import). Pure functions (phase detection, market-sample extraction, schema, summarize) are unit-tested offline against committed BetPawa event fixtures. The network fetch and the monitor loop take injected `fetch_fn`/`now_fn`/`sleep_fn` seams so the full upcoming→live→ended lifecycle is testable offline (CI is network-agnostic; live runs are in-region only).

**Tech Stack:** Python 3.8+ stdlib: `urllib.request`, `sqlite3`, `json`, `argparse`, `time`, `datetime`. pytest for tests (tests may import the script as a module).

## Global Constraints

- **stdlib only**, Python **3.8+** floor — no third-party deps, no `bookieskit` import. One `.py` file copied to a server must run.
- **In-region only** for live use — BetPawa geo-blocks US/cloud IPs (403). Network code is a thin seam; all logic is offline-testable.
- `src/` ruff-clean is unaffected (script lives in `scripts/`), but keep the script and tests ruff-clean too (repo runs ruff on `.`).
- BetPawa endpoint: `GET {domain}/api/sportsbook/v3/events/{event_id}` with headers `x-pawa-brand: betpawa-<country-brand>`, `devicetype: web`, a desktop `user-agent`. Domains + brand map inlined (mirror `src/bookieskit/bookmakers/betpawa.py`).
- Payload facts (from `tests/fixtures/event_info/betpawa/*.json`): top-level `id`, `name`, `participants[]`, `startTime` (ISO-8601 `...Z`), `totalMarketCount`, `markets[]`, `results` (null when not started; object with `display.currentPeriod.slug` + `display.minute` once in-play). Each `markets[]` item: `marketType.{id,name,displayName}` and `row[]`; each row has `prices[]` (outcomes, each with `suspended: bool`). A market's `marketType.id` is unique within an event; a multi-line market (e.g. O/U) carries multiple `row` entries.
- CLI: `python betpawa_availability_monitor.py --country <cc> --events <idA> <idB> --db run.sqlite [--prematch-interval 600] [--live-interval 120] [--max-hours 8]` and `python betpawa_availability_monitor.py --summarize run.sqlite`.

---

## File Structure

- `scripts/betpawa_availability_monitor.py` — the whole deliverable (CLI + pure functions + fetch seam + loop).
- `tests/test_betpawa_availability_monitor.py` — offline tests importing the script module.

The script imports the module under test by loading the file path (it lives outside the package). Tests use `importlib.util.spec_from_file_location`.

---

### Task 1: Phase detection

**Files:**
- Create: `scripts/betpawa_availability_monitor.py`
- Test: `tests/test_betpawa_availability_monitor.py`

**Interfaces:**
- Produces: `detect_phase(payload: dict, now: datetime) -> str` returning one of `"upcoming" | "live" | "ended"`. `FINISHED_SLUGS: set[str]`. Module-level constant `DOMAINS: dict`, `BRAND_MAP: dict` copied from the library.

Rules:
- `results is None` → `"upcoming"` if `now < startTime` else `"live"` (kickoff imminent/just passed, no result yet).
- `results` present → `"ended"` if `display.currentPeriod.slug` is in `FINISHED_SLUGS`, else `"live"`.
- `startTime` parsed from ISO-8601 with trailing `Z` → tz-aware UTC. `now` is tz-aware UTC.
- `FINISHED_SLUGS = {"MATCH_FINISHED", "ENDED", "FINISHED", "AFTER_EXTRA_TIME", "AFTER_PENALTIES", "MATCH_ABOUT_TO_END"}` (best-effort; the loop's 404 + max-live backstops guarantee termination regardless).

- [ ] **Step 1: Write failing tests** in `tests/test_betpawa_availability_monitor.py`:

```python
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "betpawa_availability_monitor.py"
_spec = importlib.util.spec_from_file_location("betpawa_availability_monitor", _MOD_PATH)
mon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mon)

FIX = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "event_info" / "betpawa"

import json
def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))

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
    now = datetime(2026, 5, 6, 12, tzinfo=timezone.utc)  # after startTime, results still null
    assert mon.detect_phase(p, now) == "live"

def test_detect_phase_ended_finished_slug():
    p = _load("live.json")
    p["results"]["display"]["currentPeriod"]["slug"] = "MATCH_FINISHED"
    now = datetime(2026, 5, 6, 8, tzinfo=timezone.utc)
    assert mon.detect_phase(p, now) == "ended"
```

- [ ] **Step 2: Run, verify fail** — `pytest tests/test_betpawa_availability_monitor.py -v` → FAIL (module/function missing).
- [ ] **Step 3: Implement** the module skeleton + `DOMAINS`/`BRAND_MAP` (copied verbatim from `src/bookieskit/bookmakers/betpawa.py`), `FINISHED_SLUGS`, `_parse_iso(s)` (handles trailing `Z`), and `detect_phase`.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** `feat(scripts): betpawa monitor phase detection`.

---

### Task 2: Market-sample extraction

**Interfaces:**
- Produces: `extract_event_meta(payload) -> dict` with keys `id` (str), `name` (str), `participants` (list[str]), `start_time` (str), `total_market_count` (int). `extract_market_samples(payload) -> list[dict]` each `{market_id, market_name, display_name, num_lines, num_outcomes, num_active}`.

Rules:
- `num_lines = len(market["row"])`; `num_outcomes = sum(len(r["prices"]) for r in row)`; `num_active = count of prices where not price.get("suspended", False)`.
- Robust to missing keys (`.get` with defaults; a market with no `row` → zeros).

- [ ] **Step 1: Write failing tests:**

```python
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
    # live.json market 3743 row[0] price 1 is suspended:true
    samples = mon.extract_market_samples(_load("live.json"))
    by_id = {s["market_id"]: s for s in samples}
    assert by_id["3743"]["num_active"] < by_id["3743"]["num_outcomes"]
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `extract_event_meta` + `extract_market_samples`. (`id` coerced to `str`.)
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** `feat(scripts): betpawa monitor market-sample extraction`.

---

### Task 3: SQLite schema + recording

**Interfaces:**
- Produces: `init_db(path) -> sqlite3.Connection` creating tables `meta(key TEXT PRIMARY KEY, value TEXT)`, `scrape(id INTEGER PK, event_id TEXT, ts REAL, iso TEXT, phase TEXT, ok INTEGER, total_market_count INTEGER, error TEXT)`, `market_sample(scrape_id INTEGER, event_id TEXT, market_id TEXT, market_name TEXT, display_name TEXT, num_lines INTEGER, num_outcomes INTEGER, num_active INTEGER)`. `record_meta(conn, dict)`. `record_scrape(conn, event_id, ts, phase, ok, payload_or_None, error) -> scrape_id` (inserts the scrape row and, when `ok` and payload present, one `market_sample` per market).

- [ ] **Step 1: Write failing tests** (use `:memory:` connection):

```python
def test_init_and_record_scrape_inserts_samples():
    conn = mon.init_db(":memory:")
    sid = mon.record_scrape(conn, "35429065", 1700000000.0, "upcoming", True, _load("wc_nf.json"), None)
    n = conn.execute("select count(*) from market_sample where scrape_id=?", (sid,)).fetchone()[0]
    assert n == 113
    row = conn.execute("select event_id, phase, ok, total_market_count from scrape where id=?", (sid,)).fetchone()
    assert row == ("35429065", "upcoming", 1, 173)

def test_record_failed_scrape_has_no_samples():
    conn = mon.init_db(":memory:")
    sid = mon.record_scrape(conn, "1", 1700000000.0, "live", False, None, "timeout")
    assert conn.execute("select count(*) from market_sample where scrape_id=?", (sid,)).fetchone()[0] == 0
    assert conn.execute("select error from scrape where id=?", (sid,)).fetchone()[0] == "timeout"
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `init_db`, `record_meta`, `record_scrape`. Commit the connection after each scrape so a crash mid-run keeps prior data.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** `feat(scripts): betpawa monitor sqlite schema + recording`.

---

### Task 4: Monitor loop (injected seams)

**Interfaces:**
- Produces: `run_monitor(db_path, country, event_ids, *, fetch_fn, now_fn, sleep_fn, prematch_interval, live_interval, max_hours, max_live_hours=4.0) -> None`. `fetch_fn(country, event_id) -> dict` (raises on failure). Each event has independent next-due scheduling; a fetch exception is recorded (`ok=0`) and retried next cycle. An event stops when: phase `ended`, OR `fetch_fn` raises a `NotFound` (HTTP 404 → event removed), OR it has been `live` longer than `max_live_hours` since `startTime` (backstop). Loop exits when all events stopped OR wall-clock since start exceeds `max_hours`.

- Define `class NotFound(Exception)` in the module; `fetch_event` raises it on HTTP 404.
- Scheduling: maintain per-event `next_due` (epoch). Each tick: for events whose `next_due <= now`, fetch+record, set `next_due = now + (prematch_interval if upcoming else live_interval)`. Sleep via `sleep_fn` until the soonest `next_due` (clamped to a small max so `max_hours` is honoured).

- [ ] **Step 1: Write a failing lifecycle test** driving scripted payloads through fake seams:

```python
def test_run_monitor_lifecycle(tmp_path):
    pre = _load("prematch.json"); pre["id"] = "100"
    live = _load("live.json"); live["id"] = "100"
    ended = _load("live.json"); ended["id"] = "100"
    ended["results"]["display"]["currentPeriod"]["slug"] = "MATCH_FINISHED"
    seq = {"100": [pre, pre, live, ended], "200": [pre, ended]}
    calls = {"100": 0, "200": 0}
    def fetch_fn(country, eid):
        i = calls[eid]; calls[eid] = min(i + 1, len(seq[eid]) - 1)
        return seq[eid][i]
    t = {"now": 1_700_000_000.0}
    def now_fn(): return t["now"]
    def sleep_fn(s): t["now"] += s
    db = str(tmp_path / "run.sqlite")
    mon.run_monitor(db, "ng", ["100", "200"], fetch_fn=fetch_fn, now_fn=now_fn,
                    sleep_fn=sleep_fn, prematch_interval=600, live_interval=120, max_hours=24)
    import sqlite3
    conn = sqlite3.connect(db)
    phases = [r[0] for r in conn.execute("select phase from scrape where event_id='100' order by id")]
    assert "upcoming" in phases and "live" in phases and "ended" in phases
    # both events reached ended → loop terminated on its own
    assert conn.execute("select count(*) from scrape where event_id='200' and phase='ended'").fetchone()[0] >= 1
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `run_monitor`, `NotFound`. `now_fn` returns epoch float; convert to ISO via `datetime.fromtimestamp(ts, timezone.utc)`. Detection uses that datetime.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** `feat(scripts): betpawa monitor lifecycle loop`.

---

### Task 5: Summarize / diff mode

**Interfaces:**
- Produces: `summarize(db_path) -> str` (returns the printable report; CLI prints it). Reports, per event: count of distinct markets seen; then a market-by-market table of presence (event A / event B / both) with peak `num_lines` and peak `num_outcomes` per market; and a final "only on A" / "only on B" difference list.

- [ ] **Step 1: Write failing test** — build a DB with two events sharing one market and each having one unique market, assert the report names the unique ones:

```python
def test_summarize_reports_diff(tmp_path):
    conn = mon.init_db(str(tmp_path / "s.sqlite"))
    mon.record_meta(conn, {"event_ids": "100,200"})
    # event 100: markets M1 (shared) + M2 (only A)
    s1 = mon.record_scrape(conn, "100", 1.0, "live", True,
        {"id": "100", "markets": [
            {"marketType": {"id": "M1", "name": "1X2"}, "row": [{"prices": [{}, {}, {}]}]},
            {"marketType": {"id": "M2", "name": "Corners"}, "row": [{"prices": [{}, {}]}]}]}, None)
    # event 200: markets M1 (shared) + M3 (only B)
    s2 = mon.record_scrape(conn, "200", 1.0, "live", True,
        {"id": "200", "markets": [
            {"marketType": {"id": "M1", "name": "1X2"}, "row": [{"prices": [{}, {}, {}]}]},
            {"marketType": {"id": "M3", "name": "Cards"}, "row": [{"prices": [{}, {}]}]}]}, None)
    report = mon.summarize(str(tmp_path / "s.sqlite"))
    assert "Corners" in report  # only on 100
    assert "Cards" in report     # only on 200
    assert "1X2" in report       # shared
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `summarize` (pure SQL aggregation + string build).
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** `feat(scripts): betpawa monitor summarize/diff`.

---

### Task 6: CLI wiring + fetch + docs

**Interfaces:**
- Produces: `fetch_event(country, event_id, timeout=30) -> dict` (urllib, headers, raises `NotFound` on 404). `build_arg_parser()`, `main(argv=None)`. `if __name__ == "__main__": sys.exit(main())`.

- [ ] **Step 1: Write failing tests** for arg parsing only (no network):

```python
def test_cli_parses_monitor_args():
    args = mon.build_arg_parser().parse_args(
        ["--country", "ng", "--events", "100", "200", "--db", "x.sqlite"])
    assert args.country == "ng" and args.events == ["100", "200"]

def test_cli_summarize_flag():
    args = mon.build_arg_parser().parse_args(["--summarize", "run.sqlite"])
    assert args.summarize == "run.sqlite"
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** `build_arg_parser` (mutually-exclusive monitor vs `--summarize`), `fetch_event`, `main` (dispatch summarize → print `summarize`; monitor → `run_monitor` with real `fetch_event`, `time.time`, `time.sleep`). Add a module docstring documenting usage, in-region requirement, and the ended-detection assumptions.
- [ ] **Step 4: Run full suite + ruff** — `pytest tests/test_betpawa_availability_monitor.py -v` PASS; `ruff check scripts tests` clean.
- [ ] **Step 5: Commit** `feat(scripts): betpawa monitor CLI + fetch + docs`.

---

### Task 7: README/docs sync (per #41 standing rule)

**Files:**
- Modify: `README.md` (or `docs/`) — add a short "BetPawa availability monitor" section pointing at the script with the run + summarize commands and the in-region note.

- [ ] **Step 1:** Add the doc section.
- [ ] **Step 2: Commit** `docs: document betpawa availability monitor script`.

---

## Self-Review notes

- Spec coverage: monitor 2 events ✓ (T4), BetPawa-only inlined endpoints ✓ (T1/T6), 10-min prematch / 2-min live cadence ✓ (T4 intervals), runs until both ended + `--max-hours` cap ✓ (T4), presence+breadth per market ✓ (T2/T3), SQLite meta/scrape/market_sample ✓ (T3), `--summarize` diff ✓ (T5), stdlib-only portable ✓ (global constraints).
- Ended detection is best-effort by slug + guaranteed-terminating by 404 and `max_live_hours`/`max_hours` backstops — documented as an assumption for owner review (no ended-state fixture exists to verify slug strings).
- Type consistency: `event_id`/`market_id` are `str` throughout; `record_scrape` returns `scrape_id`; `fetch_fn` signature `(country, event_id)` matches `fetch_event` minus the bound `timeout`.
