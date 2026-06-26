# Graph Report - src  (2026-06-26)

## Corpus Check
- 53 files · ~34,776 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 917 nodes · 2259 edges · 33 communities (28 shown, 5 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 228 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `71479d0b`
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
1. `BaseBookmaker` - 60 edges
2. `MarketRegistry` - 52 edges
3. `GhRunner` - 42 edges
4. `str` - 38 edges
5. `Queue` - 37 edges
6. `PrematchEventStub` - 31 edges
7. `CanaryReport` - 30 edges
8. `run()` - 30 edges
9. `WorkItem` - 30 edges
10. `int` - 29 edges

## Surprising Connections (you probably didn't know these)
- `int` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/betpawa.py → bookieskit/base.py
- `MarketRegistry` --uses--> `MarketRegistry`  [INFERRED]
  bookieskit/devtools/search.py → bookieskit/markets/registry.py
- `Bet9ja` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/bet9ja.py → bookieskit/base.py
- `Betika` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/betika.py → bookieskit/base.py
- `BetPawa` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/betpawa.py → bookieskit/base.py

## Communities (33 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (97): float, MarketMapping, MarketRegistry, object, str, decode_betpawa_probability(), Decode a BetPawa price.probability base64 blob to (win, refund).      Returns, Built-in market mappings.  Soccer: 1X2, O/U, BTTS, DC, 1X2 1Up, 1X2 2Up, next- (+89 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (73): Any, ArgumentParser, bool, CanaryRunner, GhRunner, int, Namespace, str (+65 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (40): Any, bool, int, PrematchEventStub, str, Any, bool, int (+32 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (56): BookCheck, bool, int, str, WorkItem, str, CanaryReport, ApproveCommand (+48 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (53): object, _bet9ja_is_live(), extract_kickoff(), extract_live_info(), extract_participants(), is_live_now(), _kickoff_bet9ja(), _kickoff_betika() (+45 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (34): AbstractEventLoop, BaseBookmaker, Any, float, int, str, Base bookmaker client with shared HTTP, retry, and rate-limiting logic., Set or replace the ``Cookie:`` header for subsequent requests.          Works (+26 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (43): Any, ArgumentParser, bool, CanaryRunner, int, Namespace, str, bool (+35 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (36): str, str, EventIds, extract_event_ids(), _extract_event_ids_bet9ja(), _extract_event_ids_betika(), _extract_event_ids_betpawa(), _extract_event_ids_betway() (+28 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (22): bool, GhRunner, int, str, int, str, GhRunner, str (+14 more)

### Community 9 - "Community 9"
Cohesion: 0.13
Nodes (24): bool, int, Path, str, bump_init(), bump_pyproject(), extract_section(), GitRunner (+16 more)

### Community 10 - "Community 10"
Cohesion: 0.11
Nodes (17): Any, str, Bet9ja, Bet9ja client — supports ng only., Build a SR-id -> Bet9ja internal-id map for ALL prematch events         under a, HTTP client for Bet9ja sportsbook API.      Bet9ja has stricter rate limits (1, Look up Bet9ja's internal event ID for a given SportRadar ID.          Bet9ja', Get list of sports that currently have live events.          Returns: (+9 more)

### Community 11 - "Community 11"
Cohesion: 0.20
Nodes (27): Any, bool, Handle, str, str, Adapter, _bet9ja_fetch(), _bet9ja_resolve() (+19 more)

### Community 12 - "Community 12"
Cohesion: 0.14
Nodes (17): Any, int, PrematchEventStub, str, Betway, Get regions/countries and leagues for a sport.          Args:             spo, Get tournaments (same as get_countries — leagues are tournaments).          Ar, Get events for a league.          Args:             region_id: Region slug (e (+9 more)

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (18): Any, bool, int, PrematchEventStub, str, SportPesa client — supports ke, tz., Fetch markets and return normalized markets.          Overrides the base because, HTTP client for SportPesa sportsbook API.      SportPesa uses country-specific s (+10 more)

### Community 14 - "Community 14"
Cohesion: 0.26
Nodes (20): Any, MarketRegistry, str, Candidate, _candidates_bet9ja(), _candidates_betika(), _candidates_betpawa(), _candidates_betway() (+12 more)

### Community 15 - "Community 15"
Cohesion: 0.19
Nodes (13): Any, bool, str, _api_prefix(), SportyBet client — supports ng, gh, ke, tz, za, cm, zm.  SportyBet also operat, Get tournaments for a sport (nested under categories).          Returns the sa, Get events for a tournament.          Args:             tournament_id: SportR, Get full event details including all markets.          Args:             even (+5 more)

### Community 16 - "Community 16"
Cohesion: 0.15
Nodes (14): bool, int, bool, MarketMapping, str, MarketRegistry, Return the MarketMapping for a canonical ID, or None if not registered., Return the MarketMapping for a platform-specific ID.          Args: (+6 more)

### Community 17 - "Community 17"
Cohesion: 0.20
Nodes (19): Any, Handle, int, MarketRegistry, str, BookCheck, check_book(), _discover_seed() (+11 more)

### Community 18 - "Community 18"
Cohesion: 0.20
Nodes (10): Any, int, str, BetPawa, Get countries/regions for a sport (with competitions).          Args:, Get tournaments/competitions for a sport.          Returns the same payload as, Get events for a tournament/competition, or all events for a sport.          A, Get full event details including all markets and odds.          Args: (+2 more)

### Community 19 - "Community 19"
Cohesion: 0.21
Nodes (13): Any, bool, str, _betpawa_seed_lookup(), _normalize_sr(), Cross-bookmaker fan-out: seed + sport -> ResolvedEvent.  Each book is resolved, Fetch a BetPawa event by internal id; return (sr_numeric, home, away)., Return the bare numeric SR id from a seed (strips sr:match: prefix). (+5 more)

### Community 20 - "Community 20"
Cohesion: 0.23
Nodes (13): bool, str, _is_bot(), _is_loop(), new_ticket_waiting(), pr_reply_waiting(), True if a #tickets human message is newer than the watermark., True if the NEWEST message in a design thread is from a human (the agent     ow (+5 more)

### Community 21 - "Community 21"
Cohesion: 0.27
Nodes (12): int, str, canary_digest(), cycle_blocked(), cycle_empty(), cycle_pr(), cycle_started(), _humanize_stream() (+4 more)

### Community 22 - "Community 22"
Cohesion: 0.24
Nodes (12): float, object, str, _decimal_string_to_hex64(), _decode_one(), _hex64_to_float64(), _hex_xor64(), BetPawa probability deobfuscation.  BetPawa hides the per-outcome probability (+4 more)

### Community 23 - "Community 23"
Cohesion: 0.21
Nodes (11): Any, str, Dataclasses for the market-add harness., Per-platform parse_markets result., VerifyResult, _market_to_odds(), Run parse_markets on a raw payload and report which canonicals resolve., Serialize one NormalizedMarket's odds into a plain dict. (+3 more)

### Community 24 - "Community 24"
Cohesion: 0.27
Nodes (10): bool, _list_betpawa_events(), Live canary: probe real bookmaker payloads on a schedule and detect drift.  Dr, Flatten BetPawa get_events responses[].responses[] into one list., _struct_bet9ja(), _struct_betika(), _struct_betpawa(), _struct_betway() (+2 more)

### Community 25 - "Community 25"
Cohesion: 0.33
Nodes (10): bool, float, int, str, build_app_jwt(), exchange_jwt_for_token(), _http_post(), mint_installation_token() (+2 more)

### Community 26 - "Community 26"
Cohesion: 0.22
Nodes (9): bool, float, int, str, acquire_lock(), Single-cycle tick lock for the unattended orchestrator.  A scheduled tick acqu, Try to take the lock. Returns True if acquired (writes the lock file),     Fals, Remove the lock file. Idempotent (a missing file is fine). (+1 more)

### Community 27 - "Community 27"
Cohesion: 0.38
Nodes (6): bool, str, gather_state(), Render the live #status board + gather the loop's current state.  Pure render, render_board(), _status_of()

## Knowledge Gaps
- **21 isolated node(s):** `object`, `object`, `Any`, `str`, `Path` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MarketRegistry` connect `Community 16` to `Community 0`, `Community 5`, `Community 6`, `Community 14`, `Community 17`, `Community 24`?**
  _High betweenness centrality (0.311) - this node is a cross-community bridge._
- **Why does `BaseBookmaker` connect `Community 5` to `Community 2`, `Community 10`, `Community 12`, `Community 13`, `Community 15`, `Community 16`, `Community 18`?**
  _High betweenness centrality (0.182) - this node is a cross-community bridge._
- **Why does `CanaryReport` connect `Community 6` to `Community 1`, `Community 3`, `Community 16`, `Community 17`, `Community 24`?**
  _High betweenness centrality (0.178) - this node is a cross-community bridge._
- **Are the 40 inferred relationships involving `BaseBookmaker` (e.g. with `Bet9ja` and `Betika`) actually correct?**
  _`BaseBookmaker` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `MarketRegistry` (e.g. with `BaseBookmaker` and `str`) actually correct?**
  _`MarketRegistry` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `GhRunner` (e.g. with `ArgumentParser` and `Any`) actually correct?**
  _`GhRunner` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `Queue` (e.g. with `ArgumentParser` and `Any`) actually correct?**
  _`Queue` has 15 INFERRED edges - model-reasoned connections that need verification._