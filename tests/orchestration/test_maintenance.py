from dataclasses import asdict

from bookieskit.devtools.canary import BookCheck, CanaryReport
from bookieskit.orchestration.maintenance import (
    SyncResult,
    canary_signatures,
    sync_canary,
)


def _check(platform, status, *, missing=(), structure_ok=True, expected=()):
    expected = list(expected) or ["1x2_ft", "over_under_ft"]
    return BookCheck(
        platform=platform, status=status, reason="",
        expected_canonicals=expected,
        resolved_canonicals=[c for c in expected if c not in missing],
        missing_canonicals=list(missing), structure_ok=structure_ok,
    )


def _report(checks, *, seed="555"):
    return CanaryReport(
        sport="soccer", seed=seed, sr_numeric="777",
        checks=list(checks), drifted=any(c.status == "drift" for c in checks),
    )


class _FakeQueue:
    """Records open_or_update / close_by_signature; configurable presence."""

    def __init__(self, present: set[str] | None = None):
        self._present = set(present or set())
        self.opened: list[str] = []
        self.updated: list[str] = []
        self.closed: list[str] = []
        self._n = 100

    def open_or_update(self, item, *, note):
        self._n += 1
        if item.signature in self._present:
            self.updated.append(item.signature)
            return self._n, "updated"
        self._present.add(item.signature)
        self.opened.append(item.signature)
        return self._n, "opened"

    def close_by_signature(self, signature, *, reason):
        if signature in self._present:
            self._present.discard(signature)
            self.closed.append(signature)
            self._n += 1
            return self._n
        return None


def test_canary_signatures_structure_drift_collapses_to_one():
    # A structure break is ONE root-cause signature, not one per missing core.
    rep = _report([_check("betika", "drift", structure_ok=False,
                          missing=["1x2_ft", "over_under_ft"])])
    sigs = dict(canary_signatures(rep))
    assert sigs == {"canary:betika:structure": "betika structure drift"}


def test_canary_signatures_missing_core_only():
    rep = _report([_check("msport", "drift", missing=["btts_ft"],
                          structure_ok=True, expected=["btts_ft", "1x2_ft"])])
    sigs = dict(canary_signatures(rep))
    assert sigs == {
        "canary:msport:missing:btts_ft": "msport missing core market btts_ft"
    }


def test_canary_signatures_seed_none():
    rep = _report([], seed=None)
    sigs = dict(canary_signatures(rep))
    assert "canary:seed-discovery" in sigs


def test_canary_signatures_no_drift_is_empty():
    rep = _report([_check("betpawa", "ok")])
    assert canary_signatures(rep) == []


def test_sync_opens_new_drift():
    rep = _report([_check("betika", "drift", structure_ok=False,
                          missing=["1x2_ft"], expected=["1x2_ft"])])
    q = _FakeQueue()
    result = sync_canary(rep, q)
    assert result.opened == ["canary:betika:structure"]  # collapses to one
    assert result.updated == []
    assert isinstance(result, SyncResult)


def test_sync_updates_persisting_drift():
    rep = _report([_check("betika", "drift", structure_ok=False,
                          missing=["1x2_ft"], expected=["1x2_ft"])])
    q = _FakeQueue(present={"canary:betika:structure"})
    result = sync_canary(rep, q)
    assert result.updated == ["canary:betika:structure"]
    assert result.opened == []


def test_sync_closes_recovered_check():
    # betika was drifting (issues open) and is OK this run -> close both.
    rep = _report([_check("betika", "ok", expected=["1x2_ft"])])
    q = _FakeQueue(present={"canary:betika:structure",
                            "canary:betika:missing:1x2_ft"})
    result = sync_canary(rep, q)
    assert set(result.closed) == {
        "canary:betika:structure", "canary:betika:missing:1x2_ft"
    }


def test_sync_does_not_close_skipped_or_unreachable():
    # An open structure issue for a platform that is unreachable/skipped this
    # run must NOT be closed (recovery can't be confirmed).
    rep = _report([
        _check("bet9ja", "unreachable", expected=["1x2_ft"]),
        _check("sportpesa", "skipped", expected=["1x2_ft"]),
    ])
    q = _FakeQueue(present={"canary:bet9ja:structure",
                            "canary:sportpesa:structure"})
    result = sync_canary(rep, q)
    assert result.closed == []


def test_sync_closes_seed_discovery_when_seed_recovered():
    rep = _report([_check("betpawa", "ok", expected=["1x2_ft"])], seed="555")
    q = _FakeQueue(present={"canary:seed-discovery"})
    result = sync_canary(rep, q)
    assert "canary:seed-discovery" in result.closed


def test_sync_isolates_per_item_gh_errors():
    class _BoomQueue(_FakeQueue):
        def open_or_update(self, item, *, note):
            raise RuntimeError("gh boom")

    rep = _report([_check("betika", "drift", structure_ok=False,
                          missing=["1x2_ft"], expected=["1x2_ft"])])
    result = sync_canary(rep, _BoomQueue())
    assert result.opened == []
    assert any("gh boom" in e for e in result.errors)


def test_sync_result_serializes_for_json():
    rep = _report([_check("betika", "drift", structure_ok=False,
                          missing=["1x2_ft"], expected=["1x2_ft"])])
    d = asdict(sync_canary(rep, _FakeQueue()))
    assert set(d) == {"opened", "updated", "closed", "errors"}
