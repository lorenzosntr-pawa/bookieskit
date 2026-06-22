"""Discover candidate markets on a raw payload (by regex term) and diff the
payload against the registry (``unmapped``).

NOTE on Betway: Betway maps markets by NAME, so a candidate's ``market_id``
here is the raw ``marketId``, not the registry key. ``unmapped`` for Betway
is therefore a best-effort discovery aid — it can surface false positives
from per-team placeholder markets (e.g. "<Home Team> Total Goals"). Treat
Betway unmapped results as hints to investigate, not as ground truth.
"""

import re
from typing import Any

from bookieskit.devtools.types import Candidate
from bookieskit.markets.parser import _parse_bet9ja_key
from bookieskit.markets.registry import MarketRegistry


def iter_candidates(payload: Any, platform: str) -> list[Candidate]:
    """Read every market on a raw payload as a Candidate (per platform)."""
    readers = {
        "betpawa": _candidates_betpawa,
        "sportybet": _candidates_sportybet,
        "msport": _candidates_msport,
        "bet9ja": _candidates_bet9ja,
        "betway": _candidates_betway,
        "sportpesa": _candidates_sportpesa,
        "betika": _candidates_betika,
    }
    reader = readers.get(platform)
    if reader is None:
        return []
    return reader(payload)


def discover(payload: Any, platform: str, term: str) -> list[Candidate]:
    """Return candidates whose name or any outcome matches ``term`` (regex).

    Case-insensitive. Matches against the market name and each outcome
    string.
    """
    pattern = re.compile(term, re.IGNORECASE)
    out: list[Candidate] = []
    for cand in iter_candidates(payload, platform):
        haystack = " ".join([cand.name, *cand.outcomes])
        if pattern.search(haystack):
            out.append(cand)
    return out


def unmapped(
    payload: Any,
    platform: str,
    sport: str,
    registry: MarketRegistry | None = None,
) -> list[Candidate]:
    """Return candidates whose platform id/key the registry does NOT map.

    A candidate is "unmapped" iff
    ``registry.get_by_platform_id(platform, candidate.market_id,
    sport=sport)`` returns None. Candidates with no usable id are kept
    (they cannot be matched). See the module docstring for the Betway
    caveat.
    """
    if registry is None:
        registry = MarketRegistry()
    out: list[Candidate] = []
    for cand in iter_candidates(payload, platform):
        if cand.market_id is None:
            out.append(cand)
            continue
        if registry.get_by_platform_id(
            platform, cand.market_id, sport=sport
        ) is None:
            out.append(cand)
    return out


# ---- Per-platform readers -------------------------------------------------


def _candidates_betpawa(payload: Any) -> list[Candidate]:
    out: list[Candidate] = []
    for m in payload.get("markets", []) or []:
        mt = m.get("marketType") or {}
        mid = mt.get("id", m.get("id"))
        rows = m.get("row", [])
        if not isinstance(rows, list):
            rows = [rows] if rows else []
        outcomes: list[str] = []
        for row in rows:
            for price in row.get("prices", []) or []:
                name = price.get("name", price.get("displayName"))
                if name:
                    outcomes.append(str(name))
        out.append(Candidate(
            platform="betpawa",
            market_id=str(mid) if mid is not None else None,
            name=str(mt.get("name", "")),
            specifier=None,
            outcomes=outcomes,
        ))
    return out


def _candidates_sportybet(payload: Any) -> list[Candidate]:
    data = payload.get("data", payload)
    out: list[Candidate] = []
    for m in data.get("markets", []) or []:
        out.append(Candidate(
            platform="sportybet",
            market_id=str(m.get("id")) if m.get("id") is not None else None,
            name=str(m.get("name", "")),
            specifier=m.get("specifier") or None,
            outcomes=[
                str(o.get("desc", "")) for o in m.get("outcomes", []) or []
            ],
        ))
    return out


def _candidates_msport(payload: Any) -> list[Candidate]:
    data = payload.get("data", payload)
    out: list[Candidate] = []
    for m in data.get("markets", []) or []:
        out.append(Candidate(
            platform="msport",
            market_id=str(m.get("id")) if m.get("id") is not None else None,
            name=str(m.get("name") or m.get("description") or ""),
            specifier=m.get("specifiers") or None,
            outcomes=[
                str(o.get("description", ""))
                for o in m.get("outcomes", []) or []
            ],
        ))
    return out


def _candidates_bet9ja(payload: Any) -> list[Candidate]:
    data = payload.get("D")
    if not isinstance(data, dict):
        return []
    odds = data.get("O", {}) or {}
    # market_key -> set of outcome suffixes
    by_key: dict[str, list[str]] = {}
    for key in odds:
        k = key
        if k.startswith("LIVES_"):
            k = "S_" + k[len("LIVES_"):]
        parsed = _parse_bet9ja_key(k)
        if parsed is None:
            continue
        market_key, _line, suffix = parsed
        by_key.setdefault(market_key, [])
        if suffix not in by_key[market_key]:
            by_key[market_key].append(suffix)
    return [
        Candidate(
            platform="bet9ja",
            market_id=key,
            name=key,
            specifier=None,
            outcomes=suffixes,
        )
        for key, suffixes in by_key.items()
    ]


def _candidates_betway(payload: Any) -> list[Candidate]:
    outcomes_by_market: dict[str, list[str]] = {}
    for o in payload.get("outcomes", []) or []:
        mid = str(o.get("marketId", ""))
        outcomes_by_market.setdefault(mid, []).append(str(o.get("name", "")))
    out: list[Candidate] = []
    for m in payload.get("marketsInGroup", []) or []:
        mid = str(m.get("marketId", ""))
        out.append(Candidate(
            platform="betway",
            market_id=mid or None,
            name=str(m.get("name", "")),
            specifier=None,
            outcomes=outcomes_by_market.get(mid, []),
        ))
    return out


def _candidates_sportpesa(payload: Any) -> list[Candidate]:
    if not isinstance(payload, dict) or not payload:
        return []
    first = next(iter(payload.values()), None)
    if not isinstance(first, list):
        return []
    out: list[Candidate] = []
    for m in first:
        if not isinstance(m, dict):
            continue
        spec = m.get("specValue")
        out.append(Candidate(
            platform="sportpesa",
            market_id=str(m.get("id")) if m.get("id") is not None else None,
            name=str(m.get("name", "")),
            specifier=str(spec) if spec is not None else None,
            outcomes=[
                str(s.get("shortName", ""))
                for s in m.get("selections", []) or []
                if isinstance(s, dict)
            ],
        ))
    return out


def _candidates_betika(payload: Any) -> list[Candidate]:
    data = payload.get("data") or []
    if not isinstance(data, list) or not data:
        return []
    match = data[0]
    if not isinstance(match, dict):
        return []
    out: list[Candidate] = []
    for grp in match.get("odds", []) or []:
        if not isinstance(grp, dict):
            continue
        sti = grp.get("sub_type_id")
        out.append(Candidate(
            platform="betika",
            market_id=str(sti) if sti is not None else None,
            name=str(grp.get("name", "")),
            specifier=None,
            outcomes=[
                str(s.get("display", ""))
                for s in grp.get("odds", []) or []
                if isinstance(s, dict)
            ],
        ))
    return out
