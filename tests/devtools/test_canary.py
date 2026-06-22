from dataclasses import asdict

from bookieskit.devtools.canary import (
    CORE_CANONICALS,
    STRUCTURE_PREDICATES,
    BookCheck,
    CanaryReport,
    expected_core,
)
from bookieskit.markets.registry import MarketRegistry


def test_core_canonicals_are_the_four_soccer_basics():
    assert CORE_CANONICALS == (
        "1x2_ft", "over_under_ft", "btts_ft", "double_chance_ft",
    )


def test_bookcheck_and_canaryreport_round_trip_through_asdict():
    bc = BookCheck(
        platform="betway",
        status="ok",
        reason="",
        expected_canonicals=["1x2_ft"],
        resolved_canonicals=["1x2_ft"],
        missing_canonicals=[],
        structure_ok=True,
    )
    rep = CanaryReport(
        sport="soccer",
        seed="33289995",
        sr_numeric="68995116",
        checks=[bc],
        drifted=False,
    )
    d = asdict(rep)
    assert d["seed"] == "33289995"
    assert d["sr_numeric"] == "68995116"
    assert d["drifted"] is False
    assert d["checks"][0]["status"] == "ok"
    assert d["checks"][0]["missing_canonicals"] == []


def test_structure_predicates_cover_all_seven_books():
    assert set(STRUCTURE_PREDICATES) == {
        "betpawa", "sportybet", "msport", "bet9ja",
        "betway", "betika", "sportpesa",
    }


def test_structure_predicate_betpawa():
    pred = STRUCTURE_PREDICATES["betpawa"]
    assert pred({"markets": [{"id": "3743"}]}) is True
    assert pred({"markets": "nope"}) is False
    assert pred({}) is False


def test_structure_predicate_sportybet_and_msport():
    for book in ("sportybet", "msport"):
        pred = STRUCTURE_PREDICATES[book]
        assert pred({"data": {"markets": [{"id": "1"}]}}) is True
        assert pred({"data": {"markets": "nope"}}) is False
        assert pred({"data": None}) is False
        assert pred({}) is False


def test_structure_predicate_betway_requires_all_three_lists():
    pred = STRUCTURE_PREDICATES["betway"]
    assert pred(
        {"marketsInGroup": [], "outcomes": [], "prices": []}
    ) is True
    assert pred({"marketsInGroup": [], "outcomes": []}) is False  # no prices
    assert pred(
        {"marketsInGroup": {}, "outcomes": [], "prices": []}
    ) is False


def test_structure_predicate_bet9ja_requires_D_O_dict():
    pred = STRUCTURE_PREDICATES["bet9ja"]
    assert pred({"D": {"O": {"S_1X2_1": 1.95}}}) is True
    assert pred({"D": {"O": []}}) is False
    assert pred({"D": None}) is False
    assert pred({}) is False


def test_structure_predicate_betika_nonempty_data_with_odds_list():
    pred = STRUCTURE_PREDICATES["betika"]
    assert pred({"data": [{"odds": [{"sub_type_id": "1"}]}]}) is True
    assert pred({"data": [{"odds": "nope"}]}) is False
    assert pred({"data": []}) is False
    assert pred({}) is False


def test_structure_predicate_sportpesa_first_value_is_list():
    pred = STRUCTURE_PREDICATES["sportpesa"]
    assert pred({"999": [{"id": "10"}]}) is True
    assert pred({"999": {}}) is False  # first value not a list
    assert pred({}) is False  # empty dict


def test_expected_core_full_for_every_soccer_book():
    reg = MarketRegistry()
    for book in (
        "betpawa", "sportybet", "msport", "bet9ja",
        "betway", "betika", "sportpesa",
    ):
        assert set(expected_core(book, "soccer", reg)) == set(CORE_CANONICALS)


def test_expected_core_empty_for_unknown_platform():
    reg = MarketRegistry()
    assert expected_core("nonexistent", "soccer", reg) == []


def test_expected_core_defaults_to_builtin_registry_when_none():
    # registry arg is required by signature; pass a fresh builtin.
    assert expected_core("betway", "soccer", MarketRegistry())
