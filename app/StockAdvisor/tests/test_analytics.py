import math

import pandas as pd
import pytest

from stock_advisor import analytics as a


def _series(values):
    return pd.Series(values, index=pd.date_range("2026-01-01", periods=len(values)), dtype=float)


A = [100.0, 110.0, 99.0]
B = [100.0, 100.0, 120.0]
INDEX = [100.0, 105.0, 99.75]


def test_to_float():
    assert a.to_float(None) is None
    assert a.to_float(float("nan")) is None
    assert a.to_float(float("inf")) is None
    assert a.to_float("x") is None
    assert a.to_float(3) == 3.0


def test_daily_returns():
    r = a.daily_returns(_series(A))
    assert list(r.round(10)) == [0.1, -0.1]


def test_annual_volatility_and_drawdown():
    assert a.annual_volatility(_series(A)) == pytest.approx(0.1414213562 * math.sqrt(252))
    assert a.max_drawdown(_series(A)) == pytest.approx(-0.1)


def test_beta():
    assert a.beta(_series(A), _series(INDEX)) == pytest.approx(2.0)


def test_beta_nan_when_too_short():
    assert math.isnan(a.beta(_series([100.0, 101.0]), _series([100.0, 101.0])))


def test_annual_return():
    assert a.annual_return(_series([100.0, 110.0, 121.0])) == pytest.approx(1.21**126 - 1)


def test_portfolio_stats():
    closes = pd.DataFrame({"A": A, "B": B}, index=pd.date_range("2026-01-01", periods=3))
    weights = {"A": 0.5, "B": 0.5}
    r = a.portfolio_daily_returns(closes, weights)
    assert list(r.round(10)) == [0.05, 0.05]
    assert a.portfolio_volatility(closes, weights) == pytest.approx(0.0)
    assert a.avg_pairwise_correlation(closes) == pytest.approx(-1.0)
    assert a.portfolio_max_drawdown(closes, weights) == pytest.approx(0.0)
    assert a.avg_pairwise_correlation(closes[["A"]]) == 0.0


def test_sector_weights():
    out = a.sector_weights({"A": 0.25, "B": 0.35, "C": 0.4}, {"A": "IT", "B": "IT", "C": "Bank"})
    assert out == {"IT": 0.6, "Bank": 0.4}
