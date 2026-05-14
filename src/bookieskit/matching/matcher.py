"""Cross-bookmaker event matching by shared provider ids.

Events from different bookmakers are paired if they share **any**
provider id — currently SportRadar or BetGenius (see
:class:`bookieskit.matching.extractor.EventIds`). The algorithm is a
small union-find: each provider id ("sr:NNN", "genius:MMM") becomes a
key; events that mention the same key end up in the same group, and
groups merge transitively when an event carries two ids whose groups
were previously separate.

In practice the transitive merge matters because BetPawa carries both
SR and Genius widgets — its rows bridge bookmakers that publish only SR
(Betway, MSport, ...) with bookmakers that may publish only Genius
(SportyBet's BetGenius events, eventually Bet9ja live).
"""

from dataclasses import dataclass

from bookieskit.matching.extractor import extract_event_ids


@dataclass
class MatchedEvent:
    """An event matched across multiple platforms.

    ``sportradar_id`` and ``genius_id`` are optional — at least one
    will be set (groups without any provider id are dropped by the
    matcher). Per-bookmaker fields are populated with the raw event
    payload when that bookmaker had an event in the group.
    """

    sportradar_id: str | None = None
    genius_id: str | None = None
    betpawa: dict | None = None
    sportybet: dict | None = None
    bet9ja: dict | None = None
    betway: dict | None = None
    msport: dict | None = None
    sportpesa: dict | None = None
    betika: dict | None = None


class _DSU:
    """Disjoint-set union with path compression. Keys are provider-id
    strings like ``"sr:70784812"`` / ``"genius:13599033"``."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, key: str) -> None:
        if key not in self._parent:
            self._parent[key] = key

    def find(self, key: str) -> str:
        # Iterative find with path compression — recursion depth would
        # be bounded but iteration is fine and avoids the stack.
        root = key
        while self._parent[root] != root:
            root = self._parent[root]
        # Compress.
        cur = key
        while self._parent[cur] != root:
            nxt = self._parent[cur]
            self._parent[cur] = root
            cur = nxt
        return root

    def union(self, a: str, b: str) -> None:
        self.add(a)
        self.add(b)
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb

    def keys(self) -> list[str]:
        return list(self._parent.keys())


def match_events(
    *event_lists: tuple[str, list[dict]],
) -> list[MatchedEvent]:
    """Group events from multiple bookmakers by shared provider ids.

    Args:
        event_lists: Tuples of ``(platform, events)`` where ``events`` is
            a list of raw event-detail payloads in that bookmaker's
            native shape. ``platform`` must be one of the keys
            recognised by
            :func:`bookieskit.matching.extractor.extract_event_ids`.

    Returns:
        One :class:`MatchedEvent` per group of events that share any
        SR or Genius id. Events that carry no recognised id are
        skipped entirely.
    """
    dsu = _DSU()
    # event_records[i] = (platform, raw_event, sr_id_or_None, genius_id_or_None)
    records: list[tuple[str, dict, str | None, str | None]] = []

    for platform, events in event_lists:
        for event in events:
            ids = extract_event_ids(event, platform=platform)
            keys = ids.keys()
            if not keys:
                continue
            # Register every id this event carries, then union them so
            # any later event hitting either id lands in the same group.
            for k in keys:
                dsu.add(k)
            first = keys[0]
            for k in keys[1:]:
                dsu.union(first, k)
            records.append((platform, event, ids.sportradar, ids.genius))

    # Group records by DSU root.
    groups: dict[str, dict] = {}
    for platform, event, sr_id, genius_id in records:
        # Every record has at least one of sr_id / genius_id (otherwise
        # keys was empty and we skipped above). Pick whichever exists
        # to look up the root.
        anchor = f"sr:{sr_id}" if sr_id else f"genius:{genius_id}"
        root = dsu.find(anchor)
        group = groups.setdefault(root, {
            "sportradar_id": None,
            "genius_id": None,
            "platforms": {},
        })
        # The first non-None id seen wins; subsequent events with the
        # same root either confirm it or skip silently. (Disagreements
        # would already have been caught at extract_event_ids time.)
        if sr_id and group["sportradar_id"] is None:
            group["sportradar_id"] = sr_id
        if genius_id and group["genius_id"] is None:
            group["genius_id"] = genius_id
        group["platforms"][platform] = event

    results: list[MatchedEvent] = []
    for g in groups.values():
        results.append(
            MatchedEvent(
                sportradar_id=g["sportradar_id"],
                genius_id=g["genius_id"],
                betpawa=g["platforms"].get("betpawa"),
                sportybet=g["platforms"].get("sportybet"),
                bet9ja=g["platforms"].get("bet9ja"),
                betway=g["platforms"].get("betway"),
                msport=g["platforms"].get("msport"),
                sportpesa=g["platforms"].get("sportpesa"),
                betika=g["platforms"].get("betika"),
            )
        )
    return results
