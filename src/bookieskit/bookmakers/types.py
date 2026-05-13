"""Shared types for bookmaker clients."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PrematchEventStub:
    """Minimal event identifier yielded by :meth:`iter_all_prematch_events`.

    Audit / aggregation callers (e.g. cross-bookmaker totals) need to dedupe
    and group events without each one knowing per-platform JSON shapes. Each
    iterator yields these stubs; callers collect / count by ``event_id``,
    ``league_id``, ``sport_id`` as needed.

    All fields are string-typed. ``sport_id`` and ``league_id`` use whatever
    the bookmaker's native identifier is (a slug for Betway, an integer
    string for SportPesa, an ``sr:sport:N`` form for MSport, etc.).
    """

    event_id: str
    league_id: str
    sport_id: str
