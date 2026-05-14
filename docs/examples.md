# Example scripts

The `examples/` directory has runnable scripts that demonstrate the lib end-to-end. Each is async, self-contained, and uses only the public API.

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
