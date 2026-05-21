# RESOLVED — 2way_handicap_ft (Asian Handicap, 2-way home/away, signed lines)

**Probed:** 2026-05-22. All four bookmakers below were probed against a
single high-profile soccer fixture:

| Bookmaker | SR id    | Match                         | State    |
|-----------|----------|-------------------------------|----------|
| SportyBet | 71583282 | CF Cruz Azul vs Pumas UNAM    | prematch |
| MSport    | 71583282 | CF Cruz Azul vs Pumas UNAM    | prematch |
| Betway    | 71583282 | CF Cruz Azul vs Pumas UNAM    | prematch |
| Betika    | 71583282 | CF Cruz Azul vs Pumas UNAM    | prematch |

BetPawa (id=3774) and Bet9ja (S_AH) are locked-in by spec; SportPesa
stays None (Akamai cookie unavailable, not probed).

The first attempt used CA Penarol vs SC Corinthians (SR 70075782) but
that match did not expose Betway's FT 2-way variant, so the canonical
fixtures were re-captured against Cruz Azul vs Pumas UNAM. The four
fixtures under `tests/fixtures/event_info/<bookmaker>/2way_handicap_ft.json`
are all from the Cruz Azul event for cross-bookmaker consistency.

## SportyBet
- `2way_handicap_ft`: sportybet_id = `"16"`
  - Market name (header): `Handicap`
  - Per-line description (`desc`): `Asian Handicap`, `Asian Handicap -0.5`,
    `Asian Handicap -1.5`, `Asian Handicap -1`, `Asian Handicap 0`,
    `Asian Handicap 0.5`, `Asian Handicap -2`, `Asian Handicap -2.5`,
    `Asian Handicap 1`, `Asian Handicap 1.5`, etc.
  - Specifier (`specifier`): `hcp=-1.5` / `hcp=-0.5` / `hcp=0` /
    `hcp=0.5` / `hcp=-1` / `hcp=1` / `hcp=-2.5` etc. (signed numeric;
    integer lines come WITHOUT a decimal, e.g. `hcp=0` and `hcp=-1`,
    while half-lines do carry it: `hcp=-0.5`).
  - Outcomes (`outcomes[].desc`): `Home (-1.5)` / `Away (+1.5)`,
    `Home (+0.5)` / `Away (-0.5)`, `Home (0)` / `Away (0)`, etc. —
    pattern is `Home (<signed_line>)` / `Away (<signed_line>)` where
    the away line is always the negation of the home line. Note that
    integer lines render as `Home (0)` (no decimal) or `Home (-1.0)`
    (one decimal — present even though the spec says `hcp=-1`); the
    parser must accept both `0` and `0.0`/`-1.0` forms.
  - Outcome ids inside the market: home id observed `1714`, away id
    `1715` for one line; ids differ per line. The parser should not
    key on outcome id — use position or `desc` string matching.
  - Disambiguation needed: SportyBet also exposes id=`14` (3-way
    European Handicap, `desc` "Handicap X:Y" with `hcp=0:1`-style
    specifiers), id=`66` (1st Half Asian Handicap), id=`88` (2nd Half
    Asian Handicap), id=`165` (Corner Handicap), id=`900312` (Bookings
    Handicap). The parser MUST gate on id=`"16"` AND restrict to FT
    (no half/period prefix in `desc`).

## MSport
- `2way_handicap_ft`: msport_id = `16`
  - Market name: `Handicap`
  - Description field (`description`): `Asian Handicap` (literal — no
    line in the description, the line is in `specifiers`).
  - Specifier (`specifiers`): `hcp=-1.5` / `hcp=-0.5` / `hcp=0.5` /
    `hcp=1.5` / `hcp=-2.5` etc. Same shape as SportyBet (signed,
    integer lines omit the decimal).
  - Outcomes (`outcomes[].description`): `Home (-1.5)` / `Away (+1.5)`,
    `Home (-0.5)` / `Away (+0.5)`, etc. Same `Home (<signed>)` /
    `Away (<signed>)` pattern as SportyBet. Outcome ids `1714` / `1715`.
  - Disambiguation: MSport also exposes id=`14` (3-way European, "Handicap
    X:Y"), `66` (1st Half AH), `88` (2nd Half AH). Gate on id=`16` AND
    full-period (no `1st half` / `2nd half` prefix on `name` or `description`).

## Betway
- `2way_handicap_ft`: betway_id = `[Handicap] [2-Way]`
  - Market name (anchor / header): literal string `[Handicap] [2-Way]`
    — the square brackets are part of the name, NOT placeholders. The
    anchor row carries `handicap=0` and `marketId=<eventId>16` (e.g.
    `7158328216`). The per-line children share the *same* marketId
    prefix `<eventId>16` and append `hcp=<signed_line>~`:
    - `Handicap` (with name=`Handicap`, NOT `[Handicap] [2-Way]`),
      `handicap=-0.5`, marketId=`7158328216hcp=-0.5~`
    - `Handicap`, `handicap=-1.5`, marketId=`7158328216hcp=-1.5~`
    - `Handicap`, `handicap=0.5`, marketId=`7158328216hcp=0.5~`
  - Parser strategy: match the anchor by `name == "[Handicap] [2-Way]"`
    AND read the per-line rows whose `marketId.startswith("<eventId>16")`
    AND whose `name == "Handicap"`. Use the `handicap` field as the
    signed line (it is a number, e.g. `-0.5`, `-1.5`, `0.5`).
  - Outcomes are referenced via the global `outcomes[]` / `prices[]`
    arrays joined by `outcomeId`. The home/away discrimination is by
    `outcomes[].name` (verbatim team names — `Cruz Azul` and `Pumas UNAM`
    — NOT `Home`/`Away`).
  - Disambiguation: Betway also exposes the 3-way `[Handicap] [3-Way]`
    anchor (marketId `<eventId>14`) and per-half variants
    `1st Half - Handicap` (`<eventId>66`), `2nd Half - Handicap`
    (`<eventId>88`), `2nd Half - Handicap - 2 Way 0.5` (`<eventId>88`,
    a one-line-only 0.5 anchor). The FT 2-way is **only** the
    `[Handicap] [2-Way]` anchor.
  - **Important availability note:** the `[Handicap] [2-Way]` market
    is NOT exposed on every event. Of five SR ids sampled
    (70075222, 70075782, 70075752, 71583282, 70075296), three exposed
    it (70075222, 71583282, 70075296) and two did NOT (70075782,
    70075752). When absent, the parser should emit no rows — not an
    error. The 2nd-half variant `2nd Half - Handicap - 2 Way 0.5` is
    a separate market and is NOT the canonical FT one.

## Betika
- `2way_handicap_ft`: betika_id = **None — NOT EXPOSED**
  - Probed sub_type_ids 1-200 against the target match (Cruz Azul) and
    against multiple other competitions. The only handicap groups
    Betika exposes are:
    - `sub_type_id=14`: `HANDICAP  (1X2)` — 3-way European handicap,
      outcomes shaped `1 (0:1)` / `X (0:1)` / `2 (0:1)`, `sbv=hcp=X:Y`
      (NOT the 2-way Asian variant).
    - `sub_type_id=65`: `1ST HALF - HANDICAP (1X2)` — 1st-half 3-way
      European handicap.
  - No `sub_type_id=16` group exists on the Betika feed (the call returns
    an empty `odds` array for every match probed). Betika simply does not
    list a 2-way Asian Handicap market in its catalogue.
  - Decision: leave `betika_id = None` in `BUILTIN_MAPPINGS`. The
    fixture `tests/fixtures/event_info/betika/2way_handicap_ft.json`
    captures the 54 distinct market groups exposed for Cruz Azul, with
    the two 3-way handicap groups included so the absence of a 2-way
    market is verifiable (the parser test for Betika `2way_handicap_ft`
    should assert that the parser produces zero outcomes against this
    fixture — there is nothing to parse).

## Concerns / follow-ups for downstream tasks

1. **Betika API quirk: `match_id` parameter is fragile with `limit=1`.**
   The probe (and the upstream `Betika.get_event_markets` /
   `Betika.get_event_detail`) call `/v1/uo/matches?match_id=X&limit=1`.
   When `competition_id` is also supplied, Betika sometimes returns a
   different match (the API's filter precedence is unclear — limit=1
   appears to win over match_id). Two cases observed:
   - `match_id=10770637, competition_id=49230, limit=1` → returned
     U. Catolica (match_id=10770619), not Penarol/Corinthians.
   - `match_id=10770637, competition_id=49230, limit=100` →
     returned both (Penarol/Corinthians IS in the list, position 2).
   - `match_id=10947835, competition_id=43044, sub_type_id=16, limit=1`
     → returned 0 odds groups.

   Workaround used here: query with `limit=100` and filter client-side
   by `m["match_id"] == target_id`. **This is a real bug in
   `Betika.get_event_markets`** which uses `limit=1` — downstream
   Task 9 (Betika fixture test) will be affected, and the helper itself
   should be patched. Logged as a concern; not fixed in this task.

2. **Betway 2-way AH is event-conditional.** Per the availability note
   above, ~40% of sampled events did NOT expose `[Handicap] [2-Way]`.
   Tests should not assume the market is always present; the parser
   must return an empty list (not raise) when the anchor row is absent.

3. **Betway anchor row marketId convention.** The anchor row
   `[Handicap] [2-Way]` has marketId `<eventId>16` (no `hcp=…~`
   suffix), but its rendered `handicap=0` is meaningless — it's a
   header, not a real line. The actual lines are children with
   marketId `<eventId>16hcp=<signed>~`. The parser must skip the
   anchor and only emit rows from the children.

4. **Outcome line formatting inconsistency on SportyBet / MSport.**
   Half-lines render `Home (-0.5)` (one decimal in description and a
   matching `hcp=-0.5` specifier), but integer-line variants render
   `Home (0)` (no decimal) and `Home (-1.0)` / `Home (+1.0)` (one
   decimal) — mixed conventions on the same market. The parser line
   extraction must accept both forms (`0`, `0.0`, `-1`, `-1.0`).

5. **No SportPesa probe.** SportPesa stays `None` for
   `2way_handicap_ft` per the spec (Akamai cookie unavailable).
