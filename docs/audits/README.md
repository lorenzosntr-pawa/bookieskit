# Live Odds Audits

Reports produced by `python -m bookieskit.devtools audit` (the harness lives in
`src/bookieskit/devtools/audit.py`).

## Modes

- `audit --prematch <seeds…>` — probe the given upcoming fixtures via the
  **prematch** path (where booking/corner markets are visible for upcoming
  events).
- `audit --live` — **auto-discover** in-play events (no fixture list needed) and
  probe the **live** feed; `--max-live N` caps how many in-play events are
  audited.

Both write a dated report to `docs/audits/<date>-wc-<mode>-audit.md` plus a
machine-readable `.json` sidecar (override the path with `--out`).

## What a report contains

For each fixture, an **odds matrix** of canonical football market × bookmaker.
Each cell is one of:

- **MAPPED+PRICED** — the parser produced odds (the cell shows them).
- **NOT OFFERED** (`—`) — the registry maps this market for the book but it did
  not resolve on this fixture. This is the *legitimate-missing* case (live nature,
  or low-level leagues where corners/cards are often unavailable). Reported,
  **never** filed as an Issue.

Below the matrix, a **MIS-MAP review** section lists, per book, the raw market
groups present on the payload that the registry does **not** map. This is the
only signal worth filing an Issue over ("the book sent it but we failed to map
it"). A cycle reviews these and files one Issue per genuine mismatch.

> Betway's MIS-MAP surface is intentionally empty: `search.unmapped` over-reports
> for Betway (the registry indexes Betway by name, candidates carry numeric ids).
> Betway odds still appear in the matrix via the parser.

## Running

**In-region only.** Live bookmakers geo-block US/cloud IPs (BetPawa returns 403
out of region), so the live probe must run from an in-region environment.
SportPesa and Betika need their session cookies (`--sportpesa-cookie` /
`--betika-cookie`). The classification/report logic itself is offline and unit-
tested against captured fixtures.
