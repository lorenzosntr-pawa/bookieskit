"""Single-cycle tick lock for the unattended orchestrator.

A scheduled tick acquires this lock before running a cycle; a tick that fires
while a previous cycle is still running fails to acquire and skips. A lock
older than ``stale_after_s`` is treated as dead (a crashed/hung tick) and
reclaimed. ``now`` is injected so the fresh/stale branches are unit-testable.
"""

import json
import os


def acquire_lock(path: str, *, stale_after_s: float, now: float,
                 pid: int = 0) -> bool:
    """Try to take the lock. Returns True if acquired (writes the lock file),
    False if a fresh lock is already held. A stale or unreadable lock is
    reclaimed."""
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                raw = json.load(handle).get("ts")
            ts = float(raw) if raw is not None else None
        except (ValueError, TypeError, OSError):
            ts = None  # corrupt / unreadable / missing ts -> reclaim
        if ts is not None and now - ts < stale_after_s:
            return False
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"ts": now, "pid": pid}, handle)
    return True


def release_lock(path: str) -> None:
    """Remove the lock file. Idempotent (a missing file is fine)."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
