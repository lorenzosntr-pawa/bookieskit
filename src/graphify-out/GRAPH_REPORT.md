# Graph Report - src  (2026-08-21)

## Corpus Check
- 45 files · ~36,604 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 992 nodes · 2434 edges · 28 communities (23 shown, 5 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 244 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8c6251d3`
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
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]

## God Nodes (most connected - your core abstractions)
1. `MarketRegistry` - 68 edges
2. `BaseBookmaker` - 60 edges
3. `GhRunner` - 42 edges
4. `str` - 38 edges
5. `Queue` - 37 edges
6. `CanaryReport` - 32 edges
7. `PrematchEventStub` - 31 edges
8. `run()` - 30 edges
9. `WorkItem` - 30 edges
10. `int` - 29 edges

## Surprising Connections (you probably didn't know these)
- `int` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/betpawa.py → bookieskit/base.py
- `bool` --uses--> `MarketRegistry`  [INFERRED]
  bookieskit/markets/parser.py → bookieskit/markets/registry.py
- `int` --uses--> `MarketRegistry`  [INFERRED]
  bookieskit/markets/parser.py → bookieskit/markets/registry.py
- `Bet9ja` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/bet9ja.py → bookieskit/base.py
- `Betika` --uses--> `BaseBookmaker`  [INFERRED]
  bookieskit/bookmakers/betika.py → bookieskit/base.py

## Communities (28 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (99): bool, float, int, MarketMapping, MarketRegistry, object, str, decode_betpawa_probability() (+91 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (75): Any, ArgumentParser, bool, CanaryRunner, GhRunner, int, Namespace, str (+67 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (39): Any, bool, int, PrematchEventStub, str, Any, bool, int (+31 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (59): BookCheck, bool, int, str, WorkItem, str, CanaryReport, BookCheck (+51 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (53): object, _bet9ja_is_live(), extract_kickoff(), extract_live_info(), extract_participants(), is_live_now(), _kickoff_bet9ja(), _kickoff_betika() (+45 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (34): AbstractEventLoop, BaseBookmaker, Any, float, int, str, Base bookmaker client with shared HTTP, retry, and rate-limiting logic., Set or replace the ``Cookie:`` header for subsequent requests.          Works (+26 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (66): Any, ArgumentParser, bool, CanaryRunner, int, Namespace, Path, str (+58 more)

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
Cohesion: 0.05
Nodes (41): Any, str, Any, int, str, Any, bool, str (+33 more)

### Community 11 - "Community 11"
Cohesion: 0.20
Nodes (27): Any, bool, Handle, str, str, Adapter, _bet9ja_fetch(), _bet9ja_resolve() (+19 more)

### Community 12 - "Community 12"
Cohesion: 0.12
Nodes (18): Any, int, PrematchEventStub, str, Betway, Betway client — supports ng, gh, ke, tz, ug, zm., Get regions/countries and leagues for a sport.          Args:             spo, Get tournaments (same as get_countries — leagues are tournaments).          Ar (+10 more)

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (18): Any, bool, int, PrematchEventStub, str, SportPesa client — supports ke, tz., Fetch markets and return normalized markets.          Overrides the base because, HTTP client for SportPesa sportsbook API.      SportPesa uses country-specific s (+10 more)

### Community 14 - "Community 14"
Cohesion: 0.06
Nodes (71): Any, bool, Handle, int, MarketRegistry, str, Any, MarketRegistry (+63 more)

### Community 15 - "Community 15"
Cohesion: 0.19
Nodes (13): Any, bool, str, _api_prefix(), SportyBet client — supports ng, gh, ke, tz, za, cm, zm.  SportyBet also operat, Get tournaments for a sport (nested under categories).          Returns the sa, Get events for a tournament.          Args:             tournament_id: SportR, Get full event details including all markets.          Args:             even (+5 more)

### Community 17 - "Community 17"
Cohesion: 0.07
Nodes (45): Any, bool, Handle, int, MarketRegistry, str, Any, str (+37 more)

### Community 20 - "Community 20"
Cohesion: 0.23
Nodes (13): bool, str, _is_bot(), _is_loop(), new_ticket_waiting(), pr_reply_waiting(), True if a #tickets human message is newer than the watermark., True if the NEWEST message in a design thread is from a human (the agent     ow (+5 more)

### Community 21 - "Community 21"
Cohesion: 0.27
Nodes (12): int, str, canary_digest(), cycle_blocked(), cycle_empty(), cycle_pr(), cycle_started(), _humanize_stream() (+4 more)

### Community 22 - "Community 22"
Cohesion: 0.24
Nodes (12): float, object, str, _decimal_string_to_hex64(), _decode_one(), _hex64_to_float64(), _hex_xor64(), BetPawa probability deobfuscation.  BetPawa hides the per-outcome probability (+4 more)

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
- **21 isolated node(s):** `Any`, `str`, `Path`, `Pattern`, `bool` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MarketRegistry` connect `Community 14` to `Community 0`, `Community 3`, `Community 5`, `Community 6`, `Community 17`?**
  _High betweenness centrality (0.336) - this node is a cross-community bridge._
- **Why does `CanaryReport` connect `Community 6` to `Community 17`, `Community 3`, `Community 1`, `Community 14`?**
  _High betweenness centrality (0.178) - this node is a cross-community bridge._
- **Why does `BaseBookmaker` connect `Community 5` to `Community 2`, `Community 10`, `Community 12`, `Community 13`, `Community 14`, `Community 15`?**
  _High betweenness centrality (0.173) - this node is a cross-community bridge._
- **Are the 44 inferred relationships involving `MarketRegistry` (e.g. with `BaseBookmaker` and `str`) actually correct?**
  _`MarketRegistry` has 44 INFERRED edges - model-reasoned connections that need verification._
- **Are the 40 inferred relationships involving `BaseBookmaker` (e.g. with `Bet9ja` and `Betika`) actually correct?**
  _`BaseBookmaker` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `GhRunner` (e.g. with `ArgumentParser` and `Any`) actually correct?**
  _`GhRunner` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `Queue` (e.g. with `ArgumentParser` and `Any`) actually correct?**
  _`Queue` has 15 INFERRED edges - model-reasoned connections that need verification._