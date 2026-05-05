"""Event matching across platforms via SportRadar IDs."""

from dataclasses import dataclass

from bookieskit.matching.extractor import extract_sportradar_id


@dataclass
class MatchedEvent:
    """An event matched across multiple platforms."""

    sportradar_id: str
    betpawa: dict | None = None
    sportybet: dict | None = None
    bet9ja: dict | None = None


def match_events(
    *event_lists: tuple[str, list[dict]],
) -> list[MatchedEvent]:
    """Match events across platforms by SportRadar ID.

    Args:
        event_lists: Tuples of (platform, events) where events
                     are raw event detail responses.

    Returns:
        List of MatchedEvent grouped by shared SportRadar ID.
    """
    # Build map: sportradar_id -> {platform: event_data}
    groups: dict[str, dict[str, dict]] = {}

    for platform, events in event_lists:
        for event in events:
            sr_id = extract_sportradar_id(event, platform=platform)
            if sr_id is None:
                continue
            if sr_id not in groups:
                groups[sr_id] = {}
            groups[sr_id][platform] = event

    # Convert to MatchedEvent list
    results: list[MatchedEvent] = []
    for sr_id, platforms in groups.items():
        results.append(
            MatchedEvent(
                sportradar_id=sr_id,
                betpawa=platforms.get("betpawa"),
                sportybet=platforms.get("sportybet"),
                bet9ja=platforms.get("bet9ja"),
            )
        )

    return results
