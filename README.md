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
- **Markets** — `bookieskit/markets/`. A `MarketRegistry` holds `MarketMapping` entries indexed by canonical id AND by (sport, platform, platform_id) for cross-sport collision handling. **13 markets ship as builtins** across 3 sports (6 soccer + 3 basketball + 4 tennis). `parse_markets(response, platform, sport=...)` returns `NormalizedMarket` instances. See [docs/markets.md](docs/markets.md).
- **Matching** — `bookieskit/matching/`. Two providers: SportRadar (every bookmaker) and BetGenius / Genius Sports (BetPawa, SportyBet, Bet9ja-live). `extract_event_ids(response, platform)` returns an `EventIds(sportradar, genius)` per platform; `match_events(...)` groups events from multiple bookmakers by **any** shared provider id via union-find. See [docs/matching.md](docs/matching.md).

## Built-in markets

**13 canonical markets across 3 sports.** Pass `sport=` to `parse_markets` for cross-sport id collisions (e.g. SportPesa's id `52` is both football O/U and basketball O/U; `sport="basketball"` picks the right one). Soccer is the default — existing soccer callers don't need to pass `sport=`.

### Soccer (6 markets, `sport="soccer"` — the default)

| Canonical id | Notes |
|---|---|
| `1x2_ft` | Home / Draw / Away |
| `over_under_ft` | Parameterized — line = total goals |
| `btts_ft` | Both Teams To Score (Yes / No) |
| `double_chance_ft` | 1X / X2 / 12 |
| `1x2_1up_ft` | Pays if your team gets a 1-goal lead at any point (SportyBet / Bet9ja / Betway only) |
| `1x2_2up_ft` | Same but 2-goal lead (SportyBet / Bet9ja / Betway only) |

### Basketball (3 markets, `sport="basketball"`)

| Canonical id | Notes |
|---|---|
| `moneyline_basketball_ft` | 2-way (home / away — no draw) |
| `over_under_basketball_ft` | Parameterized — line = total points |
| `handicap_basketball_ft` | Parameterized — **signed** line (home's perspective); both outcomes under one key |

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

- **SportPesa endpoints are gated by Akamai Bot Manager.** The client does NOT solve the challenge. Callers must supply warmed cookies harvested from a browser session — for example, by setting `self._http_client.headers["cookie"] = "..."` after entering the async context. Same posture as the BetPawa SR-id reverse-search gap. See [docs/sportpesa.md](docs/sportpesa.md).
- **SportPesa SR-id reverse search not implemented.** Same shape as the BetPawa gap below — extract an SR id from a SportPesa event-detail response, but no SR id → SportPesa internal id lookup.
- **SportPesa list-endpoint paths are best-evidence pending fixture capture.** `get_sports`, `get_countries`, `get_tournaments`, `get_events` use the most likely SportPesa URLs; the two confirmed endpoints (`get_event_detail`, `get_event_markets`) come from real captured requests. A `# fixture-resolve` comment marks each unconfirmed path; the smoke run pins them down.
- **BetPawa SR-id reverse search not implemented.** The lib can extract a BetPawa event's SR id from the SPORTRADAR widget, but cannot find a BetPawa internal id from a SR id. Workaround: start from a BetPawa id (see `examples/odds_from_betpawa_id.py`).
- **Bet9ja prematch SR-id search.** `Bet9ja.build_prematch_event_map(sport_id="1")` walks every soccer tournament — takes a few seconds on first call. Cache the returned dict if you need to look up many SR ids in one session.
- **Betway live event-detail returns only scoreboard.** `Betway.get_event_detail()` does not include markets. Use `Betway.get_markets(event_id)` (which calls `get_event_markets` under the hood).
- **SportyBet/MSport require `live=True` for live markets.** Default `live=False` uses `productId=3` which returns only player-prop markets for in-play events. Pass `live=True` to use `productId=1`.
- **GeniusSport-fed events are not handled.** Cross-bookmaker matching is built on SportRadar ids; events sourced from the GeniusSport feed don't carry an SR id and won't appear in matched results.
- **Test-coverage gaps (9 methods).** The following methods have no test: `SportyBet.get_sportradar_id` (inherited), `Bet9ja.get_live_sports`, `Bet9ja.get_live_events`, `Bet9ja.get_countries`, `Bet9ja.get_tournaments`, `Bet9ja.get_markets` (inherited), `Betway.get_tournaments`, `MSport.get_markets` (inherited), `MSport.get_sportradar_id` (inherited). The live-endpoint methods (`get_live_sports`, `get_live_events`) are the highest-risk gaps given their structurally different payload.
- **Silent error swallow in `Bet9ja.build_prematch_event_map`.** `bet9ja.py:142` contains a bare `except Exception: return {}` inside the inner `_fetch` coroutine. Any per-tournament HTTP error (rate-limit, 5xx, timeout) is silently swallowed and treated as an empty result — the caller cannot tell which tournaments failed. This is intentional best-effort behaviour but masks transient errors; a logged `BookiesKitError` subclass should replace the bare swallow.

## License

(Whatever the project's license is. Leave a placeholder if not yet set.)
