"""WorkItem model + the issue-body format.

A work item is rendered as a fenced ``yaml`` meta block (the machine-readable
dedup contract: ``signature`` + ``stream`` + flat ``meta`` scalars) followed by
human prose. The block is serialized/parsed by a tiny hand-rolled flat
``key: value`` codec — no PyYAML (runtime dep stays ``httpx``-only). Round-trip
is lossless for the string scalars the queue stores.
"""

import re
from dataclasses import dataclass, field
from typing import Any

_YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)


@dataclass
class WorkItem:
    """A unit of queued work: a dedup signature, its stream, and prose."""

    signature: str
    stream: str
    title: str
    summary: str
    meta: dict[str, Any] = field(default_factory=dict)


def render_body(item: WorkItem) -> str:
    """Render the issue body: a fenced ``yaml`` meta block then the summary.

    The block holds ``signature`` and ``stream`` first, then each ``meta`` key
    as a flat ``key: value`` scalar (values coerced to ``str``). The order is
    deterministic so re-renders are byte-stable.
    """
    lines = [
        f"signature: {item.signature}",
        f"stream: {item.stream}",
    ]
    for key, value in item.meta.items():
        lines.append(f"{key}: {value}")
    block = "\n".join(lines)
    return f"```yaml\n{block}\n```\n\n{item.summary}"


def parse_meta(body: str) -> dict[str, Any]:
    """Extract the first fenced ``yaml`` meta block as a flat dict.

    Returns ``{}`` when there is no block or it contains no ``key: value``
    lines (a hand-filed / non-ours issue is simply not matched, never a crash).
    """
    match = _YAML_BLOCK_RE.search(body)
    if match is None:
        return {}
    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        meta[key.strip()] = value.strip()
    return meta
