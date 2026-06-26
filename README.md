# bookieskit

Async HTTP clients for 7 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport, SportPesa, Betika) covering **soccer, basketball, and tennis**, with normalized markets and cross-bookmaker matching by SportRadar **or** BetGenius id.

## Installation

```bash
pip install git+https://github.com/<user>/bookieskit.git

# Dev (tests + lint)
pip install "bookieskit[dev] @ git+https://github.com/<user>/bookieskit.git"
```

Requires Python 3.11+.

## Quick start

### 1. Markets for one event

```python
import asyncio
from bookieskit import SportyBet
from bookieskit.markets import parse_markets

async def main():
    async with SportyBet(country="ng") as sb:
        # Soccer event — the default registry handles soccer ids automatically.
        detail = await sb.get_event_detail(event_id="sr:match:69339436")
        markets = parse_markets(detail, platform="sportybet")
        for m in markets:
            print(m.canonical_id, m.name)

        # Basketball event — pass sport="basketball" so SportPesa-style
        # cross-sport id collisions (e.g. id 52 = football O/U AND basketball
        # O/U) resolve to the right canonical. Other bookmakers ignore the
        # arg, so it's always safe to pass.
        detail = await sb.get_event_detail(event_id="sr:match:71550420")
        markets = parse_markets(detail, platform="sportybet", sport="basketball")

asyncio.run(main())
```

### 2. Compare odds across all 7 by SportRadar id (soccer)

```bash
python examples/odds_for_sr_id.py 69339436
```

### 3. Walk a BetPawa competition across all 7 bookmakers (any sport)

```bash
# Soccer (sport_id=2 is the default)
python examples/compare_betpawa_competition_full.py 12546

# Basketball (NBA, BetPawa sport_id=3)
python examples/compare_betpawa_competition_full.py 11971 3

# Tennis (French Open Men, BetPawa sport_id=452)
python examples/compare_betpawa_competition_full.py 16133 452
```

Prints a per-event coverage table showing which canonical markets each bookmaker exposes. See `examples/compare_betpawa_competition_full.py` for the lookup strategy (SR-id direct on SB/MS/Betway, pre-built SR-id maps for Bet9ja/Betika/SportPesa).

## Supported Bookmakers

| Bookmaker | Countries | Doc |
|-----------|-----------|------|
| BetPawa   | ng, gh, ke, ug, tz, zm, rw, cm, sl, bj, cg, cd, ls, mw, mz | [docs/betpawa.md](docs/betpawa.md) |
| SportyBet | ng, gh, ke, tz, za, cm, zm | [docs/sportybet.md](docs/sportybet.md) |
| Bet9ja    | ng | [docs/bet9ja.md](docs/bet9ja.md) |
| Betway    | ng, gh, ke, tz, ug, zm, za | [docs/betway.md](docs/betway.md) |
| MSport    | ng, gh, ke, ug, zm | [docs/msport.md](docs/msport.md) |
| SportPesa | ke, tz | [docs/sportpesa.md](docs/sportpesa.md) |
| Betika    | ke, ug, tz, mw, gh | [docs/betika.md](docs/betika.md) |

## How the lib is structured

- **Clients** — `bookieskit/bookmakers/`. One subclass of `BaseBookmaker` per platform; methods like `get_sports`, `get_events`, `get_event_detail` return raw JSON. The base class provides retry, rate-limiting, async context management, plus the convenience methods `get_markets()` and `get_sportradar_id()`.
- **Markets** — `bookieskit/markets/`. A `MarketRegistry` holds `MarketMapping` entries indexed by canonical id AND by (sport, platform, platform_id) for cross-sport collision handling. **17 markets ship as builtins** across 3 sports (10 soccer + 3 basketball + 4 tennis). `parse_markets(response, platform, sport=...)` returns `NormalizedMarket` instances. See [docs/markets.md](docs/markets.md).
- **Matching** — `bookieskit/matching/`. Two providers: SportRadar (every bookmaker) and BetGenius / Genius Sports (BetPawa, SportyBet, Bet9ja-live). `extract_event_ids(response, platform)` returns an `EventIds(sportradar, genius)` per platform; `match_events(...)` groups events from multiple bookmakers by **any** shared provider id via union-find. See [docs/matching.md](docs/matching.md).

## Built-in markets

**17 canonical markets across 3 sports.** Pass `sport=` to `parse_markets` for cross-sport id collisions (e.g. SportPesa's id `52` is both football O/U and basketball O/U; `sport="basketball"` picks the right one). Soccer is the default — existing soccer callers don't need to pass `sport=`.

### Soccer (10 markets, `sport="soccer"` — the default)

| Canonical id | Notes |
|---|---|
| `1x2_ft` | Home / Draw / Away |
| `over_under_ft` | Parameterized — line = total goals |
| `btts_ft` | Both Teams To Score (Yes / No) |
| `double_chance_ft` | 1X / X2 / 12 |
| `1x2_1up_ft` | Pays if your team gets a 1-goal lead at any point (SportyBet / Bet9ja / Betway only) |
| `1x2_2up_ft` | Same but 2-goal lead (SportyBet / Bet9ja / Betway only) |
| `next_goal_ft` | Parameterized — line = goal number (1=1st goal, 2=2nd goal, ...). Outcomes home / none / away. Covers prematch "1st Goal" and live "Nth Goal" under one canonical. |
| `home_over_under_ft` | Parameterized — line = goals scored by home team only |
| `away_over_under_ft` | Parameterized — line = goals scored by away team only |
| `2way_handicap_ft` | Parameterized — **signed** line (home's perspective); both outcomes under one signed key. Asian Handicap (no draw). |

### Basketball (3 markets, `sport="basketball"`)

| Canonical id | Notes |
|---|---|
| `moneyline_basketball_ft` | 2-way (home / away — no draw) |
| `over_under_basketball_ft` | Parameterized — line = total points |
| `2way_handicap_basketball_ft` | Parameterized — **signed** line (home's perspective); both outcomes under one key |

### Tennis (4 markets, `sport="tennis"`)

| Canonical id | Notes |
|---|---|
| `moneyline_tennis_match` | 2-way (player1 / player2) |
| `over_under_games_tennis_match` | Parameterized — line = total games |
| `over_under_sets_tennis_match` | Parameterized — line = total sets |
| `handicap_games_tennis_match` | Parameterized — signed game-spread line |

**See [docs/markets.md](docs/markets.md)** for the per-bookmaker × per-market support matrix, outcome conventions, and the handicap line representation contract.

## Examples

Each example is a self-contained async script in `examples/`.

**Multi-sport (recommended for new code):**

- **`compare_betpawa_competition_full.py`** — walks any BetPawa competition (soccer, basketball, tennis) and shows per-event mapped-market coverage across all 7 bookmakers. Sport-aware via a CLI arg.
  ```bash
  python examples/compare_betpawa_competition_full.py 12546         # soccer (default)
  python examples/compare_betpawa_competition_full.py 11971 3       # basketball (NBA)
  python examples/compare_betpawa_competition_full.py 16133 452     # tennis (French Open)
  ```

- **`find_betgenius_matches.py`** — walks all BetPawa events for one sport, extracts the BetGenius widget id, and confirms which events SportyBet also routes through BetGenius. Useful for cross-bookmaker matching when SR ids differ but the Genius id is the same. Run: `python examples/find_betgenius_matches.py` (defaults to soccer; pass a sport id arg for others).

**Soccer-focused (original):**

- **`count_5bookies.py`** — totals (sports / tournaments / events) per bookmaker across all 7. Run: `python examples/count_5bookies.py`.
- **`odds_for_sr_id.py`** — given a SportRadar id, fetch the mapped odds across all 7 bookmakers. Run: `python examples/odds_for_sr_id.py 69339436`.
- **`odds_from_betpawa_id.py`** — given a BetPawa internal id, derive the SR id from the SPORTRADAR widget and fetch all 6 others. Outputs CSV. Run: `python examples/odds_from_betpawa_id.py 34716684`.
- **`odds_for_betpawa_competition.py`** — for every event in a BetPawa soccer competition, run the above flow. Outputs one CSV row per (event, market, line, outcome). Run: `python examples/odds_for_betpawa_competition.py 12546`.

See [docs/examples.md](docs/examples.md) for more detail.

## Market-add harness (`bookieskit.devtools`)

Dev/agent tooling for the add-a-market loop — resolve an event across all
bookmakers from one seed, discover candidate markets, capture fixtures, and
verify canonical resolution. All offline-testable; no network in tests.

```bash
# Resolve a SportRadar id across every book (JSON for agents)
python -m bookieskit.devtools resolve sr:match:42 --sport soccer --json

# Discover candidate markets by name/outcome regex
python -m bookieskit.devtools discover sr:match:42 --term "handi|asian|spread"

# Autonomous discovery: markets a book exposes but the registry doesn't map
python -m bookieskit.devtools discover sr:match:42 --unmapped

# Capture raw fixtures (tests/fixtures/event_info/<book>/<name>.json)
python -m bookieskit.devtools capture sr:match:42 --name my_new_market

# Verify which canonicals parse_markets resolves
python -m bookieskit.devtools verify sr:match:42 --canonical 1x2_ft,over_under_ft

# Check docs are in sync with library changes (the CI docs-sync gate)
python -m bookieskit.devtools check-docs-sync --base origin/main
```

### Docs-sync gate

Documentation is kept in step with the library: any PR that changes
`src/bookieskit/**` must also update the affected docs (`README.md`,
`CHANGELOG.md`, or `docs/**`) in the same PR. A CI `docs-sync` job enforces
this, with a `docs:n/a` escape hatch (a `docs:n/a` label, or a bare
`docs:n/a` line in the PR body) for internal-only changes. See
[docs/docs-sync.md](docs/docs-sync.md).

## Extending

Add custom market mappings via `MarketRegistry.add(...)`:

```python
from bookieskit.markets import MarketRegistry, OutcomeMapping

registry = MarketRegistry()
registry.add(
    canonical_id="draw_no_bet_ft",
    name="Draw No Bet — Full Time",
    sportybet_id="11",
    bet9ja_key="S_DNB",
    outcomes={
        "home": OutcomeMapping(canonical_name="home", betpawa="1", sportybet="Home", bet9ja="1"),
        "away": OutcomeMapping(canonical_name="away", betpawa="2", sportybet="Away", bet9ja="2"),
    },
)
```

Pass `registry=registry` to `client.get_markets(event_id, registry=registry)` or `parse_markets(raw, platform=..., registry=registry)`.

## Limitations / known gaps

### Network gates

- **SportPesa endpoints are gated by Akamai Bot Manager.** The client does NOT solve the challenge. Callers must supply a warmed cookie harvested from a browser session, via either the constructor kwarg or the runtime setter:

  ```python
  async with SportPesa(country="ke", cookie=cookie_str) as sp:
      ...
  # Or refresh mid-session:
  sp.set_cookie(new_cookie_str)
  ```

  Without a valid cookie every request fails with Akamai's anti-bot HTML page. See [docs/sportpesa.md](docs/sportpesa.md).

### Reverse lookups not implemented

- **BetPawa SR-id reverse search not implemented.** The lib can extract a BetPawa event's SR id from the SPORTRADAR widget, but cannot find a BetPawa internal id from a SR id. Workaround: start from a BetPawa id (see `examples/odds_from_betpawa_id.py`) or walk a competition (`examples/odds_for_betpawa_competition.py`).
- **SportPesa SR-id reverse search not implemented.** Same shape: can extract an SR id (via `betradarId` on event rows), but no direct SR-id → SportPesa game-id lookup. The example index builder in `examples/compare_betpawa_competition_full.py:build_sportpesa_index` walks `get_navigation` + per-league `get_events` once to assemble a `{sr_id: game_id}` map.

### Bookmaker-specific quirks that callers must work around

- **Betika `match_id` is not globally unique — pass `competition_id`.** Within a sport, multiple matches can share the same `match_id`; the API only disambiguates when `competition_id` is also supplied. A bare lookup by `match_id + sport_id` may resolve to a different match (observed: tennis match_id `10945420` resolves to either Svrcina/Den Ouden or Tsitsipas/Mpetshi depending on which competition is in scope). `Betika.get_event_detail()` and `Betika.get_event_markets()` accept an optional `competition_id` parameter — always pass it when you have it (it's on every match row from the listing endpoint). The example index builder in `examples/compare_betpawa_competition_full.py` shows the pattern.
- **Bet9ja prematch SR-id search walks every tournament.** `Bet9ja.build_prematch_event_map(sport_id=...)` fans out one call per tournament under the sport (soccer `"1"`, basketball `"2"`, tennis `"5"`), so the first call takes a few seconds. Cache the returned `{sr_id: internal_id}` dict if you need to look up many SR ids in one session.
- **Betway event-detail returns only scoreboard.** `Betway.get_event_detail()` does not include markets — use `Betway.get_markets(event_id)` (which calls `get_event_markets` under the hood) or `Betway.get_event_markets(event_id)` for the raw response.
- **SportyBet/MSport require `live=True` for live markets.** Default `live=False` uses `productId=3`, which returns only player-prop markets for in-play events. Pass `live=True` to use `productId=1` for the full live market book.
- **Bet9ja basketball/tennis use prefixed market keys.** Soccer uses `S_*` (prematch) and `LIVES_*` (live); basketball uses `B_*`; tennis uses `T_*`. The parser dispatcher handles all four prefixes; the only impact on callers is that custom `MarketMapping`s for non-soccer Bet9ja markets must use the correct prefix in `bet9ja_key`.
- **Bet9ja does not ship per-team Over/Under for soccer goals.** `home_over_under_ft` / `away_over_under_ft` are unmapped (`bet9ja_key=None`) — Bet9ja exposes exact-goals buckets (`S_GOALSHOME` / `S_GOALSAWAY`) and a combined Home+Away O/U (`S_HAOU`), but no goal-line O/U per team. **SportPesa coverage for the three new soccer markets (`next_goal_ft` / `home_over_under_ft` / `away_over_under_ft`) is not yet locked-in** — the Akamai cookie required for the probe was unavailable at capture time. Mappings stay `None` until the next probe pass.
- **Betika does not ship 2-way Asian Handicap for soccer.** `2way_handicap_ft` is unmapped on Betika (`betika_id=None`) — Betika only exposes the 3-way `HANDICAP (1X2)` at sub_type_id=14, which is the European variant (out of scope for this release). Confirmed via probe sweep of sub_type_ids 1-200.

### Internal behaviour worth knowing

- **Silent error swallow in `Bet9ja.build_prematch_event_map`.** `src/bookieskit/bookmakers/bet9ja.py:140` contains a bare `except Exception: return {}` inside the inner `_fetch` coroutine. Any per-tournament HTTP error (rate-limit, 5xx, timeout) is silently swallowed and treated as an empty result — the caller cannot tell which tournaments failed. This is intentional best-effort behaviour but masks transient errors; a logged `BookiesKitError` subclass should replace the bare swallow.
- **Cross-bookmaker matching uses two provider ids.** SportRadar is the primary; BetGenius / Genius Sports is the secondary (used by BetPawa, SportyBet, and Bet9ja-live). `match_events(...)` groups events from multiple bookmakers by ANY shared provider id via union-find, so events that share only the BetGenius id still match. See [docs/matching.md](docs/matching.md).

## Agent company

This repo is developed by an autonomous **agent company** running on a *Signal → Work → Gate → Ship* loop: a scheduled **canary** detects bookmaker API drift, the **orchestrator** turns queued GitHub Issues into PRs via the market-add harness and the standard build pipeline, **CI** gates every change, and **release automation** ships it. See the north-star spec: [`docs/superpowers/specs/2026-06-22-agent-company-north-star.md`](docs/superpowers/specs/2026-06-22-agent-company-north-star.md).

Run one work cycle from an in-region session with `/orchestrate` (or loop it with `/loop /orchestrate`): each cycle claims the top queue item, builds it, and opens a supervised PR for review.

## License

Not yet set. Add a `LICENSE` file and a `license` field to `pyproject.toml` before publishing.
