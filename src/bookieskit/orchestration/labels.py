"""Work-queue label taxonomy + idempotent ``ensure_labels``.

Stream labels route work to an intake stream; status labels carry the in-flight
state (open/closed are native issue state; ``status:claimed``/``status:in-review``
+ assignee + linked PR carry the rest). ``ensure_labels`` creates only the
missing labels, so it is safe to call on every queue use.
"""

from bookieskit.orchestration.gh import GhRunner

STREAM_LABELS: dict[str, tuple[str, str]] = {
    "stream:maintenance": ("d73a4a", "Canary drift / keep-it-working"),
    "stream:expansion": ("0e8a16", "Scout: new sport/market/bookmaker"),
    "stream:directed": ("1d76db", "Owner-requested work"),
    "stream:capability": ("5319e7", "Adopt a new skill / MCP"),
}

STATUS_LABELS: dict[str, tuple[str, str]] = {
    "status:claimed": ("fbca04", "An agent is working this"),
    "status:in-review": ("0052cc", "PR open, awaiting review"),
    "status:blocked": ("e4e669", "Build blocked — needs owner input"),
}

CONTROL_LABELS: dict[str, tuple[str, str]] = {
    "control:paused": ("b60205", "Orchestrator paused — autonomous building halted"),
}

DESIGN_LABELS: dict[str, tuple[str, str]] = {
    "status:designing": ("c5def5", "Design in progress with owner in Slack"),
    "status:ready": ("0e8a16", "Design approved — ready to build"),
}

ALL_LABELS: dict[str, tuple[str, str]] = {
    **STREAM_LABELS,
    **STATUS_LABELS,
    **CONTROL_LABELS,
    **DESIGN_LABELS,
}


def ensure_labels(gh: GhRunner) -> list[str]:
    """Create any missing stream:*/status:* labels. Idempotent. Returns the
    names that were created (empty when everything already exists)."""
    existing = set(gh.list_labels())
    created: list[str] = []
    for name, (color, description) in ALL_LABELS.items():
        if name in existing:
            continue
        gh.create_label(name, color=color, description=description)
        created.append(name)
    return created
