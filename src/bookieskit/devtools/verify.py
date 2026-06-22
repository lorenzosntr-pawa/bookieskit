"""Run parse_markets on a raw payload and report which canonicals resolve."""

from typing import Any

from bookieskit.devtools.types import VerifyResult
from bookieskit.markets.parser import parse_markets


def _market_to_odds(market: Any) -> dict[str, Any]:
    """Serialize one NormalizedMarket's odds into a plain dict."""
    if market.lines is not None:
        return {
            "lines": {
                line: {o.canonical_name: o.odds for o in outcomes}
                for line, outcomes in market.lines.items()
            }
        }
    return {"outcomes": {o.canonical_name: o.odds for o in market.outcomes}}


def verify(
    payload: Any,
    platform: str,
    sport: str,
    canonical_ids: list[str] | None = None,
) -> VerifyResult:
    """Parse ``payload`` and report resolved canonicals (+ missing requested).

    Args:
        payload: Raw markets payload for ``platform``.
        platform: Bookmaker key.
        sport: Canonical sport (forwarded to parse_markets for id
            disambiguation, e.g. basketball O/U).
        canonical_ids: When given, ``missing`` lists those not resolved;
            otherwise every parsed canonical is reported and missing is [].

    Returns:
        VerifyResult.
    """
    markets = parse_markets(payload, platform=platform, sport=sport)
    resolved: dict[str, Any] = {
        m.canonical_id: _market_to_odds(m) for m in markets
    }
    if canonical_ids is None:
        missing: list[str] = []
    else:
        missing = [c for c in canonical_ids if c not in resolved]
    return VerifyResult(platform=platform, resolved=resolved, missing=missing)
