"""
Capture one prematch and one live event-detail response per platform.

Run once. Writes raw JSON to tests/fixtures/event_info/{platform}/{phase}.json
so the event_info extractor design / tests can bind to real shapes.

Strategy:
1. Pick a prematch BetPawa event (from a known list).
2. Find a live BetPawa event by listing soccer live events.
3. For each (event, phase): resolve SR id from BetPawa, then fetch event-detail
   from BetPawa, SportyBet, Bet9ja, Betway, MSport. Save responses.

Bet9ja needs a SR-id -> internal-id translation:
  - prematch: build_prematch_event_map (slow walk)
  - live:     scan get_live_events (cheap)
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from bookieskit import Bet9ja, BetPawa, Betway, MSport, SportyBet
from bookieskit.matching import extract_sportradar_id


FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "event_info"

# A known prematch event id (Asian football kicks off later in the day).
PREMATCH_BETPAWA_ID = "33289995"


def _save(platform: str, phase: str, payload: Any) -> None:
    out_dir = FIXTURES_ROOT / platform
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{phase}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"  wrote {path.relative_to(FIXTURES_ROOT.parents[1])}")


async def _find_live_betpawa_event(bp: BetPawa) -> str | None:
    """Return the first live BetPawa event id with markets, or None."""
    resp = await bp.get_events(event_type="LIVE", sport_id="2", take=20)
    # Response shape: {"responses": [{"responses": [<event>...]}]}
    outer = resp.get("responses") or []
    for block in outer:
        for ev in block.get("responses") or []:
            event_id = ev.get("id")
            if event_id:
                return str(event_id)
    return None


async def _capture_for_event(
    bp: BetPawa,
    sb: SportyBet,
    b9: Bet9ja,
    bw: Betway,
    ms: MSport,
    *,
    bp_event_id: str,
    phase: str,
    bet9ja_lookup: dict[str, str],
) -> None:
    print(f"\n=== {phase} :: BetPawa id={bp_event_id} ===")

    # 1. BetPawa detail (anchor for SR id).
    bp_detail = await bp.get_event_detail(event_id=bp_event_id)
    _save("betpawa", phase, bp_detail)
    sr_numeric = extract_sportradar_id(bp_detail, platform="betpawa")
    if not sr_numeric:
        print(f"  no SR id resolvable for BetPawa {bp_event_id} — abort capture")
        return
    sr_prefixed = f"sr:match:{sr_numeric}"
    print(f"  SR id: {sr_numeric}  ({sr_prefixed})")

    # 2. SportyBet (uses sr-prefixed id, live=True for live phase).
    try:
        sb_detail = await sb.get_event_detail(event_id=sr_prefixed, live=(phase == "live"))
        _save("sportybet", phase, sb_detail)
    except Exception as e:
        print(f"  sportybet ERROR: {e}")

    # 3. Betway (uses numeric SR id; same endpoint for both phases).
    try:
        bw_detail = await bw.get_event_detail(event_id=sr_numeric)
        _save("betway", phase, bw_detail)
    except Exception as e:
        print(f"  betway ERROR: {e}")

    # 4. MSport (uses sr-prefixed id, live flag).
    try:
        ms_detail = await ms.get_event_detail(event_id=sr_prefixed, live=(phase == "live"))
        _save("msport", phase, ms_detail)
    except Exception as e:
        print(f"  msport ERROR: {e}")

    # 5. Bet9ja (needs translation; live and prematch endpoints differ).
    internal = bet9ja_lookup.get(sr_numeric)
    if internal is None:
        print(f"  bet9ja: SR {sr_numeric} not in {phase} lookup — skipped")
    else:
        try:
            if phase == "live":
                b9_detail = await b9.get_live_event_detail(event_id=internal)
            else:
                b9_detail = await b9.get_event_detail(event_id=internal)
            _save("bet9ja", phase, b9_detail)
        except Exception as e:
            print(f"  bet9ja ERROR: {e}")


async def main() -> None:
    async with (
        BetPawa(country="ng") as bp,
        SportyBet(country="ng") as sb,
        Bet9ja(country="ng") as b9,
        Betway(country="ng") as bw,
        MSport(country="ng") as ms,
    ):
        # ---- pick a live BetPawa event ----
        live_id = await _find_live_betpawa_event(bp)
        print(f"live BetPawa event id: {live_id}")

        # ---- build Bet9ja lookups ----
        # Live: cheap, single call.
        live_resp = await b9.get_live_events(sport_id="3000001")
        live_events = (live_resp.get("D") or {}).get("E") or {}
        live_lookup = {
            str(ev.get("EXTID", "") or ""): str(internal_id)
            for internal_id, ev in live_events.items()
            if ev.get("EXTID")
        }
        print(f"bet9ja live lookup: {len(live_lookup)} entries")

        # Prematch: slow walk — only if we'll capture a prematch event.
        prematch_lookup = await b9.build_prematch_event_map(sport_id="1")
        print(f"bet9ja prematch lookup: {len(prematch_lookup)} entries")

        # ---- capture prematch ----
        await _capture_for_event(
            bp, sb, b9, bw, ms,
            bp_event_id=PREMATCH_BETPAWA_ID,
            phase="prematch",
            bet9ja_lookup=prematch_lookup,
        )

        # ---- capture live ----
        if live_id:
            await _capture_for_event(
                bp, sb, b9, bw, ms,
                bp_event_id=live_id,
                phase="live",
                bet9ja_lookup=live_lookup,
            )
        else:
            print("\nno live BetPawa event right now — skipping live phase")


if __name__ == "__main__":
    asyncio.run(main())
