# ElephantBet

ElephantBet runs the BtoBet `Sb.WebApi` v8.2.0.29 platform (Aspire Global).
Unlike a BetPawa white-label, it is a genuinely independent platform — no
shared client or brand plumbing with `bookmakers/betpawa.py`.

## Supported Countries

| Code | Country | API host | Status |
|------|---------|----------|--------|
| `mz` | Mozambique | `https://sports-core.elephantbet.com` | **working** — `DOMAINS` |

ElephantBet also operates Angola (`ao`), Sierra Leone (`sl`) and Malawi (`mw`)
brand sites, but their API hosts (`sports-core.elephantbet.co.ao`,
`sports-core.elephantbet.sl`) sit behind a WAF/edge layer that returns `403`
to non-browser clients — the same host class that serves BetPawa's `ao` and
`sl` jurisdictions fine, so this is a bot-detection block, not geo-blocking.
Malawi resolves no API host at all (brand site only). None of the three are
verifiable, so none are listed in `DOMAINS`; recording an unverified 403
response as a supported country would repeat a mistake this repo has already
paid for once (the Betika Double Chance 1Up entry, corrected in #54).

## Methods

| Method | HTTP | Path | When to use |
|--------|------|------|-------------|
| `get_sports()` | GET | `/rest/FEWFixture/Sports` | Full sport catalogue (167 entries incl. virtuals/Zoom — filter on `c`). |
| `get_countries(sport_id)` | GET | `/rest/FEWFixture/FixturesMenu` | Whole sport → category → tournament menu in one call. `sport_id` is accepted for interface symmetry; callers filter `s[]` themselves. |
| `get_tournaments(sport_id)` | (same as get_countries) | — | Alias — same payload as `get_countries`. |
| `get_events(tournament_id, limit=50)` | GET | `/rest/FEMobile/GetGroupedMatches` | Events (with main markets) for one tournament. |
| `get_live_events(sport_id=None)` | GET | `/rest/FEMobile/GetLiveMatchesMetaData` | Every in-play match across all sports; `sport_id` filters client-side. |
| `get_event_detail(event_id)` | GET | `/rest/FEWMatches/MatchOdds` | Full markets/odds for one match. |
| `get_markets(event_id)` | (calls `get_event_detail`) | — | Inherited convenience: returns `list[NormalizedMarket]`. |
| `get_sportradar_id(event_id)` | (calls `get_event_detail`) | — | Inherited convenience: extracts `brid`. |

Every endpoint requires the `Culture` query parameter (`pt` for `mz`), injected
automatically by the client — see Quirks.

### `get_sports() -> dict`

Raw JSON list; each entry has `id`, `n` (localised name) and `c` (stable
slug, e.g. `"soccer"`). Filter on `c`, not position — the catalogue mixes in
virtual and Zoom products.

### `get_countries(sport_id: str = "1") -> dict`

Raw JSON with `s[]` (sports), each carrying `i[]` (categories), each carrying
`i[]` (tournaments).

### `get_events(tournament_id: str, limit: int = 50) -> dict`

Raw JSON list of sports, each with `t[]` tournaments, each with `m[]`
matches. Match fields: `mid` (match id), `brid` (SportRadar id), `ht`/`at`
(team names), `d` (kickoff, `"YYYY-MM-DD HH:MM"`), `sid` (sport id), `tid`
(tournament id).

### `get_event_detail(event_id: str) -> dict`

Raw JSON shaped `{"s": ..., "t": [{"o": [<market>, ...]}]}` — markets nested
under display tabs (`t[].o[]`), each market's outcomes under `.m[]`. Note
this response is markets/odds-focused: its top-level `mid`/`brid`/`ht`/`at`/`d`
fields are `null` — team names and kickoff for cross-referencing come from
`get_events` (the `GetGroupedMatches` listing), not from event detail.

### Inherited: `get_markets(event_id, registry=None) -> list[NormalizedMarket]`

Calls `get_event_detail`, then `parse_markets(response, platform="elephantbet")`.
**Nine** canonical soccer markets are registered:

| Canonical | ElephantBet id | Market name |
|---|---|---|
| `1x2_ft` | `3` | 1X2 |
| `over_under_ft` | `29` | Acima / Abaixo |
| `btts_ft` | `7` | Ambas as equipas a marcar |
| `double_chance_ft` | `17` | HIPÓTESE DUPLA |
| `1x2_corners_ft` | `111` | QUAL DAS EQUIPAS TERÁ MAIS CANTOS? |
| `over_under_corners_ft` | `107` | Total de cantos DO JOGO |
| `over_under_bookings_ft` | `73` | Total Cartões Partida |
| `home_over_under_ft` | `353` | Totais Equipa da casa |
| `away_over_under_ft` | `352` | Totais Equipa de fora |

The captured fixture carries **153** markets, so this is deliberate breadth,
not the limit of what ElephantBet publishes. Use
`python -m bookieskit.devtools discover --unmapped` to enumerate the rest.

**Registered does not mean present on every event.** Sampling eight live
Premier League fixtures on 2026-08-25:

| Markets | Present |
|---|---|
| `1x2_ft`, `over_under_ft`, `btts_ft`, `double_chance_ft`, `home_over_under_ft`, `away_over_under_ft` | **8/8** |
| `over_under_corners_ft` | 1/8 |
| `1x2_corners_ft`, `over_under_bookings_ft` | 0/8 |

The six core markets are reliably there; corners and bookings are sparse and
appear on a minority of fixtures. Their mappings are verified against the
committed capture, which does carry all three — a caller seeing no corner
market on a given event is looking at ElephantBet's offering, not a mapping
gap.

Three canonicals were checked against the capture and are **not offered** in a
form that matches them:

- `1x2_bookings_ft` — only per-team card Over/Under exists (ids `12228`,
  `12236`); there is no "which team gets most cards" 1X2.
- `next_goal_ft` — the nearest markets are first-goal-and-final-result (`37`)
  and minute-of-first-goal (`326`), neither of which is the canonical's
  home/none/away shape.
- `1x2_1up_ft` / `1x2_2up_ft` / `double_chance_1up_ft` — no early-payout
  markets of any kind in the capture.

`2way_handicap_ft` is **deferred, not absent**. ElephantBet's Asian handicap
(id `23`) records each outcome's line from that outcome's own perspective —
home `sbv=1.5` pairs with away `sbv=-1.5`. Grouping by raw `sbv`, as the
parser does today, would pair home `+1.5` with away `+1.5`, which are two
different handicap lines. Mapping it needs sign normalisation in the parser,
so it gets its own increment. Its 3-way European sibling (id `27`, which has
an `X` outcome) is out of the canonical set entirely.

### Inherited: `get_sportradar_id(event_id) -> str | None`

Calls `get_event_detail`, then reads `brid`. Note: as above, `brid` is `null`
on the `MatchOdds` event-detail response in captures to date — use
`extract_sportradar_id` (or `extract_event_ids`) against a `get_events`
match object instead, where `brid` is populated.

## Live (in-play)

`get_live_events()` returns every live match in one call — BtoBet has no
per-sport live endpoint, so `sport_id` filters client-side on each entry's
`sid`. A sample run returned 40 matches across 10 sports (Soccer, Basketball,
Table tennis, Snooker, Cricket, Baseball, Volleyball, plus eSoccer,
eBasketball and "Rush Football" virtuals).

Each entry carries in-play state, which `extract_live_info` reads:

| Field | Meaning |
|---|---|
| `ms` | localised period name (`"1ª Parte"`, `"Pausa"`) |
| `mt` | elapsed minute |
| `sc` | score, `"home:away"` |
| `ss` | set/period score |

### The `brid` / `obrid` trap

**The two feeds disagree about which field holds the SportRadar id.** Reading
`brid` blindly corrupts cross-book matching:

| Feed | `brid` | `obrid` |
|---|---|---|
| Prematch (`GetGroupedMatches`) | **the SportRadar id** | `None` |
| Live (`GetLiveMatchesMetaData`) | BtoBet-internal id | **the SportRadar id**, or `None` |

Verified: prematch `brid="72221172"` and live `obrid=73842300` both resolve on
Betway to the same fixtures ("Fulham FC vs. Chelsea FC", "KT Sonicboom vs.
Mobis Phoebus"), while a live `brid` matches nothing anywhere.

Length is **not** a safe discriminator — live virtual events carry 7-digit
`brid` values that look like real 8-9 digit SportRadar ids. In-play state is:
every live entry carries `ms`/`mt`/`sc`/`ss` and no prematch entry does
(40/40 and 0/21 across the committed captures). `extract_event_ids` uses that
rule, so on a live entry only `obrid` is trusted and an entry without one
correctly yields `None`. Half the live sample had no `obrid` at all — mostly
virtuals, which SportRadar does not cover.

### Live prices are not available yet

Live *markets* are not parseable this increment. `FEWMatches/MatchOdds` and
`FEMobile/GetMatchTabs` both answer `204 No Content` for a live match id, and
`FEWHome/GetLiveMatchTabs` ignores `MatchID` entirely (it is a global,
sport-keyed tab config). Prices appear to live in each entry's compressed
`aot` string; decoding it is its own increment.

## Quirks

- **`Culture` is mandatory.** Every endpoint returns `400` (an RFC-9110
  problem document, not a useful body) without it. The client always sends
  it (`pt` for `mz`) so callers never have to think about it.
- **The SPA's endpoints differ from similarly-named ones in the published
  Swagger spec** (`/swagger/v1/swagger.json`, 194 endpoints, no auth
  required). `FEWFixture/TournamentMatchOdds` and `FEMobile/GetMatchOdds`
  look like the natural fits for events-with-odds and single-event-detail,
  but both answer `204 No Content` for real arguments. The endpoints this
  client uses (`FEMobile/GetGroupedMatches`, `FEWMatches/MatchOdds`) are the
  ones the brand's own SPA actually calls, verified to return data.
- **Odds arrive as strings.** `o` on each outcome is `"3.96"`, not a float.
- **Over/Under carries its line in the outcome's `sbv` field, not the market
  id.** Market id `29` ("Acima / Abaixo") spans every line — `2.5`, `1.5`,
  `3.5`, etc. — with each outcome distinguished by `sbv` (e.g. `"2.5"`). One
  registered `elephantbet_id` therefore covers every O/U line, unlike
  platforms that mint a separate market id per line.
- **`eon` holds `{{HomeTeam}}` / `{{AwayTeam}}` placeholders**, not resolved
  team names, on 1X2 outcomes (`null` on outcomes that don't reference a
  team, e.g. the draw). Team names for display come from `get_events`
  (`ht`/`at`), not from this field.
- **`brid` is the SportRadar id** (bare numeric string, no `sr:match:`
  prefix) — carried on `get_events` match objects, not on `get_event_detail`.
  Verified against Betway event `72221172`, which resolves to the same
  fixture ("Fulham FC vs. Chelsea FC"), and against MSport's
  `sr:match:72221172`. This means ElephantBet participates in real
  cross-book matching via `extract_event_ids(..., platform="elephantbet")` —
  unlike BetPawa and SportPesa, which have no reverse SR lookup, ElephantBet
  simply has not had one built yet (its match id `mid` is distinct from
  `brid`, and no `mid`-from-`brid` index exists in this increment — see the
  resolver's `elephantbet` adapter, which records a skip on `resolve` for
  exactly that reason).
- **Live state is not mapped this increment.** No live fixture has been
  captured yet to confirm field names, so `extract_live_info(..., platform="elephantbet")`
  always returns the empty `LiveInfo`.

## Recipes

### Markets and SR id from one event

```python
import asyncio
from bookieskit import ElephantBet

async def main():
    async with ElephantBet(country="mz") as eb:
        markets = await eb.get_markets(event_id="5998731")
        for m in markets:
            outcomes = m.outcomes if m.outcomes else (m.lines.get(2.5) if m.lines else [])
            print(f"  {m.name}: {len(outcomes)} outcomes")

asyncio.run(main())
```

### Cross-reference the SR id via the events listing

```python
import asyncio
from bookieskit import ElephantBet
from bookieskit.matching import extract_event_ids

async def main():
    async with ElephantBet(country="mz") as eb:
        raw = await eb.get_events(tournament_id="1428062")
        match = raw[0]["t"][0]["m"][0]
        ids = extract_event_ids(match, platform="elephantbet")
        print(f"SR id: {ids.sportradar}")

asyncio.run(main())
```

## Future increments

- **`get_live_events()`** (`GET /rest/FEMobile/LiveUpcomingFixture`) was in
  the original design spec but was not implemented this increment — no
  in-play fixture has been captured to confirm the response shape. This is
  a deliberate scope cut, not an oversight; pair with the "Live state is not
  mapped this increment" quirk above (`extract_live_info` returns empty
  `LiveInfo`) when picking this up.

## See also

- [docs/markets.md](markets.md) — registry, builtins, custom mappings.
- [docs/matching.md](matching.md) — `extract_sportradar_id`, `match_events`.
