"""Compare mapped-market coverage across all 7 bookmakers for every
event in a BetPawa competition.

WHAT THIS DOES
    1. Walks one BetPawa competition (defaults to NG comp 11971).
    2. For each event, extracts the SportRadar id from BetPawa's
       SPORTRADAR widget.
    3. Looks the same event up on each of the other 6 bookmakers,
       using the country variant where the competition naturally
       lives: ``ng`` for Bet9ja / SportyBet / MSport / Betway, and
       ``ke`` for Betika / SportPesa (neither bookmaker operates in
       Nigeria, so the Kenyan storefront is the cross-bookmaker
       proxy — same SR-id feed under the hood).
    4. Parses each bookmaker's full markets payload through the
       lib's canonical-market mappings (1X2, O/U, BTTS, DC, plus
       1Up/2Up where supported).
    5. Prints a per-event table summarising which canonical markets
       each bookmaker exposed.

PER-BOOKMAKER LOOKUP STRATEGY
    * **SportyBet / MSport**: SR id IS the eventId
      (``sr:match:<numeric>``). One get_event_detail call per event.
    * **Betway**: eventId is the bare numeric SR id. One get_markets
      call per event.
    * **Bet9ja**: internal ids — the prematch SR-id → internal map
      is pre-built once at startup via
      ``build_prematch_event_map(sport_id="1")``.
    * **Betika**: walks ``iter_all_prematch_events(sport_id=14)``
      once at startup to build a ``{sr_id: match_id}`` map, then
      one ``get_event_markets`` call per matched event.
    * **SportPesa**: same as Betika — walks
      ``iter_all_prematch_events()``, builds a ``{sr_id: game_id}``
      map, then one ``get_event_markets`` per match. Requires
      ``SPORTPESA_COOKIE`` env var (or ``sportpesa_cookie.txt`` in
      the project root) with a warmed Akamai cookie.

USAGE
    python examples/compare_betpawa_competition_full.py            # comp 11971
    python examples/compare_betpawa_competition_full.py 12345      # custom comp
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from bookieskit import (
    Bet9ja,
    Betika,
    BetPawa,
    Betway,
    MSport,
    SportPesa,
    SportyBet,
)
from bookieskit.markets import parse_markets
from bookieskit.matching import extract_event_ids

logger = logging.getLogger(__name__)

DEFAULT_COMPETITION_ID = "11971"  # BetPawa NG NBA (basketball)
NG_COUNTRY = "ng"
KE_COUNTRY = "ke"  # Betika + SportPesa proxy
SPORTPESA_COOKIE_FILE = "sportpesa_cookie.txt"

# Per-sport identifiers across bookmakers. The BetPawa response's
# `category.id` selects the row. (NBA is sport_id=3 on BetPawa NG.)
SPORT_CONFIG = {
    "2": {  # BetPawa soccer
        "name": "soccer",
        "bet9ja_sport_id": "1",
        "betika_sport_id": 14,
        "sportpesa_sport_id": 1,
        "betika_sub_type_ids": ("1", "10", "18", "29"),
        "expected_canonicals": (
            "1x2_ft", "over_under_ft", "btts_ft", "double_chance_ft",
        ),
    },
    "3": {  # BetPawa basketball
        "name": "basketball",
        "bet9ja_sport_id": "2",
        "betika_sport_id": 30,
        "sportpesa_sport_id": 2,
        "betika_sub_type_ids": ("219", "225"),  # no handicap on Betika basketball
        "expected_canonicals": (
            "moneyline_basketball_ft",
            "over_under_basketball_ft",
            "handicap_basketball_ft",
        ),
    },
}


def _load_sportpesa_cookie() -> str | None:
    """Read a warmed SportPesa cookie from env or file. None if absent."""
    env = os.environ.get("SPORTPESA_COOKIE")
    if env:
        return env.strip()
    path = Path(SPORTPESA_COOKIE_FILE)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return None


# ---- Per-event lookup helpers --------------------------------------------


async def fetch_betpawa(bp: BetPawa, betpawa_id: str) -> dict:
    """Return {sr_id, home, away, markets} for one BetPawa event."""
    detail = await bp.get_event_detail(event_id=betpawa_id)
    ids = extract_event_ids(detail, platform="betpawa")
    parts = detail.get("participants") or []
    home = (
        parts[0].get("name") if len(parts) > 0 and isinstance(parts[0], dict) else None
    )
    away = (
        parts[1].get("name") if len(parts) > 1 and isinstance(parts[1], dict) else None
    )
    markets = parse_markets(detail, platform="betpawa")
    return {
        "sr_id": ids.sportradar,
        "home": home or "?",
        "away": away or "?",
        "markets": markets,
    }


async def fetch_sportybet(sb: SportyBet, sr_id: str) -> list:
    try:
        detail = await sb.get_event_detail(event_id=f"sr:match:{sr_id}")
        return parse_markets(detail, platform="sportybet")
    except Exception as e:
        logger.warning("SportyBet sr:%s failed: %r", sr_id, e)
        return []


async def fetch_msport(ms: MSport, sr_id: str) -> list:
    try:
        detail = await ms.get_event_detail(event_id=f"sr:match:{sr_id}")
        return parse_markets(detail, platform="msport")
    except Exception as e:
        logger.warning("MSport sr:%s failed: %r", sr_id, e)
        return []


async def fetch_betway(bw: Betway, sr_id: str) -> list:
    try:
        return await bw.get_markets(event_id=sr_id)
    except Exception as e:
        logger.warning("Betway sr:%s failed: %r", sr_id, e)
        return []


async def fetch_bet9ja(
    b9: Bet9ja, sr_id: str, lookup: dict[str, str]
) -> list:
    internal = lookup.get(sr_id)
    if internal is None:
        return []
    try:
        detail = await b9.get_event_detail(event_id=internal)
        return parse_markets(detail, platform="bet9ja")
    except Exception as e:
        logger.warning("Bet9ja sr:%s (internal %s) failed: %r", sr_id, internal, e)
        return []


async def fetch_betika(
    bk: Betika,
    sr_id: str,
    lookup: dict[str, str],
    sub_type_ids: tuple[str, ...],
    sport_id: int,
) -> list:
    match_id = lookup.get(sr_id)
    if match_id is None:
        return []
    try:
        return await fetch_betika_markets_sportaware(
            bk, match_id, sub_type_ids, sport_id,
        )
    except Exception as e:
        logger.warning("Betika sr:%s (match %s) failed: %r", sr_id, match_id, e)
        return []


async def fetch_sportpesa(
    sp: SportPesa, sr_id: str, lookup: dict[str, str], sport_name: str,
) -> list:
    game_id = lookup.get(sr_id)
    if game_id is None:
        return []
    try:
        # SportPesa's market ids are sport-scoped (id=52 is football O/U
        # AND basketball O/U). Use the sport-aware parse_markets path.
        from bookieskit.markets.parser import parse_markets as _parse
        raw = await sp.get_event_markets(event_id=game_id)
        return _parse(raw, platform="sportpesa", sport=sport_name)
    except Exception as e:
        logger.warning("SportPesa sr:%s (game %s) failed: %r", sr_id, game_id, e)
        return []


# ---- Startup index builders ----------------------------------------------


async def build_betika_index(
    bk: Betika, sport_id: int,
) -> dict[str, str]:
    """Walk Betika events for one sport; return ``{sr_id: match_id}``.

    iter_all_prematch_events yields stubs without SR id, so this uses
    the raw paged API (``meta.total``-driven fan-out) to read
    ``data[i].parent_match_id`` per match — that field IS the SR id.
    """
    import math
    first = await bk.get_matches(
        sport_id=sport_id, page=1, limit=100, period_id=9,
    )
    meta_total = first.get("meta", {}).get("total", 0)
    try:
        total = int(meta_total)
    except (TypeError, ValueError):
        total = 0
    pages = max(1, math.ceil(total / 100)) if total > 0 else 1

    mapping: dict[str, str] = {}

    def _collect(page_data: dict) -> None:
        for m in page_data.get("data") or []:
            sr = m.get("parent_match_id")
            if sr in (None, 0, "0", ""):
                continue
            mapping[str(sr)] = str(m.get("match_id"))

    _collect(first)
    if pages > 1:
        results = await asyncio.gather(*(
            bk.get_matches(
                sport_id=sport_id, page=p, limit=100, period_id=9,
            )
            for p in range(2, pages + 1)
        ), return_exceptions=True)
        for r in results:
            if isinstance(r, dict):
                _collect(r)
    return mapping


async def build_sportpesa_index(
    sp: SportPesa, sportpesa_sport_id: int,
) -> dict[str, str]:
    """Walk SportPesa events for one sport; return ``{sr_id: game_id}``.

    SportPesa surfaces betradarId on each event in the list responses,
    so walk get_navigation -> per-league get_events directly to read
    each event's betradarId.
    """
    mapping: dict[str, str] = {}
    try:
        nav = await sp.get_navigation()
    except Exception as e:
        logger.warning("SportPesa get_navigation failed: %r", e)
        return mapping
    league_calls = []
    for sport in nav:
        if not isinstance(sport, dict) or sport.get("id") != sportpesa_sport_id:
            continue
        for country in sport.get("countries") or []:
            for league in country.get("leagues") or []:
                lid = league.get("id")
                if lid is not None:
                    league_calls.append(str(lid))

    async def _fetch(lid: str) -> list:
        try:
            evs = await sp.get_events(
                sport_id=str(sportpesa_sport_id), league_id=lid, pag_count=100,
            )
            return evs if isinstance(evs, list) else []
        except Exception:
            return []

    results = await asyncio.gather(*(_fetch(lid) for lid in league_calls))
    for events in results:
        for ev in events:
            if not isinstance(ev, dict):
                continue
            sr = ev.get("betradarId")
            if sr in (None, 0, "0", ""):
                continue
            mapping[str(sr)] = str(ev.get("id"))
    return mapping


async def fetch_betika_markets_sportaware(
    bk: Betika,
    match_id: str,
    sub_type_ids: tuple[str, ...],
    sport_id: int,
) -> list:
    """Aggregate Betika markets for any sport.

    The lib's ``Betika.get_event_markets`` hardcodes the four soccer
    universal sub_type_ids (1/10/18/29). For other sports (basketball:
    219/225, etc.) we have to assemble the merged shape ourselves.

    Crucially, every request MUST include ``sport_id`` — Betika's
    ``match_id`` namespace is per-sport, so a bare lookup by
    ``match_id`` returns the soccer event with the same numeric id
    (often a totally different match) rather than the intended
    basketball event. This was the silent gap in earlier versions
    that made Betika appear empty for NBA games.
    """
    from bookieskit.markets.parser import parse_markets as _parse

    async def _fetch_one(stid: str) -> dict:
        return await bk._request(
            "GET", "/v1/uo/matches",
            params={
                "match_id": match_id,
                "sport_id": str(sport_id),
                "sub_type_id": stid,
                "limit": "1",
            },
        )

    responses = await asyncio.gather(
        *(_fetch_one(stid) for stid in sub_type_ids), return_exceptions=True,
    )
    merged_odds: list[dict] = []
    merged_match: dict | None = None
    for r in responses:
        if not isinstance(r, dict):
            continue
        data = r.get("data") or []
        if not data or not isinstance(data[0], dict):
            continue
        if merged_match is None:
            merged_match = dict(data[0])
            merged_match["odds"] = []
        for grp in data[0].get("odds") or []:
            if isinstance(grp, dict):
                merged_odds.append(grp)
    if merged_match is None:
        return []
    merged_match["odds"] = merged_odds
    aggregated = {"data": [merged_match], "meta": {}}
    return _parse(aggregated, platform="betika")


# ---- Pretty-print ---------------------------------------------------------


def _canonical_short(canonical_id: str) -> str:
    return {
        "1x2_ft": "1X2",
        "over_under_ft": "O/U",
        "btts_ft": "BTTS",
        "double_chance_ft": "DC",
        "1x2_1up_ft": "1Up",
        "1x2_2up_ft": "2Up",
        "moneyline_basketball_ft": "ML",
        "over_under_basketball_ft": "O/U",
        "handicap_basketball_ft": "HCAP",
    }.get(canonical_id, canonical_id)


def _print_event_row(
    name: str,
    sr_id: str | None,
    by_book: dict[str, list],
    expected_canonicals: tuple[str, ...],
) -> None:
    """Render one event's coverage table.

    Only markets whose canonical_id is in ``expected_canonicals`` for
    the current sport are shown — bookmakers occasionally surface
    cross-sport canonicals (e.g. SportyBet's basketball events include
    a 3-way 1X2 market that the parser canonicalises to ``1x2_ft``);
    listing those would clutter the per-sport output.
    """
    print()
    print(f"  {name}  (sr_id={sr_id or '—'})")
    cols = ["BetPawa", "SportyBet", "MSport", "Betway", "Bet9ja", "Betika", "SportPesa"]
    for book in cols:
        markets = by_book.get(book) or []
        filtered = [m for m in markets if m.canonical_id in expected_canonicals]
        if not filtered:
            extra = ""
            if markets:
                extra = (
                    f"  (had {len(markets)} cross-sport "
                    f"markets the lib also recognises)"
                )
            print(f"    {book:<10}  (no expected markets){extra}")
            continue
        cells = []
        for canonical in expected_canonicals:
            m = next((x for x in filtered if x.canonical_id == canonical), None)
            if m is None:
                cells.append(f"{_canonical_short(canonical)}=—")
                continue
            short = _canonical_short(canonical)
            if m.lines:
                cells.append(f"{short}={len(m.lines)}L")
            else:
                cells.append(f"{short}={len(m.outcomes)}o")
        print(f"    {book:<10}  " + "  ".join(cells))


# ---- Main -----------------------------------------------------------------


async def main(competition_id: str, sport_id: str) -> None:
    cfg = SPORT_CONFIG.get(sport_id)
    if cfg is None:
        print(
            f"Unknown BetPawa sport_id={sport_id!r}; supported: "
            f"{list(SPORT_CONFIG.keys())}"
        )
        return
    print(
        f"Sport: {cfg['name']} (BetPawa sport_id={sport_id})"
    )
    sportpesa_cookie = _load_sportpesa_cookie()
    if sportpesa_cookie is None:
        print(
            "(no SportPesa cookie found in env SPORTPESA_COOKIE or "
            "sportpesa_cookie.txt — SportPesa column will be empty)"
        )

    async with (
        BetPawa(country=NG_COUNTRY) as bp,
        SportyBet(country=NG_COUNTRY) as sb,
        MSport(country=NG_COUNTRY) as ms,
        Betway(country=NG_COUNTRY) as bw,
        Bet9ja(country=NG_COUNTRY) as b9,
        Betika(country=KE_COUNTRY) as bk,
    ):
        # 0a. BetPawa: enumerate events for this sport's comp.
        raw = await bp.get_events(
            tournament_id=competition_id, sport_id=sport_id,
        )
        events = (raw.get("responses") or [{}])[0].get("responses") or []
        print(
            f"BetPawa NG competition {competition_id}: "
            f"{len(events)} event(s)"
        )
        if not events:
            print("Nothing to do.")
            return

        # 0b. Pre-build the Bet9ja, Betika, SportPesa SR-id indexes
        #     concurrently. Each is sport-specific.
        print("Building lookup indexes (Bet9ja, Betika, SportPesa)...")
        index_tasks = [
            b9.build_prematch_event_map(sport_id=cfg["bet9ja_sport_id"]),
            build_betika_index(bk, sport_id=cfg["betika_sport_id"]),
        ]
        if sportpesa_cookie is not None:
            sp_ctx: SportPesa | None = SportPesa(
                country=KE_COUNTRY, cookie=sportpesa_cookie
            )
            await sp_ctx.__aenter__()
            index_tasks.append(
                build_sportpesa_index(sp_ctx, cfg["sportpesa_sport_id"])
            )
        else:
            sp_ctx = None

        results = await asyncio.gather(*index_tasks, return_exceptions=True)
        bet9ja_map = results[0] if isinstance(results[0], dict) else {}
        betika_map = results[1] if isinstance(results[1], dict) else {}
        sportpesa_map = (
            results[2] if (len(results) > 2 and isinstance(results[2], dict))
            else {}
        )
        print(
            f"  Bet9ja: {len(bet9ja_map)} entries  "
            f"Betika: {len(betika_map)} entries  "
            f"SportPesa: {len(sportpesa_map)} entries"
        )

        try:
            # 1. Per-event fan-out
            for i, ev in enumerate(events, start=1):
                bp_id = ev.get("id")
                if bp_id is None:
                    continue
                bp_result = await fetch_betpawa(bp, str(bp_id))
                sr_id = bp_result["sr_id"]
                name = f"{bp_result['home']} vs {bp_result['away']}"

                by_book = {"BetPawa": bp_result["markets"]}

                if sr_id:
                    sb_task = fetch_sportybet(sb, sr_id)
                    ms_task = fetch_msport(ms, sr_id)
                    bw_task = fetch_betway(bw, sr_id)
                    b9_task = fetch_bet9ja(b9, sr_id, bet9ja_map)
                    bk_task = fetch_betika(
                        bk, sr_id, betika_map,
                        cfg["betika_sub_type_ids"],
                        cfg["betika_sport_id"],
                    )
                    if sp_ctx is not None:
                        sp_task = fetch_sportpesa(
                            sp_ctx, sr_id, sportpesa_map, cfg["name"],
                        )
                        sb_m, ms_m, bw_m, b9_m, bk_m, sp_m = await asyncio.gather(
                            sb_task, ms_task, bw_task, b9_task, bk_task, sp_task,
                        )
                    else:
                        sb_m, ms_m, bw_m, b9_m, bk_m = await asyncio.gather(
                            sb_task, ms_task, bw_task, b9_task, bk_task,
                        )
                        sp_m = []
                    by_book.update({
                        "SportyBet": sb_m,
                        "MSport": ms_m,
                        "Betway": bw_m,
                        "Bet9ja": b9_m,
                        "Betika": bk_m,
                        "SportPesa": sp_m,
                    })

                print(f"\n[{i}/{len(events)}]", end="")
                _print_event_row(
                    name, sr_id, by_book, cfg["expected_canonicals"],
                )
        finally:
            if sp_ctx is not None:
                await sp_ctx.__aexit__(None, None, None)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    comp_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_COMPETITION_ID
    # BetPawa sport_id: 2=soccer, 3=basketball. Default to basketball
    # since the default comp 11971 is NBA. Pass as second CLI arg for
    # any other sport.
    sport_id = sys.argv[2] if len(sys.argv) > 2 else "3"
    asyncio.run(main(comp_id, sport_id))
