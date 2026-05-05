# SportyBet

## Supported Countries

| Code | Domain | API Path |
|------|--------|----------|
| ng | sportybet.com | /api/ng/... |
| gh | sportybet.com | /api/gh/... |
| ke | sportybet.com | /api/ke/... |

SportyBet uses the same domain for all countries — the country is in the API path.

## Methods

### `get_sports()`

Returns sports with full category/tournament hierarchy.

**Endpoint:** `GET /api/{country}/factsCenter/popularAndSportList`

**Response:**
```json
{
  "bizCode": 10000,
  "data": {
    "sportList": [
      {
        "id": "sr:sport:1",
        "name": "Football",
        "categories": [
          {
            "id": "sr:category:1",
            "name": "England",
            "tournaments": [
              {"id": "sr:tournament:17", "name": "Premier League"}
            ]
          }
        ]
      }
    ]
  }
}
```

### `get_countries(sport_id="sr:sport:1")`

Same endpoint as `get_sports` — categories are nested under each sport.

### `get_tournaments(sport_id="sr:sport:1")`

Same endpoint — tournaments nested under categories.

### `get_events(tournament_id, sport_id="sr:sport:1", market_ids="1,18,10,29,11,26,36,14")`

Returns events with selected markets via POST.

**Endpoint:** `POST /api/{country}/factsCenter/pcEvents`

**Market IDs:** 1=1X2, 18=O/U, 10=DC, 29=BTTS, 11=DNB, 26=HT/FT, 36=CS, 14=HT 1X2

**Response:**
```json
{
  "bizCode": 10000,
  "data": [
    {
      "events": [
        {
          "eventId": "sr:match:61300947",
          "homeTeamName": "Manchester City",
          "awayTeamName": "Liverpool",
          "markets": [
            {
              "id": "1",
              "desc": "1X2 - Full Time",
              "outcomes": [
                {"id": "1", "desc": "Home", "odds": "1.95"}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### `get_event_detail(event_id)`

Returns full event with all available markets.

**Endpoint:** `GET /api/{country}/factsCenter/event?eventId={id}&productId=3`

**Response:**
```json
{
  "bizCode": 10000,
  "data": {
    "eventId": "sr:match:61300947",
    "markets": [
      {
        "id": "1",
        "desc": "1X2 - Full Time",
        "specifier": null,
        "outcomes": [
          {"id": "1", "desc": "Home", "odds": "1.95", "isActive": 1}
        ]
      },
      {
        "id": "18",
        "desc": "Over/Under",
        "specifier": "total=2.5",
        "outcomes": [
          {"id": "1", "desc": "Over", "odds": "1.80"}
        ]
      }
    ]
  }
}
```

## Notes

- All IDs are SportRadar format (e.g., `sr:match:61300947`, `sr:tournament:17`)
- `bizCode: 10000` means success
- Specifier format for parameterized markets: `key=value` (e.g., `total=2.5`, `hcp=-0.5`)
