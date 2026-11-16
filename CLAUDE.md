# bookieskit

Async Python clients for 8 African sportsbooks (BetPawa, SportyBet, Bet9ja, Betway, MSport, SportPesa, Betika, ElephantBet), with normalised market mapping/parsing and cross-book event matching (SportRadar or BetGenius id). Consumers: `comparison`, `in-house_sim`, `BOTS`, ONE_SHOTS scrapers — public API changes ripple there.

## Layout
- `src/bookieskit/bookmakers/` — one async client per book (`base.py` shared HTTP).
- `src/bookieskit/markets/` — `MarketRegistry` + `builtin_mappings.py` (canonical ids per book) and `parse_markets` (registry-driven parser).
- `src/bookieskit/matching/` — provider-id extraction and union-find event matching.
- `src/bookieskit/event_info.py` — event metadata helpers.
- `tests/fixtures/` — captured real payloads; parser tests run offline on them.

## Rules
- TDD; conventional-commit messages; smallest surgical change.
- Run tests with `.venv/Scripts/python.exe -X utf8 -m pytest`; `ruff check .` must stay clean. CI runs bare `pytest`/`ruff` on 3.11/3.12/3.13.
- Version lives in BOTH `pyproject.toml` and `src/bookieskit/__init__.py`; keep them in sync. Library/market-facing changes get a `## [Unreleased]` CHANGELOG entry. Release = bump both, promote the CHANGELOG section, push a `v<x.y.z>` tag (the workflow builds and publishes the GitHub Release).
- Commit captured fixtures in the same change that uses them; mine existing fixtures before assuming a live probe is needed.
- Live calls must run from an in-region network: the books geo-block US/cloud IPs (BetPawa returns 403). For upcoming fixtures use prematch endpoints, not the live feed (live hides booking/corner markets).
- graphify: `graphify query "what depends on <symbol>" --graph src/graphify-out/graph.json` before touching code; refresh with `graphify update src` and commit `src/graphify-out/{graph.json,GRAPH_REPORT.md}`. See `docs/GRAPHIFY.md`.

<!-- bp-kit:start -->
## Claude kit (bp-kit)
- **Project**: Async clients for 8 African sportsbooks (shared library). Family: competitor odds. Owner: Lorenzo.
- **Use**: python-reviewer. Orient with skill `bp-context` (project index, decisions, known issues).
- **Note**: Changes ripple into comparison, in-house_sim, BOTS and ONE_SHOTS scrapers. Never read sportpesa_cookie.txt.
- Run `repo-investigator` once to create CODEMAP.md; `/graphify` builds the graph it uses.
<!-- bp-kit:end -->
