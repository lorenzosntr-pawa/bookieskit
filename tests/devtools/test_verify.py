from bookieskit.devtools.verify import verify

# Reuse the existing Betway parser fixture shape (1X2 + O/U + DC + BTTS).
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


def test_verify_lists_all_parsed_canonicals_when_no_filter():
    vr = verify(BETWAY_PAYLOAD, "betway", "soccer")
    assert vr.platform == "betway"
    assert set(vr.resolved) == {"1x2_ft", "over_under_ft"}
    assert vr.missing == []
    assert vr.resolved["1x2_ft"]["outcomes"]["home"] == 1.63
    assert vr.resolved["over_under_ft"]["lines"][2.5]["over"] == 1.8


def test_verify_reports_missing_requested_canonicals():
    vr = verify(
        BETWAY_PAYLOAD, "betway", "soccer",
        canonical_ids=["1x2_ft", "btts_ft"],
    )
    assert "1x2_ft" in vr.resolved
    assert vr.missing == ["btts_ft"]


def test_verify_unknown_platform_is_empty():
    vr = verify({}, "nonexistent", "soccer", canonical_ids=["1x2_ft"])
    assert vr.resolved == {}
    assert vr.missing == ["1x2_ft"]
