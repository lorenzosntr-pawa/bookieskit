# SportPesa fixture-resolved values

Captured from a warmed `www.ke.sportpesa.com` session on 2026-05-12.

## Endpoints

| Method | Path |
|---|---|
| get_event_detail (prematch + live) | `/api/upcoming/games?gameId={id}&sportId=1&section=markets&pag_count=1` (same endpoint serves both — `state` is `{}` for both) |
| get_event_markets | `/api/games/markets?games={id}&markets=all` |
| get_sports (live) | `/api/live/sports` → `{sports: [{id, name, eventNumber}, ...]}` |
| get_sports (prematch) | NO direct endpoint exists. Derive sports list either from `/api/live/sports` (catalogue is unified) or by walking `/api/upcoming/games`. |
| get_events (prematch) | `/api/upcoming/games?sportId={id}` → returns a flat list of game objects; default page size ≈ 30, supports `pag_count` param. |
| get_events (live) | `/api/highlights/{sportId}?live=true` → flat list of game objects with `marketsCount`. |
| get_competitions / get_tournaments | NO direct endpoint. Group `/api/upcoming/games?sportId={id}` by `competition.id` to derive the prematch tournament list. |

## Event-detail JSON shape

Response is a **list** of length 1 (not a dict with `data` key). Top-level keys on `[0]`:

```
id, betgeniusId, betradarId, smsId, hasCustomBet, competition, country,
sport, competitors, dateTimestamp, date, state, marketsCount, markets
```

| Item | JSON path | Notes |
|---|---|---|
| SR id | `[0].betradarId` | Numeric integer (e.g. `71348330`). No `sr:match:` prefix. |
| BetGenius id | `[0].betgeniusId` | Often `0` if not supplied. |
| Kickoff | `[0].dateTimestamp` | Unix milliseconds. `dateTimestamp / 1000` for seconds. Also `[0].date` ISO string available. |
| Home team | `[0].competitors[0].name` | Includes `competitors[0].id`. |
| Away team | `[0].competitors[1].name` | |
| Sport | `[0].sport.id` / `[0].sport.name` | e.g. `{id: 1, name: "Football"}` |
| Competition | `[0].competition.id` / `[0].competition.name` | Numeric id + human name. |
| Country | `[0].country` | Country object. |
| Markets count | `[0].marketsCount` | Integer. |
| Inline markets | `[0].markets` | Subset of full markets (more available via `/api/games/markets`). |
| State / live info | `[0].state` | **Empty dict `{}`** on both prematch and live captures — live-info (minute/score/period) is NOT in this response. Need a separate endpoint, not currently discovered. |

## Markets JSON shape

Top level is a **dict keyed by game id**: `{"8887261": [<market>, <market>, ...]}`. The value is a **list** (not a dict with `markets` key).

Each market entry:
```
id, specValue, name, order, columns, columnsApp, selections
```

| Field | Notes |
|---|---|
| `id` | Numeric SportPesa market id. |
| `name` | Human-readable name (e.g. `"3 Way"`, `"Total Goals Over/Under - Full Time"`). |
| `specValue` | Line value for parameterized markets (e.g. `2.5` for O/U). `0` for non-parameterized. |
| `selections` | List of selection dicts: `{id, name, odds, shortName, specValue}`. |

Selection fields:
| Field | Notes |
|---|---|
| `shortName` | Canonical outcome key — match against `OutcomeMapping.sportpesa`. |
| `name` | Human-readable (e.g. `"Gold Coast Knights W"`, `"OVER 0.50"`). |
| `odds` | Decimal odds as string (e.g. `"1.04"`). |
| `specValue` | Selection-level line override; usually matches the parent market's `specValue`. |

No per-selection `probability` or `void_probability` fields — both stay `None` regardless of mode.

## Canonical market mappings

| Canonical id | SportPesa market id | SportPesa name | Outcome shortNames |
|---|---|---|---|
| `1x2_ft` | `10` | `3 Way` | home=`1`, draw=`X`, away=`2` |
| `over_under_ft` | `52` | `Total Goals Over/Under - Full Time` | over=`OV`, under=`UN` |
| `btts_ft` | `43` | `Both Teams To Score` | yes=`Yes`, no=`No` |
| `double_chance_ft` | `46` | `Double Chance` | home_draw=`1X`, draw_away=`X2`, home_away=`12` |

The spec's best-evidence defaults (`1`/`18`/`29`/`10`, all string-based outcome names like `"Over"`/`"Yes"`) were WRONG — SportPesa uses its own integer market id namespace and `OV`/`UN`/`Yes`/`No`/`1`/`X`/`2`/`1X`/`X2`/`12` shortNames.

## Notes

- **Live-info gap.** Live match minute/period/score are NOT in the event-detail response. The `state` field is empty on both captures. A separate live-info endpoint exists but wasn't discovered in this capture pass — `_live_info_sportpesa` returns `_EMPTY_LIVE_INFO` in all cases until that endpoint is found. **Not blocking** for prematch flows, market normalization, SR-id matching, or `count_5bookies.py`.
- **No probability fields.** Selections carry `id`, `name`, `odds`, `shortName`, `specValue` — no `probability` or `void_probability`. SportPesa joins Betway / Bet9ja as platforms where both probability fields stay `None`.
- **Markets endpoint returns more markets than event-detail.** The captured prematch event has `marketsCount=22` in its detail response, but `/api/games/markets` returned 59 market entries (parameterized markets contribute multiple entries per id). Always prefer `get_event_markets` for parsing.
