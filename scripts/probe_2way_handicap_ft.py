"""One-off probe: discovers Asian Handicap (2-way) market ids and
outcome strings across SportyBet, MSport, Betway, and Betika.

BetPawa (id=3774) and Bet9ja (S_AH) are already locked-in by the
spec — this probe only confirms the other 4. SportPesa is skipped
(Akamai cookie unavailable).

Usage:
    python scripts/probe_2way_handicap_ft.py <BETPAWA_EVENT_ID>

The BetPawa id should be a top-tier upcoming or live soccer event
whose detail response contains marketType.id="3774". The script:
  1. Fetches the BetPawa event detail → extracts the SR id from
     the SPORTRADAR widget.
  2. Confirms BetPawa exposes id=3774 on this event.
  3. For each of the other 4 bookmakers, fetches markets and
     prints candidate ids/keys matching r"handi|asian|spread"
     plus the outcome strings observed.
  4. Writes one JSON fixture per bookmaker under
     tests/fixtures/event_info/<bookmaker>/2way_handicap_ft.json
"""
import asyncio
import json
import re
import sys
from pathlib import Path

from bookieskit import Bet9ja, Betika, BetPawa, Betway, MSport, SportyBet
from bookieskit.matching import extract_sportradar_id

FIXTURE_DIR = Path(__file__).parent.parent / "tests/fixtures/event_info"
PATTERN = re.compile(r"handi|asian|spread", re.IGNORECASE)


async def fetch_betpawa(betpawa_id: str):
    async with BetPawa(country="ng") as bp:
        detail = await bp.get_event_detail(event_id=betpawa_id)
        markets = detail.get("markets") or []
        ah = None
        for m in markets:
            mt = m.get("marketType", {}) or {}
            if str(mt.get("id")) == "3774":
                ah = m
                break
        sr_id = extract_sportradar_id(detail, platform="betpawa")
        participants = detail.get("participants", [])
        home = participants[0]["name"] if len(participants) > 0 else "?"
        away = participants[1]["name"] if len(participants) > 1 else "?"
        return home, away, ah, sr_id, detail


async def probe_sportybet(sr_prefixed):
    async with SportyBet(country="ng") as sb:
        detail = await sb.get_event_detail(event_id=sr_prefixed, live=False)
        if not (detail.get("data") or {}).get("markets"):
            detail = await sb.get_event_detail(
                event_id=sr_prefixed, live=True,
            )
        markets = (detail.get("data") or {}).get("markets") or []
        print(f"\n=== SportyBet ({len(markets)} markets) ===", flush=True)
        for m in markets:
            n = m.get("name", "") or ""
            desc = m.get("desc", "") or ""
            if PATTERN.search(n + " " + desc):
                spec = m.get("specifier", "")
                outs = [o.get("desc") for o in m.get("outcomes") or []]
                print(
                    f"  id={m.get('id')!r}  name={n!r}  desc={desc!r}"
                    f"  spec={spec!r}  outs={outs}",
                    flush=True,
                )
        return detail


async def probe_msport(sr_prefixed):
    async with MSport(country="ng") as ms:
        detail = await ms.get_event_detail(event_id=sr_prefixed, live=False)
        if not (detail.get("data") or {}).get("markets"):
            detail = await ms.get_event_detail(
                event_id=sr_prefixed, live=True,
            )
        markets = (detail.get("data") or {}).get("markets") or []
        print(f"\n=== MSport ({len(markets)} markets) ===", flush=True)
        for m in markets:
            n = m.get("name", "") or ""
            desc = m.get("description", "") or ""
            if PATTERN.search(n + " " + desc):
                spec = m.get("specifiers", "")
                outs = [o.get("description") for o in m.get("outcomes") or []]
                print(
                    f"  id={m.get('id')!r}  name={n!r}  desc={desc!r}"
                    f"  spec={spec!r}  outs={outs}",
                    flush=True,
                )
        return detail


async def probe_betway(sr_numeric):
    async with Betway(country="ng") as bw:
        detail = await bw.get_event_detail(event_id=sr_numeric)
        sport_event = detail.get("sportEvent") or {}
        home = sport_event.get("homeTeam") or "?"
        away = sport_event.get("awayTeam") or "?"
        print(f"\n=== Betway (home={home!r}, away={away!r}) ===", flush=True)
        all_mig = []
        all_outs = []
        all_prices = []
        for skip in range(0, 600, 100):
            r = await bw.get_event_markets(
                event_id=sr_numeric, skip=skip, take=100,
            )
            mig = r.get("marketsInGroup") or []
            if not mig:
                break
            all_mig.extend(mig)
            all_outs.extend(r.get("outcomes") or [])
            all_prices.extend(r.get("prices") or [])
            if len(mig) < 100:
                break
        for m in all_mig:
            n = m.get("name", "") or ""
            if PATTERN.search(n):
                handicap = m.get("handicap")
                mid = m.get("marketId")
                print(
                    f"  name={n!r}  handicap={handicap}"
                    f"  marketId={mid!r}",
                    flush=True,
                )
        merged = {
            "marketsInGroup": all_mig,
            "outcomes": all_outs,
            "prices": all_prices,
            "sportEvent": sport_event,
        }
        return merged


async def probe_betika(sr_numeric):
    async with Betika(country="ke") as bk:
        # Walk listing to find the match by parent_match_id
        match_id = comp_id = None
        for page in range(1, 10):
            listing = await bk.get_matches(
                sport_id=14, page=page, limit=100,
            )
            data = listing.get("data") or []
            if not data:
                break
            for m in data:
                if str(m.get("parent_match_id", "")) == sr_numeric:
                    match_id = m.get("match_id")
                    comp_id = m.get("competition_id")
                    break
            if match_id is not None:
                break
        if match_id is None:
            print(
                "\n=== Betika === SR id not found in first 9 listing pages",
                flush=True,
            )
            return None
        # Fetch sub_type_id=16 specifically (the Asian Handicap candidate)
        r = await bk.get_matches(
            sport_id=14,
            match_id=str(match_id),
            competition_id=str(comp_id) if comp_id else None,
            sub_type_id="16",
            limit=1,
        )
        match = (r.get("data") or [{}])[0]
        groups = match.get("odds") or []
        print(
            f"\n=== Betika (match_id={match_id}, {len(groups)} groups) ===",
            flush=True,
        )
        for g in groups:
            sti = g.get("sub_type_id")
            name = g.get("name", "")
            outs = [s.get("display") for s in g.get("odds") or []][:6]
            print(
                f"  sub_type_id={sti!r}  name={name!r}  outs_sample={outs}",
                flush=True,
            )
        return r


async def main():
    if len(sys.argv) < 2:
        print(
            "usage: python scripts/probe_2way_handicap_ft.py "
            "<BETPAWA_EVENT_ID>"
        )
        sys.exit(1)
    bp_id = sys.argv[1]

    home, away, ah, sr_numeric, bp_detail = await fetch_betpawa(bp_id)
    print(
        f"BetPawa event: {home} vs {away}  SR={sr_numeric}",
        flush=True,
    )
    if ah is None:
        print(
            "ERROR: BetPawa event does NOT expose id=3774 — pick a different event",
            flush=True,
        )
        sys.exit(1)
    print(
        f"BetPawa id=3774 confirmed: name="
        f"{ah.get('marketType', {}).get('name')!r}",
        flush=True,
    )
    if sr_numeric is None:
        print("ERROR: no SPORTRADAR widget on this BetPawa event", flush=True)
        sys.exit(1)
    sr_prefixed = f"sr:match:{sr_numeric}"

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    # Each probe writes its own fixture
    captures = {}
    for name, fn in [
        ("sportybet", probe_sportybet),
        ("msport", probe_msport),
    ]:
        try:
            captures[name] = await fn(sr_prefixed)
        except Exception as exc:
            print(f"[{name}] probe failed: {exc!r}", flush=True)
    try:
        captures["betway"] = await probe_betway(sr_numeric)
    except Exception as exc:
        print(f"[betway] probe failed: {exc!r}", flush=True)
    try:
        captures["betika"] = await probe_betika(sr_numeric)
    except Exception as exc:
        print(f"[betika] probe failed: {exc!r}", flush=True)

    for name, capture in captures.items():
        if capture is None:
            continue
        path = FIXTURE_DIR / name / "2way_handicap_ft.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(capture, indent=2), encoding="utf-8")
        print(f"[{name}] wrote {path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
