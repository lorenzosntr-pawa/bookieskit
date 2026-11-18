# Graph Report - src  (2026-11-18)

## Corpus Check
- 20 files · ~24,451 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 644 nodes · 1362 edges · 33 communities (29 shown, 4 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 124 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bcc9fbb9`
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
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]

## God Nodes (most connected - your core abstractions)
1. `BaseBookmaker` - 66 edges
2. `str` - 44 edges
3. `PrematchEventStub` - 31 edges
4. `MarketRegistry` - 30 edges
5. `Mode` - 29 edges
6. `MarketMapping` - 25 edges
7. `ResponseError` - 23 edges
8. `NormalizedMarket` - 23 edges
9. `parse_markets()` - 21 edges
10. `float` - 21 edges

## Surprising Connections (you probably didn't know these)
- `int` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/betpawa.py → bookieskit/base.py
- `int` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/elephantbet.py → bookieskit/base.py
- `int` --uses--> `MarketRegistry`  [INFERRED]
  bookieskit/markets/parser.py → bookieskit/markets/registry.py
- `Bet9ja` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/bet9ja.py → bookieskit/base.py
- `Betika` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/betika.py → bookieskit/base.py

## Communities (33 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.10
Nodes (28): str, MarketRegistry, _keep_complete(), _parse_betika(), _parse_betway(), _parse_msport(), _parse_sportpesa(), _parse_sportybet() (+20 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (57): AbstractEventLoop, BaseBookmaker, Any, float, int, str, Base bookmaker client with shared HTTP, retry, and rate-limiting logic., Set or replace the ``Cookie:`` header for subsequent requests.          Works (+49 more)

### Community 2 - "Community 2"
Cohesion: 0.10
Nodes (52): _bet9ja_is_live(), extract_kickoff(), extract_live_info(), extract_participants(), is_live_now(), _kickoff_bet9ja(), _kickoff_betika(), _kickoff_betpawa() (+44 more)

### Community 3 - "Community 3"
Cohesion: 0.18
Nodes (16): Any, bool, str, _pick_match(), Fetch one match with every market from ``/v1/uo/match?id=``.          ``/v1/uo, Get the event-detail payload for one match.          Args:             event_, Get the event-detail payload for one match.          Args:             event_, Get one match with its full market list.          Args:             event_id: (+8 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (37): str, str, EventIds, extract_event_ids(), _extract_event_ids_bet9ja(), _extract_event_ids_betika(), _extract_event_ids_betpawa(), _extract_event_ids_betway() (+29 more)

### Community 5 - "Community 5"
Cohesion: 0.12
Nodes (20): Any, int, PrematchEventStub, str, Betway, Get regions/countries and leagues for a sport.          Args:             spo, Get tournaments (same as get_countries — leagues are tournaments).          Ar, Get events for a league.          Args:             region_id: Region slug (e (+12 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (15): Any, str, Bet9ja, Bet9ja client — supports ng only., Build a SR-id -> Bet9ja internal-id map for ALL prematch events         under a, HTTP client for Bet9ja sportsbook API.      Bet9ja has stricter rate limits (1, Look up Bet9ja's internal event ID for a given SportRadar ID.          Bet9ja', Get list of sports that currently have live events.          Returns: (+7 more)

### Community 7 - "Community 7"
Cohesion: 0.10
Nodes (23): Any, bool, int, PrematchEventStub, str, Get the full markets payload for one event.          Args:             event_, HTTP client for SportPesa sportsbook API.      SportPesa uses country-specific, Fetch markets and return normalized markets.          Overrides the base becau (+15 more)

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
Cohesion: 0.08
Nodes (39): _extract_line_from_specifier(), _parse_msport_parameterized(), _parse_msport_simple(), _parse_sportybet_parameterized(), _parse_sportybet_simple(), Market parser — transforms raw event responses into NormalizedMarkets., Parse a simple MSport market., Parse a parameterized MSport market (multiple entries, one per line). (+31 more)

### Community 13 - "Community 13"
Cohesion: 0.24
Nodes (7): Built-in market mappings.  Soccer: 1X2, O/U, BTTS, DC, 1X2 1Up, 1X2 2Up, next-, Market registry — built-in + user-extensible., MarketMapping, OutcomeMapping, Data types for market mapping., Maps one outcome across platforms., Defines how one market maps across platforms.      The ``sport`` field disambi

### Community 18 - "Community 18"
Cohesion: 0.14
Nodes (17): _parse_betpawa(), _parse_betpawa_parameterized(), _parse_betpawa_simple(), Parse BetPawa event detail response., Parse a simple BetPawa market (1X2, BTTS, DC)., Parse a parameterized BetPawa market (O/U, handicaps)., Parse BetPawa event detail response., Parse BetPawa event detail response. (+9 more)

### Community 19 - "Community 19"
Cohesion: 0.11
Nodes (15): object, Betway client — supports ng, gh, ke, tz, ug, zm., SportPesa client — supports ke, tz., # NOTE: SportPesa has no dedicated tournament / competition list endpoint, # NOTE: SportPesa has no dedicated tournament / competition list endpoint, _normalised_probability_mode(), parse_markets(), Parse raw event detail response into normalized markets.      Args:         r (+7 more)

### Community 20 - "Community 20"
Cohesion: 0.16
Nodes (13): MarketMapping, _parse_sportpesa_parameterized(), _parse_sportpesa_simple(), Parse a simple SportPesa market (1X2, BTTS, DC)., Parse a parameterized SportPesa market (Over/Under, handicaps).      Each entr, Find canonical outcome name from a SportPesa selection ``shortName``.      Exa, Parse a simple SportPesa market (1X2, BTTS, DC)., Parse a simple SportPesa market (1X2, BTTS, DC). (+5 more)

### Community 21 - "Community 21"
Cohesion: 0.13
Nodes (17): float, _parse_bet9ja(), _parse_bet9ja_key(), _parse_betika_line(), _parse_betika_parameterized(), Parse a parameterized Betika market (Over/Under).      All selections live in, Extract the line value for a parameterized Betika selection.      ``special_be, Parse a parameterized Betika market (Over/Under).      All selections live in on (+9 more)

### Community 22 - "Community 22"
Cohesion: 0.22
Nodes (9): int, _build_betway_simple(), Find canonical outcome name from Betway outcome.      Uses exact match first,, Find canonical outcome name from Betway outcome.      Uses exact match first, th, Find canonical outcome name from Betway outcome.      Uses exact match first,, Build a simple NormalizedMarket from Betway outcomes., Build a simple NormalizedMarket from Betway outcomes., Build a simple NormalizedMarket from Betway outcomes. (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.19
Nodes (14): devig_multiplicative(), devig_shin(), _implied(), margin(), float, Margin and de-vig helpers shared across bookmaker comparisons.  These helpers, Return 1/odds per outcome, or None if the odds are unusable., Return 1/odds per outcome, or None if the odds are unusable.      Unusable mea (+6 more)

### Community 24 - "Community 24"
Cohesion: 0.25
Nodes (8): _parse_betika_simple(), Parse a simple Betika market (1X2, BTTS, DC)., Resolve a Betika selection ``display`` label to a canonical name.      Case-in, Parse a simple Betika market (1X2, BTTS, DC)., Parse a simple Betika market (1X2, BTTS, DC)., Resolve a Betika selection ``display`` label to a canonical name.      Case-inse, Resolve a Betika selection ``display`` label to a canonical name.      Case-in, _resolve_outcome_betika()

### Community 25 - "Community 25"
Cohesion: 0.17
Nodes (12): _build_bet9ja_outcomes(), _incomplete_reason(), None if every expected outcome is present with odds > 1.0, else why not., None if every expected outcome is present with odds > 1.0, else why not., Build Outcome list from Bet9ja suffix/odds pairs., Find canonical outcome name from Bet9ja key suffix., Build Outcome list from Bet9ja suffix/odds pairs., Build Outcome list from Bet9ja suffix/odds pairs. (+4 more)

### Community 26 - "Community 26"
Cohesion: 0.15
Nodes (13): int, _coerce_int(), Get prematch matches from ``/v1/uo/matches``.          Args:             spor, Get prematch matches from ``/v1/uo/matches``.          Args:             spor, Get prematch matches from ``/v1/uo/matches``.          Args:             spor, Yield every prematch event in Betika's catalogue.          Uses ``meta.total``, Yield every prematch event in Betika's catalogue.          Uses ``meta.total``, Best-effort int coercion — used for Betika's stringy ``meta.total``. (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.12
Nodes (16): bool, _build_betway_parameterized(), _extract_betway_line_from_market_id(), _is_betway_child_market_id(), _is_betway_parameterized_variant(), Extract the line value from a Betway marketId path segment.      Betway encodes, Extract the line value from a Betway marketId path segment.      Betway encode, Build a parameterized NormalizedMarket from Betway entries.      Betway links al (+8 more)

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (8): _parse_elephantbet(), Parse an ElephantBet (BtoBet) MatchOdds response.      Markets are nested unde, Map an ElephantBet outcome label to its canonical name., Parse an ElephantBet (BtoBet) MatchOdds response.      Markets are nested under, Parse an ElephantBet (BtoBet) MatchOdds response.      Markets are nested unde, Map an ElephantBet outcome label to its canonical name., Map an ElephantBet outcome label to its canonical name., _resolve_outcome_elephantbet()

### Community 29 - "Community 29"
Cohesion: 0.18
Nodes (10): Betika, HTTP client for the Betika sportsbook API.      Args:         country: Countr, HTTP client for the Betika sportsbook API.      Args:         country: Countr, HTTP client for the Betika sportsbook API.      Args:         country: Countr, Get the sport catalogue.          Returns:             Raw JSON shaped as ``{, Get the sport catalogue.          Returns:             Raw JSON shaped as ``{, Get the sport catalogue.          Returns:             Raw JSON shaped as ``{, Alias for :meth:`get_sports`.          Betika does not expose a single endpoin (+2 more)

### Community 30 - "Community 30"
Cohesion: 0.20
Nodes (9): Betika client — supports ke, ug, tz, mw, gh.  Betika's API is country-agnostic, Extract :class:`PrematchEventStub`s from one ``/v1/uo/matches`` page., Extract :class:`PrematchEventStub`s from one ``/v1/uo/matches`` page., Extract :class:`PrematchEventStub`s from one ``/v1/uo/matches`` page., Extract :class:`PrematchEventStub`s from one ``/v1/uo/matches`` page., _stubs_from_page(), PrematchEventStub, Shared types for bookmaker clients. (+1 more)

### Community 31 - "Community 31"
Cohesion: 0.25
Nodes (6): Get currently-live matches from ``live.betika.com/v1/uo/matches``.          Ar, Get currently-live matches from ``live.betika.com/v1/uo/matches``.          Ar, Get currently-live matches from ``live.betika.com/v1/uo/matches``.          Ar, Issue a request against ``live.betika.com``.          Betika's live endpoints, Issue a request against ``live.betika.com``.          Betika's live endpoints, Issue a request against ``live.betika.com``.          Betika's live endpoints

### Community 32 - "Community 32"
Cohesion: 0.40
Nodes (4): Fetch the full market set and return normalized markets.          Args:, Fetch the universal market set and return normalized markets.          Overrid, Fetch the universal market set and return normalized markets.          Overrid, Fetch the universal market set and return normalized markets.          Overrid

## Knowledge Gaps
- **1 isolated node(s):** `OutcomeMapping`
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BaseBookmaker` connect `Community 1` to `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`, `Community 19`, `Community 26`, `Community 29`, `Community 30`?**
  _High betweenness centrality (0.412) - this node is a cross-community bridge._
- **Why does `MarketRegistry` connect `Community 1` to `Community 0`, `Community 12`, `Community 13`, `Community 18`, `Community 19`, `Community 20`, `Community 21`, `Community 22`, `Community 25`, `Community 27`?**
  _High betweenness centrality (0.252) - this node is a cross-community bridge._
- **Why does `extract_sportradar_id()` connect `Community 4` to `Community 1`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Are the 45 inferred relationships involving `BaseBookmaker` (e.g. with `Bet9ja` and `Betika`) actually correct?**
  _`BaseBookmaker` has 45 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `PrematchEventStub` (e.g. with `Betika` and `str`) actually correct?**
  _`PrematchEventStub` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `MarketRegistry` (e.g. with `BaseBookmaker` and `str`) actually correct?**
  _`MarketRegistry` has 19 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Base bookmaker client with shared HTTP, retry, and rate-limiting logic.`, `Base class for all bookmaker HTTP clients.      Subclasses must define:`, `Initialise the client for the given country.          Args:             count` to the rest of the system?**
  _330 weakly-connected nodes found - possible documentation gaps or missing edges._