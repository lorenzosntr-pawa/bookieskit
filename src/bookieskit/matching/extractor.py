"""SportRadar ID extraction from platform-specific responses."""


def extract_sportradar_id(
    response: dict, platform: str
) -> str | None:
    """Extract SportRadar ID from a raw event detail response.

    Args:
        response: Raw JSON from get_event_detail()
        platform: "betpawa", "sportybet", "bet9ja", "betway", or "msport"

    Returns:
        SportRadar ID as numeric string (no prefix), or None if not found.
    """
    extractors = {
        "betpawa": _extract_betpawa,
        "sportybet": _extract_sportybet,
        "bet9ja": _extract_bet9ja,
        "betway": _extract_betway,
        "msport": _extract_msport,
        "sportpesa": _extract_sportpesa,
    }
    extractor = extractors.get(platform)
    if extractor is None:
        return None
    return extractor(response)


def _strip_sr_prefix(value: str) -> str:
    """Strip 'sr:match:' prefix if present."""
    if value.startswith("sr:match:"):
        return value[len("sr:match:"):]
    return value


def _extract_betpawa(response: dict) -> str | None:
    """Extract from BetPawa widgets array.

    BetPawa uses widgets[].id (not .value) for the SportRadar ID.
    """
    widgets = response.get("widgets", [])
    for widget in widgets:
        if widget.get("type") == "SPORTRADAR":
            # BetPawa uses "id" field, fallback to "value" for compatibility
            value = widget.get("id", widget.get("value", ""))
            if value:
                return _strip_sr_prefix(str(value))
    return None


def _extract_sportybet(response: dict) -> str | None:
    """Extract from SportyBet data.eventId field."""
    data = response.get("data", {})
    event_id = data.get("eventId")
    if event_id:
        return _strip_sr_prefix(str(event_id))
    return None


def _extract_bet9ja(response: dict) -> str | None:
    """Extract from Bet9ja D.EXTID field."""
    data = response.get("D", {})
    ext_id = data.get("EXTID")
    if ext_id:
        return _strip_sr_prefix(str(ext_id))
    return None


def _extract_betway(response: dict) -> str | None:
    """Extract from Betway sportEvent.eventId (IS the SR ID)."""
    sport_event = response.get("sportEvent", {})
    event_id = sport_event.get("eventId")
    if event_id:
        return _strip_sr_prefix(str(event_id))
    return None


def _extract_msport(response: dict) -> str | None:
    """Extract from MSport data.eventId field.

    MSport returns the eventId at the top level of the `data` object,
    same shape as SportyBet — typically prefixed with `sr:match:`.
    """
    data = response.get("data", {})
    event_id = data.get("eventId")
    if event_id:
        return _strip_sr_prefix(str(event_id))
    return None


def _extract_sportpesa(response) -> str | None:
    """Extract from SportPesa ``[0].betradarId``.

    SportPesa returns event-detail as a list of length 1 (not a dict
    wrapper). The SportRadar id is the bare integer at
    ``[0].betradarId`` — already prefix-free. A value of ``0`` means
    not-supplied (the field is always present in the response shape).
    """
    if isinstance(response, list):
        games = response
    elif isinstance(response, dict):
        games = response.get("data") or response.get("games") or []
    else:
        return None
    if not isinstance(games, list) or not games:
        return None
    game = games[0]
    if not isinstance(game, dict):
        return None
    sr = game.get("betradarId")
    if sr in (None, 0, "0", ""):
        return None
    return _strip_sr_prefix(str(sr))
