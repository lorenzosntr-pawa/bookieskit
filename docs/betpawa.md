# BetPawa

## Supported Countries

| Code | Domain |
|------|--------|
| ng | betpawa.ng |
| gh | betpawa.com.gh |
| ke | betpawa.co.ke |
| ug | betpawa.co.ug |
| tz | betpawa.co.tz |
| zm | betpawa.co.zm |

## Methods

### `get_sports()`

Returns all sport categories.

**Endpoint:** `GET /api/sportsbook/v3/categories/list/all`

**Response:**
```json
{
  "categories": [
    {"id": "2", "name": "Football"},
    {"id": "3", "name": "Basketball"}
  ]
}
```

### `get_countries(sport_id)`

Returns regions/countries for a sport.

**Endpoint:** `GET /api/sportsbook/v3/categories/list/{sport_id}`

**Response:**
```json
{
  "id": "2",
  "name": "Football",
  "regions": [
    {
      "id": "1",
      "name": "England",
      "competitions": [{"id": "11965", "name": "Premier League"}]
    }
  ]
}
```

### `get_tournaments(sport_id, country_id=None)`

Same endpoint as `get_countries` — tournaments are nested under regions.

### `get_events(tournament_id, sport_id="2", event_type="UPCOMING", skip=0, take=100)`

Returns events for a competition.

**Endpoint:** `GET /api/sportsbook/v3/events/lists/by-queries?q={encoded_json}`

**Response:**
```json
{
  "results": [
    {
      "id": "32299257",
      "homeTeam": "Manchester City",
      "awayTeam": "Liverpool",
      "kickoffTime": 1704067200000,
      "markets": [...]
    }
  ],
  "totalCount": 50
}
```

### `get_event_detail(event_id)`

Returns full event with all markets and odds.

**Endpoint:** `GET /api/sportsbook/v3/events/{event_id}`

**Response:**
```json
{
  "id": "32299257",
  "homeTeam": "Manchester City",
  "awayTeam": "Liverpool",
  "markets": [
    {
      "id": "3743",
      "name": "1X2 - Full Time",
      "row": [
        {
          "prices": [
            {"name": "1", "odds": 1.95},
            {"name": "X", "odds": 3.50},
            {"name": "2", "odds": 2.10}
          ]
        }
      ]
    }
  ],
  "widgets": [
    {"type": "SPORTRADAR", "value": "sr:match:61300947"}
  ]
}
```
