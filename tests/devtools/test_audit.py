import asyncio
from dataclasses import asdict

import pytest

from bookieskit.devtools import audit as audit_mod
from bookieskit.devtools.audit import (
    AuditReport,
    BookAudit,
    FixtureAudit,
    MarketAudit,
    UnmappedGroup,
    audit_fixture,
    build_report,
    classify_book,
    expected_canonicals,
    render_markdown,
    run_audit,
)

# Betway 1X2 + O/U (parses) -- reuse the verify fixture shape.
BETWAY_PAYLOAD = {
    "marketsInGroup": [
        {"marketId": "693394361", "name": "[Win/Draw/Win]", "handicap": 0},
        {"marketId": "6933943618total=2.5~", "name": "Total", "handicap": 2.5},
    ],
    "outcomes": [
        {"outcomeId": "o1", "marketId": "693394361", "name": "Arsenal FC"},
        {"outcomeId": "o2", "marketId": "693394361", "name": "Draw"},
        {"outcomeId": "o3", "marketId": "693394361", "name": "Atletico Madrid"},
        {"outcomeId": "o9", "marketId": "6933943618total=2.5~", "name": "Over"},
        {"outcomeId": "o10", "marketId": "6933943618total=2.5~", "name": "Under"},
    ],
    "prices": [
        {"outcomeId": "o1", "priceDecimal": 1.63},
        {"outcomeId": "o2", "priceDecimal": 4.0},
        {"outcomeId": "o3", "priceDecimal": 4.6},
        {"outcomeId": "o9", "priceDecimal": 1.8},
        {"outcomeId": "o10", "priceDecimal": 2.0},
    ],
}

# A sportybet payload carrying one registry-unknown ("exotic") market group.
SPORTYBET_EXOTIC = {
    "data": {
        "markets": [
            {
                "id": "999999",
                "name": "Some Exotic Market",
                "outcomes": [{"desc": "Yes"}, {"desc": "No"}],
            }
        ]
    }
}


# ---- Task 1: classification -----------------------------------------------


def test_expected_canonicals_is_sorted_and_football_only():
    exp = expected_canonicals("betway", "soccer")
    assert "1x2_ft" in exp and "over_under_ft" in exp
    assert exp == sorted(exp)
    # football audit must not expect basketball/tennis markets
    assert not any("basketball" in c or "tennis" in c for c in exp)


def test_expected_canonicals_unknown_platform_is_empty():
    assert expected_canonicals("nonexistent", "soccer") == []


def test_classify_book_marks_parsed_markets_priced_with_odds():
    ba = classify_book(BETWAY_PAYLOAD, "betway", "soccer")
    assert isinstance(ba, BookAudit)
    assert ba.platform == "betway" and ba.status == "ok"
    by_id = {m.canonical_id: m for m in ba.markets}
    assert by_id["1x2_ft"].status == "mapped_priced"
    assert by_id["1x2_ft"].odds["outcomes"]["home"] == 1.63
    assert by_id["over_under_ft"].odds["lines"][2.5]["over"] == 1.8


def test_classify_book_marks_unparsed_expected_market_not_offered():
    ba = classify_book(BETWAY_PAYLOAD, "betway", "soccer")
    by_id = {m.canonical_id: m for m in ba.markets}
    assert by_id["btts_ft"].status == "not_offered"
    assert by_id["btts_ft"].odds is None


def test_classify_book_betway_unmapped_groups_empty_by_caveat():
    ba = classify_book(BETWAY_PAYLOAD, "betway", "soccer")
    assert ba.unmapped_groups == []


def test_classify_book_surfaces_unmapped_groups_for_non_betway():
    ba = classify_book(SPORTYBET_EXOTIC, "sportybet", "soccer")
    assert ba.status == "ok"
    assert any(g.name == "Some Exotic Market" for g in ba.unmapped_groups)
    assert all(isinstance(g, UnmappedGroup) for g in ba.unmapped_groups)


def test_bookaudit_round_trips_through_asdict():
    ba = classify_book(BETWAY_PAYLOAD, "betway", "soccer")
    d = asdict(ba)
    assert d["platform"] == "betway"
    assert isinstance(d["markets"], list)
    assert d["markets"][0]["canonical_id"] is not None


# ---- Task 2: fixture-level audit + report ---------------------------------


def test_audit_fixture_classifies_present_and_skips_absent_books():
    raws = {"betway": BETWAY_PAYLOAD}
    skipped = {"sportpesa": "no cookie", "msport": "fetch failed: Timeout()"}
    fa = audit_fixture("seed-1", "68995116", raws, skipped, "soccer")
    by_book = {b.platform: b for b in fa.books}
    assert by_book["betway"].status == "ok"
    assert by_book["sportpesa"].status == "skipped"
    assert by_book["sportpesa"].reason == "no cookie"
    assert by_book["msport"].status == "unreachable"
    # Books neither present nor skipped are reported as skipped (not probed).
    assert by_book["betpawa"].status == "skipped"


def test_build_report_counts_summary():
    fa = audit_fixture(
        "seed-1", "68995116", {"betway": BETWAY_PAYLOAD}, {}, "soccer"
    )
    rep = build_report([fa], sport="soccer", mode="prematch")
    assert isinstance(rep, AuditReport)
    assert rep.mode == "prematch"
    assert rep.summary["mapped_priced"] >= 2  # 1x2 + O/U on betway
    assert rep.summary["books_ok"] == 1
    assert rep.summary["books_skipped"] >= 1


# ---- Task 3: markdown renderer --------------------------------------------


def test_render_markdown_has_title_summary_and_fixture():
    fa = audit_fixture(
        "Arsenal vs Atletico", "68995116", {"betway": BETWAY_PAYLOAD}, {},
        "soccer",
    )
    rep = build_report([fa], sport="soccer", mode="prematch")
    md = render_markdown(rep)
    assert "# bookieskit — Live Odds Audit" in md
    assert "prematch" in md
    assert "Arsenal vs Atletico" in md
    assert "1x2_ft" in md
    assert "betway" in md
    assert "—" in md  # not-offered placeholder


def test_render_markdown_lists_unmapped_groups_section():
    fa = audit_fixture("F1", None, {"sportybet": SPORTYBET_EXOTIC}, {}, "soccer")
    rep = build_report([fa], sport="soccer", mode="prematch")
    md = render_markdown(rep)
    assert "MIS-MAP review" in md
    assert "Some Exotic Market" in md


# ---- Task 4: async run_audit ----------------------------------------------


def test_run_audit_prematch_builds_report_from_injected_runner(monkeypatch):
    async def fake_resolve(seed, sport, books, **kw):
        from bookieskit.devtools.types import Handle, ResolvedEvent

        assert kw.get("live") is False
        return ResolvedEvent(
            seed=seed,
            sport=sport,
            sr_numeric="68995116",
            home="Arsenal",
            away="Atletico",
            handles={"betway": Handle(platform="betway", event_id="e1")},
            skipped={"sportpesa": "no cookie"},
        )

    async def fake_fetch(book, handle, clients, *, live, **kwargs):
        assert live is False
        return BETWAY_PAYLOAD

    monkeypatch.setattr(audit_mod, "resolve_event", fake_resolve)
    monkeypatch.setattr(audit_mod, "_fetch_book", fake_fetch)

    rep = asyncio.run(run_audit("prematch", seeds=["123"]))
    assert rep.mode == "prematch"
    assert len(rep.fixtures) == 1
    assert rep.fixtures[0].label == "Arsenal vs Atletico"
    by_book = {b.platform: b for b in rep.fixtures[0].books}
    assert by_book["betway"].status == "ok"
    assert by_book["sportpesa"].status == "skipped"


def test_run_audit_prematch_requires_seeds():
    with pytest.raises(ValueError):
        asyncio.run(run_audit("prematch", seeds=None))


def test_run_audit_unknown_mode_raises():
    with pytest.raises(ValueError):
        asyncio.run(run_audit("bogus"))


def test_run_audit_live_uses_injected_discover(monkeypatch):
    async def fake_discover(sport, max_live, clients):
        return ["live-1"]

    async def fake_resolve(seed, sport, books, **kw):
        from bookieskit.devtools.types import Handle, ResolvedEvent

        assert kw.get("live") is True
        assert kw.get("betpawa_seed") is True
        return ResolvedEvent(
            seed=seed,
            sport=sport,
            sr_numeric=None,
            home="Home",
            away="Away",
            handles={"betway": Handle(platform="betway", event_id="e1")},
            skipped={},
        )

    async def fake_fetch(book, handle, clients, *, live, **kwargs):
        assert live is True
        return BETWAY_PAYLOAD

    monkeypatch.setattr(audit_mod, "resolve_event", fake_resolve)
    monkeypatch.setattr(audit_mod, "_fetch_book", fake_fetch)

    rep = asyncio.run(run_audit("live", discover=fake_discover))
    assert rep.mode == "live"
    assert len(rep.fixtures) == 1


def test_fetch_book_threads_sportpesa_cookie_to_client(monkeypatch):
    # Regression: a cookie-gated book must receive its cookie at construction,
    # else the live fetch hits an unauthenticated challenge (looks unreachable).
    from bookieskit.devtools import resolver as resolver_mod
    from bookieskit.devtools.types import Handle

    seen: dict = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class _FakeAdapter:
        async def fetch_raw_markets(self, client, handle, *, live):
            return {"ok": True}

    monkeypatch.setitem(resolver_mod._CLIENT_CLASSES, "sportpesa", _FakeClient)
    monkeypatch.setitem(resolver_mod._COUNTRY, "sportpesa", "ke")
    monkeypatch.setitem(audit_mod.ADAPTERS, "sportpesa", _FakeAdapter())

    raw = asyncio.run(
        audit_mod._fetch_book(
            "sportpesa",
            Handle(platform="sportpesa", event_id="e1"),
            None,
            live=True,
            sportpesa_cookie="warm-cookie",
        )
    )
    assert raw == {"ok": True}
    assert seen.get("cookie") == "warm-cookie"
    assert seen.get("country") == "ke"


def test_audit_dataclasses_construct_directly():
    # Sanity: the dataclasses are usable without the network path.
    ma = MarketAudit("1x2_ft", "mapped_priced", {"outcomes": {"home": 1.5}})
    ba = BookAudit("betway", "ok", "", [ma], [])
    fa = FixtureAudit("F", None, [ba])
    rep = AuditReport("soccer", "prematch", [fa], {"mapped_priced": 1})
    assert asdict(rep)["fixtures"][0]["books"][0]["markets"][0]["odds"]
