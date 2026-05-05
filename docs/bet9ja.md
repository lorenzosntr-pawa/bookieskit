# Bet9ja

## Supported Countries

| Code | Domain |
|------|--------|
| ng | sports.bet9ja.com |

## Rate Limiting

Bet9ja is rate-limit sensitive. Defaults:
- Max concurrent: 15
- Request delay: 25ms

## Methods

### `get_sports()`

Returns full sport/category/tournament hierarchy in one call.

**Endpoint:** `GET /desktop/feapi/PalimpsestAjax/GetSports?DISP=0&v_cache_version=1.301.2.225`

**Response:**
```json
{
  "R": "OK",
  "D": {
    "PAL": {
      "sports": [{"id": "1", "name": "Football"}]
    }
  }
}
```

### `get_countries()` / `get_tournaments()`

Same as `get_sports()` — Bet9ja returns the full hierarchy in one call.

### `get_events(tournament_id)`

Returns events for a tournament group.

**Endpoint:** `GET /desktop/feapi/PalimpsestAjax/GetEventsInGroup`

**Response:**
```json
{
  "R": "OK",
  "D": {
    "E": [
      {"id": "707096003", "name": "Man City vs Liverpool"}
    ]
  }
}
```

### `get_event_detail(event_id)`

Returns full event with flat odds structure.

**Endpoint:** `GET /desktop/feapi/PalimpsestAjax/GetEvent?EVENTID={id}`

**Response:**
```json
{
  "R": "D",
  "D": {
    "EXTID": "sr:match:61300947",
    "O": {
      "S_1X2_1": "1.50",
      "S_1X2_X": "3.20",
      "S_1X2_2": "2.10",
      "S_OU@2.5_O": "1.80",
      "S_OU@2.5_U": "2.00"
    }
  }
}
```

## Response Codes

- `"R": "OK"` or `"R": "D"` = success
- `"R": "E"` = not found / error

## Odds Key Format

```
S_{MARKET}[@{PARAM}]_{OUTCOME}

Examples:
  S_1X2_1          -> 1X2 Home
  S_1X2_X          -> 1X2 Draw
  S_OU@2.5_O       -> Over 2.5
  S_AH@-0.5_1      -> Asian Handicap -0.5 Home
  S_GGNG_Y         -> BTTS Yes
```
