# Mapping & parser v2 — design

Date: 2026-11-16 · Owner: Lorenzo · Status: approved 2026-11-16
Evidence: [`2026-11-16-mapping-gap-audit.md`](2026-11-16-mapping-gap-audit.md) (offline audit of the 41 market fixtures).

## Intent

bookieskit exists to put BetPawa and its competitors side by side, market by
market. Today it can only do that for 22 canonical markets (14% of BetPawa's
soccer market types), some of its output is silently wrong, and adding a market
costs ~50 hand-written lines (one more full copy per period). Phase 2 makes the
mapping/parsing layer **correct first, then broad, then cheap to extend**.

## Goals

1. **Correct**: no silently wrong prices. Fix the three audited bugs:
   - Betway marketId prefix attribution (`parser.py:766-773`, `916-923`):
     `<eid>184` ("1st Goal & 1X2") is attributed to `<eid>18` (O/U) → O/U FT
     vanishes and the 2-way goal handicap returns Corner Handicap prices.
   - `sport` is never passed by the clients' convenience path (`base.py:254`
     and the per-book overrides) → basketball/tennis parse as soccer.
   - Suspended / placeholder prices (BetPawa 0.0, Bet9ja literal "1", Betway
     missing price → 0.0) come out as real odds.
2. **Broad**: map the families BetPawa offers that ≥ 4 competitors also offer,
   in this order: 1H/2H variants of mapped markets → DNB, Odd/Even, Correct
   Score, HT/FT, 3-way handicap, Exact goals, Highest scoring half → combos
   (1X2&O/U, 1X2&BTTS, DC&O/U, DC&BTTS) → basketball & tennis (set winner,
   set-1 totals/handicap, player games O/U, quarter/half markets).
3. **Cheap to extend**: a new market with an existing shape = one small data
   entry per book; a 1H/2H variant = no copy of the FT block; a new book = one
   new adapter + one mapping table, no edits to other books.
4. **Measured**: a coverage report (per book × sport: raw types, mapped types,
   % of BetPawa families covered by each competitor) regenerated from fixtures,
   so every step shows its gain.

## Non-goals

- New bookmakers, new sports, live-odds infra, pricing/de-vig logic beyond what
  `feat/book-compare-support` already carries.
- Rebuilding the deleted orchestration/devtools tooling.

## Anti-goals (failure even if it "works")

- Any change in output for the 22 existing markets that is not an intended bug
  fix → breaks `comparison`, `in-house_sim`, `BOTS/PM_ODDS_BOT`.
- Breaking the public API: `parse_markets(...)` signature, `NormalizedMarket` /
  `Outcome` fields (additive only), existing `canonical_id` strings,
  `MarketRegistry` public methods, client classes.
- A "generic" parser that is harder to read than today's per-book code.

## Constraints

- Offline tests only in CI; fixtures are committed in the same change that uses
  them. Live captures need an in-region network; use prematch, not live.
- Python 3.11–3.13, ruff-clean, TDD.
- Consumers pin by git; a breaking change needs a minor-version bump and a
  CHANGELOG note.

## Approaches (decided)

| | Approach | Trade-off |
|---|---|---|
| A | Fix bugs, then add markets on the current structure | Fast first wins; mapping file grows ~1.1k → 4k+ lines; new books stay expensive |
| B | Redesign first (structured canonical key, per-book tables, shared parser) | Cheap breadth later; nothing visible for a while; big-bang risk for consumers |
| **C ✔** | **Bug fixes now → golden snapshot safety net → incremental migration proven by the snapshot → breadth on the new model** | Bugs fixed immediately, zero consumer breakage, breadth gets cheap |

Lorenzo picked **C** (2026-11-16).

## Design

### Step 0 — fixtures & measurement (small)
- `scripts/capture_fixtures.py`: given a SportRadar id (or BetPawa event id) and
  sport, fetch each book's prematch event detail with the existing clients and
  write `tests/fixtures/event_info/<book>/<name>.json`. Stdlib + bookieskit only,
  no CLI framework. Replaces the deleted `devtools capture`.
- `scripts/coverage_report.py`: offline, from fixtures → `docs/coverage.md`
  (seeded from the audit's `coverage.py`).
- One fresh in-region capture round: ≥ 3 soccer, 2 basketball, 2 tennis events
  across all 8 books (fills the Betika/SportPesa gap the audit flagged).
  Run from Lorenzo's machine (in-region); the SportPesa client loads its own
  cookie — the builder never opens the cookie file. *(Builder's call:)* the
  capture runs in parallel with Steps 1–3, which use the existing 41 fixtures;
  new fixtures join the golden snapshot as they land, each diff reviewed in its PR.
  If a book cannot be captured, its Step 4 acceptance is scoped to the fixtures
  that exist and the gap is listed in the PR.

### Step 1 — correctness fixes (small, ships alone)
- Merge `feat/book-compare-support` (BetPawa 1X2 2UP mapping, `base_url`
  override, de-vig helpers) after a rebase on `main`.
- Betway: attribute a child marketId to a parent only when the remainder after
  the parent id starts a specifier (e.g. `hcp=`, `total=`), never a digit.
  Regression test on `wc_nf` (O/U FT present; goal handicap 0.5 = 2.25/1.61).
- `sport`: the convenience methods take `sport: str | None = None` and pass it
  through; where a payload carries its sport, derive it. Test: SportPesa tennis
  fixture → tennis canonicals, not `moneyline_basketball_ft`.
- Suspended prices (odds ≤ 1.0 or missing): if **any** outcome of a line is
  suspended, the **whole line** is dropped; if any outcome of a simple market is
  suspended, the **whole market** is dropped; a parameterized market with no
  lines left is dropped. Every market returned is complete, so margin/de-vig on
  it is always valid. *(Lorenzo, 2026-11-16: option A — chosen over keeping
  partial outcomes or adding a `suspended` flag.)*

### Step 2 — golden snapshot
- `tests/golden/`: for every market fixture, the JSON of
  `parse_markets(fixture, platform, sport=<correct sport>, probability="with_void")`.
- Test compares live output to the snapshot; a regen script updates it, and any
  diff is reviewed in the PR. Taken **after** Step 1, so it encodes the fixed
  behaviour.

### Step 3 — the new model (incremental, snapshot must stay identical)
- **Structured canonical key**: `MarketKey(type, period, scope, sport)` —
  e.g. `type="over_under"`, `period="1h"`, `scope="match"|"home"|"away"|"corners"|"bookings"`.
  `canonical_id` stays a string derived from the key (`over_under_ft` etc.);
  irregular legacy ids (`moneyline_basketball_ft`, `over_under_games_tennis_match`)
  keep an explicit alias so they never change.
  *(Builder's call)* **Naming rule for new ids**, following the existing
  pattern: soccer = `<type>[_<scope>]_<period>` (`over_under_1h`,
  `over_under_corners_2h`); other sports = `<type>[_<scope>]_<sport>_<period>`
  (`over_under_basketball_1h`, `handicap_games_tennis_set1`). The key fields are
  also exposed on `NormalizedMarket` (additive: `market_type`, `period`,
  `scope`, `sport`) so consumers never parse id strings.
- *(Builder's call)* **Lines stay `float`.** Period (`1h`, `q1`, `set1`) and
  scope (`home`, `corners`, player) live in the key, not the line, so almost
  every remaining line is one number. 3-way handicap `hcp=0:1` maps to the
  home-perspective float (`0:1` → `-1.0`, `1:0` → `+1.0`), the same sign
  convention the audit confirmed for 2-way handicaps across books. Combos with a
  total (1X2&O/U 2.5) key on the total. Correct score / HT/FT have no line.
- **Per-book mapping tables** in `markets/books/<book>.py`: canonical key → book
  market id (or id per period) + outcome labels. Each book declares its **default
  outcome vocabulary** once (e.g. SportyBet `Home/Draw/Away`, `Over/Under`,
  `Yes/No`), so most entries carry no hand-written labels.
- **Book adapters**: each book converts its raw payload to one intermediate
  shape `RawMarket(market_id, specifiers: dict[str, str], outcomes: [RawOutcome(label, odds, true_prob, void_prob)])`.
  SportyBet and MSport share one adapter (field names differ only). Line
  extraction is generic over specifiers (`total`, `hcp`, `setnr`, `goalnr`,
  multi-key `hcp=0:1`).
- **One resolver**: `RawMarket` + book table → `NormalizedMarket`. Per-book quirks
  (Betway name-based ids, team placeholders) live in the adapter, not the resolver.
- `MarketMapping` / `OutcomeMapping` / `MarketRegistry.register(...)` keep working
  as a compatibility layer that builds the new tables.
- Migration order: SportyBet+MSport → BetPawa → Bet9ja → SportPesa → Betika →
  ElephantBet → Betway (hardest last). Each book is one PR; the snapshot is the gate.

### Step 4 — breadth (on the new model)
In the order listed under Goals. Acceptance per market: mapped on BetPawa and on
every competitor whose fixtures carry it, verified against a fixture test, and
visible in the coverage report. Combo outcome names follow
`<part1>&<part2>` (e.g. `home&over`). Correct-score outcomes are `"h:a"`
strings; HT/FT outcomes are `"<ht>/<ft>"` using `home/draw/away`.

## Delivery

One PR per step (Step 3 one per book), each with CHANGELOG entry, green CI, and
a reviewer pass (`python-reviewer` + `bp-reviewer`). Version bump at the end of
Step 1 (patch) and at the end of Step 3 (minor, if any API is added).

## Left to the builder

- Internal names of the new modules/classes.
- How derived sport is detected per payload.
- Exact layout of the coverage report.
