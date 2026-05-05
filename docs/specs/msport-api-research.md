# MSport API Research (In Progress)

## Status: API discovery incomplete — need Playwright to capture network traffic

## What we found so far

### Base URL
`https://www.msport.com/api/ng/facts-center/query/frontend/`

### Working endpoints

**Sports list (prematch):**
```
GET /api/ng/facts-center/query/frontend/sports
Response: { bizCode: 10000, data: { sports: [...], esportIds: [...], productStatus: {...} } }
31 sports with SportRadar IDs (sr:sport:1, sr:sport:2, etc.)
```

**Live sports:**
```
GET /api/ng/facts-center/query/frontend/live-matches/sports
Response: { bizCode: 10000, data: { productStatus: {...}, sports: [...] } }
24 live sports with counts (Soccer: 30 live, Tennis: 16 live, etc.)
```

### Discovered paths (from JS bundle analysis)
```
/facts-center/query/frontend/sports                    -- Sports list (works!)
/facts-center/query/frontend/sports-matches-list       -- Needs params (bizCode 19000)
/facts-center/query/frontend/live-matches              -- Needs params (bizCode 19000)
/facts-center/query/frontend/live-matches/list         -- 
/facts-center/query/frontend/live-matches/sports       -- Live sports (works!)
/facts-center/query/frontend/live-matches/count        -- 
/facts-center/query/frontend/focus-matches/v3          -- Focus/featured matches
/facts-center/query/frontend/all-matches/today         -- Today's matches
/facts-center/query/frontend/all-matches/next-7-days   -- Next 7 days
/facts-center/query/frontend/match/{id}/bet-builder/*  -- Bet builder (works)
/facts-center/query/frontend/event/tracker/*           -- Event tracker
/facts-center/query/frontend/market-info               -- Market info
/facts-center/query/frontend/market-group-info         -- Market groups
/facts-center/query/frontend/default-market-info/v2    -- Default markets
```

### Key characteristics
- Uses SportRadar IDs natively (same as SportyBet)
- SR IDs visible in URLs: sr:match:61301231, sr:tournament:17
- bizCode: 10000 = success, 19000 = needs parameters, 19003 = invalid params
- Multi-country via /api/{region}/... path (ng, gh, etc.)
- Vue.js SPA with lazy-loaded chunks
- Socket.io for real-time updates
- Chunk files: main.14c6cf01.js, matches.5f76d290.js

### Next steps
Use Playwright to:
1. Navigate to https://www.msport.com/ng/web/sports/list/Soccer?t=sr:tournament:17
2. Capture network requests for events listing
3. Navigate to an event detail page
4. Capture network requests for full markets/odds
5. Check the exact request format (headers, body, params)

### JS bundle references
- `getAvailableSports` -> `(a.l3)()` -> `/facts-center/query/frontend/sports`
- `getPrematchSports` -> `(a.l3)(3)` -> same endpoint with productId?
- `getSportsMatches` -> probably `/facts-center/query/frontend/sports-matches-list`
- `getLiveEvents` -> probably `/facts-center/query/frontend/live-matches`
