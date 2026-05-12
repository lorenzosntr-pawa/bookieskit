"""Given a SportRadar event ID (live or prematch), fetch odds for the
mapped (built-in) markets from each of the 6 bookmakers.

Usage:
    python examples/odds_for_sr_id.py <sr_id> [--prematch]

SR ID accepted as bare numeric ("69339436") or prefixed ("sr:match:69339436").
Defaults to live (productId=1 / live endpoints). Pass --prematch for upcoming
events.

Resolution per bookmaker:
- SportyBet, MSport: eventId IS sr:match:XXX → direct lookup,
  productId switch by --live/--prematch
- Betway: eventId IS the bare numeric SR id; uses get_markets() (separate
  markets endpoint, returns same shape for live + prematch)
- Bet9ja: SR id → internal id via find_event_id_by_sr_id (live scan); then
  get_event_detail
- BetPawa, SportPesa: no SR-id reverse search yet. Skipped here.
  (SportPesa also requires warmed Akamai cookies — see docs/sportpesa.md.)
"""

import asyncio
import sys

# SportPesa is imported but currently unused in the fan-out because there is
# no SR-id → SportPesa-internal-id lookup yet. Kept here to make extension
# obvious once a reverse-search path lands.
from bookieskit import (
    Bet9ja,
    Betway,
    MSport,
    SportPesa,  # noqa: F401
    SportyBet,
)
from bookieskit.markets import parse_markets


def _normalize_sr_id(s: str) -> tuple[str, str]:
    if s.startswith("sr:match:"):
        return s[len("sr:match:"):], s
    return s, f"sr:match:{s}"


async def odds_sportybet(sr_numeric: str, sr_prefixed: str, *, live: bool) -> dict:
    out = {"name": "SportyBet"}
    async with SportyBet(country="ng") as sb:
        try:
            detail = await sb.get_event_detail(event_id=sr_prefixed, live=live)
            data = detail.get("data") or {}
            if not data or not data.get("markets"):
                return {**out, "status": "no markets returned", "raw_event_id": sr_prefixed}  # noqa: E501
            out["home"] = data.get("homeTeamName") or data.get("homeTeam")
            out["away"] = data.get("awayTeamName") or data.get("awayTeam")
            out["markets"] = parse_markets(detail, platform="sportybet")
            out["status"] = "ok"
        except Exception as e:
            out["status"] = f"error: {e}"
    return out


async def odds_msport(sr_numeric: str, sr_prefixed: str, *, live: bool) -> dict:
    out = {"name": "MSport"}
    async with MSport(country="ng") as ms:
        try:
            detail = await ms.get_event_detail(event_id=sr_prefixed, live=live)
            data = detail.get("data") or {}
            if not data or not data.get("markets"):
                return {**out, "status": "no markets returned", "raw_event_id": sr_prefixed}  # noqa: E501
            out["home"] = data.get("homeTeam")
            out["away"] = data.get("awayTeam")
            out["markets"] = parse_markets(detail, platform="msport")
            out["status"] = "ok"
        except Exception as e:
            out["status"] = f"error: {e}"
    return out


async def odds_betway(sr_numeric: str, sr_prefixed: str, *, live: bool) -> dict:
    out = {"name": "Betway"}
    async with Betway(country="ng") as bw:
        try:
            # Pull team names from event detail
            detail = await bw.get_event_detail(event_id=sr_numeric)
            sport_event = detail.get("sportEvent") or {}
            name = sport_event.get("name") or ""
            home, away = "?", "?"
            if " vs" in name:
                parts = name.split(" vs", 1)
                home = parts[0].strip()
                away = parts[1].strip(" .")
            out["home"] = home
            out["away"] = away
            # Markets come from the dedicated markets endpoint
            out["markets"] = await bw.get_markets(event_id=sr_numeric)
            out["status"] = "ok"
        except Exception as e:
            out["status"] = f"error: {e}"
    return out


async def odds_bet9ja(sr_numeric: str, sr_prefixed: str, *, live: bool) -> dict:
    out = {"name": "Bet9ja"}
    async with Bet9ja(country="ng") as b9:
        try:
            internal = await b9.find_event_id_by_sr_id(sr_numeric)
            if internal is None:
                return {**out, "status": "not found in live events"}
            if live:
                detail = await b9.get_live_event_detail(event_id=internal)
            else:
                detail = await b9.get_event_detail(event_id=internal)
            data = detail.get("D") or {}
            ds = data.get("DS") or (data.get("A") or {}).get("DS") or ""
            parts = ds.split(" - ") if " - " in ds else ds.split(" v ")
            out["home"] = parts[0] if parts else "?"
            out["away"] = parts[-1] if len(parts) > 1 else "?"
            out["markets"] = parse_markets(detail, platform="bet9ja")
            out["status"] = "ok"
            out["internal_id"] = internal
        except Exception as e:
            out["status"] = f"error: {e}"
    return out


async def odds_betpawa(sr_numeric: str, sr_prefixed: str, *, live: bool) -> dict:
    return {
        "name": "BetPawa",
        "status": "skipped (no SR-ID search yet — pass a BetPawa internal id directly)",
    }


async def odds_sportpesa(sr_numeric: str, sr_prefixed: str, *, live: bool) -> dict:
    return {
        "name": "SportPesa",
        "status": "skipped (no SR-ID reverse search yet; also requires warmed Akamai cookies — see docs/sportpesa.md)",  # noqa: E501
    }


def _print(r: dict) -> None:
    name = r["name"]
    status = r.get("status", "?")
    print(f"\n=== {name} ===")
    if status != "ok":
        print(f"  status: {status}")
        return
    home = r.get("home") or "?"
    away = r.get("away") or "?"
    extra = f" (internal_id={r['internal_id']})" if "internal_id" in r else ""
    print(f"  Event: {home} vs {away}{extra}")
    markets = r.get("markets") or []
    print(f"  Mapped markets matched: {len(markets)}")
    for m in markets:
        if m.lines:
            for line in sorted(m.lines.keys()):
                odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.lines[line])
                print(f"    {m.name} [{line}]: {odds}")
        else:
            odds = ", ".join(f"{o.canonical_name}={o.odds}" for o in m.outcomes)
            print(f"    {m.name}: {odds}")


async def main(sr_input: str, live: bool):
    sr_numeric, sr_prefixed = _normalize_sr_id(sr_input)
    mode = "LIVE" if live else "PREMATCH"
    print(f"Looking up SR ID: {sr_prefixed} (numeric: {sr_numeric})  mode: {mode}")
    print("Mapped markets in registry: 1X2, Over/Under, BTTS, Double Chance")

    results = await asyncio.gather(
        odds_sportybet(sr_numeric, sr_prefixed, live=live),
        odds_msport(sr_numeric, sr_prefixed, live=live),
        odds_betway(sr_numeric, sr_prefixed, live=live),
        odds_bet9ja(sr_numeric, sr_prefixed, live=live),
        odds_betpawa(sr_numeric, sr_prefixed, live=live),
        odds_sportpesa(sr_numeric, sr_prefixed, live=live),
    )
    for r in results:
        _print(r)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("usage: python examples/odds_for_sr_id.py <sr_id> [--prematch]")
        sys.exit(1)
    sr_input = args[0]
    live = "--prematch" not in args
    asyncio.run(main(sr_input, live))
