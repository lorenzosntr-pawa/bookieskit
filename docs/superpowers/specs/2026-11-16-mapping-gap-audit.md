# bookieskit mapping/parsing audit — phase 2 (2026-11-16, branch chore/strip-to-core, offline, fixtures only)

Scripts: this folder (matrix.py, coverage.py, ...). All numbers below come from those scripts.

## 0. Canonical catalogue (matrix.py)
22 canonical markets total: 13 soccer, 3 basketball, 4 tennis (+ next_goal/home/away O/U/2way hcp soccer).
Mapped competitors per canonical (of 7):
- 7/7: 1x2_ft, over_under_ft, btts_ft, double_chance_ft, moneyline_basketball_ft, over_under_basketball_ft, moneyline_tennis_match, over_under_games_tennis_match
- 6: handicap_games_tennis_match, home_over_under_ft, away_over_under_ft
- 5: 1x2_corners_ft, over_under_corners_ft, over_under_bookings_ft, 2way_handicap_basketball_ft, next_goal_ft
- 4: 1x2_1up_ft, 1x2_2up_ft (no betpawa_id!), 1x2_bookings_ft, 2way_handicap_ft (soccer: sportybet/bet9ja/betway/msport only)
- 3: over_under_sets_tennis_match; 2: double_chance_1up_ft
No first-half/second-half market, no correct score, no HT/FT, no draw-no-bet, no odd/even, no European handicap, no player props, no basketball quarters/halves, no tennis set betting/set winner.

## 1. Coverage per book x sport (coverage.py -> coverage_out.txt, rank_out.txt)
Method: every market-bearing fixture under tests/fixtures/event_info (41 fixtures; skipped event lists: betway live/prematch,
sportpesa listings, elephantbet events/live). "raw types" = distinct market ids (Betway: market name; Bet9ja: key prefix).
"registered" = registry has a same-sport mapping for that id. Outcomes = raw selections vs outcomes parse_markets(sport=...) returns.

| book | sport | fx | raw types | registered | %types | raw outcomes | parsed | %outc |
|---|---|---|---|---|---|---|---|---|
| betpawa | soccer | 4 | 297 | 41 | 14% | 1968 | 202 | 10% |
| betpawa | basketball | 1 | 10 | 3 | 30% | 43 | 14 | 33% |
| betpawa | tennis | 1 | 11 | 4 | 36% | 52 | 24 | 46% |
| sportybet | soccer | 3 | 770 | 39 | 5% | 10154 | 260 | 3% |
| msport | soccer | 4 | 547 | 47 | 9% | 7019 | 267 | 4% |
| bet9ja | soccer | 4 | 598 | 37 | 6% | 3183 | 225 | 7% |
| betway | soccer | 3 | 429 | 38 | 9% | 3008 | 169 | 6% |
| elephantbet | soccer | 1 | 153 | 9 | 6% | 689 | 53 | 8% |
| sportpesa | soccer | 1 | 22 | 4 | 18% | 196 | 50 | 26% |
| betika | soccer | 5 | 64 | 17 | 27% | 287 | 75 | 26% |
(full table incl. basketball/tennis in rank_out.txt). Betika/SportPesa fixtures are thin (Betika: 4 of 5 soccer fixtures hold 1-4 markets) — their % is not representative.

### Cross-book families (families.py = hand-curated id table, verified against raw_names.tsv)
47 families that BetPawa offers in the fixtures are UNMAPPED on BetPawa; all 47 are offered by >=2 competitors, 31 by >=5, 12 by all 7:
- 7/7 comps: 1X2 1H, O/U 1H, BTTS 1H, Correct score FT, Correct score 1H, HT/FT, DNB FT, Odd/Even FT, 3-way (European) hcp FT, Highest scoring half, 1X2&O/U, 1X2&BTTS
- 6: Odd/Even 1H, DC 1H, Exact goals FT, Home clean sheet, Home win to nil
- 5: 1X2 2H, O/U 2H, BTTS 2H, DC 2H, CS 2H, OE 2H, 3-way hcp 1H/2H, DNB 1H, DC&O/U, DC&BTTS, Winning margin, Corners O/U 1H, basketball Odd/Even
- 4: DNB 2H, tennis set winner, set-1 total games, set-1 game hcp, player games O/U, basketball Winner&Total, 4Q handicap
- 3: 1X2 2Up (BetPawa id 28000850 offered in 2 BetPawa fixtures, mapping has betpawa_id=None while bet9ja/betway/sportybet/msport are mapped), Multigoals, Corner hcp, Asian hcp 1H, Anytime goalscorer, 4Q total/1X2
Period markets: 19 of the 47 are 1H/2H variants of markets already mapped at FT (no period dimension exists in the catalogue).

### Mapped-but-dark cells (book offers the family, canonical exists, book yields nothing)
- Betway over_under_ft: offered in 3/3 soccer fixtures, parsed in 1/3 (BUG, see 3.1).
- SportPesa: Asian hcp FT (id 51), Home/Away team O/U (353/352) present in markets.json, unmapped for soccer (51/352/353 are only registered for basketball/tennis).
- ElephantBet: Asian hcp soccer (23 "Handicap Asiatico"), basketball (23), tennis game hcp (23 "Games - Handicap Europeu"), Bookings 1X2 (85 "Cards Matchbet"), next goal (5).
- Betika: soccer Asian hcp not mapped (betika_id None) — fixture 2way_handicap_ft.json has none, so unconfirmed.

## 2. Same-event check (crossbook.py, wc_nf = Norway - France on 5 books)
- over_under_ft: betpawa/sportybet/bet9ja/msport aligned; **Betway MISSING**.
- 2way_handicap_ft: betpawa {-0.5: 4.54/1.22, 0.5: 2.33/1.64}; sportybet/bet9ja/msport agree (home-perspective sign is consistent);
  **Betway {0.5: 2.20/1.60, 1.5: 1.77/1.94, 2.5: 1.49/2.45} = Corner Handicap prices** (raw goal AH 0.5 = 2.25/1.61), and the -0.5 line is lost.
- home/away team O/U, next goal, 1X2, corners O/U: aligned across books (Bet9ja only orders outcomes differently).
- builtin_mappings.py:239 `1x2_2up_ft` betpawa_id=None although BetPawa ships "1X2 2UP - FT" id 28000850 (fixtures: 2 BetPawa files).
- builtin_mappings.py:1082 soccer AH sportpesa_id=None "NOT PROBED — cookie unavailable", yet tests/fixtures/event_info/sportpesa/markets.json already contains id 51 "Asian Handicap - Full Time" (offline-minable).

## 3. Correctness risks (evidence from fixtures)
3.1 **Betway marketId-prefix attribution collides on un-delimited SR type ids** — parser.py:766-773 attributes any row whose marketId
    startswith a parameterized parent's marketId; parser.py:916-923 then lets the LAST handicap==0 entry overwrite parent_outcomes; parser.py:1005 returns None.
    - "1st Goal & 1X2" (eventId+"184...") and "1st Half - Odd/Even Corners" (eventId+"183") are folded into O/U FT (eventId+"18") -> over_under_ft dropped in betway/wc_nf.json and betway/2way_handicap_ft.json.
    - "Corner Handicap" (eventId+"165"), "1st Corner", "Last Corner", "1X2 (3Up)" (eventId+"1601xup"), "<team> Total Corners" folded into 2way_handicap_ft (eventId+"16") -> wc_nf emits corner-handicap odds as goal AH and loses -0.5.
    Silent wrong prices, not just gaps. Any SR id that is a string-prefix of another (1/10/16/18/19/20...) is exposed.
3.2 **Clients never pass sport=** — base.py:254, betika.py:301, betway.py:340, sportpesa.py:136 call parse_markets without sport. nosport.py: 7 of 9 non-soccer fixtures change:
    sportpesa/tennis -> moneyline_basketball_ft + 2way_handicap_basketball_ft (wrong sport labels); sportybet & msport basketball -> extra soccer 1x2_ft/over_under_ft (SR id 1/18 = regular-time markets labelled as soccer FT);
    elephantbet/tennis loses moneyline_tennis_match (labelled basketball); elephantbet/basketball gains soccer home/away O/U. Root: flat first-wins index registry.py:51-62 and Betway fallback parser.py:783 iterating all-sport list_markets().
3.3 **Suspended / placeholder prices emitted as real odds** (no suspended flag on Outcome, types.py:6-27):
    BetPawa `suspended: True, price: 0.0` -> 13 parsed outcomes at 0.0 in betpawa/live.json (parser.py:215, 275 ignore `suspended`);
    Bet9ja literal "1" -> 30 parsed outcomes at 1.0 (parser.py:522; e.g. wc_nf S_OU@0.5_O=1 vs U=16);
    Betway missing price -> 3 outcomes at 0.0 via price_map.get(oid, 0) (parser.py:847, 946, 967).
3.4 Bet9ja lines with one side only (5 lines, e.g. wc_nf over_under_ft 8.5 ['over']) pass through as half-markets.
3.5 Latent: SportyBet prefix fallback parser.py:472-474 has no empty-label guard (MSport has it, parser.py:1172) — an empty sportybet label would match every outcome; 0 such labels today.
    `_extract_line_from_specifier` (parser.py:448-456) only knows total/hcp/goalnr: any multi-key specifier (setnr, quarternr, hcp=0:1, variant=) cannot be mapped without parser changes.
    Bet9ja live keys: only LIVES_ is normalised (parser.py:508-515); other live sport prefixes silently dropped (no fixture to confirm).
    Betway 1X2-type outcomes rely on positional sentinels (26 outcome cells use __HOME__/__POS_n__) — reorder = wrong side, no check.
Non-issues checked: handicap sign is home-perspective and consistent across betpawa/sportybet/bet9ja/msport on wc_nf; no non-exact label match other than "<label> <line>" (sanity2.py: 0 suspicious fuzzy matches).

## 4. Structure
- builtin_mappings.py 1109 lines for 22 canonicals (50 lines each); 416 outcome-label cells, 80 empty. A canonical = one MarketMapping with 8 id fields + per-outcome 8 label strings.
- parser.py 1581 lines, 37 functions; per book: betway 357, bet9ja 190, betika 154, betpawa 132, sportybet 126, sportpesa 124, msport 121, elephantbet 99. Each book re-implements simple/parameterized/resolve (sportybet vs msport differ only in field names desc/description, specifier/specifiers).
- Add a market with existing shape: 1 place (a MarketMapping block). Add a market needing a new shape (period-specific specifiers, combo outcomes "1 - Over", correct score 26 outcomes, player props, multi-key specifiers): touch the mapping + up to 8 parsers' line/outcome logic.
- Add a book: types.py (2 dataclass fields), registry.py (index dict, _register x2, add() signature+body, get_by_platform_id dict — 16 per-book references across registry/types), parser.py (new parser + dispatch), and every mapping block.
- Canonical model has no period / team / participant / line-kind dimensions: "1x2_ft", "moneyline_basketball_ft", "over_under_games_tennis_match" are flat strings, so 1H/2H/quarters/sets each need a full copy of the FT mapping.
- No fixture-driven regression test of the kind used here (raw vs parsed coverage; same-event cross-book check) — that is how 3.1 went unnoticed.
