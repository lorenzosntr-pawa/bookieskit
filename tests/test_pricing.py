import pytest

from bookieskit.pricing import devig_multiplicative, devig_shin, margin

ODDS = [2.0, 3.5, 4.0]


def test_margin_three_way():
    assert margin(ODDS) == pytest.approx(0.035714, abs=1e-6)


def test_devig_multiplicative():
    p = devig_multiplicative(ODDS)
    assert p == pytest.approx([0.482759, 0.275862, 0.241379], abs=1e-6)
    assert sum(p) == pytest.approx(1.0, abs=1e-9)


def test_devig_shin():
    p = devig_shin(ODDS)
    assert p == pytest.approx([0.486734, 0.274328, 0.238938], abs=1e-6)
    assert sum(p) == pytest.approx(1.0, abs=1e-9)
    assert p[0] > devig_multiplicative(ODDS)[0]


def test_shin_zero_margin_returns_implied():
    assert devig_shin([2.0, 2.0]) == [0.5, 0.5]


@pytest.mark.parametrize("fn", [margin, devig_multiplicative, devig_shin])
@pytest.mark.parametrize(
    "odds", [[2.0, None, 3.0], [2.0, 0.0, 3.0], [1.0, 2.0], [2.0]]
)
def test_bad_odds_return_none(fn, odds):
    assert fn(odds) is None
