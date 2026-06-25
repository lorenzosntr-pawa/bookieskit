from bookieskit.orchestration import runner


def test_acquire_on_free_lock(tmp_path):
    p = str(tmp_path / "tick.lock")
    assert runner.acquire_lock(p, stale_after_s=7200, now=1000.0, pid=1) is True


def test_busy_when_fresh_lock_held(tmp_path):
    p = str(tmp_path / "tick.lock")
    assert runner.acquire_lock(p, stale_after_s=7200, now=1000.0, pid=1) is True
    # 10 minutes later, still within the 2h stale window -> busy
    assert runner.acquire_lock(p, stale_after_s=7200, now=1600.0, pid=2) is False


def test_reclaim_when_stale(tmp_path):
    p = str(tmp_path / "tick.lock")
    assert runner.acquire_lock(p, stale_after_s=7200, now=1000.0, pid=1) is True
    # 3 hours later -> stale -> reclaimed
    assert runner.acquire_lock(p, stale_after_s=7200, now=1000.0 + 3 * 3600, pid=2) is True


def test_release_is_idempotent(tmp_path):
    p = str(tmp_path / "tick.lock")
    runner.acquire_lock(p, stale_after_s=7200, now=1000.0, pid=1)
    runner.release_lock(p)
    runner.release_lock(p)  # no error on missing file
    assert runner.acquire_lock(p, stale_after_s=7200, now=1000.0, pid=3) is True


def test_corrupt_lock_is_reclaimed(tmp_path):
    p = tmp_path / "tick.lock"
    p.write_text("not json")
    assert runner.acquire_lock(str(p), stale_after_s=7200, now=1000.0, pid=1) is True


def test_missing_ts_key_is_reclaimed(tmp_path):
    # A valid JSON lock that omits "ts" is as untrustworthy as a corrupt one
    # -> reclaim regardless of `now` (don't slip through as ts=0 / fresh).
    p = tmp_path / "tick.lock"
    p.write_text('{"pid": 7}')
    assert runner.acquire_lock(str(p), stale_after_s=7200, now=1000.0, pid=1) is True
