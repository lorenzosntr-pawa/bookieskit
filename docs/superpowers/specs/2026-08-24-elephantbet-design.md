# ElephantBet — new bookmaker client (design)

**Date:** 2026-08-24
**Status:** design, awaiting owner review
**Scope:** add ElephantBet as the eighth bookmaker in `bookieskit`, first
increment covering core soccer markets on Mozambique.

## Context

bookieskit covers seven African bookmakers. ElephantBet is a competitor in
markets bookieskit already tracks — notably Mozambique, a BetPawa
jurisdiction — and the owner wants it in the library, with a further handful
of bookmakers to follow.

The owner's opening framing was that ElephantBet might cover "new brands from
BetPawa". It does not: reconnaissance confirmed a genuinely independent
platform. That distinction mattered, because a BetPawa white-label would have
been a brand entry on the existing client rather than a new subsystem.

## Findings

Established by live reconnaissance on 2026-08-24. Every claim below was
observed, not inferred.

| | |
|---|---|
| Platform | **BtoBet `Sb.WebApi` v8.2.0.29** (Aspire Global) |
| API host (MZ) | `https://sports-core.elephantbet.com` |
| Contract | **Published OpenAPI** at `/swagger/v1/swagger.json` — 194 endpoints |
| Auth | **None** for catalogue and odds |
| Locale | Portuguese; `Culture` is a required query parameter |
| Front end | Hash-routed SPA, brand `65k`, served from `fecdn.btobet.com` |

The marketing site (`www.elephantbet.co.mz`) is WordPress and carries no API
references; the sportsbook SPA and its API host were found via the app shell
at `fecdn.btobet.com/app/sb/spa/65k`.

Validated response, `GET /rest/FEWFixture/Sports?culture=pt` → 200, 167 sports:

```json
[{"id": 1, "n": "Futebol", "c": "soccer", "ni": 0, "t": 3, "cl": "sb-green"}]
```

The 167-entry catalogue includes virtual and Zoom products (e.g. `zoom-soccer`),
so sport selection must filter on the `c` slug rather than trust the count.

### SignalR is out of scope

The platform also exposes `/signalr` for live push. It is deliberately not
used. `BaseBookmaker` is a request/response HTTP client with retry, pooling and
a concurrency semaphore; a persistent-connection feed is a different lifecycle
that would have to be modelled across the whole library. The REST endpoints
cover prematch and live, which is what the library needs.

## Jurisdictions

ElephantBet operates in four BetPawa jurisdictions. Only one is usable.

| CC | Country | Brand site | API host | Status |
|----|---------|-----------|----------|--------|
| `mz` | Mozambique | `www.elephantbet.co.mz` (200) | `sports-core.elephantbet.com` | **working, 167 sports** |
| `ao` | Angola | `www.elephantbet.ao` (200) | `sports-core.elephantbet.co.ao` | exists, **403** |
| `sl` | Sierra Leone | `www.elephantbet.sl` (403) | `sports-core.elephantbet.sl` | exists, **403** |
| `mw` | Malawi | `www.elephantbet.mw` (401) | none resolved | brand site only |

The 403s are an edge/WAF layer rejecting non-browser clients, not geo-blocking:
BetPawa's own `ao` and `sl` jurisdictions answer normally from the same host.

**Decision: `DOMAINS` ships `mz` only.** Adding `ao`, `sl` or `mw` on the
strength of a 403 would record an unverified guess as fact — the mistake this
repo has already paid for once (see the Betika entry in the Double Chance 1Up
work, corrected in #54). They are documented as known-but-unverified, with the
probe recorded so re-checking is one command.

## Goals

1. `ElephantBet` client usable exactly like the other seven — `async with`
   and sync `with`, same retry/rate-limit behaviour.
2. Core soccer markets normalised through the existing `MarketRegistry`.
3. Cross-book matching **if** the payload exposes provider ids (see Risks).
4. Documented in `docs/elephantbet.md` to the standard of the other books.

## Non-goals (this increment)

- SignalR live push.
- `SearchEventsByName`. ElephantBet would be the first book in the library
  with native event search; that is a new capability on `BaseBookmaker` and
  deserves its own design, not a smuggled-in extra.
- Corners, bookings, handicaps, next-goal, per-team O/U.
- Basketball and tennis.
- Jurisdictions beyond `mz`.

## Architecture

The client follows the existing seven-book pattern exactly. No new
abstractions, no changes to `BaseBookmaker`.

| Piece | File | Change |
|---|---|---|
| Client | `bookmakers/elephantbet.py` | new — `DOMAINS`, `DEFAULT_HEADERS`, `NAME`, `PLATFORM_KEY`, methods |
| Package export | `bookmakers/__init__.py`, `__init__.py` | add `ElephantBet` |
| Mapping fields | `markets/types.py` | `elephantbet_id` on `MarketMapping`, `elephantbet` on `OutcomeMapping` |
| Market ids | `markets/builtin_mappings.py` | ids on the four core soccer markets; empty elsewhere |
| Parser arm | `markets/parser.py` | `_parse_elephantbet` + dispatch entry |
| Event info | `event_info.py` | kickoff / participants / live-info extractors + dispatch |
| Matching | `matching/extractor.py` | provider-id extraction (conditional — see Risks) |
| Harness | `devtools/{adapters,resolver,sports,coverage}.py` | adapter, `ALL_BOOKS`, sport-id row |
| Config | `config.py` | `ELEPHANTBET_MAX_CONCURRENT`, `ELEPHANTBET_REQUEST_DELAY` |
| Fixtures | `tests/fixtures/event_info/elephantbet/` | captured payloads |
| Docs | `docs/elephantbet.md`, `README.md`, `CHANGELOG.md` | per docs-sync gate |

### Client method mapping

| Method | Endpoint |
|---|---|
| `get_sports()` | `GET /rest/FEWFixture/Sports` — **validated** |
| `get_countries(sport_id)` | `GET /rest/FEWFixture/FixturesMenu` |
| `get_tournaments(sport_id)` | same endpoint (alias, as BetPawa does) |
| `get_events(tournament_id)` | `GET /rest/FEWFixture/TournamentMatchOdds` |
| `get_event_detail(event_id)` | `GET /rest/FEMobile/GetMatchOdds` |
| `get_live_events(sport_id)` | `GET /rest/FEMobile/LiveUpcomingFixture` |

`Culture` is required on most endpoints and is injected by the client
(`pt` for `mz`) rather than pushed onto callers. `FixturesMenu` also accepts
`BrandID` and `TimeOffset`; both are set from client config.

### Adding an eighth platform: known cost

`MarketMapping` and `OutcomeMapping` carry one field per bookmaker. Adding
ElephantBet therefore edits every mapping literal in `builtin_mappings.py`
(22 markets, ~66 outcome blocks) purely to add empty placeholders, plus the
18 source files that name platforms explicitly.

This is accepted deliberately. The owner confirmed the pipeline is a handful
of bookmakers (2–4), not a wave; a dict-keyed platform model would be the
right answer for 5–15 books and the wrong answer for 3. Revisit if the list
grows.

## Data flow

```
get_event_detail(event_id)
  -> GET /rest/FEMobile/GetMatchOdds?matchId=...&Culture=pt
  -> raw JSON
  -> parse_markets(payload, platform="elephantbet")
       -> _parse_elephantbet: walk markets, look up (platform, market_id)
          in MarketRegistry, map outcome labels to canonical names
  -> list[NormalizedMarket]
```

## Error handling

Inherited from `BaseBookmaker` unchanged: `ResponseError` on non-2xx,
`TimeoutError`, `RateLimitError` on 429, retry with backoff on
`RETRYABLE_STATUS_CODES`. Two ElephantBet-specific cases:

- **Missing `Culture`** returns `400` with an RFC-9110 problem document, not a
  useful body. The client always sends `Culture`, and a regression test pins
  that so it cannot regress into a silent 400.
- **WAF `403`** on non-`mz` hosts. Not handled specially — `UnsupportedCountryError`
  fires first, because those countries are not in `DOMAINS`.

## Testing

Follows the repo's existing discipline: ids and outcome labels lifted from real
captured payloads, never guessed; fixtures committed in the same PR as the code
that reads them.

1. **Client tests** (`tests/test_elephantbet.py`) — respx-mocked URL, header
   and country-resolution assertions, mirroring `test_betpawa.py`. Includes a
   test that `Culture` is always sent.
2. **Parser tests** (`tests/test_parser_elephantbet.py`) — real captured
   fixtures under `tests/fixtures/event_info/elephantbet/`, asserting each of
   the four canonical markets resolves with the fixture's actual odds.
3. **Coverage golden snapshot** — `tests/devtools/test_coverage.py` gains the
   `elephantbet` column.
4. **Live smoke, manual** — `get_sports()` against `mz`, in-region.

Mocked tests cannot detect upstream drift; that is what the canary is for.
This was demonstrated during the v3→v4 BetPawa outage (#50), where 949 mocked
tests stayed green while every live call 404'd.

## Risks and open questions

1. **Provider ids — resolved first, before any other implementation task.**
   bookieskit's cross-book value rests on SportRadar / Genius ids. Whether
   `GetMatchOdds` exposes them is unknown. If it does, ElephantBet joins
   `match_events()` and the audit harness. If it does not, it is a standalone
   scrape target with the same limitation SportPesa and Betika already carry.
   This changes scope, not feasibility, and the answer must be recorded in
   `docs/elephantbet.md` either way.
2. **Market/odds payload shape is unknown.** Only the catalogue endpoint has
   been validated. The first implementation step captures one real
   `GetMatchOdds` payload; the four market ids come from that capture.
3. **WAF exposure.** `ao` and `sl` are already 403 from this host. If `mz`
   later develops the same edge behaviour, ElephantBet joins SportyBet (#52)
   as unreachable. The canary would surface it.
4. **Catalogue noise.** 167 sports including virtuals and Zoom products means
   sport selection must filter on the `c` slug.

## Success criteria

- `ElephantBet("mz").get_sports()` returns the live sport catalogue in-region.
- `parse_markets(payload, platform="elephantbet")` resolves `1x2_ft`,
  `over_under_ft`, `btts_ft` and `double_chance_ft` from a committed fixture.
- `python -m bookieskit.devtools coverage` shows an `elephantbet` column, and
  `docs/coverage.md` is byte-identical to its output.
- `ruff check .` clean; full suite green on 3.11 / 3.12 / 3.13.
- Whether ElephantBet supports cross-book matching is documented as a fact,
  not left open.

## Future increments

1. Provider-id matching, if payloads permit.
2. Corners, bookings, handicaps, next-goal, per-team O/U.
3. Basketball and tennis.
4. `SearchEventsByName` as a new library capability — own design.
5. `ao` / `sl` / `mw` jurisdictions, if a request path past the WAF is found.
