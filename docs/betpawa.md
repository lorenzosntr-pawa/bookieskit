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
  "withRegions": [],
  "onlyMeta": [
    {
      "category": {"id": "2", "name": "Football"},
      "eventCounts": {"live": 5, "upcoming": 1000}
    }
  ]
}
```

### `get_countries(sport_id)`

Returns regions/countries for a sport.

**Endpoint:** `GET /api/sportsbook/v3/categories/list/{sport_id}`

**Response:**
```json
{
  "withRegions": [
    {
      "category": {"id": "2", "name": "Football"},
      "regions": [
        {
          "region": {"id": "1", "name": "England"},
          "competitions": [
            {"competition": {"id": "11965", "name": "Premier League"}}
          ]
        }
      ]
    }
  ]
}
```

### `get_tournaments(sport_id)`

Same endpoint as `get_countries` — tournaments are nested under regions.

### `get_events(tournament_id, sport_id="2", event_type="UPCOMING", skip=0, take=100)`

Returns events for a competition.

**Endpoint:** `GET /api/sportsbook/v3/events/lists/by-queries?q={encoded_json}`

**Response:**
```json
{
  "responses": [
    {
      "responses": [
        {
          "id": "32299257",
          "participants": [
            {"name": "Manchester City", "role": "HOME"},
            {"name": "Liverpool", "role": "AWAY"}
          ],
          "competition": {"id": "11965", "name": "Premier League"},
          "widgets": [{"type": "SPORTRADAR", "id": "sr:match:61300947"}]
        }
      ]
    }
  ]
}
```

### `get_event_detail(event_id)`

Returns full event with all markets and odds.

**Endpoint:** `GET /api/sportsbook/v3/events/{event_id}`

**Response:**
```json
{
  "id": "32299257",
  "participants": [
    {"name": "Manchester City", "role": "HOME"},
    {"name": "Liverpool", "role": "AWAY"}
  ],
  "markets": [
    {
      "marketType": {"id": "3743", "name": "1X2"},
      "row": [
        {
          "prices": [
            {"name": "1", "price": 1.95},
            {"name": "X", "price": 3.50},
            {"name": "2", "price": 2.10}
          ]
        }
      ]
    }
  ],
  "widgets": [
    {"type": "SPORTRADAR", "id": "sr:match:61300947"}
  ]
}
```
