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

# SportyBet's eventSource.sourceId namespacing marker — seven leading
# ``1``s prepended to the provider id on some rows (preMatchSource for
# both BET_RADAR and BET_GENIUS; liveSource for BET_GENIUS). Stripping
# yields the bare provider id that matches BetPawa's GENIUSSPORTS
# widget id (for Genius) or the raw SR id (for BetRadar). Observed via
# live probe in 2026-05; see ``docs/sportybet.md`` for details.
_SPORTYBET_SOURCE_ID_PREFIX = "1111111"


def _strip_sportybet_source_prefix(source_id: str) -> str:
    """Strip the 7-ones SportyBet namespacing prefix from a sourceId.

    No-op when the prefix is absent or when stripping would leave an
    empty string (defensive guard against a degenerate ``"1111111"``
    payload).
    """
    if (
        source_id.startswith(_SPORTYBET_SOURCE_ID_PREFIX)
        and len(source_id) > len(_SPORTYBET_SOURCE_ID_PREFIX)
    ):
        return source_id[len(_SPORTYBET_SOURCE_ID_PREFIX):]
    return source_id


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
            ``"betway"``, ``"msport"``, ``"sportpesa"``, ``"betika"``,
            ``"elephantbet"``. Unknown platforms return an empty
            :class:`EventIds`.

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
        "elephantbet": _extract_event_ids_elephantbet,
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

    Primary (typed): ``data.eventSource.{preMatchSource, liveSource}``
    each carry ``sourceType`` (``BET_RADAR`` / ``BET_GENIUS``) and
    ``sourceId``. The sourceId is sometimes prefixed with seven ``1``s
    as a SportyBet namespacing marker — the prefix is stripped so the
    Genius id matches BetPawa's GENIUSSPORTS widget id.

    Fallback / cross-check: ``data.eventId`` always carries
    ``"sr:match:<sr_id>"`` regardless of provider (a BetGenius event
    still has an SR id for the same physical match). Used to populate
    ``sportradar`` when eventSource is absent (minimal list-view
    payloads). When both signals are present and the SR ids disagree,
    a warning is logged and eventSource wins.
    """
    data = response.get("data") or {}
    if not isinstance(data, dict):
        return EventIds()

    sr_id: str | None = None
    genius_id: str | None = None

    # Primary path: structured eventSource. preMatchSource and
    # liveSource may carry different providers (e.g. prematch via
    # SportRadar and live via BetGenius) — populate both ids when
    # seen.
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
            bare = _strip_sportybet_source_prefix(str(sid))
            if stype == "BET_RADAR" and sr_id is None:
                sr_id = _strip_sr_prefix(bare)
            elif stype == "BET_GENIUS" and genius_id is None:
                genius_id = bare

    # Fallback / cross-check: data.eventId carries the SR id. Accepts
    # ``sr:match:<id>`` and bare-numeric forms (the latter for legacy
    # responses that omit the prefix).
    event_id = data.get("eventId")
    if isinstance(event_id, (str, int)) and event_id != "":
        ev_str = str(event_id)
        if ev_str.startswith("sr:match:"):
            from_eventid = ev_str[len("sr:match:"):]
        else:
            from_eventid = ev_str
        if sr_id is None:
            sr_id = from_eventid
        elif sr_id != from_eventid:
            logger.warning(
                "SportyBet eventId SR id %r disagrees with "
                "eventSource SR id %r — using eventSource value",
                from_eventid, sr_id,
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


# ---- ElephantBet ------------------------------------------------------------


# The live feed always carries in-play state; the prematch listing never
# does. That is the only reliable way to tell which field holds the provider
# id, because BtoBet's own ids are NOT length-distinguishable from SportRadar
# ids (virtual events carry 7-digit brids; real SR match ids are 8-9 digits).
_ELEPHANTBET_LIVE_MARKERS = ("ms", "mt", "sc", "ss")


def _extract_event_ids_elephantbet(response) -> EventIds:
    """Extract ElephantBet's SportRadar id, which moves between fields.

    The two feeds disagree about what ``brid`` means, so reading it blindly
    corrupts cross-book matching:

    - **Prematch** (``GetGroupedMatches``): ``brid`` IS the SportRadar id.
      Verified -- ``brid="72221172"`` resolves on Betway and MSport to the
      same fixture ("Fulham FC vs. Chelsea FC").
    - **Live** (``GetLiveMatchesMetaData``): ``brid`` is a BtoBet-internal
      id and the SportRadar id lives in ``obrid``, which is ``None`` on half
      the entries. Verified -- ``obrid=73842300`` resolves on Betway to "KT
      Sonicboom vs. Mobis Phoebus", while its ``brid`` matches nothing.

    Length cannot separate them: live virtual events ("Rush Football",
    "eBasketball") carry 7-digit ``brid`` values that look plausibly like
    8-9 digit SportRadar ids. What does separate them is in-play state --
    every live entry carries ``ms``/``mt``/``sc``/``ss`` and no prematch
    entry does (verified 40/40 and 0/21 against the committed captures).

    So on a live entry only ``obrid`` is trusted, and an entry without one
    has no SportRadar id at all. No Genius Sports id is exposed by either
    feed.
    """
    if not isinstance(response, dict):
        return EventIds()
    is_live = any(key in response for key in _ELEPHANTBET_LIVE_MARKERS)
    raw = response.get("obrid" if is_live else "brid")
    if raw in (None, 0, "0", ""):
        return EventIds()
    return EventIds(sportradar=_strip_sr_prefix(str(raw)))
