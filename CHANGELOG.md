# Changelog

All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.14.0] - 2026-05-21

### Added
- Three new canonical soccer markets:
  - `next_goal_ft` — "next goal scored" (Home / None / Away). Parameterized by **goal number** (`lines[1.0]` is 1st goal prematch; live events can expose `lines[2.0]`, `lines[3.0]`, etc. under one canonical id). Mapped on BetPawa, SportyBet, Bet9ja, Betway, MSport (live-only), and Betika.
  - `home_over_under_ft` — Over/Under on goals scored by the home team only. Mapped on BetPawa, SportyBet, Betway, MSport, Betika. Bet9ja does not ship this market; SportPesa not yet probed.
  - `away_over_under_ft` — same shape for the away team, same coverage.
- `_TeamScopedBetwayRegistry` — wraps a `MarketRegistry` to substitute literal `[Home Team]` / `[Away Team]` placeholders in Betway mapping keys with the actual team names from the event payload. Used internally by `_parse_betway`; custom mappings can use the same placeholders.
- `_extract_betway_line_from_market_id` — extracts the line value from Betway `marketId` segments containing `goalnr=N~`. Covers `next_goal_ft` prematch where Betway ships a single `handicap=0` entry instead of per-line entries.

### Changed
- `_extract_line_from_specifier` (SportyBet + MSport) now recognises `goalnr=N` alongside `total=N` and `hcp=N`.
- `_build_betway_parameterized` restructured into three mutually-exclusive cases: (1) parent-with-per-line distribution; (2) parent-only with line from marketId; (3) per-line entries without a parent.
- Built-in canonical market count: 13 → 16 (9 soccer + 3 basketball + 4 tennis).

## [0.13.1] — 2026-05-18

Two bug fixes uncovered by cross-bookmaker validation on an OKC/SAS basketball event and a Svrcina/Den Ouden tennis event.

### Fixed

- **Betika `match_id` collisions** — within a sport, multiple matches can share the same `match_id`; Betika's API only disambiguates when `competition_id` is also supplied. A bare `match_id + sport_id` lookup was silently returning a different match (observed: tennis match_id `10945420` resolves to either Svrcina/Den Ouden or Tsitsipas/Mpetshi depending on which competition is in scope). `Betika.get_event_detail()` and `Betika.get_event_markets()` now accept an optional `competition_id` parameter and forward it on every sub_type_id call. The `examples/compare_betpawa_competition_full.py` Betika index builder now stores `(match_id, competition_id)` tuples and the per-match fetcher forwards the competition id. Documented as a quirk in `docs/betika.md` and as a known gap in the README.
- **Betway parameterized parser per-line index** — the parameterized parser was passing the parent-list index `i` to `_resolve_outcome_betway`, which broke position sentinels (`__POS_2__`) for every line whose outcomes don't land at the start of the parent list. Fixed by filtering to each line's outcome group first, then enumerating within that group so `i` is line-local.

### Added

- **Betika tennis Game Handicap** — registry now maps `betika_id="187"` on `handicap_games_tennis_match`. Live re-validation confirms Betika tennis handicap odds are within rounding of BetPawa / SportyBet / MSport / Bet9ja / SportPesa at every shared line. The earlier `betika_id=None` was a fixture artifact: the captured fixture had been taken with a bare `match_id` and was silently fetching a different match that had no handicap group.

### Tests

527 → 530 passing (+3: two for the Betika client `competition_id` forwarding, one for the parser-side Game Handicap mapping).

## [0.13.0] — 2026-05-18

Second non-soccer sport: tennis. Four canonical markets land across all 7 bookmakers.

### Added

- **Four tennis canonical markets** in the default `MarketRegistry`:
  - `moneyline_tennis_match` (non-parameterized, 2 outcomes — no draw)
  - `over_under_games_tennis_match` (parameterized, line = total games)
  - `over_under_sets_tennis_match` (parameterized, line = total sets)
  - `handicap_games_tennis_match` (parameterized, signed game-spread line)

- **Working tennis coverage on all 7 bookmakers** (each fixture-bound to a live ATP match). Per-bookmaker market id discovery:
  - BetPawa: `2043818` ML, `4895` Total Games, `3597899` Total Sets, `3532590` Match Handicap Games
  - SportyBet, MSport, Betway, Betika: SR-standard codes `186` (Winner), `189` (Total Games), `314` (Total Sets), `187` (Game Handicap)
  - Bet9ja: `T_*`-prefixed keys (`T_12`, `T_OUG`, `T_TS`, `T_GH`) — parser now accepts `T_*` prefix alongside `S_*` (soccer), `B_*` (basketball), `LIVES_*` (soccer-live)
  - SportPesa: `382` ML, `226` Total Games, `51` Game Handicap

- **Sport-aware registry collision handling**: SportPesa `id=51` is BOTH basketball Handicap AND tennis Game Handicap. The sport-aware lookup added in 0.12.0 disambiguates: `parse_markets(..., sport="tennis")` resolves `51` to game handicap, `sport="basketball"` to basketball handicap. Both pinned with regression tests.

### Coverage gaps

By design, captured at the platform/event level:
- **MSport** doesn't expose Total Sets directly (no SR market id `314` in any tennis event captured).
- **Betika** offers only ML + Total Games for tennis on the captured event; sub_type_ids 187/188/314 returned nothing.
- **SportPesa** doesn't expose Total Sets on the captured event (only 13 market types ship; no id matches the SR `314` code).

These gaps are mapped as `None` in `BUILTIN_MAPPINGS` — the lib won't synthesise markets that bookmakers don't publish. Documented in `docs/markets.md`.

### Example script

`examples/compare_betpawa_competition_full.py` now ships a third `SPORT_CONFIG` row for `sport_id="452"` (tennis). Run it against any BetPawa tennis competition:

```
python examples/compare_betpawa_competition_full.py 16133 452   # French Open Men
```

Verified live across the 52-event French Open Men's Singles: every event resolves on every bookmaker via SR id, with each bookmaker reporting whichever subset of the 4 markets it offers for that specific match.

### Test count

502 → 527 passing (+25 from the new tennis parser parametrize sweep — 7 platforms × ML/OU-G + 3 platforms × OU-S + 6 platforms × HCAP-G + 2 sport-scoping regressions).

## [0.12.0] — 2026-05-18

Completes basketball coverage to all 7 bookmakers by closing the three gaps deferred from 0.11.0.

### Added

- **`MarketMapping.sport`** field (defaults to `"soccer"`). Lets the registry disambiguate market ids that overlap across sports on the same platform. The 3 basketball mappings added in 0.11.0 now carry `sport="basketball"`; all soccer mappings inherit the default.
- **Sport-aware registry lookup**: `MarketRegistry.get_by_platform_id(platform, id, sport=None)` accepts an optional `sport=` argument. When provided, lookup uses a new `(platform, sport, id)` index; without it, the flat per-platform index returns the first-registered mapping (pre-0.12.0 behaviour, typically soccer). The flat indexes now use first-wins so existing back-compat assertions keep passing.
- **`parse_markets(..., sport=None)`** parameter. Wraps the registry in a thin `_SportScopedRegistry` that injects the sport filter on every per-parser lookup — no per-parser changes needed.
- **Bet9ja basketball support**: parser now accepts `B_*` market-key prefix (basketball) alongside the existing `S_*` (soccer) and `LIVES_*` (live soccer). `_parse_bet9ja_key` preserves the original 2-char prefix so registry lookups match the correct `bet9ja_key`. Tested against a captured Baskets Bonn vs Wurzburg Baskets event — all three markets parse correctly (ML 2 outcomes, O/U 13 lines, handicap 13 lines).
- **Betika basketball ML + O/U fixture**: captured a multi-market `basketball.json` for Betika (Oklahoma vs San Antonio, sub_type_ids 219 + 225). The parser already accepted those SR-standard codes; the missing piece was just a fixture that exercised them. Handicap is **not offered** by Betika for basketball — pinned with a dedicated test that asserts the canonical_id is absent.
- **SportPesa basketball end-to-end**: the three mapping rows that were `sportpesa_id=None` in 0.11.0 now carry the real ids (`382` ML, `52` O/U, `51` handicap). The sport-aware registry lookup picks the basketball mapping when `parse_markets(..., sport="basketball")` is called; the bare lookup still returns the football O/U for id `52` (pre-0.12.0 callers unchanged). Fixture-bound tests pin both behaviours.

### Test count

492 → 502 passing (+10 across the SportPesa basketball trio, Bet9ja basketball additions to the parametrize, Betika ML+O/U + the no-handicap regression test).

## [0.11.0] — 2026-05-18

First non-soccer sport: basketball. Three canonical markets land for the big-three basketball bets across 4 of 7 bookmakers.

### Added

- **Three basketball canonical markets** in the default `MarketRegistry`:
  - `moneyline_basketball_ft` (non-parameterized, 2 outcomes — home / away, no draw)
  - `over_under_basketball_ft` (parameterized, total points line)
  - `handicap_basketball_ft` (parameterized, signed point spread)

- **Working basketball coverage on 4 bookmakers**, fixture-bound to live captures: **BetPawa**, **SportyBet**, **MSport**, **Betway**. Each fixture lives under `tests/fixtures/event_info/<platform>/basketball.json` and is exercised by `tests/test_parser_basketball.py`.

- **Per-bookmaker market ids discovered by live probe**:
  - BetPawa: `4791` / `5009` / `3777` ("Asian Handicap"), outcomes `"1"` / `"2"`
  - SportyBet, MSport: `"219"` / `"225"` / `"223"` (SR-standard codes), outcomes `"Home"` / `"Away"`
  - Betway: names `"Winner (Incl. Overtime)"` / `"Total (Incl. Overtime)"` / `"Handicap (Incl. Overtime)"`, team-name outcomes resolved via the `__POS_2__` position sentinel for away (basketball ML is 2-way, so the soccer `__AWAY__` sentinel at index 2 doesn't apply).

### Design decisions

- **Handicap shape** uses one signed line key per row with both outcomes (home + away) in the same bucket — wire-faithful with how bookmakers actually ship the data. The earlier-considered alternative of splitting into `{-5.5: [home], +5.5: [away]}` was dropped in favour of the simpler wire-faithful shape; callers infer the away team's effective line by negating the key.

### Deferred

- **Bet9ja basketball**: market key prefix is `B_*` (vs soccer's `S_*`); the existing parser doesn't dispatch on it yet. Mappings are wired (`B_12`, `B_OUN`, `B_H`) so a small parser tweak unlocks it. Live fixture captured.
- **SportPesa basketball**: SportPesa's market ids are sport-scoped — id `52` maps to football O/U **and** basketball O/U, which collides in the registry's flat `_by_sportpesa` index. Sport-aware registry lookups are needed before SportPesa basketball can land. Live fixture (plus full markets payload) captured for the future implementation.
- **Betika basketball**: ML + O/U mappings work in principle (Betika uses the same SR-standard codes 219/225 the parser already accepts), but the captured fixture is the default 1X2-only view rather than the multi-market aggregator output. A small follow-up will capture a multi-market basketball fixture for fixture-bound coverage. Handicap is **not offered** by Betika for basketball.

### Documentation

- `docs/markets.md` rewritten around two sport-scoped tables (soccer + basketball) plus a notes section covering outcome conventions per platform, the handicap signed-line contract, and the three deferred platforms.

### Test count

472 → 492 passing (+20 across the 4-platform basketball parser parametrize, three new registry assertions for the basketball builtins, and the BetPawa-specific fixture-bound suite).

## [0.10.0] — 2026-05-18

Closed the country-coverage gap on BetPawa (now matches their full advertised footprint) and added 4 new SportyBet markets.

### Added

- **BetPawa: 6 new countries** completing the 15-country list advertised on BetPawa's [country selector landing page](https://www.betpawa.com/). Discovered by clicking each entry on the live landing page via Playwright and reading the redirect target, then verified by probing `/api/sportsbook/v2/categories/list/by-sport` with the discovered `x-pawa-brand` header:
  - `bj` (Benin) → `https://www.betpawa.bj` / `betpawa-benin`
  - `cg` (Congo - Brazzaville) → `https://cg.betpawa.com` / `betpawa-congobrazzaville`
  - `cd` (DR Congo) → `https://www.betpawa.cd` / `betpawa-drc`
  - `ls` (Lesotho) → `https://ls.betpawa.com` / `betpawa-lesotho`
  - `mw` (Malawi) → `https://www.betpawa.mw` / `betpawa-malawi`
  - `mz` (Mozambique) → `https://www.betpawa.co.mz` / `betpawa-mozambique`

  `cg` and `ls` introduce a third URL pattern (`<cc>.betpawa.com`) alongside the existing `www.betpawa.<cc>` and `www.betpawa.<co|com>.<cc>` patterns. The lib binds to the direct subdomain form to avoid a 308 redirect on every request. The `cd` brand header is `betpawa-drc` (not `drcongo` or `democraticrepublicofcongo`; discovered via brand sweep).
- **SportyBet: 4 new countries** verified via `/factsCenter/popularAndSportList` returning 16-22 sports each:
  - `tz` (Tanzania): 22 sports
  - `za` (South Africa): 21 sports
  - `cm` (Cameroon): 16 sports
  - `zm` (Zambia): 21 sports

### Documented (not supported)

- **SportyBet `ca` (Canada)** is a real SportyBet market (`https://sportybet.ca/` returns 200) but uses a different API platform. The current client's `/api/{cc}/factsCenter/...` contract returns HTTP 502 for `ca`. Intentionally NOT in `DOMAINS`; documented in `docs/sportybet.md` with the path that would be needed for a future Canadian client.

### Documentation

- `docs/betpawa.md` and `docs/sportybet.md` now show the full per-country URL/brand/path tables. The BetPawa doc enumerates the three URL patterns explicitly.
- README "Supported Bookmakers" table reflects the new BetPawa (15) and SportyBet (7) country lists.

### Test count

461 → 472 passing (+11; parametrized 6 new BetPawa countries and 4 new SportyBet countries, plus a regression test pinning that `ca` raises `UnsupportedCountryError`).

## [0.9.1] — 2026-05-15

Patch release addressing review feedback on the 0.9.0 BetGenius integration. The 0.9.0 release shipped a code path (and supporting tests) for a SportyBet payload shape that doesn't appear in production. This release replaces it with the correct shape, observed via the live API.

### Fixed

- **SportyBet's BetGenius prefix is on `eventSource.sourceId`, not `data.eventId`** — and it's seven `1`s, not eight. The 0.9.0 extractor checked for `data.eventId == "sr:match:11111111<gid>"` (8 ones, on eventId), but the live probe behind `examples/find_betgenius_matches.py` showed SportyBet's `eventId` always carries the SportRadar id regardless of provider, and the 7-ones prefix appears on `eventSource.{preMatchSource,liveSource}.sourceId` for BET_GENIUS rows (and BET_RADAR preMatchSource rows). The 0.9.0 fallback branch therefore never fired on real data. Replaced with a `_strip_sportybet_source_prefix` helper that strips the 7-ones prefix from any sourceId, so the bare provider id matches BetPawa's `GENIUSSPORTS` widget id format. A real BetGenius event now correctly produces an `EventIds` with both `sportradar` and `genius` populated (the eventId carries the SR id; sourceId carries the Genius id). (`src/bookieskit/matching/extractor.py`, `tests/test_extractor.py`, `tests/test_matcher.py`)
- **Synthetic test payloads replaced with real-shape ones.** Six tests in `test_extractor.py` and three in `test_matcher.py` were binding against `eventId = "sr:match:1111111113599033"` — a shape that never exists in real SportyBet responses. They now use `eventId = "sr:match:<real_sr_id>"` + `eventSource.sourceId = "1111111<id>"`, mirroring the actual fixture shapes the audit captured.

### Changed

- **`examples/find_betgenius_matches.py` logs failures instead of swallowing them.** Both `fetch_betpawa_event` and `sportybet_lookup` previously did `except Exception: return None`, which conflated network timeouts / 500s / parse errors with "no Genius widget found." Now uses `logger.warning(...)` so operators can see per-event failures in stderr. `logging.basicConfig` wired in `__main__`.

### Documentation

- `docs/matching.md` and `docs/sportybet.md` corrected: the 0.9.0 entries claimed an 8-ones synthetic encoding on `eventId`; both pages now describe the actual 7-ones prefix on `eventSource.sourceId` and note that `eventId` always carries the SR id even for BetGenius events.

### Test count

456 → 461 passing (+5 net; removed one synthetic-payload test, added four `_strip_sportybet_source_prefix` unit tests + a mixed-phase eventSource test + a shared-SR regression test).

## [0.9.0] — 2026-05-14

Added a second provider — **BetGenius / Genius Sports** — alongside SportRadar for cross-bookmaker event matching. BetPawa and SportyBet expose Genius ids in their event-detail responses; the matcher now pairs events that share **any** provider id, so a BetPawa row with both SR and Genius widgets bridges a Betway row (SR only) with a SportyBet Genius event (Genius only).

### Added

- **`EventIds` dataclass** (`bookieskit.matching.EventIds`) — frozen `(sportradar: str | None, genius: str | None)` with a `keys()` helper that yields provider-prefixed strings (`"sr:NNN"`, `"genius:MMM"`) for the matcher's union-find.
- **`extract_event_ids(response, platform)`** — new unified entry point. Returns an `EventIds` per platform, populating whichever provider ids the payload carries. Re-exported from the top-level package.
- **BetPawa Genius widget extraction.** `widgets[type=GENIUSSPORTS].id` is parsed alongside `widgets[type=SPORTRADAR].id`. Both already present in captured prematch + live fixtures.
- **SportyBet `eventSource` + `11111111` decoding.** Primary path: `data.eventSource.{preMatchSource,liveSource}.{sourceType,sourceId}` — `BET_RADAR` → `sportradar`, `BET_GENIUS` → `genius`. Fallback: `data.eventId == "sr:match:11111111<genius_id>"` (the synthetic encoding SportyBet uses for BetGenius events). When both signals are present and disagree, a `WARNING` is logged via `bookieskit.matching.extractor` and `eventSource` wins.
- **`MatchedEvent.genius_id`** field on the matcher's output row. `sportradar_id` was relaxed from required `str` to `str | None = None` so Genius-only matches (no SR id on either side) can still produce a row.
- **Union-find matcher.** `match_events` now groups events by any shared provider id; transitive bridges (BetPawa SR ↔ Betway; BetPawa Genius ↔ SportyBet → all three in one group) are handled correctly. ~30 lines of DSU replaces the previous keyed-dict implementation.

### Changed

- `MatchedEvent.sportradar_id` is now `str | None = None` (was `str`). Pre-existing callers that construct `MatchedEvent(sportradar_id="x")` keep working unchanged. Callers that read `me.sportradar_id` as if always non-None should add a None-check if they want to support Genius-only matches.
- `extract_sportradar_id` is now a thin wrapper around `extract_event_ids(...).sportradar`. Behaviour for SR-only payloads is unchanged; an event with only a Genius widget (no SR) now correctly returns `None` (previously also `None` — same outcome via a cleaner path).

### Deferred

- **Bet9ja live BetGenius**. The captured live fixture is a SportRadar event (`D.A.PRV=60`, `D.A.BRMATCHID` populated). Without a Bet9ja-live Genius-event fixture we can't confirm the path for the Genius case, so `extract_event_ids(response, platform="bet9ja").genius` returns `None` today. Open an issue with a captured live Genius payload to land the wiring.

### Documentation

- `docs/matching.md` rewritten around the two-provider model: new `EventIds` section, full per-platform path table for both providers, SportyBet `11111111` encoding documented, union-find matcher described, `MatchedEvent` dataclass shape updated.
- `docs/betpawa.md` documents the parallel SPORTRADAR / GENIUSSPORTS widgets.
- `docs/sportybet.md` documents the `eventSource` typed paths plus the `11111111` synthetic encoding and the cross-check / warning behaviour.
- `docs/bet9ja.md` flags the deferred live-Genius wiring with the open-fixture caveat.

### Test count

428 → 456 passing (+28 across the `EventIds` dataclass contract, 7-platform `extract_event_ids` dispatch, BetPawa both-widgets fixture-bound, SportyBet eventSource + eventId fallback + cross-check warning, MatchedEvent `genius_id` field, and 4 union-find matcher scenarios including transitive bridge and Genius-only match).

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
