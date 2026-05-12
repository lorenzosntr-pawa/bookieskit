# bookieskit

Async HTTP clients for 6 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport, SportPesa), with normalized markets and cross-bookmaker matching by SportRadar id.

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

async def main():
    async with SportyBet(country="ng") as sb:
        markets = await sb.get_markets(event_id="sr:match:69339436")
        for m in markets:
            print(m.canonical_id, m.name, len(m.outcomes or []))

asyncio.run(main())
```

### 2. Compare odds across all 6 by SportRadar id

```bash
python examples/odds_for_sr_id.py 69339436
```

See `examples/odds_for_sr_id.py` for the implementation.

### 3. Walk a BetPawa competition into a CSV

```bash
python examples/odds_for_betpawa_competition.py 12546
```

See `examples/odds_for_betpawa_competition.py`.

## Supported Bookmakers

| Bookmaker | Countries | Doc |
|-----------|-----------|------|
| BetPawa   | ng, gh, ke, ug, tz, zm | [docs/betpawa.md](docs/betpawa.md) |
| SportyBet | ng, gh, ke | [docs/sportybet.md](docs/sportybet.md) |
| Bet9ja    | ng | [docs/bet9ja.md](docs/bet9ja.md) |
| Betway    | ng, gh, ke, tz, ug, zm | [docs/betway.md](docs/betway.md) |
| MSport    | ng, gh, ke | [docs/msport.md](docs/msport.md) |
| SportPesa | ke, tz | [docs/sportpesa.md](docs/sportpesa.md) |

## How the lib is structured

- **Clients** — `bookieskit/bookmakers/`. One subclass of `BaseBookmaker` per platform; methods like `get_sports`, `get_events`, `get_event_detail` return raw JSON. The base class provides retry, rate-limiting, async context management, plus the convenience methods `get_markets()` and `get_sportradar_id()`.
- **Markets** — `bookieskit/markets/`. A `MarketRegistry` holds `MarketMapping` entries (one per canonical market). The parser dispatches by platform key and returns `NormalizedMarket` instances. Six markets ship as builtins. See [docs/markets.md](docs/markets.md).
- **Matching** — `bookieskit/matching/`. `extract_sportradar_id(response, platform)` pulls the SR id out of a raw event-detail response. `match_events(...)` groups events from multiple bookmakers by shared SR id. See [docs/matching.md](docs/matching.md).

## Built-in markets

| Canonical id | Name | BetPawa | SportyBet | Bet9ja | Betway | MSport | SportPesa |
|---|---|---|---|---|---|---|---|
| `1x2_ft` | 1X2 — Full Time | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `over_under_ft` | Over/Under — Full Time | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `btts_ft` | Both Teams To Score — Full Time | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `double_chance_ft` | Double Chance — Full Time | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `1x2_1up_ft` | 1X2 1Up — Full Time | — | ✅ | ✅ | ✅ | — | — |
| `1x2_2up_ft` | 1X2 2Up — Full Time | — | ✅ | ✅ | ✅ | — | — |

The 1Up / 2Up markets pay as a 1X2 if your team gets to a 1- or 2-goal lead at any point. BetPawa, MSport and SportPesa are intentionally unmapped (BetPawa to be added at production cutover; MSport and SportPesa don't expose this market).

## Examples

Each example is a self-contained async script in `examples/`.

- **`count_5bookies.py`** — totals (sports / tournaments / events) per bookmaker. Now iterates all 6 bookmakers; the original filename is kept to avoid breaking external references. Run: `python examples/count_5bookies.py`.
- **`odds_for_sr_id.py`** — given a SportRadar id, fetch the mapped odds across all 6 bookmakers. Run: `python examples/odds_for_sr_id.py 69339436` (defaults to live; pass `--prematch` for upcoming).
- **`odds_from_betpawa_id.py`** — given a BetPawa internal id, derive the SR id from the SPORTRADAR widget and fetch all 5 others. Outputs CSV. Run: `python examples/odds_from_betpawa_id.py 34716684`.
- **`odds_for_betpawa_competition.py`** — for every event in a BetPawa competition, run the above flow. Outputs one CSV row per (event, market, line, outcome). Run: `python examples/odds_for_betpawa_competition.py 12546`.

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
