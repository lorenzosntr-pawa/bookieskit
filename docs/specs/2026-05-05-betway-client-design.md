# Betway Client Design

## Overview

Add Betway as the 4th bookmaker in bookieskit. Betway operates across multiple African countries via `betwayafrica.com` with a clean REST API. Its event IDs ARE SportRadar IDs natively, making cross-platform matching trivial.

## API Endpoints

| Level | Endpoint |
|-------|----------|
| Sports | `GET https://config.betwayafrica.com/cron/sports/{countryCode}/en-US` |
| Countries/Leagues | `GET https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/Feeds/RegionsAndLeagues/{sportId}?countryCode={cc}` |
| Events | `GET https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/BetBook/Highlights/?countryCode={cc}&sportId={sport}&marketTypes=[Win/Draw/Win]&leagueIds={league}&Skip=0&Take=50` |
| Event detail | `GET https://feeds-roa2.betwayafrica.com/br/_apis/sport/v3/Feeds/Events/EventAndGameState?eventId={id}&countryCode={cc}` |
| Event markets | `GET https://feeds-roa2.betwayafrica.com/br/_apis/sport/v1/MarketGroupings/MarketGroupNamesAndMarketsForEvent?eventId={id}&countryCode={cc}&cultureCode=en-US&skip=0&take=100` |

## New Files

- `src/bookieskit/bookmakers/betway.py` — Betway client class
- `tests/test_betway.py` — Client tests
- `tests/test_parser_betway.py` — Market parser tests

## Modified Files

- `src/bookieskit/__init__.py` — add `Betway` export
- `src/bookieskit/bookmakers/__init__.py` — add `Betway` export
- `src/bookieskit/markets/types.py` — add `betway` field to `OutcomeMapping`
- `src/bookieskit/markets/builtin_mappings.py` — add Betway IDs and outcome names
- `src/bookieskit/markets/parser.py` — add `_parse_betway` function
- `src/bookieskit/matching/extractor.py` — add `_extract_betway`
- `docs/betway.md` — API documentation

## Client Class

```python
from bookieskit import Betway

async with Betway(country="ng") as client:
    sports = await client.get_sports()
    countries = await client.get_countries(sport_id="soccer")
    events = await client.get_events(league_id="international-clubs_uefa-champions-league")
    detail = await client.get_event_detail(event_id="69339436")
    markets = await client.get_markets(event_id="69339436")
    sr_id = await client.get_sportradar_id(event_id="69339436")  # "69339436"
```

## Class Design

```python
class Betway(BaseBookmaker):
    DOMAINS = {
        "ng": "https://feeds-roa2.betwayafrica.com",
        "gh": "https://feeds-roa2.betwayafrica.com",
        "ke": "https://feeds-roa2.betwayafrica.com",
        "tz": "https://feeds-roa2.betwayafrica.com",
        "ug": "https://feeds-roa2.betwayafrica.com",
        "zm": "https://feeds-roa2.betwayafrica.com",
    }
    # Country code mapping (internal) for API params
    COUNTRY_CODES = {
        "ng": "NG",
        "gh": "GH",
        "ke": "KE",
        "tz": "TZ",
        "ug": "UG",
        "zm": "ZM",
    }
    CONFIG_BASE_URL = "https://config.betwayafrica.com"
    DEFAULT_HEADERS = {
        "accept": "application/json",
        "user-agent": "Mozilla/5.0 ...",
    }
    MAX_CONCURRENT = 50
    REQUEST_DELAY = 0.0
    NAME = "Betway"
    PLATFORM_KEY = "betway"
```

## Multi-Country

All countries use the same domain — differentiated by `countryCode` query param:
- `ng` → `countryCode=NG`
- `gh` → `countryCode=GH`
- `ke` → `countryCode=KE`
- `tz` → `countryCode=TZ`
- `ug` → `countryCode=UG`
- `zm` → `countryCode=ZM`

## SportRadar ID

Betway's `eventId` IS the SportRadar ID directly (numeric, no prefix). Confirmed by matching:
- Betway eventId: `69339436`
- SportyBet eventId: `sr:match:69339436`

Extraction is trivial: `return str(response["sportEvent"]["eventId"])`

## OutcomeMapping Update

Add `betway: str` field to existing `OutcomeMapping` dataclass:

```python
@dataclass(frozen=True)
class OutcomeMapping:
    canonical_name: str
    betpawa: str
    sportybet: str
    bet9ja: str
    betway: str  # NEW
```

## Built-in Market Mappings Update

### 1X2 - Full Time

| | BetPawa | SportyBet | Bet9ja | Betway |
|---|---|---|---|---|
| Market ID | `3743` | `1` | `S_1X2` | `[Win/Draw/Win]` |
| Home | `1` | `Home` | `1` | `{homeTeam}` (position 1) |
| Draw | `X` | `Draw` | `X` | `Draw` |
| Away | `2` | `Away` | `2` | `{awayTeam}` (position 3) |

### Over/Under - Full Time

| | BetPawa | SportyBet | Bet9ja | Betway |
|---|---|---|---|---|
| Market ID | `5000` | `18` | `S_OU` | `[Total Goals]` |
| Over | `Over` | `Over` | `O` | `Over` |
| Under | `Under` | `Under` | `U` | `Under` |

### Both Teams To Score

| | BetPawa | SportyBet | Bet9ja | Betway |
|---|---|---|---|---|
| Market ID | `3795` | `29` | `S_GGNG` | `[Both Teams To Score]` |
| Yes | `Yes` | `Yes` | `Y` | `Yes` |
| No | `No` | `No` | `N` | `No` |

### Double Chance

| | BetPawa | SportyBet | Bet9ja | Betway |
|---|---|---|---|---|
| Market ID | `4693` | `10` | `S_DC` | `[Double Chance]` |
| Home/Draw | `1X` | `Home or Draw` | `1X` | `{homeTeam} or Draw` (position 1) |
| Draw/Away | `X2` | `Draw or Away` | `X2` | `Draw or {awayTeam}` (position 2) |
| Home/Away | `12` | `Home or Away` | `12` | `{homeTeam} or {awayTeam}` (position 3) |

**Note:** Betway uses team names in outcomes for 1X2 and DC. The parser uses **position-based matching** (index in outcomes array) rather than name matching for these markets. Only "Draw", "Over", "Under", "Yes", "No" are fixed strings.

## Market Parser

Betway's response is denormalized:
- `marketsInGroup[]` — market definitions with `marketId`, `name`, `handicap`
- `outcomes[]` — outcome definitions with `outcomeId`, `marketId`, `name`
- `prices[]` — odds with `outcomeId`, `priceDecimal`

Parser must:
1. Find markets by `name` (e.g., `[Win/Draw/Win]`, `[Total Goals]`)
2. Collect outcomes for each market by joining on `marketId`
3. Collect prices for each outcome by joining on `outcomeId`
4. For parameterized markets: group by `handicap` field on the market

## Response Structures

### Sports
```json
{
  "sports": [
    {
      "sportId": "soccer",
      "name": "Soccer",
      "hasLiveInPlayEvents": true,
      "liveInPlayCount": 29,
      "hasUpcomingEvents": true
    }
  ]
}
```

### Regions/Leagues
```json
{
  "regions": [
    {
      "regionId": "england",
      "name": "England",
      "sportId": "soccer",
      "leagues": [
        {"leagueId": "premier-league", "name": "Premier League"}
      ]
    }
  ]
}
```

### Events (Highlights)
```json
{
  "events": [
    {
      "eventId": 69339436,
      "name": "Arsenal FC vs. Atletico Madrid",
      "homeTeam": "Arsenal FC",
      "awayTeam": "Atletico Madrid",
      "sportId": "soccer",
      "regionId": "international-clubs",
      "leagueId": "uefa-champions-league",
      "isLive": false,
      "expectedStartEpoch": 1778007600
    }
  ],
  "markets": [...],
  "outcomes": [...],
  "prices": [{"outcomeId": "...", "priceDecimal": 1.63}]
}
```

### Event Detail
```json
{
  "sportEvent": {
    "eventId": 69339436,
    "name": "Arsenal FC vs. Atletico Madrid",
    "homeTeam": "Arsenal FC",
    "awayTeam": "Atletico Madrid",
    "isLive": false
  }
}
```

### Event Markets
```json
{
  "marketGroupNames": ["Main", "Totals", "Goals", ...],
  "marketsInGroup": [
    {"marketId": "693394361", "name": "[Win/Draw/Win]", "displayName": "1X2", "handicap": 0},
    {"marketId": "6933943618total=2.5~", "name": "Total", "displayName": "Total (2.5)", "handicap": 2.5}
  ],
  "outcomes": [
    {"outcomeId": "6933943611", "marketId": "693394361", "name": "Arsenal FC"},
    {"outcomeId": "6933943612", "marketId": "693394361", "name": "Draw"},
    {"outcomeId": "6933943613", "marketId": "693394361", "name": "Atletico Madrid"}
  ],
  "prices": [
    {"outcomeId": "6933943611", "priceDecimal": 1.63},
    {"outcomeId": "6933943612", "priceDecimal": 4.0},
    {"outcomeId": "6933943613", "priceDecimal": 4.6}
  ]
}
```

## Testing

- Unit tests for client methods (mocked HTTP)
- Unit tests for market parser (fixture data)
- Integration test (real API, marked skip-by-default)

## Backwards Compatibility

Adding `betway` field to `OutcomeMapping` is a breaking change for any code constructing `OutcomeMapping` directly. Since this is an internal library and v0.2.0, this is acceptable. The field will have a default value of `""` for backwards compatibility with existing code that doesn't use Betway.

Updated `OutcomeMapping`:
```python
@dataclass(frozen=True)
class OutcomeMapping:
    canonical_name: str
    betpawa: str
    sportybet: str
    bet9ja: str
    betway: str = ""  # Default empty for backwards compat
```
