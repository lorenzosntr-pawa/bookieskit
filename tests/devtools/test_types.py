from dataclasses import asdict

from bookieskit.devtools.types import (
    Candidate,
    Handle,
    ResolvedEvent,
    VerifyResult,
)


def test_handle_defaults_extra_to_empty_dict():
    h = Handle(platform="betway", event_id="123")
    assert h.platform == "betway"
    assert h.event_id == "123"
    assert h.extra == {}
    # extra dicts are per-instance (no shared mutable default)
    h.extra["competition_id"] = "7"
    assert Handle(platform="x", event_id=None).extra == {}


def test_resolved_event_round_trips_through_asdict():
    ev = ResolvedEvent(
        seed="sr:match:42",
        sport="soccer",
        sr_numeric="42",
        home="A",
        away="B",
        handles={"betway": Handle(platform="betway", event_id="42")},
        skipped={"sportpesa": "cookie missing"},
    )
    d = asdict(ev)
    assert d["sr_numeric"] == "42"
    assert d["handles"]["betway"]["event_id"] == "42"
    assert d["skipped"]["sportpesa"] == "cookie missing"


def test_candidate_fields():
    c = Candidate(
        platform="sportybet",
        market_id="18",
        name="Over/Under",
        specifier="total=2.5",
        outcomes=["Over", "Under"],
    )
    assert c.market_id == "18"
    assert c.outcomes == ["Over", "Under"]


def test_verify_result_fields():
    vr = VerifyResult(
        platform="betpawa",
        resolved={"1x2_ft": {"outcomes": {"home": 1.5}}},
        missing=["over_under_ft"],
    )
    assert "1x2_ft" in vr.resolved
    assert vr.missing == ["over_under_ft"]
