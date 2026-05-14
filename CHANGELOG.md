# Changelog

All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] — 2026-05-14

Expanded country coverage across BetPawa, MSport, and Betway after probing each bookmaker's live API endpoints. Fixed a latent MSport bug discovered during the probe — `GH` and `KE` country entries in `DOMAINS` had been silently broken since they were added.

### Fixed

- **MSport per-country `operid` header.** The lib previously hardcoded `operid=2` in `DEFAULT_HEADERS`, but the MSport API rejects every other country with `bizCode 19000 "invalid operId"`. Country-to-operid mapping discovered by sweeping values 1..15 per country: `ng=2, gh=3, ke=1, ug=4, zm=5`. The `gh` and `ke` entries that shipped with the original MSport client never actually worked at runtime; only `ng` did. New `_OPERID_PER_COUNTRY` map in `bookmakers/msport.py` plus `_build_headers` override resolves the correct value per instance. (`msport.py`, `tests/test_msport.py`)

### Added

- **BetPawa 3 new countries**: `rw` (https://www.betpawa.rw / `betpawa-rwanda`), `cm` (https://www.betpawa.cm / `betpawa-cameroon`), `sl` (https://www.betpawa.sl / `betpawa-sierraleone`). Verified against the live `/api/sportsbook/v2/categories/list/by-sport` endpoint with the candidate brand header. BetPawa total: 9 countries.
- **MSport 2 new countries**: `ug` (operid=4), `zm` (operid=5). Verified by live `get_sports()` calls returning 31 sports each. MSport total: 5 countries (and `gh`/`ke` now actually work, see above).
- **Betway 1 new country**: `za` (countryCode=ZA). Verified against `config.betwayafrica.com/cron/sports/ZA/en-US`. Betway total: 7 countries.

### Documentation

- Per-bookmaker doc pages (`docs/{betpawa,msport,betway,sportybet}.md`) now have a full Countries table including the URL/header pattern that pairs with each country code. README "Supported Bookmakers" table reflects the expanded counts.
- `docs/sportybet.md` notes that further SportyBet country expansion was attempted in 0.8.0 but blocked by anti-bot / TLS-cert issues when probing from outside an African residential IP. The lib keeps the existing `ng`/`gh`/`ke` entries; future additions should be PR'd with a successful probe transcript.

### Test count

416 → 428 passing (+12 across `_OPERID_PER_COUNTRY` parametrize, the 3 new BetPawa countries' DOMAINS+brand assertions, the new Betway `za` country code, MSport new-country domain resolution, and the explicit `ke→operid=1` regression test).

## [0.7.1] — 2026-05-14

Patch release addressing five issues surfaced by code review of the 0.7.0 Betika integration. All changes additive — no breaking changes.

### Fixed

- **`BaseBookmaker._request` now preserves absolute URLs in error reporting.** Previously, when a subclass routed to a different host via an absolute path (e.g. `Betika._live_request` → `https://live.betika.com/...`), exceptions like `RequestError`/`RateLimitError` carried a corrupted URL string `"https://api.betika.com" + "https://live.betika.com/..."`. The retry logic itself was correct; only the recorded URL was wrong, which would mislead operator logs and Sentry. (`base.py`)
- **`_parse_betika_line` now extracts the line from `special_bet_value="total=N.N"`** in addition to bare numeric strings. Captured fixtures show Betika's Over/Under selections use the `total=N.N` format; the parser previously fell through silently to the `display`-label fallback (which works today but is brittle if Betika ever drops the line from the label). (`markets/parser.py`)
- **`_kickoff_betika` preserves tz-aware ISO offsets** instead of overwriting them with UTC. Betika serves naive UTC today; this guards against a future shift to offset-aware serialization (where overwriting `+03:00` with UTC would silently shift the moment by 3 hours). (`event_info.py`)

### Changed

- **Consolidated three near-duplicate `_betika_first_match` helpers into a single shared module.** The dict-or-bare-list shape walk previously lived in `event_info.py`, `markets/parser.py`, and inline in `matching/extractor.py`. All three now import from `bookmakers/_betika_shape.py` (`betika_first_match`). DRY win; tests in `test_betika_shape.py` pin the contract.
- **Parser and SR-id extractor docstrings now list all 7 supported platforms.** Both `parse_markets` and `extract_sportradar_id` previously omitted `sportpesa` (stale from 0.6.0) and `betika` (new in 0.7.0) from their `platform` parameter docstrings.

### Added

- **Multi-market fixture `tests/fixtures/event_info/betika/markets.json`** — real `Betika.get_event_markets` payload for one event with all four universal market groups (1X2, Double Chance, Over/Under, BTTS) merged. Five new fixture-bound parser tests bind against this real shape rather than relying purely on synthetic payloads.
- **`test_betika_listed_in_supported_count` now reads `pyproject.toml` directly via `tomllib`** instead of `importlib.metadata.metadata("bookieskit").get("Summary")`. The previous form would fail spuriously when developers edited the package description without running `pip install -e .` again.

### Test count

399 → 416 passing (+17 across the new shape helper module, fixture-bound parser tests, absolute-URL regression tests, the tz-aware kickoff guard, and the `total=N` line-format test).

## [0.7.0] — 2026-05-14

### Added

- **Betika client** (`bookieskit.Betika`) — async HTTP client for the Betika sportsbook API. Country-agnostic at the API layer; supports `ke`, `ug`, `tz`, `mw`, `gh` (all map to `api.betika.com` for prematch and `live.betika.com` for in-play). Methods: `get_sports`, `get_navigation` (alias), `get_matches`, `get_live_matches`, `get_event_detail`, `get_event_markets` (4-call aggregation across `sub_type_id ∈ {1, 10, 18, 29}`), `get_markets`, `iter_all_prematch_events` (driven by `meta.total`), plus inherited `get_sportradar_id` / `set_cookie`. API is open — no Cloudflare gate, no warmed cookies needed, `MAX_CONCURRENT=50` / `REQUEST_DELAY=0.0`.
- **Betika field on `OutcomeMapping`** (`betika: str`) **and `betika_id: str | None` on `MarketMapping`.** The four universal builtin markets (1X2, Over/Under, BTTS, Double Chance) wire to Betika `sub_type_id` `1` / `18` / `29` / `10` respectively, with outcome display labels (`"1"`/`"X"`/`"2"`, `"Over"`/`"Under"`, `"Yes"`/`"No"`, `"1/X"`/`"X/2"`/`"1/2"`).
- **Betika parser branch** in `bookieskit.markets.parser`. Case-insensitive outcome resolution (Betika's BTTS feed has been observed returning both `"YES"`/`"NO"` and `"Yes"`/`"No"`). Over/Under line value parsed from `special_bet_value` when present, falling back to the embedded number in the display label (`"OVER 2.5"` → 2.5).
- **Betika SR-id extractor** at `data[0].parent_match_id`. Tolerates both string (prematch) and integer (live) types via `str()` coercion. Cross-verified against SportyBet: `parent_match_id="70784812"` resolves to the same Man City vs Crystal Palace match.
- **`MatchedEvent.betika` field** on `bookieskit.matching.MatchedEvent`. The cross-bookmaker `match_events(*platforms)` helper now accepts a `("betika", [...])` tuple alongside the other six platforms; matched events populate `.betika` like any other field.
- **Betika event-info extractors** for kickoff (`data[0].start_time`, naive ISO → UTC), participants (`data[0].home_team` / `away_team`), and live info (`data[0].match_time`, `event_status`, `current_score`).
- **Top-level `Betika` export** (`from bookieskit import Betika`). Version bumped to `0.7.0`.

### Changed

- **Package description and README tagline** now advertise 7 bookmakers (was 6). Supported tables and built-in markets matrices include a Betika column.
- **Examples (`count_5bookies.py`, `odds_for_sr_id.py`, `odds_from_betpawa_id.py`, `odds_for_betpawa_competition.py`) fanned to include Betika.** `count_5bookies.py` runs Betika's full prematch enumeration plus per-page live walks. The CSV-producing scripts add a `Betika` column; like SportPesa it is currently a placeholder (no SR-id reverse search yet — pass a Betika `match_id` directly to `get_event_detail` if you need its odds).

### Documentation

- `docs/betika.md` (new) — methods table, quirks (open API, country-agnostic, two hosts, one-market-per-call, case-insensitive outcome resolution, line embedded in display label), and recipes.
- `docs/markets.md`, `docs/matching.md`, `docs/examples.md` extended with Betika rows / mentions.
- `tests/fixtures/event_info/betika/RESOLVED.md` — decision record for captured fixtures: which JSON paths hold the SR id, kickoff, participants, live info, and the four universal `sub_type_id` mappings.

### Migration notes (0.6.0 → 0.7.0)

Purely additive — no breaking changes. Existing callers do not need to update unless they explicitly want to include Betika in cross-bookmaker fan-outs (in which case add a `("betika", [...])` tuple to `match_events` calls, or `Betika` to client lists).

## [0.6.0] — 2026-05-13

### Added

- **`BaseBookmaker.set_cookie(cookie)` and `cookie=` constructor kwarg.** Replaces the `client._http_client.headers["cookie"] = ...` workaround. Primarily needed for SportPesa (Akamai-gated) but available on every client. Works pre- and post-context; calling `set_cookie` mid-session updates both the stored value and the live httpx headers so the next request carries the new cookie.
- **`PrematchEventStub(event_id, league_id, sport_id)`** — minimal event identifier type re-exported from the top-level `bookieskit` package. Yielded by the new catalogue iterators.
- **`Betway.iter_all_prematch_events()`**, **`MSport.iter_all_prematch_events()`**, **`SportPesa.iter_all_prematch_events()`** — async iterators that yield `PrematchEventStub` for every event in the bookmaker's full prematch catalogue. Each one wraps the per-bookmaker fan-out pattern (Betway: regions → leagues → per-league events; MSport: cursor pagination via `lastEventId`; SportPesa: navigation tree → per-league fan-out). All run their underlying HTTP calls concurrently under the client's existing `MAX_CONCURRENT` semaphore, deduplicate by event id, and tolerate per-call failures gracefully.
- **`Betway.get_live_events(sport_id, ...)`** — new method hitting `/br/_apis/sport/v1/BetBook/LiveInPlay/`. `market_types` defaults to `""` (no filter) so the call covers every sport — passing the football-specific `"[Win/Draw/Win]"` silently drops non-football events.
- **`SportPesa.get_navigation()`** — fetches `/api/navigation`, returning the full sport → country → league tree (13 sports, ~302 leagues at writing).
- **`SportPesa.get_live_events_started(sport_id)`** — authoritative currently-in-play events from `/api/live/sports/{sport_id}/events/started`. Use instead of the `eventNumber` field on `/api/live/sports` (that field is a separately-cached counter and unreliable).
- **`SportPesa.get_live_sport_events(sport_id)`** — broader `/api/live/sports/{sport_id}/events` (all events offering live markets, including near-future ones).
- **`MSport.get_events()`** gains `last_event_id` and `limit` kwargs for cursor pagination. `/sports-matches-list` returns ~50 events per page by default — without the cursor, callers were seeing only ~12 tournaments / ~50 events for soccer instead of the real ~200 / ~1000+.

### Changed (potentially breaking)

- **`SportPesa.get_events(...)` parameter renamed** `competition_id` → `league_id`. The SportPesa API silently ignores `competitionId` (it accepts the parameter but returns the unfiltered rolling 100 events) — only `leagueId` actually filters. Callers using the old name need to rename the kwarg. There is no compatibility shim.
- **`SportPesa.get_countries()` and `SportPesa.get_tournaments()` removed.** SportPesa exposes no dedicated countries or tournaments endpoint. Use `get_navigation()` and walk the returned tree (`countries`, `leagues` are nested under each `sport`).
- **`SportPesa.get_sports()` no longer accepts a `live=` parameter.** The previous `live=False`/`live=True` argument was a no-op (the endpoint is `/api/live/sports` regardless); callers passing `live=` will now see a `TypeError`.
- **`SportPesa.get_event_detail(event_id, live=False)`** still accepts the `live=` argument for API symmetry but it is ignored — the SportPesa endpoint serves the same payload for prematch and in-play games.
- **`Betway.get_live_events()` `market_types` default is now `""` (was `"[Win/Draw/Win]"`).** Empty means "no filter"; the previous default silently dropped events from sports that don't carry 1X2 (tennis, cricket, basketball, table tennis, handball, cycling). Callers that depended on the filter behaviour should pass an explicit `market_types=...` value.
- **`Betway.get_events()`** continues to default `market_types` to `"[Win/Draw/Win]"` for backward compatibility, but the new `iter_all_prematch_events()` overrides this to `""` internally so cross-sport enumeration works correctly. Callers using `get_events()` directly across non-football sports should pass `market_types=""`.

### Fixed

- **SportPesa parser** binds to the real captured shape: response is `{<game_id>: [<market>, ...]}` (not `data[0].markets`), selections use `shortName` not `name`, parameterized markets use `specValue` not `special_bet_value`, and the canonical market ids are `10` (1X2), `52` (O/U), `43` (BTTS), `46` (DC) — not `1`/`18`/`29`/`10` as the original spec guessed.
- **SportPesa SR-id extractor** now reads `[0].betradarId` from the list-shaped event-detail response (was previously expecting `data[0].additional_info.sportradar_id`, which doesn't exist).
- **SportPesa event-info extractors** (kickoff, participants, live_info) bound to real fixture shapes: `[0].dateTimestamp` (epoch ms), `[0].competitors[0/1].name`, `state: {}` (live-info not in this endpoint, returns empty).
- **`count_5bookies.py`** now reports accurate cross-bookmaker totals. Previously several columns were stubbed (BetPawa Tour(L)=0, Bet9ja Tour(L)=0, Betway Events(P)=n/a) because of unread response fields or unwalked endpoints. All six bookmakers now report real numbers and sit in consistent ranges.

### Documentation

- `docs/sportpesa.md` overhauled. Methods table reflects the real API (no `get_countries`/`get_tournaments`, `league_id` not `competition_id`, plus the new methods). Quirks section enumerates every pagination parameter that's been verified to be silently ignored — the `competitionId` vs `leagueId` asymmetry is called out explicitly.
- `docs/betway.md` and `docs/msport.md` methods tables extended with `iter_all_prematch_events`, plus `Betway.get_live_events` and the `last_event_id`/`limit` kwargs on `MSport.get_events`.
- `tests/fixtures/event_info/sportpesa/RESOLVED.md` (new) — decision record for the captured fixtures: which JSON paths hold the SR id, kickoff, participants, etc.

### Migration notes (0.5.0 → 0.6.0)

Callers that pinned to `0.5.0` and used any of the following will need a small change:

```python
# OLD (0.5.0)
async with SportPesa(country="ke") as sp:
    sp._http_client.headers["cookie"] = warmed_cookie
    events = await sp.get_events(sport_id="1", competition_id="67600")
    sports = await sp.get_sports(live=False)
    countries = await sp.get_countries(sport_id="1")

# NEW (0.6.0)
async with SportPesa(country="ke", cookie=warmed_cookie) as sp:
    events = await sp.get_events(sport_id="1", league_id="67600")
    sports = await sp.get_sports()                # no `live=` kwarg
    nav = await sp.get_navigation()                # replaces get_countries/get_tournaments
```

For `Betway.get_live_events()`, code that relied on the previous football-1X2 default must pass it explicitly:

```python
# OLD: implicitly filtered to football 1X2
events = await bw.get_live_events(sport_id="soccer")

# NEW (0.6.0): pass it if you need it
events = await bw.get_live_events(sport_id="soccer", market_types="[Win/Draw/Win]")
```

## [0.5.0] — 2026-05-12

### Added

- **`SportPesa` client** as the 6th supported bookmaker. Countries: `ke`, `tz`. Carries the full event-detail / markets / SR-id contract in line with the existing 5 bookmakers.
- Six built-in markets (1X2, O/U, BTTS, DC + the 1Up/2Up specialty variants) gained a `sportpesa_id` / `sportpesa=` column on `MarketMapping` / `OutcomeMapping` for the 4 universal markets.
- `MatchedEvent.sportpesa: dict | None = None` added to the cross-bookmaker matcher.
- Probability-mode plumbing on the SportPesa parser (the platform doesn't actually expose probability fields; the parser accepts the kwarg silently).
- `examples/odds_for_sr_id.py`, `examples/count_5bookies.py`, `examples/odds_from_betpawa_id.py`, `examples/odds_for_betpawa_competition.py` fan out across all 6 bookmakers.

### Changed

- Tagline `5 African sportsbooks` → `6 African sportsbooks` in README, pyproject description, and several docs.

## [0.4.0] and earlier

See git history. Pre-CHANGELOG release; supported BetPawa / SportyBet / Bet9ja / Betway / MSport with cross-bookmaker normalization via SportRadar ids.

[0.6.0]: https://github.com/<user>/bookieskit/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/<user>/bookieskit/compare/v0.4.0...v0.5.0
