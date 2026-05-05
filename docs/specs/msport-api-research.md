# MSport API Research (COMPLETE)

## Summary

MSport uses **nearly identical API to SportyBet** — same headers, same SportRadar IDs, very similar response structure.

## Required Headers

```
operid: 2
clientid: web
platform: web
```

Same as SportyBet!

## Base URL

`https://www.msport.com/api/{region}/facts-center/query/frontend/`

Where `{region}` = `ng`, `gh`, etc.

## Endpoints

### Sports (prematch)
```
GET /sports
Response: { bizCode: 10000, data: { sports: [{sportId: "sr:sport:1", sportName: "Soccer", count: 0}] } }
31 sports with SportRadar IDs
```

### Events by Sport (prematch)
```
GET /sports-matches-list?sportId=sr:sport:1
Response: { bizCode: 10000, data: { tournaments: [{
  category: "England",
  tournament: "Premier League",
  tournamentId: "sr:tournament:17",
  events: [{
    homeTeam: "Liverpool", awayTeam: "Chelsea",
    eventId: "sr:match:61301233"
  }]
}] } }
```

### Event Detail (full markets)
```
GET /match/detail?eventId=sr:match:61301231&productId=3
Response: { bizCode: 10000, data: {
  eventId: "sr:match:61301231",
  homeTeam: "Fulham", awayTeam: "Bournemouth",
  markets: [407 markets!] {
    id: 1, description: "1x2", name: "1x2",
    specifiers: null,
    outcomes: [
      {description: "Home", id: "1", odds: "2.76"},
      {description: "Draw", id: "2", odds: "3.77"},
      {description: "Away", id: "3", odds: "2.39"}
    ]
  }
} }
```

### Live Sports
```
GET /live-matches/sports
Response: { bizCode: 10000, data: { sports: [
  {sportId: "sr:sport:1", sportName: "Soccer", count: 30},
  {sportId: "sr:sport:2", sportName: "Basketball", count: 18},
  ...24 sports
] } }
```

### Live Events
```
GET /live-matches?sportId=sr:sport:1
Response: { bizCode: 10000, data: {
  events: [...live events...],
  count: 30
} }
```

### Live Events List (with tournaments)
```
GET /live-matches/list?sportId=sr:sport:1
Response: { bizCode: 10000, data: {
  tournaments: [...],
  events: [...],
  comingSoons: [...]
} }
```

## Comparison with SportyBet

| Feature | SportyBet | MSport |
|---------|-----------|--------|
| Base path | /api/{region}/factsCenter/ | /api/{region}/facts-center/query/frontend/ |
| Headers | operid=2, clientid=web, platform=web | SAME |
| Sport IDs | sr:sport:1 | SAME |
| Event IDs | sr:match:XXXXX | SAME |
| Tournament IDs | sr:tournament:XX | SAME |
| Market ID field | `id` | `id` (same) |
| Market name field | `desc` | `description` (different!) |
| Outcome name field | `desc` | `description` (different!) |
| Specifier field | `specifier` | `specifiers` (plural!) |
| Odds field | `odds` | `odds` (same) |
| bizCode success | 10000 | 10000 (same) |
| Sports endpoint | /popularAndSportList | /sports |
| Events endpoint | POST /pcEvents | GET /sports-matches-list?sportId= |
| Event detail | GET /event?eventId= | GET /match/detail?eventId=&productId=3 |
| Live events | /popularAndSportList (productId=1) | /live-matches?sportId= |

## Key Differences from SportyBet

1. `description` instead of `desc` for market and outcome names
2. `specifiers` (plural) instead of `specifier`
3. Events listing uses GET with query params (SportyBet uses POST)
4. Different endpoint paths but same data structure
5. Event detail returns 407 markets (very comprehensive)
6. Multi-country via same domain (`/api/ng/`, `/api/gh/`)

## Market Structure (id=1 = 1X2, same as SportyBet)

```json
{
  "id": 1,
  "description": "1x2",
  "name": "1x2",
  "specifiers": null,
  "outcomes": [
    {"description": "Home", "id": "1", "odds": "2.76", "isActive": 1},
    {"description": "Draw", "id": "2", "odds": "3.77", "isActive": 1},
    {"description": "Away", "id": "3", "odds": "2.39", "isActive": 1}
  ]
}
```

## Implementation Notes

Adding MSport to bookieskit will be very straightforward:
- Same headers as SportyBet
- Same SR IDs (matching works automatically)
- Parser needs minor adaptation: `description` instead of `desc`
- Events fetching uses GET (simpler than SportyBet's POST)
- Market IDs are identical: 1=1X2, 18=O/U, 29=BTTS, 10=DC
