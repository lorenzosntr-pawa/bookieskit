# Betika fixture-resolved values

Captured from `api.betika.com` / `live.betika.com` on 2026-05-13. No auth or warmed cookies required — Betika's API is open.

## Endpoints

| Method | Path |
|---|---|
| get_sports | `/v1/sports` |
| get_matches (prematch) | `/v1/uo/matches?sport_id=N&page=K&limit=100[&sub_type_id=M][&competition_id=L][&match_id=X]` |
| get_live_matches | `https://live.betika.com/v1/uo/matches?sport_id=N&page=K&limit=100[&match_id=X]` |
| get_event_detail (prematch) | `/v1/uo/matches?match_id=X&limit=1` |
| get_event_detail (live) | `https://live.betika.com/v1/uo/matches?match_id=X&limit=1` |

## Event-detail JSON shape

Response shape: `{"data": [<match>], "meta": {...}}`. `data` is always a list (length 1 when filtering by `match_id`).

| Item | JSON path | Notes |
|---|---|---|
| SR id | `data[0].parent_match_id` | Bare numeric, no `sr:match:` prefix. **Type inconsistency:** string in prematch (e.g. `"70784812"`), integer in live (e.g. `71463790`). Extractor handles both via `str()` conversion. Verified by cross-reference with SportyBet (`70784812` = Man City vs Crystal Palace on both). |
| Betika internal id | `data[0].match_id` | Different from `parent_match_id`. Used in URLs / lookups. |
| Kickoff | `data[0].start_time` | String `"YYYY-MM-DD HH:MM:SS"` (naive ISO, UTC). |
| Home team | `data[0].home_team` | |
| Away team | `data[0].away_team` | |
| Sport id | `data[0].sport_id` | Type varies (str / int). |
| Competition id | `data[0].competition_id` | String. |
| Embedded markets | `data[0].odds[]` | One market group by default (typically 1X2); filter via `&sub_type_id=N` to fetch other markets. |

## Live-info JSON keys

The live response carries a much wider top-level object than prematch; the in-play scoreboard fields are exposed directly on `data[0]`.

| Item | JSON path | Notes |
|---|---|---|
| Match minute | `data[0].match_time` | String `"MM:SS"` (e.g. `"35:51"`). Parse the minute portion as int. |
| Period | `data[0].event_status` | Human label (e.g. `"1st half"`). Lower-cased status also available via `match_status` (`"ACTIVE"`) and numeric `live_match_status` (`1`). |
| Home score | derived from `data[0].current_score` | String `"H:A"` (e.g. `"0:0"`); split on `":"` and take index 0. Alternatives: `ht_score`, `ft_score` (both `"-:-"` while live), or per-period via `set_score[].score`. |
| Away score | derived from `data[0].current_score` | Same string; take index 1 after split. |

Additional live-only fields available on the same object: `bet_status`, `bet_stop_reason`, `betradar_timestamp`, `home_corners` / `away_corners`, `home_yellow_card` / `away_yellow_card`, `home_red_card` / `away_red_card`, `set_score` (list of per-period scores), `will_go_live`, `streamable`.

## Market sub_type_id mappings (confirmed)

| Canonical | `sub_type_id` | Outcome `display` strings |
|---|---|---|
| `1x2_ft` | `"1"` | `"1"`, `"X"`, `"2"` |
| `over_under_ft` | `"18"` | `"OVER N.5"`, `"UNDER N.5"` (line embedded in label) |
| `btts_ft` | `"29"` | `"Yes"` / `"No"` (case-mixed: also seen `"YES"`/`"NO"`) |
| `double_chance_ft` | `"10"` | `"1/X"`, `"X/2"`, `"1/2"` |
| `1x2_ht` (1st Half) | `"60"` | Not wired in v1 |

Parser MUST match outcomes case-insensitively (the parser's `_resolve_outcome_betika` lowercases both sides before comparing).

## OU `special_bet_value` format

The Over/Under selection's `special_bet_value` is NOT a bare numeric string. Captured shape:

```
{"display": "OVER 2.5", "odd_value": "2.15", "special_bet_value": "total=2.5"}
```

The parser's `_parse_betika_line` handles both formats (`"2.5"` and `"total=2.5"`) plus the display-fallback path (`"OVER 2.5"` → 2.5) when `special_bet_value` is empty or malformed.

## Captured `markets.json` fixture

`tests/fixtures/event_info/betika/markets.json` is the output of `Betika.get_event_markets(event_id="10908218")` — Valencia vs Rayo Vallecano, captured 2026-05-14. Carries all four universal market groups merged into one `data[0].odds[]` array. Used by the fixture-bound parser tests to exercise the real response shape for every canonical market in one go.

## Notes

- No probability fields on selections. `_parse_betika` accepts `probability` kwarg but both `Outcome` probability fields stay `None`.
- API is open: no Cloudflare, no warmed cookies, no rate limit observed.
- Country is informational: `api.betika.com` serves the same catalogue regardless of country code in the URL or any `country=` header / param.
- Captured event (prematch): Man City vs Crystal Palace (parent_match_id="70784812"), kickoff 2026-05-13 22:00:00 UTC.
- Captured event (live): Ulinzi Stars vs Leopards (parent_match_id=71463790), kickoff 2026-05-13 16:00:00 UTC.
