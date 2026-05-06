"""Unit tests for bookieskit.event_info — pure-data, bound to captured fixtures."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bookieskit.event_info import (
    LiveInfo,
    Mode,
    Participants,
    extract_kickoff,
    extract_live_info,
    extract_participants,
    is_live_now,
)

FIXTURES = Path(__file__).parent / "fixtures" / "event_info"


def _load(platform: str, phase: str) -> dict:
    with open(FIXTURES / platform / f"{phase}.json", encoding="utf-8") as f:
        return json.load(f)


def test_dataclasses_construct_with_all_none():
    li = LiveInfo()
    assert li.minute is None
    assert li.period is None
    assert li.score_home is None
    assert li.score_away is None
    p = Participants()
    assert p.home is None
    assert p.away is None


def test_dataclasses_are_frozen():
    li = LiveInfo()
    with pytest.raises(AttributeError):
        li.minute = 5  # type: ignore[misc]


def test_mode_alias_is_literal():
    # Literal has no meaningful runtime identity, but get_args() exposes
    # its parameters — that's the strongest check available at runtime.
    from typing import get_args
    assert set(get_args(Mode)) == {"prematch", "live"}


def test_is_live_now_none_returns_false():
    assert is_live_now(None) is False


def test_is_live_now_past_kickoff_returns_true():
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert is_live_now(past) is True


def test_is_live_now_future_kickoff_returns_false():
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert is_live_now(future) is False


def test_is_live_now_exactly_now_returns_true():
    # `>=` boundary — at the exact kickoff instant, treat as live.
    now = datetime.now(timezone.utc)
    assert is_live_now(now) is True


def test_betpawa_kickoff_prematch():
    d = _load("betpawa", "prematch")
    k = extract_kickoff(d, "betpawa")
    assert k == datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_betpawa_kickoff_live():
    d = _load("betpawa", "live")
    k = extract_kickoff(d, "betpawa")
    assert k == datetime(2026, 5, 6, 6, 0, 0, tzinfo=timezone.utc)


def test_betpawa_participants_prematch():
    d = _load("betpawa", "prematch")
    p = extract_participants(d, "betpawa")
    assert p.home == "Wuhan Three Towns FC"
    assert p.away == "Qingdao Hainiu FC"


def test_betpawa_participants_live():
    d = _load("betpawa", "live")
    p = extract_participants(d, "betpawa")
    assert p.home == "FC Tokyo"
    assert p.away == "JEF United Chiba"


def test_betpawa_live_info_prematch_all_none():
    d = _load("betpawa", "prematch")
    li = extract_live_info(d, "betpawa")
    assert li == LiveInfo()


def test_betpawa_live_info_live():
    d = _load("betpawa", "live")
    li = extract_live_info(d, "betpawa")
    assert li.minute == 96
    assert li.period == "Second Half"
    assert li.score_home == 0
    assert li.score_away == 3


def test_betpawa_live_info_mode_prematch_overrides_live_data():
    """Explicit mode='prematch' suppresses live data even on a live fixture."""
    d = _load("betpawa", "live")
    li = extract_live_info(d, "betpawa", mode="prematch")
    assert li == LiveInfo()


def test_sportybet_kickoff_prematch():
    d = _load("sportybet", "prematch")
    k = extract_kickoff(d, "sportybet")
    assert k == datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_sportybet_kickoff_live():
    d = _load("sportybet", "live")
    k = extract_kickoff(d, "sportybet")
    assert k == datetime(2026, 5, 6, 6, 0, 0, tzinfo=timezone.utc)


def test_sportybet_participants_prematch():
    d = _load("sportybet", "prematch")
    p = extract_participants(d, "sportybet")
    assert p.home == "Wuhan Three Towns FC"
    assert p.away == "Qingdao Hainiu FC"


def test_sportybet_participants_live():
    d = _load("sportybet", "live")
    p = extract_participants(d, "sportybet")
    assert p.home == "FC Tokyo"
    assert p.away == "JEF United Chiba"


def test_sportybet_live_info_prematch_all_none():
    d = _load("sportybet", "prematch")
    li = extract_live_info(d, "sportybet")
    assert li == LiveInfo()


def test_sportybet_live_info_live():
    d = _load("sportybet", "live")
    li = extract_live_info(d, "sportybet")
    assert li.minute == 90
    assert li.period == "H2"
    assert li.score_home == 0
    assert li.score_away == 3


def test_bet9ja_kickoff_prematch_auto():
    d = _load("bet9ja", "prematch")
    k = extract_kickoff(d, "bet9ja")
    assert k == datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_bet9ja_kickoff_live_auto_returns_none():
    d = _load("bet9ja", "live")
    assert extract_kickoff(d, "bet9ja") is None


def test_bet9ja_participants_prematch_auto():
    d = _load("bet9ja", "prematch")
    p = extract_participants(d, "bet9ja")
    assert p.home == "Wuhan Three Towns"
    assert p.away == "Qingdao Hainiu FC"


def test_bet9ja_participants_live_auto_returns_none():
    d = _load("bet9ja", "live")
    p = extract_participants(d, "bet9ja")
    assert p == Participants()


def test_bet9ja_live_info_prematch_auto_all_none():
    d = _load("bet9ja", "prematch")
    li = extract_live_info(d, "bet9ja")
    assert li == LiveInfo()


def test_bet9ja_live_info_live_auto():
    d = _load("bet9ja", "live")
    li = extract_live_info(d, "bet9ja")
    assert li.minute == 91
    assert li.period == "2nd Half"
    assert li.score_home == 0
    assert li.score_away == 3


def test_bet9ja_explicit_mode_live_on_prematch_fixture_yields_nones():
    """User asserts live, but fixture is prematch shape — follow the mode,
    yield Nones where the live fields are absent. Must not raise."""
    d = _load("bet9ja", "prematch")
    assert extract_kickoff(d, "bet9ja", mode="live") is None
    assert extract_participants(d, "bet9ja", mode="live") == Participants()
    assert extract_live_info(d, "bet9ja", mode="live") == LiveInfo()


def test_bet9ja_explicit_mode_prematch_on_live_fixture_yields_nones():
    """User asserts prematch, but fixture is live shape — follow the mode,
    yield Nones where the prematch fields are absent. Must not raise."""
    d = _load("bet9ja", "live")
    assert extract_kickoff(d, "bet9ja", mode="prematch") is None
    assert extract_participants(d, "bet9ja", mode="prematch") == Participants()
    assert extract_live_info(d, "bet9ja", mode="prematch") == LiveInfo()


def test_bet9ja_explicit_mode_matches_auto_on_correct_fixture():
    d_pm = _load("bet9ja", "prematch")
    d_lv = _load("bet9ja", "live")
    assert extract_kickoff(d_pm, "bet9ja", mode="prematch") == \
           extract_kickoff(d_pm, "bet9ja")
    assert extract_live_info(d_lv, "bet9ja", mode="live") == \
           extract_live_info(d_lv, "bet9ja")


def test_betway_kickoff_prematch():
    d = _load("betway", "prematch")
    assert extract_kickoff(d, "betway") == \
           datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_betway_kickoff_live():
    d = _load("betway", "live")
    assert extract_kickoff(d, "betway") == \
           datetime(2026, 5, 6, 6, 0, 0, tzinfo=timezone.utc)


def test_betway_participants_prematch():
    p = extract_participants(_load("betway", "prematch"), "betway")
    assert p.home == "Wuhan Three Towns FC"
    assert p.away == "Qingdao Hainiu FC"


def test_betway_participants_live():
    p = extract_participants(_load("betway", "live"), "betway")
    assert p.home == "FC Tokyo"
    assert p.away == "JEF United Chiba"


def test_betway_live_info_prematch_auto_all_none_despite_zero_score_artefact():
    """Betway prematch carries score=['0','0'] but no time/state — must
    NOT emit fake 0-0; auto-detect via time-key absence."""
    d = _load("betway", "prematch")
    li = extract_live_info(d, "betway")
    assert li == LiveInfo()


def test_betway_live_info_live_auto():
    d = _load("betway", "live")
    li = extract_live_info(d, "betway")
    assert li.minute == 90
    assert li.period == "2nd half"
    assert li.score_home == 0
    assert li.score_away == 3


def test_betway_live_info_explicit_prematch_mode_overrides_anything():
    """mode='prematch' forces all live fields to None, even on a live fixture."""
    d = _load("betway", "live")
    li = extract_live_info(d, "betway", mode="prematch")
    assert li == LiveInfo()


def test_msport_kickoff_prematch():
    d = _load("msport", "prematch")
    assert extract_kickoff(d, "msport") == \
           datetime(2026, 5, 6, 11, 0, 0, tzinfo=timezone.utc)


def test_msport_kickoff_live():
    d = _load("msport", "live")
    assert extract_kickoff(d, "msport") == \
           datetime(2026, 5, 6, 6, 0, 0, tzinfo=timezone.utc)


def test_msport_participants_prematch():
    p = extract_participants(_load("msport", "prematch"), "msport")
    assert p.home == "Wuhan Three Towns"
    assert p.away == "Qingdao Hainiu FC"


def test_msport_participants_live():
    p = extract_participants(_load("msport", "live"), "msport")
    assert p.home == "Tokyo"
    assert p.away == "Ichihara Chiba"


def test_msport_live_info_prematch_all_none():
    li = extract_live_info(_load("msport", "prematch"), "msport")
    assert li == LiveInfo()


def test_msport_live_info_live():
    li = extract_live_info(_load("msport", "live"), "msport")
    assert li.minute == 90
    assert li.period is None  # statusDescription is None in this fixture
    assert li.score_home == 0
    assert li.score_away == 3


@pytest.mark.parametrize(
    "platform", ["betpawa", "sportybet", "bet9ja", "betway", "msport"]
)
def test_empty_dict_does_not_raise(platform):
    assert extract_kickoff({}, platform) is None
    assert extract_participants({}, platform) == Participants()
    assert extract_live_info({}, platform) == LiveInfo()


def test_unknown_platform_returns_empty():
    fixture = _load("betpawa", "live")
    assert extract_kickoff(fixture, "no-such-platform") is None
    assert extract_participants(fixture, "no-such-platform") == Participants()
    assert extract_live_info(fixture, "no-such-platform") == LiveInfo()


def test_invalid_mode_silently_treated_as_none():
    """Unknown mode strings must not raise; behavior matches mode=None."""
    d = _load("betpawa", "live")
    li_invalid = extract_live_info(d, "betpawa", mode="garbage")  # type: ignore[arg-type]
    li_default = extract_live_info(d, "betpawa")
    assert li_invalid == li_default


def test_invalid_mode_on_betway_does_not_force_prematch():
    """Specifically: a bogus mode should NOT silently become 'prematch'
    (which would zero out live data on Betway)."""
    d = _load("betway", "live")
    li = extract_live_info(d, "betway", mode="LIVE")  # type: ignore[arg-type]
    # 'LIVE' is not in the Mode literal → fall back to auto-detect → live data.
    assert li.minute == 90


ALL_PLATFORMS = ["betpawa", "sportybet", "bet9ja", "betway", "msport"]


def _kickoffs_for(phase: str) -> dict[str, datetime | None]:
    return {p: extract_kickoff(_load(p, phase), p) for p in ALL_PLATFORMS}


def test_kickoffs_agree_across_platforms_prematch():
    kicks = _kickoffs_for("prematch")
    assert all(k is not None for k in kicks.values()), kicks
    base = kicks["betpawa"]
    for platform, k in kicks.items():
        assert k is not None
        delta = abs((k - base).total_seconds())
        assert delta <= 300, f"{platform} kickoff drifts {delta}s vs betpawa"


def test_kickoffs_agree_across_platforms_live_except_bet9ja():
    kicks = _kickoffs_for("live")
    # Bet9ja's live response has no kickoff.
    assert kicks["bet9ja"] is None
    base = kicks["betpawa"]
    for platform, k in kicks.items():
        if platform == "bet9ja":
            continue
        assert k is not None, platform
        delta = abs((k - base).total_seconds())
        assert delta <= 300, f"{platform} kickoff drifts {delta}s vs betpawa"


def test_participants_present_for_all_except_bet9ja_live():
    """Sanity: every fixture except bet9ja-live yields non-None home/away."""
    for phase in ("prematch", "live"):
        for platform in ALL_PLATFORMS:
            p = extract_participants(_load(platform, phase), platform)
            if platform == "bet9ja" and phase == "live":
                assert p == Participants(), platform
            else:
                assert p.home and p.away, f"{platform}/{phase}"


def test_top_level_reexports():
    """Public surface must be importable from `bookieskit` directly."""
    import bookieskit

    for name in (
        "extract_kickoff",
        "extract_live_info",
        "extract_participants",
        "is_live_now",
        "LiveInfo",
        "Participants",
        "Mode",
    ):
        assert hasattr(bookieskit, name), name


@pytest.mark.parametrize("platform", ["betpawa", "sportybet", "msport"])
def test_explicit_mode_matches_auto_on_live_fixture(platform):
    """Spec §5: for platforms whose mode is informational only,
    explicit mode='live' agrees with auto-detect on a healthy live fixture."""
    d = _load(platform, "live")
    assert extract_live_info(d, platform, mode="live") == \
           extract_live_info(d, platform)


@pytest.mark.parametrize("platform", ["betpawa", "sportybet", "msport"])
def test_explicit_mode_matches_auto_on_prematch_fixture(platform):
    """Same as above for prematch fixtures."""
    d = _load(platform, "prematch")
    assert extract_live_info(d, platform, mode="prematch") == \
           extract_live_info(d, platform)
