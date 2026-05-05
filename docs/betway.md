# Betway

## Supported Countries

| Code | Country |
|------|---------|
| ng | Nigeria |
| gh | Ghana |
| ke | Kenya |
| tz | Tanzania |
| ug | Uganda |
| zm | Zambia |

All countries use the same API domain — differentiated by `countryCode` parameter.

## SportRadar ID

Betway event IDs ARE SportRadar IDs natively. No extraction needed — `get_sportradar_id()` returns the event ID directly without an API call.

## Methods

### `get_sports()`

Returns all available sports with live/upcoming counts.

**Endpoint:** `GET https://config.betwayafrica.com/cron/sports/{countryCode}/en-US`

**Response:**
```json
{
  "sports": [
    {
      "sportId": "soccer",
      "name": "Soccer",
      "liveInPlayCount": 29,
      "hasUpcomingEvents": true
    }
  ]
}
```

### `get_countries(sport_id="soccer")`

Returns regions and leagues for a sport.

**Endpoint:** `GET /br/_apis/sport/v1/Feeds/RegionsAndLeagues/{sportId}?countryCode={cc}`

**Response:**
```json
{
  "regions": [
    {
      "regionId": "england",
      "name": "England",
      "leagues": [
        {"leagueId": "premier-league", "name": "Premier League"}
      ]
    }
  ]
}
```

### `get_events(league_id, sport_id="soccer")`

Returns events with inline markets, outcomes, and prices.

**Endpoint:** `GET /br/_apis/sport/v1/BetBook/Highlights/?countryCode={cc}&sportId={sport}&leagueIds={league}`

League ID format: `"{regionId}_{leagueId}"` (e.g., `"international-clubs_uefa-champions-league"`)

**Response:**
```json
{
  "events": [
    {
      "eventId": 69339436,
      "homeTeam": "Arsenal FC",
      "awayTeam": "Atletico Madrid",
      "isLive": false,
      "expectedStartEpoch": 1778007600
    }
  ],
  "markets": [...],
  "outcomes": [...],
  "prices": [{"outcomeId": "...", "priceDecimal": 1.63}]
}
```

### `get_event_detail(event_id)`

Returns event info and game state.

**Endpoint:** `GET /br/_apis/sport/v3/Feeds/Events/EventAndGameState?eventId={id}&countryCode={cc}`

### `get_event_markets(event_id)`

Returns all markets for an event (denormalized).

**Endpoint:** `GET /br/_apis/sport/v1/MarketGroupings/MarketGroupNamesAndMarketsForEvent?eventId={id}&countryCode={cc}`

**Response:**
```json
{
  "marketGroupNames": ["Main", "Totals", "Goals"],
  "marketsInGroup": [
    {"marketId": "693394361", "name": "[Win/Draw/Win]", "displayName": "1X2", "handicap": 0}
  ],
  "outcomes": [
    {"outcomeId": "6933943611", "marketId": "693394361", "name": "Arsenal FC"}
  ],
  "prices": [
    {"outcomeId": "6933943611", "priceDecimal": 1.63}
  ]
}
```

## Notes

- Uses **string-based sport IDs** (slugs: "soccer", "tennis", "basketball")
- **Denormalized responses** — events, markets, outcomes, prices in separate arrays linked by IDs
- **Position-based outcome matching** for 1X2 and Double Chance (outcomes use team names, not "1"/"X"/"2")
- `get_sportradar_id()` does NOT make an API call — returns the event ID directly
