"""Event-id extraction from platform-specific responses.

Two providers ship event ids that bookieskit can cross-bookmaker match on:

- **SportRadar** — the primary numeric id used by every supported
  bookmaker (BetPawa, SportyBet, Bet9ja, Betway, MSport, SportPesa,
  Betika). Carried under platform-specific JSON paths.
- **BetGenius / Genius Sports** — secondary provider used by BetPawa,
  SportyBet, and Bet9ja live. BetPawa exposes it as a separate widget
  (``type=GENIUSSPORTS``); SportyBet exposes it via
  ``data.eventSource.preMatchSource.sourceType=BET_GENIUS`` and via a
  synthetic ``sr:match:11111111<genius_id>`` encoding on ``data.eventId``.

:class:`EventIds` carries one of each. :func:`extract_event_ids` is the
new entry point; :func:`extract_sportradar_id` is kept as a thin
back-compat wrapper that returns ``EventIds.sportradar``.
"""

import logging
from dataclasses import dataclass

from bookieskit.bookmakers._betika_shape import betika_first_match

logger = logging.getLogger(__name__)

# SportyBet's synthetic Genius encoding: real event id is
# ``sr:match:11111111<genius_id>`` where the 8 leading ``1``s mark the
# id as a BetGenius event. Real SportRadar ids are typically <= 8
# digits, so a numeric tail starting with eight ``1``s and longer than
# 8 chars is unambiguously a Genius encoding.
_SPORTYBET_GENIUS_PREFIX = "11111111"


@dataclass(frozen=True)
class EventIds:
    """Provider-keyed event ids extracted from one bookmaker payload.

    Both fields are optional — most platforms (and most events) ship only
    a SportRadar id. BetPawa, SportyBet, and Bet9ja-live events may carry
    a Genius Sports id alongside (or instead of) the SR id.

    Use :meth:`keys` to get the union-find keys that
    :func:`match_events` joins on.
    """

    sportradar: str | None = None
    genius: str | None = None

    def keys(self) -> tuple[str, ...]:
        """Provider-prefixed id strings, in stable order (sr first, genius second).

        Used by :func:`match_events` to group events from multiple
        bookmakers that share any provider id. Empty tuple if both
        fields are None — the matcher then skips the event.
        """
        out: list[str] = []
        if self.sportradar:
            out.append(f"sr:{self.sportradar}")
        if self.genius:
            out.append(f"genius:{self.genius}")
        return tuple(out)


def extract_event_ids(response, platform: str) -> EventIds:
    """Extract every known provider id from a raw event-detail response.

    Args:
        response: Raw JSON returned by the bookmaker's event-detail call.
        platform: One of ``"betpawa"``, ``"sportybet"``, ``"bet9ja"``,
            ``"betway"``, ``"msport"``, ``"sportpesa"``, ``"betika"``.
            Unknown platforms return an empty :class:`EventIds`.

    Returns:
        :class:`EventIds` with whichever provider ids the platform
        carries. Missing or unrecognised ids stay ``None``.
    """
    extractors = {
        "betpawa": _extract_event_ids_betpawa,
        "sportybet": _extract_event_ids_sportybet,
        "bet9ja": _extract_event_ids_bet9ja,
        "betway": _extract_event_ids_betway,
        "msport": _extract_event_ids_msport,
        "sportpesa": _extract_event_ids_sportpesa,
        "betika": _extract_event_ids_betika,
    }
    fn = extractors.get(platform)
    if fn is None:
        return EventIds()
    return fn(response)


def extract_sportradar_id(response: dict, platform: str) -> str | None:
    """Extract the SportRadar id only — back-compat wrapper.

    Equivalent to ``extract_event_ids(response, platform).sportradar``.
    Pre-existing callers that only care about the SR id keep working
    without change. To pick up Genius ids (BetPawa, SportyBet, eventually
    Bet9ja live), switch to :func:`extract_event_ids`.
    """
    return extract_event_ids(response, platform).sportradar


def _strip_sr_prefix(value: str) -> str:
    """Strip ``sr:match:`` prefix if present."""
    if value.startswith("sr:match:"):
        return value[len("sr:match:"):]
    return value


# ---- BetPawa --------------------------------------------------------------


def _extract_event_ids_betpawa(response: dict) -> EventIds:
    """BetPawa carries provider ids on parallel widget entries.

    Walk ``widgets[]`` once; pick the first SPORTRADAR id and the first
    GENIUSSPORTS id we see. BetPawa repeats SPORTRADAR with
    ``retention="PREMATCH"`` and ``retention="INPLAY"`` — both rows
    have the same id, so the first wins.
    """
    sr_id: str | None = None
    genius_id: str | None = None
    for widget in response.get("widgets") or []:
        if not isinstance(widget, dict):
            continue
        wtype = widget.get("type")
        value = widget.get("id", widget.get("value", ""))
        if not value:
            continue
        if wtype == "SPORTRADAR" and sr_id is None:
            sr_id = _strip_sr_prefix(str(value))
        elif wtype == "GENIUSSPORTS" and genius_id is None:
            genius_id = str(value)
    return EventIds(sportradar=sr_id, genius=genius_id)


# ---- SportyBet ------------------------------------------------------------


def _extract_event_ids_sportybet(response: dict) -> EventIds:
    """SportyBet exposes provider info two ways; we use both.

    Primary (typed):
        ``data.eventSource.preMatchSource.{sourceType, sourceId}`` plus
        the parallel ``liveSource``. ``sourceType`` is ``"BET_RADAR"`` or
        ``"BET_GENIUS"``.

    Fallback / cross-check:
        ``data.eventId`` carries ``"sr:match:<sr_id>"`` for SR events and
        ``"sr:match:11111111<genius_id>"`` for Genius events (eight
        leading ``1``s mark the synthetic encoding). When both signals
        are present and disagree, eventSource wins and a warning is
        logged.
    """
    data = response.get("data") or {}
    if not isinstance(data, dict):
        return EventIds()

    sr_id: str | None = None
    genius_id: str | None = None

    # Primary path: structured eventSource.
    source = data.get("eventSource") or {}
    if isinstance(source, dict):
        for key in ("preMatchSource", "liveSource"):
            s = source.get(key) or {}
            if not isinstance(s, dict):
                continue
            stype = s.get("sourceType")
            sid = s.get("sourceId")
            if sid in (None, "", 0):
                continue
            sid_str = str(sid)
            if stype == "BET_RADAR" and sr_id is None:
                sr_id = _strip_sr_prefix(sid_str)
            elif stype == "BET_GENIUS" and genius_id is None:
                genius_id = sid_str

    # Fallback / cross-check: data.eventId. Accepts ``sr:match:<id>``
    # and bare-numeric forms; the ``sr:match:11111111<gid>`` synthetic
    # encoding is only recognised when the prefix is present (a bare
    # number can never be a synthetic Genius id).
    event_id = data.get("eventId")
    if isinstance(event_id, (str, int)) and event_id != "":
        ev_str = str(event_id)
        if ev_str.startswith("sr:match:"):
            numeric = ev_str[len("sr:match:"):]
            is_genius_encoding = (
                numeric.startswith(_SPORTYBET_GENIUS_PREFIX)
                and len(numeric) > len(_SPORTYBET_GENIUS_PREFIX)
            )
        else:
            numeric = ev_str
            is_genius_encoding = False

        if is_genius_encoding:
            decoded = numeric[len(_SPORTYBET_GENIUS_PREFIX):]
            if genius_id is None:
                genius_id = decoded
            elif genius_id != decoded:
                logger.warning(
                    "SportyBet eventId genius decode %r disagrees with "
                    "eventSource.sourceId %r — using eventSource value",
                    decoded, genius_id,
                )
        else:
            if sr_id is None:
                sr_id = numeric
            elif sr_id != numeric:
                logger.warning(
                    "SportyBet eventId SR id %r disagrees with "
                    "eventSource.sourceId %r — using eventSource value",
                    numeric, sr_id,
                )

    return EventIds(sportradar=sr_id, genius=genius_id)


# ---- Bet9ja ---------------------------------------------------------------


def _extract_event_ids_bet9ja(response: dict) -> EventIds:
    """Bet9ja prematch reads ``D.EXTID``; live Genius is deferred.

    Live responses live at ``D.A``; their EXTID may eventually carry a
    Genius id, but the binding fixture for that case isn't captured yet.
    See ``docs/matching.md`` for the open item.
    """
    data = response.get("D") or {}
    if not isinstance(data, dict):
        return EventIds()
    ext_id = data.get("EXTID")
    if ext_id:
        return EventIds(sportradar=_strip_sr_prefix(str(ext_id)))
    return EventIds()


# ---- Betway ---------------------------------------------------------------


def _extract_event_ids_betway(response: dict) -> EventIds:
    """Betway's ``sportEvent.eventId`` IS the SR id (already prefix-free)."""
    sport_event = response.get("sportEvent") or {}
    if not isinstance(sport_event, dict):
        return EventIds()
    event_id = sport_event.get("eventId")
    if event_id in (None, "", 0):
        return EventIds()
    return EventIds(sportradar=_strip_sr_prefix(str(event_id)))


# ---- MSport ---------------------------------------------------------------


def _extract_event_ids_msport(response: dict) -> EventIds:
    """MSport's ``data.eventId`` carries ``sr:match:<id>``."""
    data = response.get("data") or {}
    if not isinstance(data, dict):
        return EventIds()
    event_id = data.get("eventId")
    if not event_id:
        return EventIds()
    return EventIds(sportradar=_strip_sr_prefix(str(event_id)))


# ---- SportPesa ------------------------------------------------------------


def _extract_event_ids_sportpesa(response) -> EventIds:
    """SportPesa's ``[0].betradarId`` is the SR id (bare int)."""
    if isinstance(response, list):
        games = response
    elif isinstance(response, dict):
        games = response.get("data") or response.get("games") or []
    else:
        return EventIds()
    if not isinstance(games, list) or not games:
        return EventIds()
    game = games[0]
    if not isinstance(game, dict):
        return EventIds()
    sr = game.get("betradarId")
    if sr in (None, 0, "0", ""):
        return EventIds()
    return EventIds(sportradar=_strip_sr_prefix(str(sr)))


# ---- Betika ---------------------------------------------------------------


def _extract_event_ids_betika(response) -> EventIds:
    """Betika's ``data[0].parent_match_id`` is the SR id."""
    match = betika_first_match(response)
    if match is None:
        return EventIds()
    sr = match.get("parent_match_id")
    if sr in (None, 0, "0", ""):
        return EventIds()
    return EventIds(sportradar=_strip_sr_prefix(str(sr)))
