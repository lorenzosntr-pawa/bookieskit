# Example scripts

The `examples/` directory has runnable scripts that demonstrate the lib end-to-end. Each is async, self-contained, and uses only the public API.

The newer multi-sport scripts (`compare_betpawa_competition_full.py`, `find_betgenius_matches.py`) are the recommended starting points for new code — they exercise every public surface the lib has, including the sport-aware registry lookups and the BetGenius id extraction. The original four scripts are soccer-focused and predate the multi-sport mappings.

## `compare_betpawa_competition_full.py`

Walks any BetPawa competition (soccer, basketball, or tennis) and prints a per-event coverage table showing which canonical markets each of the 7 bookmakers exposes for that event. The country variant used per bookmaker is chosen so the competition naturally lives on each platform — `ng` for Bet9ja/SportyBet/MSport/Betway, `ke` for Betika/SportPesa.

```bash
# Soccer (BetPawa NG comp id, sport_id=2 default)
python examples/compare_betpawa_competition_full.py 12546

# Basketball (NBA Conference Finals, sport_id=3)
python examples/compare_betpawa_competition_full.py 11971 3

# Tennis (French Open Men's Singles, sport_id=452)
python examples/compare_betpawa_competition_full.py 16133 452
```

Requires `SPORTPESA_COOKIE` env var (or `sportpesa_cookie.txt` in repo root) for the SportPesa column. Without it, SportPesa shows empty.

Per-bookmaker lookup strategy:

| Bookmaker | Strategy |
|---|---|
| SportyBet, MSport | SR-id direct lookup (`sr:match:<id>`) |
| Betway | SR-id direct (Betway's eventId IS the bare SR numeric) |
| Bet9ja | One-shot SR-id → internal-id map via `build_prematch_event_map(sport_id=...)` |
| Betika | One-shot SR-id → match_id map by paging `get_matches(sport_id=...)`; then a sport-aware market aggregator (calls the right basketball/tennis `sub_type_id`s) |
| SportPesa | One-shot SR-id → game_id map via `get_navigation` + per-league `get_events`; markets parsed with `parse_markets(..., sport="basketball")` / `sport="tennis"` to disambiguate SportPesa's sport-scoped market ids |

Sample output for a French Open match:

```
[1/52]
  Houkes, Max vs Cecchinato, Marco  (sr_id=71557966)
    BetPawa     ML=2o  OU-G=5L  OU-S=1L  HCAP-G=5L
    SportyBet   ML=2o  OU-G=7L  OU-S=1L  HCAP-G=7L
    MSport      ML=2o  OU-G=7L  OU-S=—   HCAP-G=3L
    Betway      ML=2o  OU-G=1L  OU-S=—   HCAP-G=1L
    Bet9ja      ML=2o  OU-G=3L  OU-S=1L  HCAP-G=3L
    Betika      ML=2o  OU-G=1L  OU-S=—   HCAP-G=—
    SportPesa   ML=2o  OU-G=1L  OU-S=—   HCAP-G=1L
```

Notation: `2o` = 2 outcomes (non-parameterized), `5L` = 5 lines (parameterized), `—` = market not published. Empty cells are bookmaker-side data gaps, not parser bugs — see `docs/markets.md` for the per-platform coverage matrix.

## `find_betgenius_matches.py`

Walks every BetPawa event for one sport, fetches event-detail per event, extracts the `GENIUSSPORTS` widget id, and looks each one up on SportyBet to confirm SportyBet also routes via BetGenius for that event. Useful for cross-bookmaker matching when SR ids differ but the BetGenius id is the same.

```bash
python examples/find_betgenius_matches.py            # soccer (sport_id=2 default)
python examples/find_betgenius_matches.py 3          # basketball
```

Logs per-event failures to stderr so silent network errors don't masquerade as "no Genius widget found". See `docs/matching.md` for the two-provider matching model.

## `count_5bookies.py`

Total counts (sports, prematch tournaments, live tournaments, prematch events, live events) per bookmaker (note: name is historical — the script now spans all 7 bookmakers). Hits one or two API calls per bookmaker — useful as a smoke test that everything is wired and reachable.

```bash
python examples/count_5bookies.py
```

## `odds_for_sr_id.py`

Given a SportRadar event id, fetch normalized odds for the mapped markets across all 7 bookmakers. Defaults to live; pass `--prematch` for upcoming events.

```bash
python examples/odds_for_sr_id.py 69339436
python examples/odds_for_sr_id.py 69339436 --prematch
```

Resolution per bookmaker:
- SportyBet, MSport, Betway: direct lookup by SR id.
- Bet9ja: live → `find_event_id_by_sr_id`. Prematch → not implemented in this script (use `odds_for_betpawa_competition.py` if your scope is one BetPawa competition).
- BetPawa, SportPesa, Betika: skipped (no SR-id reverse search).

## `odds_from_betpawa_id.py`

Same as above, but seeded with a BetPawa internal id. The script:
1. Hits BetPawa's event detail.
2. Extracts the SR id from the SPORTRADAR widget.
3. Dispatches the other 6 bookmakers in parallel.
4. Writes one CSV row per (market, line, outcome) with seven bookmaker columns.

```bash
python examples/odds_from_betpawa_id.py 34716684
python examples/odds_from_betpawa_id.py 34716684 --prematch
python examples/odds_from_betpawa_id.py 34716684 --csv my_event.csv
```

The resulting CSV is a tidy, rectangular grid suitable for opening in Excel / Numbers / Sheets.

## `odds_for_betpawa_competition.py`

Walks every event in a BetPawa competition and produces a CSV with one row per (event, market, line, outcome) and seven bookmaker columns.

```bash
python examples/odds_for_betpawa_competition.py 12546
python examples/odds_for_betpawa_competition.py 12546 --live
python examples/odds_for_betpawa_competition.py 12546 --csv epl_today.csv
```

Optimisation: the script pre-builds Bet9ja's SR-id → internal-id map once at startup (`get_live_events` for live mode; `build_prematch_event_map` for prematch). Per-event lookup is then O(1).

## See also

- [README.md](../README.md) — install + quick start.
- [docs/markets.md](markets.md) — what `get_markets()` returns.
- [docs/matching.md](matching.md) — how SR-id matching works.
