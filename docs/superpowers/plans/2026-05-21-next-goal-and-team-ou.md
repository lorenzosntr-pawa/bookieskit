# Next Goal + Team Over/Under Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three new canonical soccer markets to `bookieskit`'s built-in registry — `next_goal_ft` (covers both prematch "1st Goal" and live "Nth Goal" via line=goal-number), `home_over_under_ft`, and `away_over_under_ft` — mapped across all 7 supported bookmakers. Bumps version `0.13.1 → 0.14.0`.

**Architecture:** Three new entries in `BUILTIN_MAPPINGS` plus two targeted parser changes: (a) `_extract_line_from_specifier` learns the `goalnr=` key (used by SportyBet + MSport for the Nth-goal specifier); (b) a new `_TeamScopedBetwayRegistry` wrapper substitutes the literal `[Home Team]` / `[Away Team]` placeholders in Betway mapping keys with the actual team names from the event payload. Both changes mirror existing patterns — the `goalnr=` key sits alongside the already-handled `total=` / `hcp=` keys, and `_TeamScopedBetwayRegistry` mirrors the existing `_SportScopedRegistry` shape. No changes to `NormalizedMarket`, `OutcomeMapping`, or `MarketRegistry` shapes.

**Tech Stack:** Python 3.11+, `httpx` async, `pytest`, `pytest-asyncio`. No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-05-21-next-goal-and-team-ou-design.md`.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/bookieskit/markets/parser.py` | modify | `_extract_line_from_specifier`: add `"goalnr"` to recognised keys. New `_TeamScopedBetwayRegistry` class. `_parse_betway` hook to wrap registry when team names are present. |
| `src/bookieskit/markets/builtin_mappings.py` | modify | Append three new `MarketMapping` entries: `next_goal_ft`, `home_over_under_ft`, `away_over_under_ft`. |
| `src/bookieskit/__init__.py` | modify | Bump `__version__` to `"0.14.0"`. |
| `pyproject.toml` | modify | Bump `version` to `0.14.0`. |
| `scripts/probe_next_goal_and_team_ou.py` | create | One-off probe script that walks 5 bookmakers (Bet9ja, MSport, SportPesa, Betika, Betway) against a live (or near-live) soccer event and prints candidate market ids / outcome strings. Outputs become the locked-in registry values. |
| `tests/fixtures/event_info/bet9ja/next_goal_and_team_ou.json` | create (probe-output) | Captured Bet9ja response covering the three new markets — drives parser tests. |
| `tests/fixtures/event_info/msport/next_goal_and_team_ou.json` | create (probe-output) | Captured MSport response. |
| `tests/fixtures/event_info/sportpesa/next_goal_and_team_ou.json` | create (probe-output) | Captured SportPesa response. |
| `tests/fixtures/event_info/betika/next_goal_and_team_ou.json` | create (probe-output) | Captured Betika response. |
| `tests/fixtures/event_info/betway/next_goal_and_team_ou.json` | create (probe-output) | Captured Betway response (with realistic `sportEvent.homeTeam` / `awayTeam` strings to test placeholder substitution). |
| `tests/fixtures/event_info/RESOLVED_next_goal_and_team_ou.md` | create | Decision record: which IDs were probed, which bookmakers genuinely don't expose each market, and the outcome strings observed. |
| `tests/test_registry.py` | modify | Smoke tests: `get_by_canonical("next_goal_ft")`, etc. all return the expected mapping. |
| `tests/test_parser_betpawa.py` | modify | Three new tests against the existing `betpawa/prematch.json` (confirms IDs `28000224`, `5006`, `5003`). |
| `tests/test_parser_sportybet.py` | modify | Three new fixture-driven tests against existing `sportybet/prematch.json` (confirms IDs `8`, `19`, `20`). One unit test for `_extract_line_from_specifier` recognising `goalnr=`. |
| `tests/test_parser_msport.py` | modify | Up to three new tests against the probe-captured MSport fixture (one per market that MSport exposes). |
| `tests/test_parser_bet9ja.py` | modify | Up to three new tests against the probe-captured Bet9ja fixture. |
| `tests/test_parser_betway.py` | modify | Up to three new tests against the probe-captured Betway fixture. One unit test for `_TeamScopedBetwayRegistry` placeholder substitution. |
| `tests/test_parser_sportpesa.py` | modify | Up to three new tests against the probe-captured SportPesa fixture. |
| `tests/test_parser_betika.py` | modify | Up to three new tests against the probe-captured Betika fixture. |
| `docs/markets.md` | modify | Bump market count (13 → 16); add three rows to the Soccer support matrix; add a `next_goal_ft` line-semantic subsection; add a Betway placeholder-substitution subsection. |
| `README.md` | modify | Bump "13 markets" → "16 markets" and soccer "6 markets" → "9 markets" throughout; append three rows to the soccer table; update Limitations / known gaps if any bookmaker is genuinely unmapped. |
| `CHANGELOG.md` | modify | New `[0.14.0]` section. |

Each task ends with a commit so the work integrates incrementally.

---

# Phase 0 — Probe & fixture capture

## Task 1: Write the probe script

**Files:**
- Create: `scripts/probe_next_goal_and_team_ou.py`

- [ ] **Step 1: Create the probe script**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add scripts/probe_next_goal_and_team_ou.py
git commit -m "chore(scripts): add next-goal + team-O/U probe harness"
```

## Task 2: Run the probe against a live event and capture fixtures

**Files:**
- Modify: `tests/fixtures/event_info/<bookmaker>/next_goal_and_team_ou.json` (one per bookmaker)
- Create: `tests/fixtures/event_info/RESOLVED_next_goal_and_team_ou.md`

- [ ] **Step 1: Find a suitable SR match id**

Pick a soccer fixture that's live or near-live (within 24h of kick-off) — most bookmakers expose the three target markets only on actively traded events. Cross-check that SportyBet has it:

```bash
python examples/odds_for_sr_id.py 70784812   # or any current SR id
```

If SportyBet returns a markets payload with `id=8` (Next Goal) and `id=19` / `id=20` (Home/Away O/U), the SR id is good for probing.

- [ ] **Step 2: Set SportPesa cookie**

SportPesa is gated by Akamai Bot Manager. Harvest a cookie from a real browser session and export it:

```powershell
$env:SPORTPESA_COOKIE = "<paste cookie string from devtools>"
```

If you can't get a SportPesa cookie, skip the SportPesa probe — register `sportpesa_id=None` for all three markets and document the gap in the RESOLVED file.

- [ ] **Step 3: Run the probe**

```bash
python scripts/probe_next_goal_and_team_ou.py <SR_ID>
```

Expected output: candidate market ids and outcome strings per bookmaker, plus one JSON fixture per bookmaker written under `tests/fixtures/event_info/<bookmaker>/next_goal_and_team_ou.json`.

- [ ] **Step 4: Hand-verify each candidate**

For each bookmaker, look at the printed candidate(s) and the corresponding fixture file. Note:

- The market id / key string that the registered `MarketMapping` field should hold.
- The exact outcome strings — `display` (Betika), `desc` (SportyBet/MSport), `shortName` (SportPesa), suffix after the last underscore (Bet9ja), `name` (BetPawa/Betway).
- For Betway: confirm the team-name shape — e.g. observed `"Arsenal Total Goals"` confirms the `[Home Team] Total Goals` placeholder pattern is correct.
- For `next_goal_ft`: note the goal-number specifier shape (`goalnr=1`? `formattedHandicap="1"`? `@1_`?).

- [ ] **Step 5: Write the RESOLVED file**

Create `tests/fixtures/event_info/RESOLVED_next_goal_and_team_ou.md` with one section per bookmaker:

```markdown
# RESOLVED — next_goal_ft + home_over_under_ft + away_over_under_ft

**Probed:** YYYY-MM-DD against SR match <SR_ID> (<home> vs <away>).

## Bet9ja
- `next_goal_ft`: bet9ja_key = `<KEY>` (none-outcome suffix = `<X|N|Z>`)
  - OR: NOT EXPOSED — `bet9ja_key=None`. Reason: <observed>.
- `home_over_under_ft`: bet9ja_key = `<KEY>`
- `away_over_under_ft`: bet9ja_key = `<KEY>`

## MSport
- ...

## SportPesa
- ...

## Betika
- ...

## Betway
- `next_goal_ft`: betway_id = `<NAME>`
- `home_over_under_ft`: betway_id = `[Home Team] Total Goals` (confirmed via observed `"<homeTeam> Total Goals"`)
- `away_over_under_ft`: betway_id = `[Away Team] Total Goals`
```

- [ ] **Step 6: Commit fixtures and RESOLVED**

```bash
git add tests/fixtures/event_info/bet9ja/next_goal_and_team_ou.json \
        tests/fixtures/event_info/msport/next_goal_and_team_ou.json \
        tests/fixtures/event_info/sportpesa/next_goal_and_team_ou.json \
        tests/fixtures/event_info/betika/next_goal_and_team_ou.json \
        tests/fixtures/event_info/betway/next_goal_and_team_ou.json \
        tests/fixtures/event_info/RESOLVED_next_goal_and_team_ou.md
git commit -m "test(fixtures): capture next-goal + team-O/U markets across 5 bookmakers"
```

---

# Phase 1 — Specifier parser extension (`goalnr=`)

## Task 3: Add `goalnr` to recognised specifier keys

**Files:**
- Modify: `src/bookieskit/markets/parser.py` (function `_extract_line_from_specifier`)
- Modify: `tests/test_parser_sportybet.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_parser_sportybet.py`:

```python
def test_extract_line_from_specifier_recognises_goalnr():
    from bookieskit.markets.parser import _extract_line_from_specifier
    assert _extract_line_from_specifier("goalnr=1") == 1.0
    assert _extract_line_from_specifier("goalnr=2") == 2.0
    assert _extract_line_from_specifier("total=2.5|goalnr=3") == 2.5  # total wins (first match)
    # Non-recognised key still returns None
    assert _extract_line_from_specifier("foo=1") is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_parser_sportybet.py::test_extract_line_from_specifier_recognises_goalnr -v
```

Expected: FAIL — assertion `_extract_line_from_specifier("goalnr=1") == 1.0` is False because the current function only accepts `("total", "hcp")`.

- [ ] **Step 3: Add `goalnr` to the recognised key list**

Open `src/bookieskit/markets/parser.py`. Locate `_extract_line_from_specifier` (around line 376) and modify the key check:

```python
def _extract_line_from_specifier(specifier: str) -> float | None:
    """Extract line value from a specifier string.

    Shared by SportyBet and MSport — both use the same pipe-delimited
    key=value format (e.g., "total=2.5", "hcp=-0.5", "goalnr=1").
    """
    for part in specifier.split("|"):
        if "=" in part:
            key, value = part.split("=", 1)
            if key in ("total", "hcp", "goalnr"):
                try:
                    return float(value)
                except ValueError:
                    continue
    return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_parser_sportybet.py::test_extract_line_from_specifier_recognises_goalnr -v
```

Expected: PASS.

- [ ] **Step 5: Run the full parser test suite to confirm no regressions**

```bash
pytest tests/test_parser_sportybet.py tests/test_parser_msport.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_parser_sportybet.py
git commit -m "feat(parser): recognise goalnr= specifier for next-goal markets"
```

---

# Phase 2 — `_TeamScopedBetwayRegistry` wrapper

## Task 4: Add the `_TeamScopedBetwayRegistry` class

**Files:**
- Modify: `src/bookieskit/markets/parser.py`
- Modify: `tests/test_parser_betway.py`

- [ ] **Step 1: Write the failing unit test**

Append to `tests/test_parser_betway.py`:

```python
def test_team_scoped_betway_registry_substitutes_placeholders():
    from bookieskit.markets.parser import _TeamScopedBetwayRegistry
    from bookieskit.markets.registry import MarketRegistry
    from bookieskit.markets.types import MarketMapping, OutcomeMapping

    inner = MarketRegistry(load_builtins=False)
    inner.add(
        canonical_id="home_over_under_ft",
        name="Over/Under Home Team - Full Time",
        betway_id="[Home Team] Total Goals",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over", betpawa="", sportybet="",
                bet9ja="", betway="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under", betpawa="", sportybet="",
                bet9ja="", betway="Under",
            ),
        },
        parameterized=True,
    )

    scoped = _TeamScopedBetwayRegistry(
        inner, home_team="Aston Villa", away_team="Brighton",
    )

    # Substituted form resolves
    mapping = scoped.get_by_platform_id(
        "betway", "Aston Villa Total Goals"
    )
    assert mapping is not None
    assert mapping.canonical_id == "home_over_under_ft"

    # Direct (non-placeholder) lookup still works for non-team markets
    inner.add(
        canonical_id="1x2_ft",
        name="1X2", betway_id="[Win/Draw/Win]",
        outcomes={}, parameterized=False,
    )
    scoped = _TeamScopedBetwayRegistry(
        inner, home_team="Aston Villa", away_team="Brighton",
    )
    direct = scoped.get_by_platform_id("betway", "[Win/Draw/Win]")
    assert direct is not None
    assert direct.canonical_id == "1x2_ft"

    # Wrong team name returns None
    miss = scoped.get_by_platform_id("betway", "Nottingham Total Goals")
    assert miss is None

    # Non-betway platform is a no-op fallback
    assert scoped.get_by_platform_id("sportybet", "x") is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_parser_betway.py::test_team_scoped_betway_registry_substitutes_placeholders -v
```

Expected: FAIL — `_TeamScopedBetwayRegistry` doesn't exist yet.

- [ ] **Step 3: Add the `_TeamScopedBetwayRegistry` class**

In `src/bookieskit/markets/parser.py`, add the class just below the existing `_SportScopedRegistry` class (around line 50):

```python
class _TeamScopedBetwayRegistry:
    """Wraps a MarketRegistry to substitute [Home Team] / [Away Team]
    placeholders in Betway mapping keys with the actual team names from
    the current event payload. Used only for the duration of one
    ``_parse_betway`` call.

    Mirrors :class:`_SportScopedRegistry` — re-scope a view of the
    registry without mutating the underlying indexes. The direct
    ``get_by_platform_id`` lookup is unchanged (covers every
    non-team-named market); placeholder substitution only fires when
    the direct lookup misses, and only iterates mappings that actually
    carry a placeholder token.
    """

    _PLACEHOLDER_HOME = "[Home Team]"
    _PLACEHOLDER_AWAY = "[Away Team]"

    def __init__(
        self, inner: MarketRegistry, home_team: str, away_team: str
    ) -> None:
        self._inner = inner
        self._home = home_team
        self._away = away_team

    def get_by_platform_id(
        self,
        platform: str,
        platform_id: str,
        sport: str | None = None,
    ) -> MarketMapping | None:
        result = self._inner.get_by_platform_id(
            platform, platform_id, sport=sport
        )
        if result is not None:
            return result
        if platform != "betway":
            return None
        for mapping in self._inner.list_markets():
            bid = mapping.betway_id
            if not bid or (
                self._PLACEHOLDER_HOME not in bid
                and self._PLACEHOLDER_AWAY not in bid
            ):
                continue
            substituted = bid.replace(
                self._PLACEHOLDER_HOME, self._home
            ).replace(self._PLACEHOLDER_AWAY, self._away)
            if substituted == platform_id:
                return mapping
        return None

    def list_markets(self) -> list[MarketMapping]:
        return self._inner.list_markets()

    def __getattr__(self, name: str):
        return getattr(self._inner, name)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_parser_betway.py::test_team_scoped_betway_registry_substitutes_placeholders -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_parser_betway.py
git commit -m "feat(parser): add _TeamScopedBetwayRegistry placeholder wrapper"
```

## Task 5: Hook `_TeamScopedBetwayRegistry` into `_parse_betway`

**Files:**
- Modify: `src/bookieskit/markets/parser.py` (function `_parse_betway`)
- Modify: `tests/test_parser_betway.py`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_parser_betway.py`:

```python
def test_parse_betway_resolves_team_name_placeholder():
    from bookieskit.markets.parser import parse_markets
    from bookieskit.markets.registry import MarketRegistry
    from bookieskit.markets.types import MarketMapping, OutcomeMapping

    registry = MarketRegistry(load_builtins=False)
    registry.add(
        canonical_id="home_over_under_ft",
        name="Over/Under Home Team - Full Time",
        betway_id="[Home Team] Total Goals",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over", betpawa="", sportybet="",
                bet9ja="", betway="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under", betpawa="", sportybet="",
                bet9ja="", betway="Under",
            ),
        },
        parameterized=True,
    )

    response = {
        "sportEvent": {
            "homeTeam": "Aston Villa",
            "awayTeam": "Brighton",
        },
        "marketsInGroup": [
            {
                "marketId": "m1",
                "name": "Aston Villa Total Goals",
                "handicap": 0,
            },
            {
                "marketId": "m2",
                "name": "Aston Villa Total Goals",
                "handicap": 2.5,
            },
        ],
        "outcomes": [
            {"marketId": "m1", "outcomeId": "m2~over", "name": "Over"},
            {"marketId": "m1", "outcomeId": "m2~under", "name": "Under"},
        ],
        "prices": [
            {"outcomeId": "m2~over", "priceDecimal": 1.85},
            {"outcomeId": "m2~under", "priceDecimal": 1.95},
        ],
    }

    markets = parse_markets(response, platform="betway", registry=registry)
    assert len(markets) == 1
    m = markets[0]
    assert m.canonical_id == "home_over_under_ft"
    assert m.lines is not None
    assert 2.5 in m.lines
    odds_by_name = {o.canonical_name: o.odds for o in m.lines[2.5]}
    assert odds_by_name == {"over": 1.85, "under": 1.95}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_parser_betway.py::test_parse_betway_resolves_team_name_placeholder -v
```

Expected: FAIL — `_parse_betway` doesn't yet wrap the registry.

- [ ] **Step 3: Hook the wrapper into `_parse_betway`**

Open `src/bookieskit/markets/parser.py`. Locate `_parse_betway` (around line 593) and add the wrapping logic at the top of the function, before any existing code:

```python
def _parse_betway(
    response: dict, registry: MarketRegistry, _mode: ProbabilityMode = "off"
) -> list[NormalizedMarket]:
    """Parse Betway event markets response.

    Betway returns denormalized data: marketsInGroup[], outcomes[], prices[]
    as separate arrays linked by marketId and outcomeId. Per-team markets
    (Home/Away Total Goals) carry the literal team name in the market-name
    field; we wrap the registry with _TeamScopedBetwayRegistry so the
    canonical mappings can register the [Home Team] / [Away Team]
    placeholder form and have it substituted at parse-time.
    """
    sport_event = response.get("sportEvent", {})
    home_team = str(sport_event.get("homeTeam", ""))
    away_team = str(sport_event.get("awayTeam", ""))
    if home_team and away_team:
        registry = _TeamScopedBetwayRegistry(
            registry, home_team, away_team,
        )  # type: ignore[assignment]

    results: list[NormalizedMarket] = []
    markets_in_group = response.get("marketsInGroup", [])
    # ...rest of the function unchanged
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_parser_betway.py::test_parse_betway_resolves_team_name_placeholder -v
```

Expected: PASS.

- [ ] **Step 5: Run the full Betway parser test suite to confirm no regressions**

```bash
pytest tests/test_parser_betway.py -v
```

Expected: all pass (the placeholder hook is a no-op when home/away team names aren't present in the registered mappings).

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_parser_betway.py
git commit -m "feat(parser): wrap betway registry with team-scoped placeholder resolver"
```

---

# Phase 3 — Add `next_goal_ft` builtin mapping

## Task 6: Append `next_goal_ft` to BUILTIN_MAPPINGS

**Files:**
- Modify: `src/bookieskit/markets/builtin_mappings.py`
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Write the failing registry smoke test**

Append to `tests/test_registry.py`:

```python
def test_registry_has_next_goal_ft():
    from bookieskit.markets.registry import MarketRegistry
    r = MarketRegistry()
    m = r.get_by_canonical("next_goal_ft")
    assert m is not None
    assert m.name == "Next Goal - Full Time"
    assert m.parameterized is True
    assert m.sport == "soccer"
    assert m.betpawa_id == "28000224"
    assert m.sportybet_id == "8"
    # Outcomes: home, none, away
    assert set(m.outcomes.keys()) == {"home", "none", "away"}
    assert m.outcomes["home"].betpawa == "1"
    assert m.outcomes["none"].betpawa == "None"
    assert m.outcomes["none"].sportybet == "None"
    assert m.outcomes["away"].betpawa == "2"

    # Platform-id lookups
    assert r.get_by_platform_id("betpawa", "28000224") is m
    assert r.get_by_platform_id("sportybet", "8") is m
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_registry.py::test_registry_has_next_goal_ft -v
```

Expected: FAIL — `next_goal_ft` not in `_by_canonical`.

- [ ] **Step 3: Append the mapping to BUILTIN_MAPPINGS**

Open `src/bookieskit/markets/builtin_mappings.py`. After the last existing mapping (the tennis handicap), and before the closing `]` of the list, append:

```python
    # =================== Soccer — Next Goal ============================
    # 1st Goal / Nth Goal: which team scores the next goal. Prematch
    # always carries goal-number 1 (line=1.0); during live play multiple
    # goal numbers can be exposed (line=2.0 after the first goal is
    # scored, etc.). The line value is the GOAL NUMBER, not a goal-count
    # threshold — distinct semantic from over_under_ft despite reusing
    # the parameterized lines dict.
    #
    # Per-bookmaker line-extraction shapes:
    #   - SportyBet/MSport: specifier="goalnr=N" — extended
    #     _extract_line_from_specifier recognises goalnr= alongside
    #     total= and hcp=.
    #   - BetPawa: formattedHandicap="N" — already read first by
    #     _parse_betpawa_parameterized.
    #   - Bet9ja: line in @-segment of the odds key (S_NG@N_outcome).
    #   - Betway: per-line entries with handicap=N.
    #   - SportPesa: specValue=N on the market entry.
    #   - Betika: special_bet_value="N" or extracted from display.
    #
    # IDs for bet9ja/betway/sportpesa/betika are locked-in via the
    # probe script run as Phase 0 of this implementation.
    MarketMapping(
        canonical_id="next_goal_ft",
        name="Next Goal - Full Time",
        betpawa_id="28000224",
        sportybet_id="8",
        bet9ja_key=None,        # set from probe; None if Bet9ja doesn't expose
        betway_id=None,         # set from probe
        msport_id="8",          # tentative SR-code mirror; probe confirms
        sportpesa_id=None,      # set from probe
        betika_id=None,         # set from probe
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
            # The none-outcome strings for bet9ja / sportpesa / betika
            # are tentative best-guesses (SR convention "X" / "None");
            # probe confirms or replaces.
            "none": OutcomeMapping(
                canonical_name="none",
                betpawa="None",
                sportybet="None",
                bet9ja="X",
                betway="__POS_2__",
                msport="None",
                sportpesa="X",
                betika="None",
            ),
            "away": OutcomeMapping(
                canonical_name="away",
                betpawa="2",
                sportybet="Away",
                bet9ja="2",
                betway="__AWAY__",
                msport="Away",
                sportpesa="2",
                betika="2",
            ),
        },
        parameterized=True,
    ),
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_registry.py::test_registry_has_next_goal_ft -v
```

Expected: PASS.

- [ ] **Step 5: Run the full registry test suite**

```bash
pytest tests/test_registry.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/builtin_mappings.py tests/test_registry.py
git commit -m "feat(markets): add next_goal_ft canonical (parameterized by goal number)"
```

## Task 7: Apply Phase-0 probe results to `next_goal_ft`

**Files:**
- Modify: `src/bookieskit/markets/builtin_mappings.py` (the `next_goal_ft` entry just added)

- [ ] **Step 1: Open the RESOLVED record**

```bash
cat tests/fixtures/event_info/RESOLVED_next_goal_and_team_ou.md
```

For each of the five probed bookmakers (Bet9ja, MSport, SportPesa, Betika, Betway), note the recorded `next_goal_ft` value (either the actual id/key or "NOT EXPOSED").

- [ ] **Step 2: Update the `next_goal_ft` mapping with locked-in values**

Open `src/bookieskit/markets/builtin_mappings.py`. In the `next_goal_ft` entry, replace each `None  # set from probe` with the resolved value from the RESOLVED file, and replace the tentative outcome strings (`bet9ja="X"`, `sportpesa="X"`, `betika="None"`) with the observed ones. If a bookmaker doesn't expose the market, leave the id as `None` but update the comment to explain:

```python
bet9ja_key=None,  # Bet9ja does not currently expose Next Goal at full match level
```

- [ ] **Step 3: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all pass (no test asserts a specific probe-derived id yet — those come in Tasks 8-12).

- [ ] **Step 4: Commit**

```bash
git add src/bookieskit/markets/builtin_mappings.py
git commit -m "feat(markets): lock-in next_goal_ft ids from probe results"
```

## Task 8: Test `next_goal_ft` against BetPawa prematch fixture

**Files:**
- Modify: `tests/test_parser_betpawa.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_parser_betpawa.py`:

```python
def test_parse_betpawa_next_goal_ft_from_real_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betpawa/prematch.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="betpawa")
    ng = next(
        (m for m in markets if m.canonical_id == "next_goal_ft"),
        None,
    )
    assert ng is not None
    assert ng.name == "Next Goal - Full Time"
    assert ng.lines is not None
    # Prematch always has goal-number 1 (the next-goal-to-be-scored)
    assert 1.0 in ng.lines
    line1 = {o.canonical_name: o for o in ng.lines[1.0]}
    assert set(line1.keys()) == {"home", "none", "away"}
    # From the fixture: 1=1.94, None=11.04, 2=2.20
    assert line1["home"].odds == 1.94
    assert line1["none"].odds == 11.04
    assert line1["away"].odds == 2.20
```

- [ ] **Step 2: Run test to verify it passes**

```bash
pytest tests/test_parser_betpawa.py::test_parse_betpawa_next_goal_ft_from_real_fixture -v
```

Expected: PASS — `next_goal_ft` is in the registry, the BetPawa parser already reads `formattedHandicap` as the line key, and the outcome strings `"1"` / `"None"` / `"2"` match `OutcomeMapping.betpawa`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_parser_betpawa.py
git commit -m "test(parser): next_goal_ft against betpawa prematch fixture"
```

## Task 9: Test `next_goal_ft` against SportyBet prematch fixture

**Files:**
- Modify: `tests/test_parser_sportybet.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_parser_sportybet.py`:

```python
def test_parse_sportybet_next_goal_ft_from_real_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/sportybet/prematch.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="sportybet")
    ng = next(
        (m for m in markets if m.canonical_id == "next_goal_ft"),
        None,
    )
    assert ng is not None
    assert ng.lines is not None
    assert 1.0 in ng.lines  # 1st Goal — goalnr=1 → line=1.0
    line1 = {o.canonical_name: o for o in ng.lines[1.0]}
    assert set(line1.keys()) == {"home", "none", "away"}
    # From the fixture: Home=1.93, None=11.00, Away=2.20
    assert line1["home"].odds == 1.93
    assert line1["none"].odds == 11.00
    assert line1["away"].odds == 2.20
```

- [ ] **Step 2: Run test to verify it passes**

```bash
pytest tests/test_parser_sportybet.py::test_parse_sportybet_next_goal_ft_from_real_fixture -v
```

Expected: PASS — the `goalnr=` specifier change from Task 3 makes this work.

- [ ] **Step 3: Commit**

```bash
git add tests/test_parser_sportybet.py
git commit -m "test(parser): next_goal_ft against sportybet prematch fixture"
```

## Task 10: Per-bookmaker fixture-backed tests for `next_goal_ft` (MSport, Bet9ja, Betway, SportPesa, Betika)

**Files:**
- Modify: `tests/test_parser_msport.py`
- Modify: `tests/test_parser_bet9ja.py`
- Modify: `tests/test_parser_betway.py`
- Modify: `tests/test_parser_sportpesa.py`
- Modify: `tests/test_parser_betika.py`

For each bookmaker where the probe locked-in a non-`None` id for `next_goal_ft`, add one fixture-backed test. Skip the test for any bookmaker whose registry value is `None`.

- [ ] **Step 1: MSport — write test if applicable**

If `msport_id` was set to a non-None value in Task 7, append to `tests/test_parser_msport.py`:

```python
def test_parse_msport_next_goal_ft_from_probe_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/msport/next_goal_and_team_ou.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="msport")
    ng = next(
        (m for m in markets if m.canonical_id == "next_goal_ft"),
        None,
    )
    assert ng is not None
    assert ng.lines is not None
    # At least goal-number 1 must be present on a live or prematch event
    assert 1.0 in ng.lines
    line1 = {o.canonical_name: o for o in ng.lines[1.0]}
    assert "home" in line1 and "away" in line1
    # MSport may or may not expose the "None" outcome — depends on capture
```

Run: `pytest tests/test_parser_msport.py::test_parse_msport_next_goal_ft_from_probe_fixture -v`
Expected: PASS.

- [ ] **Step 2: Bet9ja — write test if applicable**

If `bet9ja_key` was set in Task 7, append to `tests/test_parser_bet9ja.py`:

```python
def test_parse_bet9ja_next_goal_ft_from_probe_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/bet9ja/next_goal_and_team_ou.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="bet9ja")
    ng = next(
        (m for m in markets if m.canonical_id == "next_goal_ft"),
        None,
    )
    assert ng is not None
    assert ng.lines is not None
    line_keys = list(ng.lines.keys())
    assert any(k >= 1.0 for k in line_keys)
```

Run: `pytest tests/test_parser_bet9ja.py::test_parse_bet9ja_next_goal_ft_from_probe_fixture -v`
Expected: PASS.

- [ ] **Step 3: Betway — write test if applicable**

If `betway_id` was set (the `next_goal_ft` Betway entry uses a literal name like `"Next Goal"`, NOT a placeholder), append to `tests/test_parser_betway.py`:

```python
def test_parse_betway_next_goal_ft_from_probe_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betway/next_goal_and_team_ou.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="betway")
    ng = next(
        (m for m in markets if m.canonical_id == "next_goal_ft"),
        None,
    )
    assert ng is not None
    assert ng.lines is not None
```

Run: `pytest tests/test_parser_betway.py::test_parse_betway_next_goal_ft_from_probe_fixture -v`
Expected: PASS.

- [ ] **Step 4: SportPesa — write test if applicable**

Same pattern, against `tests/fixtures/event_info/sportpesa/next_goal_and_team_ou.json`. Skip if `sportpesa_id=None`.

- [ ] **Step 5: Betika — write test if applicable**

Same pattern, against `tests/fixtures/event_info/betika/next_goal_and_team_ou.json`. Skip if `betika_id=None`.

- [ ] **Step 6: Commit all per-bookmaker tests**

```bash
git add tests/test_parser_msport.py tests/test_parser_bet9ja.py \
        tests/test_parser_betway.py tests/test_parser_sportpesa.py \
        tests/test_parser_betika.py
git commit -m "test(parser): next_goal_ft fixture-backed tests across bookmakers"
```

---

# Phase 4 — Add `home_over_under_ft` + `away_over_under_ft` builtins

## Task 11: Append `home_over_under_ft` to BUILTIN_MAPPINGS

**Files:**
- Modify: `src/bookieskit/markets/builtin_mappings.py`
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Write the failing registry smoke test**

Append to `tests/test_registry.py`:

```python
def test_registry_has_home_over_under_ft():
    from bookieskit.markets.registry import MarketRegistry
    r = MarketRegistry()
    m = r.get_by_canonical("home_over_under_ft")
    assert m is not None
    assert m.name == "Over/Under Home Team - Full Time"
    assert m.parameterized is True
    assert m.sport == "soccer"
    assert m.betpawa_id == "5006"
    assert m.sportybet_id == "19"
    assert m.betway_id == "[Home Team] Total Goals"
    assert set(m.outcomes.keys()) == {"over", "under"}

    assert r.get_by_platform_id("betpawa", "5006") is m
    assert r.get_by_platform_id("sportybet", "19") is m
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_registry.py::test_registry_has_home_over_under_ft -v
```

Expected: FAIL.

- [ ] **Step 3: Append the mapping**

In `src/bookieskit/markets/builtin_mappings.py`, after the `next_goal_ft` entry, append:

```python
    # =================== Soccer — Home Team Over/Under =================
    # Per-team Over/Under: line = total goals scored by the home team
    # specifically (e.g. line=1.5 means home scores 2+). Every bookmaker
    # we support ships this as a distinct market id from the away
    # variant — so we model it as two separate canonicals
    # (home_over_under_ft + away_over_under_ft) rather than a single
    # canonical with team encoded in outcome names.
    #
    # Betway is the special case: its market name carries the literal
    # team name (e.g. "Aston Villa Total Goals"). We register the
    # canonical with the [Home Team] placeholder; the
    # _TeamScopedBetwayRegistry wrapper substitutes the placeholder
    # against sportEvent.homeTeam at parse-time.
    MarketMapping(
        canonical_id="home_over_under_ft",
        name="Over/Under Home Team - Full Time",
        betpawa_id="5006",
        sportybet_id="19",
        bet9ja_key=None,                       # set from probe
        betway_id="[Home Team] Total Goals",   # placeholder substituted at parse-time; format confirmed by probe
        msport_id="19",                        # tentative SR-code mirror; probe confirms
        sportpesa_id=None,                     # set from probe
        betika_id=None,                        # set from probe
        sport="soccer",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="O",
                betway="Over",
                msport="Over",
                sportpesa="OV",
                betika="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="U",
                betway="Under",
                msport="Under",
                sportpesa="UN",
                betika="Under",
            ),
        },
        parameterized=True,
    ),
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_registry.py::test_registry_has_home_over_under_ft -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/builtin_mappings.py tests/test_registry.py
git commit -m "feat(markets): add home_over_under_ft canonical"
```

## Task 12: Append `away_over_under_ft` to BUILTIN_MAPPINGS

**Files:**
- Modify: `src/bookieskit/markets/builtin_mappings.py`
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Write the failing registry smoke test**

Append to `tests/test_registry.py`:

```python
def test_registry_has_away_over_under_ft():
    from bookieskit.markets.registry import MarketRegistry
    r = MarketRegistry()
    m = r.get_by_canonical("away_over_under_ft")
    assert m is not None
    assert m.name == "Over/Under Away Team - Full Time"
    assert m.parameterized is True
    assert m.sport == "soccer"
    assert m.betpawa_id == "5003"
    assert m.sportybet_id == "20"
    assert m.betway_id == "[Away Team] Total Goals"
    assert set(m.outcomes.keys()) == {"over", "under"}

    assert r.get_by_platform_id("betpawa", "5003") is m
    assert r.get_by_platform_id("sportybet", "20") is m
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_registry.py::test_registry_has_away_over_under_ft -v
```

Expected: FAIL.

- [ ] **Step 3: Append the mapping**

In `src/bookieskit/markets/builtin_mappings.py`, after the `home_over_under_ft` entry, append:

```python
    # =================== Soccer — Away Team Over/Under =================
    # Mirror of home_over_under_ft for the away team. Same shape, same
    # outcome conventions; betway_id uses the [Away Team] placeholder.
    MarketMapping(
        canonical_id="away_over_under_ft",
        name="Over/Under Away Team - Full Time",
        betpawa_id="5003",
        sportybet_id="20",
        bet9ja_key=None,                       # set from probe
        betway_id="[Away Team] Total Goals",   # placeholder substituted at parse-time
        msport_id="20",                        # tentative SR-code mirror; probe confirms
        sportpesa_id=None,                     # set from probe
        betika_id=None,                        # set from probe
        sport="soccer",
        outcomes={
            "over": OutcomeMapping(
                canonical_name="over",
                betpawa="Over",
                sportybet="Over",
                bet9ja="O",
                betway="Over",
                msport="Over",
                sportpesa="OV",
                betika="Over",
            ),
            "under": OutcomeMapping(
                canonical_name="under",
                betpawa="Under",
                sportybet="Under",
                bet9ja="U",
                betway="Under",
                msport="Under",
                sportpesa="UN",
                betika="Under",
            ),
        },
        parameterized=True,
    ),
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_registry.py::test_registry_has_away_over_under_ft -v
```

Expected: PASS.

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```bash
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/builtin_mappings.py tests/test_registry.py
git commit -m "feat(markets): add away_over_under_ft canonical"
```

## Task 13: Apply Phase-0 probe results to home_/away_over_under_ft

**Files:**
- Modify: `src/bookieskit/markets/builtin_mappings.py` (both entries)

- [ ] **Step 1: Open the RESOLVED record**

```bash
cat tests/fixtures/event_info/RESOLVED_next_goal_and_team_ou.md
```

- [ ] **Step 2: Update both team-O/U entries with locked-in values**

For each `None  # set from probe` in the `home_over_under_ft` and `away_over_under_ft` entries, replace with the resolved value from the RESOLVED file (or update the comment if the bookmaker doesn't expose the market).

- [ ] **Step 3: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/bookieskit/markets/builtin_mappings.py
git commit -m "feat(markets): lock-in home/away_over_under_ft ids from probe"
```

## Task 14: Test `home_over_under_ft` + `away_over_under_ft` against BetPawa and SportyBet fixtures

**Files:**
- Modify: `tests/test_parser_betpawa.py`
- Modify: `tests/test_parser_sportybet.py`

- [ ] **Step 1: Append BetPawa tests**

```python
def test_parse_betpawa_home_over_under_ft_from_real_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betpawa/prematch.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="betpawa")
    home_ou = next(
        (m for m in markets if m.canonical_id == "home_over_under_ft"),
        None,
    )
    assert home_ou is not None
    assert home_ou.lines is not None
    # The fixture has lines 0.5 / 1.5 / 2.5 from rows id=374100486/485/493
    assert 0.5 in home_ou.lines
    line05 = {o.canonical_name: o.odds for o in home_ou.lines[0.5]}
    assert line05 == {"over": 1.23, "under": 3.47}


def test_parse_betpawa_away_over_under_ft_from_real_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betpawa/prematch.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="betpawa")
    away_ou = next(
        (m for m in markets if m.canonical_id == "away_over_under_ft"),
        None,
    )
    assert away_ou is not None
    assert away_ou.lines is not None
    assert len(away_ou.lines) >= 1
    # At least one line must have both over and under outcomes
    for line, outs in away_ou.lines.items():
        names = {o.canonical_name for o in outs}
        if {"over", "under"}.issubset(names):
            return
    raise AssertionError("no away O/U line had both over and under")
```

Run: `pytest tests/test_parser_betpawa.py -v`. Expected: all new tests pass.

- [ ] **Step 2: Append SportyBet tests**

```python
def test_parse_sportybet_home_over_under_ft_from_real_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/sportybet/prematch.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="sportybet")
    home_ou = next(
        (m for m in markets if m.canonical_id == "home_over_under_ft"),
        None,
    )
    assert home_ou is not None
    assert home_ou.lines is not None
    # From the fixture: id=19 has total=0.5, 1.5, 2.5, 3.5
    assert 0.5 in home_ou.lines
    line05 = {o.canonical_name: o.odds for o in home_ou.lines[0.5]}
    assert line05 == {"over": 1.27, "under": 3.50}


def test_parse_sportybet_away_over_under_ft_from_real_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/sportybet/prematch.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="sportybet")
    away_ou = next(
        (m for m in markets if m.canonical_id == "away_over_under_ft"),
        None,
    )
    assert away_ou is not None
    assert away_ou.lines is not None
    # From the fixture: id=20 total=0.5 has Over=1.35, Under=3.00
    assert 0.5 in away_ou.lines
    line05 = {o.canonical_name: o.odds for o in away_ou.lines[0.5]}
    assert line05 == {"over": 1.35, "under": 3.00}
```

Run: `pytest tests/test_parser_sportybet.py -v`. Expected: all new tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_parser_betpawa.py tests/test_parser_sportybet.py
git commit -m "test(parser): home/away_over_under_ft against betpawa+sportybet fixtures"
```

## Task 15: Per-bookmaker fixture-backed tests for `home_over_under_ft` + `away_over_under_ft` (MSport, Bet9ja, Betway, SportPesa, Betika)

**Files:**
- Modify: `tests/test_parser_msport.py`
- Modify: `tests/test_parser_bet9ja.py`
- Modify: `tests/test_parser_betway.py`
- Modify: `tests/test_parser_sportpesa.py`
- Modify: `tests/test_parser_betika.py`

For each bookmaker with non-`None` ids for `home_over_under_ft` / `away_over_under_ft`, add one fixture-backed test per market.

- [ ] **Step 1: Betway — fixture-backed test (most important because of placeholder logic)**

Append to `tests/test_parser_betway.py`:

```python
def test_parse_betway_home_over_under_ft_with_placeholder():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betway/next_goal_and_team_ou.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="betway")
    home_ou = next(
        (m for m in markets if m.canonical_id == "home_over_under_ft"),
        None,
    )
    assert home_ou is not None, (
        "Placeholder substitution failed — check that "
        "sportEvent.homeTeam in the fixture matches what Betway returned, "
        "and that the captured market name follows the "
        "'<homeTeam> Total Goals' shape."
    )
    assert home_ou.lines is not None
    assert len(home_ou.lines) >= 1


def test_parse_betway_away_over_under_ft_with_placeholder():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/betway/next_goal_and_team_ou.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))

    markets = parse_markets(response, platform="betway")
    away_ou = next(
        (m for m in markets if m.canonical_id == "away_over_under_ft"),
        None,
    )
    assert away_ou is not None
    assert away_ou.lines is not None
```

Run: `pytest tests/test_parser_betway.py -v`. Expected: PASS.

- [ ] **Step 2: MSport — fixture-backed tests**

Append to `tests/test_parser_msport.py`:

```python
def test_parse_msport_home_over_under_ft_from_probe_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/msport/next_goal_and_team_ou.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))
    markets = parse_markets(response, platform="msport")
    home_ou = next(
        (m for m in markets if m.canonical_id == "home_over_under_ft"),
        None,
    )
    assert home_ou is not None
    assert home_ou.lines is not None


def test_parse_msport_away_over_under_ft_from_probe_fixture():
    import json
    from pathlib import Path
    from bookieskit.markets.parser import parse_markets

    fixture = Path("tests/fixtures/event_info/msport/next_goal_and_team_ou.json")
    response = json.loads(fixture.read_text(encoding="utf-8"))
    markets = parse_markets(response, platform="msport")
    away_ou = next(
        (m for m in markets if m.canonical_id == "away_over_under_ft"),
        None,
    )
    assert away_ou is not None
    assert away_ou.lines is not None
```

- [ ] **Step 3: Bet9ja — fixture-backed tests (skip whichever the probe shows unmapped)**

Same pattern, against `tests/fixtures/event_info/bet9ja/next_goal_and_team_ou.json`.

- [ ] **Step 4: SportPesa — fixture-backed tests (skip if cookie unavailable)**

Same pattern, against `tests/fixtures/event_info/sportpesa/next_goal_and_team_ou.json`.

- [ ] **Step 5: Betika — fixture-backed tests**

Same pattern, against `tests/fixtures/event_info/betika/next_goal_and_team_ou.json`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_parser_msport.py tests/test_parser_bet9ja.py \
        tests/test_parser_betway.py tests/test_parser_sportpesa.py \
        tests/test_parser_betika.py
git commit -m "test(parser): home/away_over_under_ft fixture-backed tests across bookmakers"
```

---

# Phase 5 — Documentation

## Task 16: Update `docs/markets.md`

**Files:**
- Modify: `docs/markets.md`

- [ ] **Step 1: Bump market counts**

Open `docs/markets.md`. Change:

- Line ~25: `"13 markets ship in the default MarketRegistry — 6 soccer + 3 basketball + 4 tennis."` → `"16 markets ship in the default MarketRegistry — 9 soccer + 3 basketball + 4 tennis."`

- [ ] **Step 2: Append three rows to the Soccer (full time) support matrix**

In the `### Soccer (full time)` table (around line 29), after the `1x2_2up_ft` row, add:

```markdown
| `next_goal_ft` | Next Goal — Full Time | yes (line = goal number) | ✅ | ✅ | <bet9ja-status> | <betway-status> | <msport-status> | <sportpesa-status> | <betika-status> |
| `home_over_under_ft` | Over/Under — Home Team — Full Time | yes (line = goals) | ✅ | ✅ | <bet9ja-status> | <betway-status> | <msport-status> | <sportpesa-status> | <betika-status> |
| `away_over_under_ft` | Over/Under — Away Team — Full Time | yes (line = goals) | ✅ | ✅ | <bet9ja-status> | <betway-status> | <msport-status> | <sportpesa-status> | <betika-status> |
```

Replace each `<bookmaker-status>` with `✅` (mapped) or `—` (not exposed by that bookmaker), based on the RESOLVED file.

- [ ] **Step 3: Add a `next_goal_ft` line-semantic explainer**

After the soccer table, before the `### Tennis (full match)` heading, add:

```markdown
The `next_goal_ft` market is parameterized by **goal number**: `line=1.0` is "1st goal", `line=2.0` is "2nd goal", and so on. Prematch events always carry `line=1.0` only; live events can carry multiple goal numbers under one `NormalizedMarket` (e.g. after the home team scores the 1st goal, the bookmaker exposes both "2nd goal" and "3rd goal" odds and the parser groups them under the same canonical id). Outcomes are `home` / `none` / `away` — `none` means no further goal in regular time.

Per-bookmaker goal-number specifier shapes:
- **SportyBet / MSport**: `specifier="goalnr=N"`. `_extract_line_from_specifier` recognises `goalnr=` alongside `total=` and `hcp=`.
- **BetPawa**: `formattedHandicap="N"` per row in the parameterized payload — handled by the existing `_parse_betpawa_parameterized` flow.
- **Bet9ja / Betway / SportPesa / Betika**: line embedded in the per-line entry the same way as `over_under_ft` — no parser change required.
```

- [ ] **Step 4: Add a Betway placeholder-substitution subsection**

Just before `## Custom mappings` (around line 140), add a new subsection:

```markdown
## Betway team-name placeholders

Some Betway markets carry the literal team name in the market-name field — e.g. `"Aston Villa Total Goals"` / `"Brighton Total Goals"` for `home_over_under_ft` / `away_over_under_ft`. The canonical mappings register the placeholder form `"[Home Team] Total Goals"` / `"[Away Team] Total Goals"` (literal `[Home Team]` / `[Away Team]` tokens).

At parse-time, `_parse_betway` wraps the supplied registry in `_TeamScopedBetwayRegistry` using `sportEvent.homeTeam` / `awayTeam` from the response. The wrapper substitutes the literal placeholders against the actual team names on every miss; non-team-named markets take the fast direct-lookup path unchanged. Custom mappings can use the same `[Home Team]` / `[Away Team]` tokens in `betway_id` to participate in this mechanism — no code changes needed.
```

- [ ] **Step 5: Run any doc-lint checks (if configured)**

```bash
git diff docs/markets.md | head -100
```

Visually verify the table renders correctly and the new subsections fit the existing prose style.

- [ ] **Step 6: Commit**

```bash
git add docs/markets.md
git commit -m "docs(markets): add next_goal_ft + team-O/U + betway placeholders"
```

## Task 17: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Bump market counts in the headline**

Search for `"13 markets ship as builtins"` and replace with `"16 markets ship as builtins"`. Search for `"6 soccer"` and replace with `"9 soccer"`. Confirm both bullet line (around L79) and the count summary (L84) are updated.

- [ ] **Step 2: Add three rows to the soccer table**

In the `### Soccer (6 markets, sport="soccer" — the default)` heading (around L86), change `6 markets` to `9 markets`. Below the `1x2_2up_ft` row, add:

```markdown
| `next_goal_ft` | Parameterized — line = goal number (1=1st goal, 2=2nd goal, ...). Outcomes home / none / away. Covers prematch "1st Goal" and live "Nth Goal" under one canonical. |
| `home_over_under_ft` | Parameterized — line = goals scored by home team only |
| `away_over_under_ft` | Parameterized — line = goals scored by away team only |
```

- [ ] **Step 3: Update Limitations / known gaps if applicable**

If any bookmaker is genuinely unmapped after probing (e.g. "Bet9ja does not currently expose Next Goal at full match level"), add a one-line entry under the Limitations / known gaps section, matching the existing style of the 1Up/2Up unmapped-bookmaker note.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): document 3 new soccer markets (next_goal + team O/U)"
```

## Task 18: Add CHANGELOG entry and bump version

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `src/bookieskit/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Read the existing CHANGELOG**

```bash
head -30 CHANGELOG.md
```

Note the existing version-section format.

- [ ] **Step 2: Add a `[0.14.0]` section**

Insert at the top of `CHANGELOG.md`, under any unreleased notes:

```markdown
## [0.14.0] - 2026-05-21

### Added
- Three new canonical soccer markets:
  - `next_goal_ft` — "next goal scored" (Home / None / Away). Parameterized by **goal number** (`lines[1.0]` is 1st goal prematch; live events can expose `lines[2.0]`, `lines[3.0]`, etc. under one canonical id). Mapped across BetPawa, SportyBet, and any other bookmaker that survived the probe.
  - `home_over_under_ft` — Over/Under on goals scored by the home team only.
  - `away_over_under_ft` — Over/Under on goals scored by the away team only.
- `_TeamScopedBetwayRegistry` — wraps a `MarketRegistry` to substitute literal `[Home Team]` / `[Away Team]` placeholders in Betway mapping keys with the actual team names from the event payload. Used internally by `_parse_betway`; custom mappings can use the same placeholders.

### Changed
- `_extract_line_from_specifier` (SportyBet + MSport) now recognises `goalnr=N` alongside `total=N` and `hcp=N`.
- Built-in canonical market count: 13 → 16 (9 soccer + 3 basketball + 4 tennis).
```

- [ ] **Step 3: Bump `__version__`**

In `src/bookieskit/__init__.py`, change `__version__ = "0.13.1"` → `__version__ = "0.14.0"`.

- [ ] **Step 4: Bump `pyproject.toml` version**

In `pyproject.toml`, change `version = "0.13.1"` (or whatever the current value is — verify with `grep '^version' pyproject.toml`) to `version = "0.14.0"`.

- [ ] **Step 5: Run the full test suite one final time**

```bash
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md src/bookieskit/__init__.py pyproject.toml
git commit -m "chore: bump to 0.14.0 for next_goal_ft + home/away_over_under_ft"
```

---

# Done

Final summary of what's now in the repo:

- `BUILTIN_MAPPINGS` has 3 new entries (`next_goal_ft`, `home_over_under_ft`, `away_over_under_ft`), all `sport="soccer"`, all `parameterized=True`.
- The parser handles `goalnr=` specifiers (SportyBet/MSport) and Betway `[Home Team]` / `[Away Team]` placeholders.
- All 7 bookmakers either have locked-in ids for each new market or have a documented `None` gap.
- Tests cover registry lookups, parser behaviour against real fixtures (BetPawa + SportyBet) and probe-captured fixtures (others), and one targeted unit test for `_TeamScopedBetwayRegistry`.
- Docs (`README.md`, `docs/markets.md`, `CHANGELOG.md`) reflect the new markets and the placeholder convention.
- Version bumped to `0.14.0`.

If any probed bookmaker is missing from the captured fixtures (e.g. SportPesa cookie wasn't available), the corresponding tests are skipped and the gap is documented inline in `RESOLVED_next_goal_and_team_ou.md` and `README.md`. The implementation is shippable even if 1-2 bookmakers stay unmapped — additional bookmakers can be added later by re-running the probe and committing the resulting fixtures + registry edits.
