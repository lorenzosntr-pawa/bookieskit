"""Maintenance stream: reconcile a CanaryReport into the work queue.

Each current drift -> a deduped ``stream:maintenance`` Issue (open on first
sight, comment on persistence). A check that is OK this run closes its open
issues (recovery), but a skipped/unreachable platform is left untouched because
recovery can't be confirmed. Per-issue gh errors are isolated so one failure
doesn't abort the reconciliation.
"""

from dataclasses import dataclass, field

from bookieskit.devtools.canary import BookCheck, CanaryReport
from bookieskit.orchestration.queue import Queue
from bookieskit.orchestration.workitem import WorkItem

_STREAM = "stream:maintenance"
_SEED_SIGNATURE = "canary:seed-discovery"


@dataclass
class SyncResult:
    """Outcome of a sync_canary run, all lists of signatures."""

    opened: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    closed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _check_signatures(check: BookCheck) -> list[tuple[str, str]]:
    """The drift signatures a single BookCheck contributes.

    A structure break is ONE root-cause signature — the missing canonicals are
    a *consequence* of the broken structure, not separate problems (a
    structure-broken check has ``missing_canonicals == expected``). Only when
    structure is intact but specific core markets stopped resolving do we emit
    one signature per missing canonical.
    """
    if not check.structure_ok:
        return [(
            f"canary:{check.platform}:structure",
            f"{check.platform} structure drift",
        )]
    return [
        (
            f"canary:{check.platform}:missing:{canonical}",
            f"{check.platform} missing core market {canonical}",
        )
        for canonical in check.missing_canonicals
    ]


def canary_signatures(report: CanaryReport) -> list[tuple[str, str]]:
    """(signature, human title) for each drift in the report.

    Kinds: ``canary:<platform>:structure``,
    ``canary:<platform>:missing:<canonical>``, and ``canary:seed-discovery``
    when ``report.seed is None``.
    """
    out: list[tuple[str, str]] = []
    for check in report.checks:
        if check.status == "drift":
            out += _check_signatures(check)
    if report.seed is None:
        out.append((_SEED_SIGNATURE, "canary seed discovery failed"))
    return out


def _possible_signatures(check: BookCheck) -> list[str]:
    """Every signature a platform *could* have, used to find recoveries."""
    sigs = [f"canary:{check.platform}:structure"]
    sigs += [
        f"canary:{check.platform}:missing:{c}"
        for c in check.expected_canonicals
    ]
    return sigs


def sync_canary(report: CanaryReport, queue: Queue) -> SyncResult:
    """Reconcile a CanaryReport into the maintenance stream."""
    result = SyncResult()
    current = canary_signatures(report)
    current_sigs = {sig for sig, _ in current}

    # 1. Open or update each current drift (in canary_signatures' deterministic
    # order, so result.opened/updated are stable across runs).
    for signature, title in current:
        item = WorkItem(
            signature=signature,
            stream=_STREAM,
            title=title,
            summary=f"Canary drift detected: {title}.",
            meta={"source": "canary"},
        )
        try:
            _, action = queue.open_or_update(
                item, note=f"Still drifting: {title}."
            )
        except Exception as exc:  # per-operation isolation
            result.errors.append(f"{signature}: {exc}")
            continue
        (result.opened if action == "opened" else result.updated).append(
            signature
        )

    # 2. Recovery: close issues for platforms that are OK this run.
    for check in report.checks:
        if check.status != "ok":
            continue  # never close for skipped/unreachable
        for signature in _possible_signatures(check):
            if signature in current_sigs:
                continue
            try:
                number = queue.close_by_signature(
                    signature, reason=f"Recovered: {check.platform} is OK."
                )
            except Exception as exc:
                result.errors.append(f"{signature}: {exc}")
                continue
            if number is not None:
                result.closed.append(signature)

    # 3. Seed-discovery recovery: a run with a seed clears the discovery issue.
    if report.seed is not None and _SEED_SIGNATURE not in current_sigs:
        try:
            number = queue.close_by_signature(
                _SEED_SIGNATURE, reason="Recovered: seed discovery succeeded."
            )
        except Exception as exc:
            result.errors.append(f"{_SEED_SIGNATURE}: {exc}")
        else:
            if number is not None:
                result.closed.append(_SEED_SIGNATURE)

    return result
