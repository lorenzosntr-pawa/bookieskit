# 2-way Handicap (soccer) + basketball rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 0.15.0 with two coordinated changes — (a) rename `handicap_basketball_ft` → `2way_handicap_basketball_ft` to disambiguate the 2-way vs 3-way handicap naming convention, and (b) add a new soccer canonical `2way_handicap_ft` (Asian Handicap, 2-way home/away, signed lines) mapped across BetPawa, Bet9ja, SportyBet, MSport, Betway, and Betika.

**Architecture:** No parser changes needed — handicap is already a fully-supported pattern across every bookmaker via the existing parameterized-with-signed-line machinery. The new canonical is just three more `MarketMapping` entries in `BUILTIN_MAPPINGS` and one new id in `Betika._UNIVERSAL_SUB_TYPE_IDS`. The basketball rename is a single-string flip in the mapping plus mechanical updates across tests/docs/examples that pin the old `canonical_id` string. Live probe locks-in the four unknown bookmaker IDs before merging (same workflow as 0.14.0).

**Tech Stack:** Python 3.11+, `httpx` async, `pytest`. No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-05-22-2way-handicap-design.md` (commit `9b2e9f9`).

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `scripts/probe_2way_handicap_ft.py` | create | One-off probe harness that walks 4 bookmakers (SportyBet, MSport, Betway, Betika) against a current event and prints candidate market ids/names. Drives the fixture capture. |
| `tests/fixtures/event_info/sportybet/2way_handicap_ft.json` | create (probe output) | Captured SportyBet response covering Asian Handicap (id=16). |
| `tests/fixtures/event_info/msport/2way_handicap_ft.json` | create (probe output) | Captured MSport response. |
| `tests/fixtures/event_info/betway/2way_handicap_ft.json` | create (probe output) | Captured Betway response (with `sportEvent.homeTeam`/`awayTeam` spliced in for the team-name placeholder mechanism). |
| `tests/fixtures/event_info/betika/2way_handicap_ft.json` | create (probe output) | Captured Betika response. |
| `tests/fixtures/event_info/RESOLVED_2way_handicap_ft.md` | create | Decision record: locked-in IDs per bookmaker, gaps documented (e.g. SportPesa NOT PROBED). |
| `src/bookieskit/markets/builtin_mappings.py` | modify | (a) Rename `canonical_id` on the basketball handicap entry. (b) Append new `2way_handicap_ft` MarketMapping. |
| `src/bookieskit/bookmakers/betika.py` | modify | Extend `_UNIVERSAL_SUB_TYPE_IDS` from 7 → 8 (add `"16"`). Bump docstring counts. |
| `src/bookieskit/__init__.py` | modify | Bump `__version__` to `"0.15.0"`. |
| `pyproject.toml` | modify | Bump `version` to `"0.15.0"`. |
| `tests/test_parser_basketball.py` | modify | Replace 5 occurrences of `"handicap_basketball_ft"` with `"2way_handicap_basketball_ft"`. |
| `tests/test_parser_betpawa_basketball.py` | modify | Replace 2 occurrences. |
| `tests/test_parser_tennis.py` | modify | Replace 1 occurrence (in a sport-scope negative-assertion). |
| `tests/test_registry.py` | modify | (a) Bump builtin count 16→17 (and `add_custom_mapping` count 17→18). (b) Add `test_registry_has_2way_handicap_ft` smoke test. (c) Update any test pinning `"handicap_basketball_ft"`. |
| `tests/test_parser_betpawa.py` | modify | Add `test_parse_betpawa_2way_handicap_ft_from_probe_fixture` against captured BetPawa fixture. |
| `tests/test_parser_bet9ja.py` | modify | Add `test_parse_bet9ja_2way_handicap_ft_from_probe_fixture` against captured Bet9ja fixture. |
| `tests/test_parser_sportybet.py` | modify | Add fixture-driven test post-probe. |
| `tests/test_parser_msport.py` | modify | Add fixture-driven test post-probe. |
| `tests/test_parser_betway.py` | modify | Add fixture-driven test post-probe. |
| `tests/test_parser_betika.py` | modify | Add fixture-driven test post-probe. |
| `tests/test_betika.py` | modify | Bump expected sub_type_id fan-out call count 7 → 8 in tests that pin it. |
| `examples/compare_betpawa_competition_full.py` | modify | Update 2 occurrences of `"handicap_basketball_ft"` to the new id. |
| `docs/markets.md` | modify | Bump count 16→17; soccer table +1 row; basketball table row rename; signed-line convention prose carries over. |
| `README.md` | modify | Bump count 16→17, soccer 9→10; soccer table +1 row; basketball table row rename. |
| `CHANGELOG.md` | modify | New `## [0.15.0]` section with **Renamed** + **Added** + **Changed** subheaders. The historic `handicap_basketball_ft` reference in earlier sections stays unchanged. |

Each task ends with a commit so the work integrates incrementally.

---

# Phase 0 — Probe & fixture capture

## Task 1: Write probe script

**Files:**
- Create: `scripts/probe_2way_handicap_ft.py`

- [ ] **Step 1: Create the probe script**

```python
"""One-off probe: discovers Asian Handicap (2-way) market ids and
outcome strings across SportyBet, MSport, Betway, and Betika.

BetPawa (id=3774) and Bet9ja (S_AH) are already locked-in by the
spec — this probe only confirms the other 4. SportPesa is skipped
(Akamai cookie unavailable).

Usage:
    python scripts/probe_2way_handicap_ft.py <BETPAWA_EVENT_ID>

The BetPawa id should be a top-tier upcoming or live soccer event
whose detail response contains marketType.id="3774". The script:
  1. Fetches the BetPawa event detail → extracts the SR id from
     the SPORTRADAR widget.
  2. Confirms BetPawa exposes id=3774 on this event.
  3. For each of the other 4 bookmakers, fetches markets and
     prints candidate ids/keys matching r"handi|asian|spread"
     plus the outcome strings observed.
  4. Writes one JSON fixture per bookmaker under
     tests/fixtures/event_info/<bookmaker>/2way_handicap_ft.json
"""
import asyncio
import json
import re
import sys
from pathlib import Path

from bookieskit import Bet9ja, Betika, BetPawa, Betway, MSport, SportyBet
from bookieskit.matching import extract_sportradar_id

FIXTURE_DIR = Path(__file__).parent.parent / "tests/fixtures/event_info"
PATTERN = re.compile(r"handi|asian|spread", re.IGNORECASE)


async def fetch_betpawa(betpawa_id: str):
    async with BetPawa(country="ng") as bp:
        detail = await bp.get_event_detail(event_id=betpawa_id)
        markets = detail.get("markets") or []
        ah = None
        for m in markets:
            mt = m.get("marketType", {}) or {}
            if str(mt.get("id")) == "3774":
                ah = m
                break
        sr_id = extract_sportradar_id(detail, platform="betpawa")
        participants = detail.get("participants", [])
        home = participants[0]["name"] if len(participants) > 0 else "?"
        away = participants[1]["name"] if len(participants) > 1 else "?"
        return home, away, ah, sr_id, detail


async def probe_sportybet(sr_prefixed):
    async with SportyBet(country="ng") as sb:
        detail = await sb.get_event_detail(event_id=sr_prefixed, live=False)
        if not (detail.get("data") or {}).get("markets"):
            detail = await sb.get_event_detail(
                event_id=sr_prefixed, live=True,
            )
        markets = (detail.get("data") or {}).get("markets") or []
        print(f"\n=== SportyBet ({len(markets)} markets) ===", flush=True)
        for m in markets:
            n = m.get("name", "") or ""
            desc = m.get("desc", "") or ""
            if PATTERN.search(n + " " + desc):
                spec = m.get("specifier", "")
                outs = [o.get("desc") for o in m.get("outcomes") or []]
                print(
                    f"  id={m.get('id')!r}  name={n!r}  desc={desc!r}"
                    f"  spec={spec!r}  outs={outs}",
                    flush=True,
                )
        return detail


async def probe_msport(sr_prefixed):
    async with MSport(country="ng") as ms:
        detail = await ms.get_event_detail(event_id=sr_prefixed, live=False)
        if not (detail.get("data") or {}).get("markets"):
            detail = await ms.get_event_detail(
                event_id=sr_prefixed, live=True,
            )
        markets = (detail.get("data") or {}).get("markets") or []
        print(f"\n=== MSport ({len(markets)} markets) ===", flush=True)
        for m in markets:
            n = m.get("name", "") or ""
            desc = m.get("description", "") or ""
            if PATTERN.search(n + " " + desc):
                spec = m.get("specifiers", "")
                outs = [o.get("description") for o in m.get("outcomes") or []]
                print(
                    f"  id={m.get('id')!r}  name={n!r}  desc={desc!r}"
                    f"  spec={spec!r}  outs={outs}",
                    flush=True,
                )
        return detail


async def probe_betway(sr_numeric):
    async with Betway(country="ng") as bw:
        detail = await bw.get_event_detail(event_id=sr_numeric)
        sport_event = detail.get("sportEvent") or {}
        home = sport_event.get("homeTeam") or "?"
        away = sport_event.get("awayTeam") or "?"
        print(f"\n=== Betway (home={home!r}, away={away!r}) ===", flush=True)
        all_mig = []
        all_outs = []
        all_prices = []
        for skip in range(0, 600, 100):
            r = await bw.get_event_markets(
                event_id=sr_numeric, skip=skip, take=100,
            )
            mig = r.get("marketsInGroup") or []
            if not mig:
                break
            all_mig.extend(mig)
            all_outs.extend(r.get("outcomes") or [])
            all_prices.extend(r.get("prices") or [])
            if len(mig) < 100:
                break
        for m in all_mig:
            n = m.get("name", "") or ""
            if PATTERN.search(n):
                handicap = m.get("handicap")
                mid = m.get("marketId")
                print(
                    f"  name={n!r}  handicap={handicap}"
                    f"  marketId={mid!r}",
                    flush=True,
                )
        merged = {
            "marketsInGroup": all_mig,
            "outcomes": all_outs,
            "prices": all_prices,
            "sportEvent": sport_event,
        }
        return merged


async def probe_betika(sr_numeric):
    async with Betika(country="ke") as bk:
        # Walk listing to find the match by parent_match_id
        match_id = comp_id = None
        for page in range(1, 10):
            listing = await bk.get_matches(
                sport_id=14, page=page, limit=100,
            )
            data = listing.get("data") or []
            if not data:
                break
            for m in data:
                if str(m.get("parent_match_id", "")) == sr_numeric:
                    match_id = m.get("match_id")
                    comp_id = m.get("competition_id")
                    break
            if match_id is not None:
                break
        if match_id is None:
            print(
                "\n=== Betika === SR id not found in first 9 listing pages",
                flush=True,
            )
            return None
        # Fetch sub_type_id=16 specifically (the Asian Handicap candidate)
        r = await bk.get_matches(
            sport_id=14,
            match_id=str(match_id),
            competition_id=str(comp_id) if comp_id else None,
            sub_type_id="16",
            limit=1,
        )
        match = (r.get("data") or [{}])[0]
        groups = match.get("odds") or []
        print(
            f"\n=== Betika (match_id={match_id}, {len(groups)} groups) ===",
            flush=True,
        )
        for g in groups:
            sti = g.get("sub_type_id")
            name = g.get("name", "")
            outs = [s.get("display") for s in g.get("odds") or []][:6]
            print(
                f"  sub_type_id={sti!r}  name={name!r}  outs_sample={outs}",
                flush=True,
            )
        return r


async def main():
    if len(sys.argv) < 2:
        print(
            "usage: python scripts/probe_2way_handicap_ft.py "
            "<BETPAWA_EVENT_ID>"
        )
        sys.exit(1)
    bp_id = sys.argv[1]

    home, away, ah, sr_numeric, bp_detail = await fetch_betpawa(bp_id)
    print(
        f"BetPawa event: {home} vs {away}  SR={sr_numeric}",
        flush=True,
    )
    if ah is None:
        print(
            "ERROR: BetPawa event does NOT expose id=3774 — pick a different event",
            flush=True,
        )
        sys.exit(1)
    print(
        f"BetPawa id=3774 confirmed: name="
        f"{ah.get('marketType', {}).get('name')!r}",
        flush=True,
    )
    if sr_numeric is None:
        print("ERROR: no SPORTRADAR widget on this BetPawa event", flush=True)
        sys.exit(1)
    sr_prefixed = f"sr:match:{sr_numeric}"

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    # Each probe writes its own fixture
    captures = {}
    for name, fn in [
        ("sportybet", probe_sportybet),
        ("msport", probe_msport),
    ]:
        try:
            captures[name] = await fn(sr_prefixed)
        except Exception as exc:
            print(f"[{name}] probe failed: {exc!r}", flush=True)
    try:
        captures["betway"] = await probe_betway(sr_numeric)
    except Exception as exc:
        print(f"[betway] probe failed: {exc!r}", flush=True)
    try:
        captures["betika"] = await probe_betika(sr_numeric)
    except Exception as exc:
        print(f"[betika] probe failed: {exc!r}", flush=True)

    for name, capture in captures.items():
        if capture is None:
            continue
        path = FIXTURE_DIR / name / "2way_handicap_ft.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(capture, indent=2), encoding="utf-8")
        print(f"[{name}] wrote {path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Commit**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add scripts/probe_2way_handicap_ft.py
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "chore(scripts): add 2way_handicap_ft probe harness"
```

## Task 2: Run probe + capture fixtures + write RESOLVED

**Files:**
- Create: `tests/fixtures/event_info/<bookmaker>/2way_handicap_ft.json` (4 files)
- Create: `tests/fixtures/event_info/RESOLVED_2way_handicap_ft.md`

- [ ] **Step 1: Find a current BetPawa event with id=3774**

```bash
python -c "
import asyncio
from bookieskit import BetPawa

async def main():
    async with BetPawa(country='ng') as bp:
        listing = await bp.get_events(sport_id='2', event_type='UPCOMING')
        events = []
        for o in listing.get('responses', []):
            for ev in o.get('responses', []):
                events.append(ev)
        # Probe first 10 for id=3774 presence
        for ev in events[:10]:
            try:
                d = await bp.get_event_detail(event_id=ev.get('id'))
                ids = {str(m.get('marketType', {}).get('id')) for m in (d.get('markets') or [])}
                has_ah = '3774' in ids
                has_sr = any(
                    w.get('type') == 'SPORTRADAR' for w in d.get('widgets', [])
                )
                if has_ah and has_sr:
                    print(f\"GOOD: id={ev.get('id')} name={ev.get('name')}\")
                    break
            except Exception as e:
                print(f\"skip {ev.get('id')}: {e}\")

asyncio.run(main())
"
```

Pick the first event reported as `GOOD:` and note its BetPawa id.

- [ ] **Step 2: Run the probe**

```bash
python scripts/probe_2way_handicap_ft.py <BETPAWA_ID>
```

Expected output:
- Confirmation that BetPawa id=3774 is present
- Per-bookmaker candidate market ids printed (e.g. `id='16' name='Asian Handicap'` for SportyBet)
- One JSON fixture per bookmaker written to `tests/fixtures/event_info/<bookmaker>/2way_handicap_ft.json`

- [ ] **Step 3: Hand-verify candidates**

For each bookmaker, read the printed candidates and the fixture file. For each, note:
- The exact market id / key string
- The exact outcome strings (e.g. `Home` / `Away` for SportyBet, `1` / `2` for Betika)
- For Betway: confirm the literal market name (likely `Asian Handicap` or `Handicap - 2 Way` based on Betway's known naming patterns)

If a bookmaker doesn't expose Asian Handicap on this event, mark that bookmaker as "NOT EXPOSED on probed event" and try once more on a different event before giving up.

- [ ] **Step 4: Write the RESOLVED file**

Create `tests/fixtures/event_info/RESOLVED_2way_handicap_ft.md` with this content:

```markdown
# RESOLVED — 2way_handicap_ft

**Probed:** 2026-05-22 against BetPawa event <BP_ID> (SR <SR_ID>,
<home> vs <away>).

BetPawa and Bet9ja IDs were locked-in from the spec; this probe
confirms the remaining 4 (SportPesa skipped — Akamai cookie
unavailable).

## SportyBet
- `2way_handicap_ft`: sportybet_id = `<observed id, likely 16>`
- Specifier shape: `<observed, likely hcp=-1.5>`
- Outcome strings: `<observed, likely Home / Away>`

## MSport
- `2way_handicap_ft`: msport_id = `<observed, likely 16>`
- Specifier shape: `<observed, likely hcp=-1.5>`
- Outcome strings: `<observed, likely Home / Away>`

## Betway
- `2way_handicap_ft`: betway_id = `<observed literal name>`
- Outcome shape: team-name positional (`__HOME__` at pos 0, `__POS_2__` at pos 1)
- Line shape: `handicap=<signed>` per market entry

## Betika
- `2way_handicap_ft`: betika_id = `<observed sub_type_id, likely 16>`
- Specifier shape: `<observed, likely special_bet_value=-1.5>`
- Outcome strings: `<observed, likely 1 / 2>`

## SportPesa
- NOT PROBED — Akamai cookie unavailable. sportpesa_id stays None.

## Bet9ja (confirmed pre-probe)
- `2way_handicap_ft`: bet9ja_key = `S_AH`
- Key shape: `S_AH@<signed_line>_1` / `S_AH@<signed_line>_2`
- Outcome strings: `1` (home) / `2` (away)
- 32 odds keys observed on the diagnostic run = ~16 lines × 2 outcomes.

## BetPawa (confirmed pre-probe)
- `2way_handicap_ft`: betpawa_id = `3774`
- Wire name: "Asian Handicap - FT"; displayName: "2-Way Handicap | Full Time"
- BetPawa's `Handicap 1X2 - FT` (id=4724, displayName "3-Way Handicap")
  is the European variant — EXCLUDED.
```

Fill in `<observed>` placeholders with the actual values from the probe output.

- [ ] **Step 5: Commit fixtures + RESOLVED**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add tests/fixtures/event_info/
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "$(cat <<'EOF'
test(fixtures): capture 2way_handicap_ft markets across 4 bookmakers

Probed SportyBet, MSport, Betway, Betika against a current BetPawa
upcoming event. BetPawa (3774) and Bet9ja (S_AH) IDs were locked-in
by spec; this probe confirms the remaining 4. SportPesa stays None
(Akamai cookie unavailable). See RESOLVED_2way_handicap_ft.md for
the per-bookmaker decisions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 1 — Rename `handicap_basketball_ft` → `2way_handicap_basketball_ft`

## Task 3: Rename basketball canonical across all files

**Files:**
- Modify: `src/bookieskit/markets/builtin_mappings.py` (1 string change + comment update)
- Modify: `tests/test_parser_basketball.py` (5 occurrences)
- Modify: `tests/test_parser_betpawa_basketball.py` (2 occurrences)
- Modify: `tests/test_parser_tennis.py` (1 occurrence — negative assertion)
- Modify: `examples/compare_betpawa_competition_full.py` (2 occurrences)

The historic reference at `CHANGELOG.md:109` stays unchanged — it documents what shipped under the old name in a prior version.

- [ ] **Step 1: Update `src/bookieskit/markets/builtin_mappings.py`**

Open the file, locate the `handicap_basketball_ft` MarketMapping (around lines 343-382). Change:

```python
    # Basketball handicap uses signed lines: home -5.5 means home gives
    # 5.5 points. The bookmakers ship the home-perspective signed line
    # (e.g. -5.5); the parser stores the home outcome at key=-5.5 and
    # the away outcome at key=+5.5 per the spec ("each side ships with
    # its own signed line"). Callers pair entries by abs().
    MarketMapping(
        canonical_id="handicap_basketball_ft",
        name="Handicap - Full Time (incl. OT)",
```

to:

```python
    # Basketball handicap (2-way, home/away) uses signed lines: home
    # -5.5 means home gives 5.5 points. The bookmakers ship the
    # home-perspective signed line (e.g. -5.5); the parser stores the
    # home outcome at key=-5.5 and the away outcome at key=+5.5 per
    # the spec ("each side ships with its own signed line"). Callers
    # pair entries by abs(). The "2way_" prefix on the canonical_id
    # disambiguates from a hypothetical future 3way (European 1X2)
    # handicap variant; see 2way_handicap_ft for the soccer companion.
    MarketMapping(
        canonical_id="2way_handicap_basketball_ft",
        name="2-Way Handicap - Full Time (incl. OT)",
```

Note: the `name` field also gets the explicit "2-Way" prefix for consistency. The change is JUST these two lines plus the comment block above.

- [ ] **Step 2: Update `tests/test_parser_basketball.py`**

Replace all 5 occurrences of `"handicap_basketball_ft"` (lines 57, 58, 69, 131, 148, 164) with `"2way_handicap_basketball_ft"`. Use sed or your editor's project-wide find/replace, scoped to this file:

```bash
python -c "
from pathlib import Path
p = Path('tests/test_parser_basketball.py')
text = p.read_text(encoding='utf-8')
new = text.replace('handicap_basketball_ft', '2way_handicap_basketball_ft')
assert new.count('2way_handicap_basketball_ft') == 6, 'expected 6 hits, got ' + str(new.count('2way_handicap_basketball_ft'))
p.write_text(new, encoding='utf-8')
print('updated test_parser_basketball.py')
"
```

(The expected count is 6 because line 58 also references the name in an f-string error message.)

- [ ] **Step 3: Update `tests/test_parser_betpawa_basketball.py`**

```bash
python -c "
from pathlib import Path
p = Path('tests/test_parser_betpawa_basketball.py')
text = p.read_text(encoding='utf-8')
new = text.replace('handicap_basketball_ft', '2way_handicap_basketball_ft')
assert new.count('2way_handicap_basketball_ft') == 2
p.write_text(new, encoding='utf-8')
print('updated test_parser_betpawa_basketball.py')
"
```

- [ ] **Step 4: Update `tests/test_parser_tennis.py`**

```bash
python -c "
from pathlib import Path
p = Path('tests/test_parser_tennis.py')
text = p.read_text(encoding='utf-8')
new = text.replace('handicap_basketball_ft', '2way_handicap_basketball_ft')
assert new.count('2way_handicap_basketball_ft') == 1
p.write_text(new, encoding='utf-8')
print('updated test_parser_tennis.py')
"
```

- [ ] **Step 5: Update `examples/compare_betpawa_competition_full.py`**

```bash
python -c "
from pathlib import Path
p = Path('examples/compare_betpawa_competition_full.py')
text = p.read_text(encoding='utf-8')
new = text.replace('handicap_basketball_ft', '2way_handicap_basketball_ft')
assert new.count('2way_handicap_basketball_ft') == 2
p.write_text(new, encoding='utf-8')
print('updated compare_betpawa_competition_full.py')
"
```

- [ ] **Step 6: Run the full test suite to confirm no regressions**

```bash
python -m pytest tests/ -q
```

Expected: all tests pass. If any test fails, it's likely a stale `handicap_basketball_ft` reference somewhere not caught by the grep — investigate and fix.

- [ ] **Step 7: Commit**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add src/bookieskit/markets/builtin_mappings.py tests/test_parser_basketball.py tests/test_parser_betpawa_basketball.py tests/test_parser_tennis.py examples/compare_betpawa_competition_full.py
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "$(cat <<'EOF'
refactor(markets): rename handicap_basketball_ft -> 2way_handicap_basketball_ft

Breaking change. The "2way_" prefix disambiguates from a hypothetical
future 3way (European 1X2) handicap variant — for consistency with
the new 2way_handicap_ft soccer canonical being added in this release.

Mapping fields (per-bookmaker ids, outcome strings) are unchanged;
only the canonical_id string flips. Updates 5 test files and 1
example script that pinned the old id. Docs and CHANGELOG land in a
later commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 2 — Add `2way_handicap_ft` to BUILTIN_MAPPINGS

## Task 4: Append `2way_handicap_ft` MarketMapping with tentative IDs

**Files:**
- Modify: `src/bookieskit/markets/builtin_mappings.py`
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Write the failing registry smoke test**

Append to `tests/test_registry.py`:

```python
def test_registry_has_2way_handicap_ft():
    from bookieskit.markets.registry import MarketRegistry
    r = MarketRegistry()
    m = r.get_by_canonical("2way_handicap_ft")
    assert m is not None
    assert m.name == "2-Way Asian Handicap - Full Time"
    assert m.parameterized is True
    assert m.sport == "soccer"
    assert m.betpawa_id == "3774"
    assert m.bet9ja_key == "S_AH"
    assert set(m.outcomes.keys()) == {"home", "away"}
    # Per-bookmaker outcome strings (verified by spec)
    assert m.outcomes["home"].betpawa == "1"
    assert m.outcomes["home"].bet9ja == "1"
    assert m.outcomes["away"].betpawa == "2"
    assert m.outcomes["away"].bet9ja == "2"
    # Platform-id lookups
    assert r.get_by_platform_id("betpawa", "3774") is m
    assert r.get_by_platform_id("bet9ja", "S_AH") is m
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/test_registry.py::test_registry_has_2way_handicap_ft -v
```

Expected: FAIL — `2way_handicap_ft` not in registry yet.

- [ ] **Step 3: Append the MarketMapping**

Open `src/bookieskit/markets/builtin_mappings.py`. After the last existing soccer entry (just after `away_over_under_ft` which was added in 0.14.0) and BEFORE the basketball section comment, append:

```python
    # =================== Soccer — 2-way Asian Handicap ==================
    # Asian Handicap (2-way, home/away). Signed line from home's
    # perspective — line=-1.5 means home gives 1.5 goals. Both outcomes
    # live under a single signed key (same convention as
    # 2way_handicap_basketball_ft and handicap_games_tennis_match).
    #
    # The "2way_" prefix distinguishes this from a hypothetical future
    # 3way_handicap_ft (the European 1X2 handicap with draw). BetPawa
    # ships both as separate markets (id=3774 vs id=4724); Bet9ja
    # similarly ships S_AH (Asian) vs S_1X2HND (European). The 3-way
    # variant is explicitly out of scope for this release.
    #
    # Quarter lines (0.25 / 0.75 steps) work natively — the lines dict
    # accepts any float key.
    #
    # SportPesa stays None — Akamai cookie unavailable at probe time;
    # same precedent as the 0.14.0 soccer markets.
    MarketMapping(
        canonical_id="2way_handicap_ft",
        name="2-Way Asian Handicap - Full Time",
        betpawa_id="3774",
        sportybet_id="16",        # SR-code mirror; probe confirms
        bet9ja_key="S_AH",
        betway_id=None,           # locked-in via probe (TBD literal)
        msport_id="16",           # SR-code mirror; probe confirms
        sportpesa_id=None,        # NOT PROBED — Akamai cookie unavailable
        betika_id="16",           # mirror; probe confirms
        sport="soccer",
        outcomes={
            "home": OutcomeMapping(
                canonical_name="home",
                betpawa="1",
                sportybet="Home",
                bet9ja="1",
                betway="__HOME__",
                msport="Home",
                sportpesa="1",
                betika="1",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__POS_2__",
                msport="Away",
                sportpesa="2",
                betika="2",
            ),
        },
        parameterized=True,
    ),
```

- [ ] **Step 4: Run to verify passing**

```bash
python -m pytest tests/test_registry.py::test_registry_has_2way_handicap_ft -v
```

Expected: PASS.

- [ ] **Step 5: Bump builtin-count tests**

Two pre-existing tests in `tests/test_registry.py` assert a hardcoded builtin count. After 0.14.0 these are at 16 and 17. Bump them to 17 and 18 (the new soccer canonical adds 1).

Search for and update both. Use this one-liner to confirm the current values, then edit:

```bash
grep -n "len.*== 16\|len.*== 17\|builtins.*== 16\|builtins.*== 17" tests/test_registry.py
```

Edit each occurrence: 16 → 17, 17 → 18, plus any inline comments mentioning the builtin count (e.g. `# 16 builtins` → `# 17 builtins`).

- [ ] **Step 6: Run the full registry suite**

```bash
python -m pytest tests/test_registry.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add src/bookieskit/markets/builtin_mappings.py tests/test_registry.py
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "$(cat <<'EOF'
feat(markets): add 2way_handicap_ft canonical (Asian Handicap, soccer)

Per-team Over/Under's signed-line counterpart for soccer. Outcomes
home/away (no draw); line is signed from home's perspective. Both
outcomes live under one signed key — same convention as
2way_handicap_basketball_ft and handicap_games_tennis_match.

IDs confirmed by spec: BetPawa=3774, Bet9ja=S_AH. SportyBet/MSport/
Betika tentatively set to SR-code 16; Betway placeholder None.
Probe-confirmed values land in the next commit (Task 5).

SportPesa stays None — Akamai cookie unavailable.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

## Task 5: Lock-in 2way_handicap_ft IDs from probe results

**Files:**
- Modify: `src/bookieskit/markets/builtin_mappings.py` (the `2way_handicap_ft` entry just added)

- [ ] **Step 1: Read the RESOLVED record**

```bash
cat tests/fixtures/event_info/RESOLVED_2way_handicap_ft.md
```

Note the probed values for SportyBet, MSport, Betway, Betika.

- [ ] **Step 2: Update fields**

For each tentative field in the `2way_handicap_ft` mapping, replace the comment `# SR-code mirror; probe confirms` (or `# locked-in via probe (TBD literal)`) with the locked-in value and `# locked-in via probe`:

- `sportybet_id="<observed>"` (most likely still `"16"`)
- `msport_id="<observed>"` (most likely still `"16"`)
- `betway_id="<observed literal name>"` (e.g. `"Asian Handicap"` or `"Handicap - 2 Way"`)
- `betika_id="<observed>"` (most likely still `"16"`)

If any bookmaker's probe found the market genuinely unavailable, set that field to `None` with a one-line comment explaining (mirroring the existing `betika_id=None` precedent on basketball handicap).

If outcome strings differ from the SR-convention defaults, update them too. E.g. if Betika ships `display="Home"` instead of `display="1"`, change `betika="1"` to `betika="Home"`.

- [ ] **Step 3: Run the full test suite**

```bash
python -m pytest tests/ -q
```

Expected: all pass (no new tests yet assert specific probe-derived strings; the smoke test from Task 4 covers BetPawa/Bet9ja which are stable).

- [ ] **Step 4: Commit**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add src/bookieskit/markets/builtin_mappings.py
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "feat(markets): lock-in 2way_handicap_ft ids from probe results"
```

---

# Phase 3 — Extend Betika `_UNIVERSAL_SUB_TYPE_IDS`

## Task 6: Add `"16"` to Betika's universal sub_type_ids

**Files:**
- Modify: `src/bookieskit/bookmakers/betika.py`
- Modify: `tests/test_betika.py`

- [ ] **Step 1: Find the constant**

Current value (after 0.14.0): `_UNIVERSAL_SUB_TYPE_IDS = ("1", "8", "10", "18", "19", "20", "29")` at line 23 of `src/bookieskit/bookmakers/betika.py`.

- [ ] **Step 2: Update the constant + docstrings**

In `src/bookieskit/bookmakers/betika.py`, change the constant to:

```python
# Sub-type ids fanned out by get_event_markets to assemble a complete
# per-event market set. Each id maps to one canonical market in the
# built-in registry: 1=1X2, 8=Next Goal, 10=Double Chance, 16=2-Way
# Asian Handicap, 18=O/U, 19=Home O/U, 20=Away O/U, 29=BTTS.
_UNIVERSAL_SUB_TYPE_IDS = ("1", "8", "10", "16", "18", "19", "20", "29")
```

Find the `get_event_markets` and `get_markets` docstrings (around line 215+ and 285+ respectively). Bump any "seven" → "eight" or "7" → "8" references; update the id-to-market list to include `16=2-Way Asian Handicap`.

- [ ] **Step 3: Update tests pinning the fan-out count**

In `tests/test_betika.py`, find tests asserting a specific number of HTTP calls or expected sub_type_ids:

```bash
grep -n "len(respx.calls)\|sub_type_id.*==\|assert.*== 7\|== {.*'29'" tests/test_betika.py
```

For each test that pins the call count to 7, bump to 8. For tests asserting the expected set of sub_type_ids called, add `"16"` to the expected set.

Specifically:
- `test_betika_get_event_markets_aggregates_seven_sub_type_ids` (or whatever it's named) → rename to `_aggregates_eight_sub_type_ids` and update expectation
- `test_betika_get_event_markets_forwards_competition_id_on_every_call` → bump expected call count

- [ ] **Step 4: Run the Betika tests**

```bash
python -m pytest tests/test_betika.py -v
```

Expected: all pass.

- [ ] **Step 5: Run the full suite**

```bash
python -m pytest tests/ -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add src/bookieskit/bookmakers/betika.py tests/test_betika.py
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "$(cat <<'EOF'
feat(betika): extend _UNIVERSAL_SUB_TYPE_IDS to cover 2way_handicap_ft

Adds sub_type_id 16 to the fan-out tuple (now 8 ids).
Betika.get_markets() now surfaces the new 2way_handicap_ft canonical
end-to-end without callers needing to manually fetch sub_type_id=16.

Same pattern as the 0.14.0 fix that added 8/19/20 for next_goal_ft
and home/away_over_under_ft.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 4 — Per-bookmaker fixture-backed parser tests

## Task 7: Test 2way_handicap_ft against BetPawa fixture

**Files:**
- Modify: `tests/test_parser_betpawa.py`

- [ ] **Step 1: Check that the BetPawa prematch fixture has id=3774**

```bash
python -c "
import json
d = json.load(open('tests/fixtures/event_info/betpawa/prematch.json', encoding='utf-8'))
markets = d.get('markets') or []
ah = [m for m in markets if str(m.get('marketType', {}).get('id')) == '3774']
print(f'BetPawa prematch fixture has id=3774: {bool(ah)} ({len(ah)} entries)')
if ah:
    rows = ah[0].get('row') or []
    print(f'rows: {len(rows)}')
    for r in rows[:3]:
        print(f'  formattedHandicap={r.get(\"formattedHandicap\")} handicap={r.get(\"handicap\")} prices={[(p.get(\"name\"), p.get(\"price\")) for p in (r.get(\"prices\") or [])][:4]}')
"
```

If the prematch fixture has id=3774 with multiple lines and prices: write the test using concrete odds from the fixture. If not, use the probe-captured fixture (`tests/fixtures/event_info/betpawa/2way_handicap_ft.json` — but the probe writes that to a SEPARATE file from the existing `prematch.json`; check both).

- [ ] **Step 2: Write the test**

Append to `tests/test_parser_betpawa.py`. If the existing prematch fixture has the market, use the concrete-odds variant; otherwise use the tolerant variant. The concrete variant (preferred when possible):

```python
def test_parse_betpawa_2way_handicap_ft_from_real_fixture():
    """If the BetPawa prematch fixture contains marketType.id=3774
    (Asian Handicap - FT / 2-Way Handicap), parse_markets should
    surface a parameterized 2way_handicap_ft canonical with at least
    one line having both home and away outcomes.
    """
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betpawa/prematch.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="betpawa")
    ah = next(
        (m for m in markets if m.canonical_id == "2way_handicap_ft"),
        None,
    )
    # If the prematch fixture doesn't contain id=3774 (some events
    # don't ship the market), fall back to probe-captured fixture.
    if ah is None:
        fixture = Path(
            "tests/fixtures/event_info/betpawa/2way_handicap_ft.json"
        )
        if not fixture.exists():
            import pytest
            pytest.skip(
                "BetPawa fixture doesn't contain 2way_handicap_ft "
                "(id=3774) and no probe fixture available"
            )
        response = json.loads(fixture.read_text(encoding="utf-8"))
        markets = parse_markets(response, platform="betpawa")
        ah = next(
            (m for m in markets if m.canonical_id == "2way_handicap_ft"),
            None,
        )
    assert ah is not None, "BetPawa 2way_handicap_ft (id=3774) not found"
    assert ah.lines is not None
    assert len(ah.lines) >= 1
    # At least one line must have both home + away outcomes
    assert any(
        {"home", "away"}.issubset({o.canonical_name for o in outs})
        for outs in ah.lines.values()
    ), f"no line had both home and away: {ah.lines}"
```

- [ ] **Step 3: Run the test**

```bash
python -m pytest tests/test_parser_betpawa.py::test_parse_betpawa_2way_handicap_ft_from_real_fixture -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add tests/test_parser_betpawa.py
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "test(parser): 2way_handicap_ft against betpawa fixture"
```

## Task 8: Test 2way_handicap_ft against Bet9ja fixture

**Files:**
- Modify: `tests/test_parser_bet9ja.py`

- [ ] **Step 1: Write a synthetic test against the S_AH wire shape**

We have wire samples from the diagnostic run (e.g. `S_AH@-1.5_1: 1.85`). Write a synthetic-payload test that exercises the parser end-to-end against a known good shape:

Append to `tests/test_parser_bet9ja.py`:

```python
def test_parse_bet9ja_2way_handicap_ft_synthetic():
    """Bet9ja Asian Handicap (S_AH) — signed line in @-segment of the
    odds key, outcomes _1 (home) / _2 (away). Each (line, outcome)
    pair produces an Outcome under the line key.
    """
    from bookieskit.markets.parser import parse_markets

    response = {
        "D": {
            "O": {
                "S_AH@-1.5_1": "2.40",
                "S_AH@-1.5_2": "1.55",
                "S_AH@-0.5_1": "1.75",
                "S_AH@-0.5_2": "2.05",
                "S_AH@0_1": "1.55",
                "S_AH@0_2": "2.40",
                "S_AH@0.5_1": "1.35",
                "S_AH@0.5_2": "3.10",
            }
        }
    }
    markets = parse_markets(response, platform="bet9ja")
    ah = next(
        (m for m in markets if m.canonical_id == "2way_handicap_ft"),
        None,
    )
    assert ah is not None, "2way_handicap_ft not produced from S_AH"
    assert ah.lines is not None
    assert set(ah.lines.keys()) == {-1.5, -0.5, 0.0, 0.5}
    line_n15 = {o.canonical_name: o.odds for o in ah.lines[-1.5]}
    assert line_n15 == {"home": 2.40, "away": 1.55}
    line_p05 = {o.canonical_name: o.odds for o in ah.lines[0.5]}
    assert line_p05 == {"home": 1.35, "away": 3.10}
```

- [ ] **Step 2: Run the test**

```bash
python -m pytest tests/test_parser_bet9ja.py::test_parse_bet9ja_2way_handicap_ft_synthetic -v
```

Expected: PASS — `S_AH` already matches the registered `bet9ja_key`, and `_parse_bet9ja_key` handles the `@-1.5_1` shape natively.

- [ ] **Step 3: Optionally add a fixture-driven test**

If `tests/fixtures/event_info/bet9ja/next_goal_and_team_ou.json` (captured during 0.14.0) contains `S_AH` keys, also add a fixture-driven test:

```bash
python -c "
import json
d = json.load(open('tests/fixtures/event_info/bet9ja/next_goal_and_team_ou.json', encoding='utf-8'))
odds = (d.get('D') or {}).get('O') or {}
ah_keys = [k for k in odds if k.startswith('S_AH')]
print(f'S_AH keys in fixture: {len(ah_keys)}')
print(ah_keys[:5])
"
```

If the fixture has `S_AH` keys, append a second test:

```python
def test_parse_bet9ja_2way_handicap_ft_from_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path(
        "tests/fixtures/event_info/bet9ja/next_goal_and_team_ou.json"
    )
    response = json.loads(fixture.read_text(encoding="utf-8"))
    markets = parse_markets(response, platform="bet9ja")
    ah = next(
        (m for m in markets if m.canonical_id == "2way_handicap_ft"),
        None,
    )
    assert ah is not None, "Bet9ja 2way_handicap_ft (S_AH) not in fixture"
    assert ah.lines is not None
    assert len(ah.lines) >= 1
    assert any(
        {"home", "away"}.issubset({o.canonical_name for o in outs})
        for outs in ah.lines.values()
    )
```

If the fixture has NO `S_AH` keys, skip this step and rely only on the synthetic test.

- [ ] **Step 4: Run both tests**

```bash
python -m pytest tests/test_parser_bet9ja.py -v -k "2way_handicap_ft"
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add tests/test_parser_bet9ja.py
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "test(parser): 2way_handicap_ft against bet9ja S_AH (synthetic + fixture)"
```

## Task 9: Per-bookmaker fixture tests for SportyBet, MSport, Betway, Betika

**Files:**
- Modify: `tests/test_parser_sportybet.py`
- Modify: `tests/test_parser_msport.py`
- Modify: `tests/test_parser_betway.py`
- Modify: `tests/test_parser_betika.py`

For each of the 4 probed bookmakers, add one fixture-driven test against `tests/fixtures/event_info/<bookmaker>/2way_handicap_ft.json` (created in Task 2). The tests use a tolerant pattern: confirm the canonical was found and at least one line has both home and away outcomes.

- [ ] **Step 1: SportyBet test**

Append to `tests/test_parser_sportybet.py`:

```python
def test_parse_sportybet_2way_handicap_ft_from_probe_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/sportybet/2way_handicap_ft.json")
    if not fixture.exists():
        import pytest
        pytest.skip("SportyBet probe fixture not captured")
    response = json.loads(fixture.read_text(encoding="utf-8"))
    markets = parse_markets(response, platform="sportybet")
    ah = next(
        (m for m in markets if m.canonical_id == "2way_handicap_ft"),
        None,
    )
    assert ah is not None, "SportyBet 2way_handicap_ft not in fixture"
    assert ah.lines is not None
    assert any(
        {"home", "away"}.issubset({o.canonical_name for o in outs})
        for outs in ah.lines.values()
    )
```

Run: `python -m pytest tests/test_parser_sportybet.py::test_parse_sportybet_2way_handicap_ft_from_probe_fixture -v`.
Expected: PASS (or SKIP if the probe didn't capture this bookmaker).

- [ ] **Step 2: MSport test**

Append to `tests/test_parser_msport.py`:

```python
def test_parse_msport_2way_handicap_ft_from_probe_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/msport/2way_handicap_ft.json")
    if not fixture.exists():
        import pytest
        pytest.skip("MSport probe fixture not captured")
    response = json.loads(fixture.read_text(encoding="utf-8"))
    markets = parse_markets(response, platform="msport")
    ah = next(
        (m for m in markets if m.canonical_id == "2way_handicap_ft"),
        None,
    )
    assert ah is not None, "MSport 2way_handicap_ft not in fixture"
    assert ah.lines is not None
    assert any(
        {"home", "away"}.issubset({o.canonical_name for o in outs})
        for outs in ah.lines.values()
    )
```

- [ ] **Step 3: Betway test**

Append to `tests/test_parser_betway.py`:

```python
def test_parse_betway_2way_handicap_ft_from_probe_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betway/2way_handicap_ft.json")
    if not fixture.exists():
        import pytest
        pytest.skip("Betway probe fixture not captured")
    response = json.loads(fixture.read_text(encoding="utf-8"))
    markets = parse_markets(response, platform="betway")
    ah = next(
        (m for m in markets if m.canonical_id == "2way_handicap_ft"),
        None,
    )
    assert ah is not None, "Betway 2way_handicap_ft not in fixture"
    assert ah.lines is not None
    assert any(
        {"home", "away"}.issubset({o.canonical_name for o in outs})
        for outs in ah.lines.values()
    )
```

- [ ] **Step 4: Betika test**

Append to `tests/test_parser_betika.py`:

```python
def test_parse_betika_2way_handicap_ft_from_probe_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betika/2way_handicap_ft.json")
    if not fixture.exists():
        import pytest
        pytest.skip("Betika probe fixture not captured")
    response = json.loads(fixture.read_text(encoding="utf-8"))
    markets = parse_markets(response, platform="betika")
    ah = next(
        (m for m in markets if m.canonical_id == "2way_handicap_ft"),
        None,
    )
    assert ah is not None, "Betika 2way_handicap_ft not in fixture"
    assert ah.lines is not None
    assert any(
        {"home", "away"}.issubset({o.canonical_name for o in outs})
        for outs in ah.lines.values()
    )
```

- [ ] **Step 5: Run all four tests**

```bash
python -m pytest tests/test_parser_sportybet.py tests/test_parser_msport.py tests/test_parser_betway.py tests/test_parser_betika.py -v -k "2way_handicap_ft"
```

Expected: PASS (or SKIP for any bookmaker whose probe didn't capture the market).

- [ ] **Step 6: Commit**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add tests/test_parser_sportybet.py tests/test_parser_msport.py tests/test_parser_betway.py tests/test_parser_betika.py
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "test(parser): 2way_handicap_ft fixture-backed tests for 4 probed bookmakers"
```

---

# Phase 5 — Documentation + version bump

## Task 10: Update `docs/markets.md`

**Files:**
- Modify: `docs/markets.md`

- [ ] **Step 1: Bump market count**

Find the line that currently reads `"16 markets ship in the default MarketRegistry — 9 soccer + 3 basketball + 4 tennis."` (or similar). Change to `"17 markets ship in the default MarketRegistry — 10 soccer + 3 basketball + 4 tennis."`.

- [ ] **Step 2: Add a row to the Soccer (full time) support matrix**

In the soccer table, after the `away_over_under_ft` row, append:

```markdown
| `2way_handicap_ft` | 2-Way Asian Handicap — Full Time | yes (signed line=goals) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ NOT PROBED | ✅ |
```

(The column order is BetPawa | SportyBet | Bet9ja | Betway | MSport | SportPesa | Betika. If the probe found any of the 4 confirmed bookmakers to genuinely NOT expose the market, use `❌ NOT EXPOSED` instead of `✅` for that column.)

- [ ] **Step 3: Update the Basketball (full time) row**

Change `| handicap_basketball_ft |` → `| 2way_handicap_basketball_ft |`. Update any inline prose mentioning `handicap_basketball_ft` to use the new name.

- [ ] **Step 4: Update the Handicap line convention subsection**

Find the "Handicap line convention" prose. Append the new soccer canonical alongside the existing basketball/tennis ones — one sentence addition:

```markdown
The same signed-line convention applies to `2way_handicap_ft` (soccer Asian Handicap) — `line=-1.5` means the home team gives 1.5 goals.
```

- [ ] **Step 5: Visual sanity check**

```bash
git diff docs/markets.md | head -80
```

Confirm the table renders with the new row and that the rename is consistent.

- [ ] **Step 6: Commit**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add docs/markets.md
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "docs(markets): add 2way_handicap_ft row; rename basketball handicap row"
```

## Task 11: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Bump headline counts**

Find every occurrence of `"16 markets"` and change to `"17 markets"`. Find `"9 soccer"` and change to `"10 soccer"`. Find the soccer-section heading like `### Soccer (9 markets, sport="soccer" — the default)` and change to `10 markets`.

- [ ] **Step 2: Add soccer-table row**

After the `away_over_under_ft` row in the soccer table, append:

```markdown
| `2way_handicap_ft` | Parameterized — **signed** line (home's perspective); both outcomes under one signed key. Asian Handicap (no draw). |
```

- [ ] **Step 3: Update basketball-table row**

Change `| handicap_basketball_ft |` → `| 2way_handicap_basketball_ft |`. Update any inline mention.

- [ ] **Step 4: Update Limitations / known gaps if applicable**

If the probe surfaced any bookmaker that genuinely doesn't expose the new market, document with a one-line entry under Limitations / known gaps (matching the 0.14.0 Bet9ja team-O/U precedent).

- [ ] **Step 5: Commit**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add README.md
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "docs(readme): document 2way_handicap_ft + basketball canonical rename"
```

## Task 12: CHANGELOG entry + version bump to 0.15.0

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `src/bookieskit/__init__.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_sportpesa.py` (the version-pin test from 0.14.0)

- [ ] **Step 1: Add `[0.15.0]` section to CHANGELOG**

Insert at the top of `CHANGELOG.md`, just below any unreleased section header (or right at the top if there's no unreleased section):

```markdown
## [0.15.0] - 2026-05-22

### Renamed
- `handicap_basketball_ft` → `2way_handicap_basketball_ft`. **Breaking change** for downstream consumers that pinned the old `canonical_id` string. No deprecation alias provided — the version bump signals it. The "2way_" prefix disambiguates from a hypothetical future 3-way (European 1X2) handicap variant; the mapping fields (per-bookmaker ids, outcome strings) are unchanged, only the canonical_id flips.

### Added
- New canonical soccer market `2way_handicap_ft` — Asian Handicap (2-way, home/away) with signed lines from home's perspective. Mapped on BetPawa (id=3774, "Asian Handicap - FT"), Bet9ja (`S_AH`), SportyBet, MSport, Betway, and Betika. SportPesa stays `None` (Akamai cookie unavailable; same precedent as the 0.14.0 markets).

### Changed
- `Betika._UNIVERSAL_SUB_TYPE_IDS` extended 7 → 8 (added `"16"` for the new Asian Handicap). `Betika.get_event_markets()` / `Betika.get_markets()` now surface the new canonical end-to-end without callers needing to manually fetch sub_type_id=16.
- Built-in canonical market count: 16 → 17 (10 soccer + 3 basketball + 4 tennis).
```

- [ ] **Step 2: Bump `__version__`**

In `src/bookieskit/__init__.py`, change `__version__ = "0.14.0"` to `__version__ = "0.15.0"`.

- [ ] **Step 3: Bump `pyproject.toml`**

In `pyproject.toml`, find `version = "0.14.0"` (near the top under `[project]` or `[tool.poetry]`) and change to `"0.15.0"`.

- [ ] **Step 4: Bump the version-pin test from 0.14.0**

In `tests/test_sportpesa.py`, find `test_top_level_version_bumped` (or similar) and change the expected version string from `"0.14.0"` to `"0.15.0"`.

```bash
grep -n "0.14.0" tests/test_sportpesa.py
```

If multiple occurrences, update all that are version-pin assertions.

- [ ] **Step 5: Run the full test suite one final time**

```bash
python -m pytest tests/ -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" add CHANGELOG.md src/bookieskit/__init__.py pyproject.toml tests/test_sportpesa.py
git -C "C:/Users/loren/Desktop/betpawa/bookieskit" -c user.email="lorenzo.santoro@pawatech.com" -c user.name="Lorenzo Santoro" commit -m "$(cat <<'EOF'
chore: bump to 0.15.0 for 2way_handicap_ft + basketball rename

Three coordinated changes shipped as 0.15.0:

- Renamed handicap_basketball_ft -> 2way_handicap_basketball_ft
  (breaking; no deprecation alias).
- Added 2way_handicap_ft soccer canonical (Asian Handicap, 2-way,
  signed lines).
- Extended Betika._UNIVERSAL_SUB_TYPE_IDS 7 -> 8 so Betika.get_markets()
  surfaces the new soccer canonical.

Built-in canonical count: 16 -> 17. See CHANGELOG.md for full details
and the migration note for downstream consumers.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Done

Final state on the branch:

- `BUILTIN_MAPPINGS`: 17 entries (10 soccer + 3 basketball + 4 tennis). The renamed `2way_handicap_basketball_ft` keeps all its existing per-bookmaker IDs; the new `2way_handicap_ft` is fully mapped except for SportPesa.
- Parser unchanged — the existing parameterized-with-signed-line machinery handles the new canonical natively.
- `Betika._UNIVERSAL_SUB_TYPE_IDS` extended 7 → 8 (adds `"16"`).
- Test coverage: 1 new registry smoke test + 1 BetPawa fixture test + 1 Bet9ja synthetic test + 4 per-bookmaker fixture tests (post-probe) + bumped Betika fan-out call-count assertion.
- Docs: `docs/markets.md` and `README.md` reflect 17 markets, the new soccer row, and the basketball rename.
- `CHANGELOG.md` documents the rename as a breaking change under **Renamed**; the new canonical under **Added**; the Betika fan-out bump under **Changed**.
- Version: `0.14.0` → `0.15.0`.

If the probe surfaced any bookmaker that genuinely doesn't expose Asian Handicap on the probed event, the corresponding test is `pytest.skip()`-marked and the gap is documented in `RESOLVED_2way_handicap_ft.md` and `README.md`. The implementation is shippable even if 1-2 bookmakers stay unmapped beyond SportPesa.
