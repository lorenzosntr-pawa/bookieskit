# RESOLVED — next_goal_ft + home_over_under_ft + away_over_under_ft

**Probed:** 2026-05-21. Because the bookmakers don't all expose the same
markets on the same fixture (live vs prematch availability shifts), three
different soccer SR ids were used so that every captured fixture has the
relevant markets actually present:

| Bookmaker | SR id     | Match                                  | State     |
|-----------|-----------|----------------------------------------|-----------|
| Bet9ja    | 71549302  | Qatar vs Sudan (Int. Friendly)         | prematch  |
| MSport    | 71549302  | Qatar vs Sudan (Int. Friendly)         | prematch  |
| SportPesa | —         | —                                      | NOT PROBED|
| Betika    | 71443804  | Wolfsburg vs Paderborn (Bundesliga 2)  | prematch  |
| Betway    | 70926700  | Negelle Arsi vs Shire Endaselassie FC  | live      |

Probe-script notes (bugs found, not modified per task constraints):

- The probe script `scripts/probe_next_goal_and_team_ou.py` calls
  `Bet9ja.get_live_event_markets` (does not exist; the real method is
  `get_live_event_detail`). For this run we used the prematch path on a
  prematch fixture, so the script succeeded for Bet9ja via
  `build_prematch_event_map` + `get_event_detail`.
- The probe calls `SportPesa.get_navigation(sport_id=14)` but
  `SportPesa.get_navigation()` takes no positional/keyword args. Combined
  with the absence of an Akamai cookie, SportPesa was skipped entirely.
- The probe calls `Betika.get_events(...)` but Betika exposes
  `get_matches(...)` instead. The Betika fixture was captured manually
  using the correct `get_matches(match_id=..., sub_type_id=...,
  competition_id=...)` flow, merging sub_type_ids 1/8/19/20 into a
  single match-shaped payload (the shape `Betika.get_event_markets`
  produces for the four universal ids).
- The probe calls `Betway.get_event_markets(f"sr:match:{sr_id}")` but
  Betway only accepts the bare numeric SR id (the prefixed form returns
  400 "value is not valid"). The Betway fixture was captured manually
  using the bare id, and `sportEvent` (which lives on
  `get_event_detail`, not `get_event_markets`) was merged in so the
  fixture has homeTeam/awayTeam for the parser.

## Bet9ja
- `next_goal_ft`: bet9ja_key = `S_1STGOAL`
  - none-outcome suffix: `X` (outcomes are `S_1STGOAL_1` / `S_1STGOAL_X` / `S_1STGOAL_2`)
  - Notes: Bet9ja keys carry no specifier; the canonical "1st goal" is
    full-time. There is also `S_1STGHT` (1st goal in 1st half) and
    `S_1STGHTH` / `S_1STGHTA` (1st goal in half — home/away view) —
    these are NOT what we want for `next_goal_ft`.
- `home_over_under_ft`: bet9ja_key = `S_HAOU` (shared with away_over_under_ft).
  Bet9ja ships per-team O/U as a single combined market with the 4 outcomes
  per line distinguished by suffix: `_OH`=Over Home, `_UH`=Under Home,
  `_OA`=Over Away, `_UA`=Under Away. The parser routes outcomes to the
  right canonical via OutcomeMapping.bet9ja matching.
- `away_over_under_ft`: bet9ja_key = `S_HAOU` (shared — see above).

## MSport
- `next_goal_ft`: msport_id = `8`
  - Market name: `Next Goal`
  - Specifier shape: `goalnr=1` (specifies which goal — 1 = next)
  - Outcomes: `Home` / `None` / `Away` (note: `desc` field uses
    "Home"/"None"/"Away", not "1"/"X"/"2")
  - Notes: Observed only on the live probe (id 68746506 Mohun Bagan v
    Sporting Club Delhi). The prematch probe on Qatar v Sudan did not
    expose it. MSport reuses id=8 for related half-time goal markets
    with the same `goalnr=N` specifier convention.
- `home_over_under_ft`: msport_id = `19`
  - Market name: `Home O/U`
  - Specifier: `total=N.5` (e.g. `total=1.5`, `total=2.5`, ...)
  - Outcomes: `Over N.5` / `Under N.5`
- `away_over_under_ft`: msport_id = `20`
  - Market name: `Away O/U`
  - Specifier: `total=N.5`
  - Outcomes: `Over N.5` / `Under N.5`

## SportPesa
- NOT PROBED — Akamai cookie unavailable, and the probe script's
  `get_navigation(sport_id=14)` call is incompatible with the real
  signature. All three fields stay `None`.

## Betika
- `next_goal_ft`: betika_id = `8`
  - Market name: `1ST GOAL` (yes — Betika labels "next goal" as
    "1ST GOAL" but the special_bet_value is `goalnr=1` and the outcomes
    are `NONE` / `1` / `2`, confirming it's the next/first-goal market)
  - Specifier shape: `special_bet_value="goalnr=1"`
  - Outcomes: `display`=`NONE` / `1` / `2`; `odd_key`=`none`/`home`/`away`
    or competitor names
- `home_over_under_ft`: betika_id = `19`
  - Market name: `<HOME_TEAM> TOTAL` (e.g. `WOLFSBURG TOTAL`)
  - Specifier: `special_bet_value=total=N.5`
  - Outcomes: `display`=`OVER N.5` / `UNDER N.5`
- `away_over_under_ft`: betika_id = `20`
  - Market name: `<AWAY_TEAM> TOTAL` (e.g. `PADERBORN TOTAL`)
  - Specifier: `special_bet_value=total=N.5`
  - Outcomes: `display`=`OVER N.5` / `UNDER N.5`

## Betway
- `next_goal_ft`: betway_id = `1st Goal`
  - Market name on Betway: `1st Goal` (displayName: `First Team To Score`)
  - Specifier shape: encoded in the `marketId` — e.g.
    `709267008goalnr=1~` — so the marketId carries `goalnr=1`. The
    `marketTypeCName` is also `1st Goal`.
  - Outcome names: home team name / `None` / away team name (observed
    pattern in `outcomes` for `1st Goal` markets).
- `home_over_under_ft`: betway_id = `<Home Team> Total`
  - Market name shape: literal home-team name + " Total" (e.g.
    `Negelle Arsi Total`). NOT the `[Home Team]` bracket-placeholder
    pattern — Betway uses the verbatim team string in the market name.
  - Specifier: encoded in marketId — `<eventId>19total=N.5~`
  - Outcomes: `Over` / `Under` (displayName includes the line, e.g.
    `Negelle Arsi Total (1.5)`).
  - Notes: There IS a `[Total Goals]` placeholder-style market on
    Betway, but that's the *global* total-goals market (the bracket
    text is literal — it's NOT a per-team market). The bracket /
    placeholder pattern in the original spec
    (`[Home Team] Total Goals`) does NOT match what Betway exposes;
    the parser should match on `f"{home_team} Total"` instead.
- `away_over_under_ft`: betway_id = `<Away Team> Total`
  - Same pattern as home: literal away-team name + " Total"
    (e.g. `Shire Endaselassie FC Total`). marketId shape:
    `<eventId>20total=N.5~`.

## Concerns / follow-ups for downstream tasks

1. **Probe script bugs** (do NOT block this task; flagged for future
   cleanup): wrong method names for Bet9ja (`get_live_event_markets` →
   `get_live_event_detail`), Betika (`get_events` → `get_matches`),
   wrong arg for SportPesa (`get_navigation(sport_id=...)` →
   `get_navigation()`), wrong id prefix for Betway (`sr:match:N` →
   `N`), wrong source for Betway sportEvent (it's on `get_event_detail`
   not `get_event_markets`).

2. **Bet9ja per-team O/U found — earlier probe was wrong.** The Wolfsburg
   v Paderborn re-probe (2026-05-21) found `S_HAOU` is the combined Home
   + Away O/U market with team-distinguishing outcome suffixes
   (`_OH`/`_UH`/`_OA`/`_UA`). The first probe (Qatar v Sudan)
   mis-classified this as "combined, not per-team". Both
   `home_over_under_ft` and `away_over_under_ft` now share
   `bet9ja_key="S_HAOU"` with team-suffixed OutcomeMapping.bet9ja values.

3. **Betway placeholder spec mismatch** — the design doc / plan
   assumes a `[Home Team] Total Goals` placeholder pattern. Observed
   reality is `<Verbatim Home Team> Total` (no "Goals", no brackets).
   The `_TeamScopedBetwayRegistry` (Task 4) needs to substitute the
   actual `homeTeam` / `awayTeam` from `sportEvent` into the candidate
   market-name match, and accept the trailing `" Total"` (no "Goals").

4. **MSport Next Goal only appears on live events** — the prematch
   fixture for Qatar v Sudan (SR 71549302) did not include market id=8.
   The 68746506 live probe captured the shape. Downstream tests should
   use a live-style MSport fixture for `next_goal_ft`.

5. **Betika market labels include the team name in upper case**
   (`WOLFSBURG TOTAL`). The parser will identify the market via
   `sub_type_id` (19 / 20), so the variable team-name suffix is fine —
   but any name-based parsing must lowercase + strip the team prefix.
