# Graph Report - src  (2026-11-16)

## Corpus Check
- 19 files · ~23,368 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 488 nodes · 1155 edges · 18 communities (14 shown, 4 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 115 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4149e1e1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]

## God Nodes (most connected - your core abstractions)
1. `BaseBookmaker` - 65 edges
2. `str` - 40 edges
3. `PrematchEventStub` - 30 edges
4. `MarketRegistry` - 30 edges
5. `Mode` - 29 edges
6. `MarketMapping` - 25 edges
7. `NormalizedMarket` - 22 edges
8. `float` - 21 edges
9. `ProbabilityMode` - 19 edges
10. `NormalizedMarket` - 18 edges

## Surprising Connections (you probably didn't know these)
- `int` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/betpawa.py → bookieskit/base.py
- `int` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/elephantbet.py → bookieskit/base.py
- `bool` --uses--> `MarketRegistry`  [INFERRED]
  bookieskit/markets/parser.py → bookieskit/markets/registry.py
- `Bet9ja` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/bet9ja.py → bookieskit/base.py
- `Betika` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/betika.py → bookieskit/base.py

## Communities (18 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (87): bool, float, MarketMapping, str, MarketRegistry, _build_bet9ja_outcomes(), _build_betway_parameterized(), _build_betway_simple() (+79 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (40): AbstractEventLoop, BaseBookmaker, Any, float, int, str, Base bookmaker client with shared HTTP, retry, and rate-limiting logic., Set or replace the ``Cookie:`` header for subsequent requests.          Works (+32 more)

### Community 2 - "Community 2"
Cohesion: 0.10
Nodes (52): _bet9ja_is_live(), extract_kickoff(), extract_live_info(), extract_participants(), is_live_now(), _kickoff_bet9ja(), _kickoff_betika(), _kickoff_betpawa() (+44 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (32): Any, bool, int, PrematchEventStub, str, object, Betika, _coerce_int() (+24 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (35): str, str, EventIds, extract_event_ids(), _extract_event_ids_bet9ja(), _extract_event_ids_betika(), _extract_event_ids_betpawa(), _extract_event_ids_betway() (+27 more)

### Community 5 - "Community 5"
Cohesion: 0.14
Nodes (17): Any, int, PrematchEventStub, str, Betway, Get regions/countries and leagues for a sport.          Args:             spo, Get tournaments (same as get_countries — leagues are tournaments).          Ar, Get events for a league.          Args:             region_id: Region slug (e (+9 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (15): Any, str, Bet9ja, Bet9ja client — supports ng only., Build a SR-id -> Bet9ja internal-id map for ALL prematch events         under a, HTTP client for Bet9ja sportsbook API.      Bet9ja has stricter rate limits (1, Look up Bet9ja's internal event ID for a given SportRadar ID.          Bet9ja', Get list of sports that currently have live events.          Returns: (+7 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (16): Any, bool, int, PrematchEventStub, str, Get the full markets payload for one event.          Args:             event_, HTTP client for SportPesa sportsbook API.      SportPesa uses country-specific, Fetch markets and return normalized markets.          Overrides the base becau (+8 more)

### Community 8 - "Community 8"
Cohesion: 0.13
Nodes (15): Any, bool, int, PrematchEventStub, str, _api_prefix(), MSport, MSport client — supports ng, gh, ke, ug, zm. (+7 more)

### Community 9 - "Community 9"
Cohesion: 0.16
Nodes (13): Any, int, str, _culture(), ElephantBet, HTTP client for ElephantBet (BtoBet platform).  ElephantBet runs BtoBet ``Sb.W, Get every in-play match, optionally filtered to one sport.          BtoBet has, Get full markets and odds for one match.          Args:             event_id: (+5 more)

### Community 10 - "Community 10"
Cohesion: 0.19
Nodes (13): Any, bool, str, _api_prefix(), SportyBet client — supports ng, gh, ke, tz, za, cm, zm.  SportyBet also operat, Get tournaments for a sport (nested under categories).          Returns the sa, Get events for a tournament.          Args:             tournament_id: SportR, Get full event details including all markets.          Args:             even (+5 more)

### Community 11 - "Community 11"
Cohesion: 0.17
Nodes (11): Any, int, str, BetPawa, BetPawa client — supports all 15 of BetPawa's advertised countries., Get all available sports/categories.          Returns:             Raw JSON w, Get countries/regions for a sport (with competitions).          Args:, Get tournaments/competitions for a sport.          Returns the same payload as (+3 more)

### Community 12 - "Community 12"
Cohesion: 0.16
Nodes (10): bool, MarketMapping, str, Return the MarketMapping for a canonical ID, or None if not registered., Return the MarketMapping for a platform-specific ID.          Args:, Initialize registry.          Args:             load_builtins: Load built-in, Return all registered market mappings in insertion order.          Returns:, Register a mapping in all lookup indices.          The flat per-platform index (+2 more)

### Community 13 - "Community 13"
Cohesion: 0.24
Nodes (7): Built-in market mappings.  Soccer: 1X2, O/U, BTTS, DC, 1X2 1Up, 1X2 2Up, next-, Market registry — built-in + user-extensible., MarketMapping, OutcomeMapping, Data types for market mapping., Maps one outcome across platforms., Defines how one market maps across platforms.      The ``sport`` field disambi

## Knowledge Gaps
- **1 isolated node(s):** `OutcomeMapping`
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BaseBookmaker` connect `Community 1` to `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`?**
  _High betweenness centrality (0.483) - this node is a cross-community bridge._
- **Why does `MarketRegistry` connect `Community 1` to `Community 0`, `Community 3`, `Community 12`, `Community 13`?**
  _High betweenness centrality (0.248) - this node is a cross-community bridge._
- **Why does `extract_sportradar_id()` connect `Community 1` to `Community 4`?**
  _High betweenness centrality (0.144) - this node is a cross-community bridge._
- **Are the 44 inferred relationships involving `BaseBookmaker` (e.g. with `Bet9ja` and `Betika`) actually correct?**
  _`BaseBookmaker` has 44 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `PrematchEventStub` (e.g. with `Betika` and `str`) actually correct?**
  _`PrematchEventStub` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `MarketRegistry` (e.g. with `BaseBookmaker` and `str`) actually correct?**
  _`MarketRegistry` has 19 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Base bookmaker client with shared HTTP, retry, and rate-limiting logic.`, `Base class for all bookmaker HTTP clients.      Subclasses must define:`, `Initialise the client for the given country.          Args:             count` to the rest of the system?**
  _190 weakly-connected nodes found - possible documentation gaps or missing edges._