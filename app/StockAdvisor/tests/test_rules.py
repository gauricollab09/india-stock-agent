from dataclasses import dataclass

import pytest

from stock_advisor.rules import Violation, check_rules, normalized_weights
from stock_advisor.schemas import PickInput, Requirements


@dataclass(frozen=True)
class FakeStock:
    ticker: str
    sector: str


STOCKS = {
    "HDFCBANK.NS": FakeStock("HDFCBANK.NS", "Financial Services"),
    "ICICIBANK.NS": FakeStock("ICICIBANK.NS", "Financial Services"),
    "INFY.NS": FakeStock("INFY.NS", "Information Technology"),
    "TCS.NS": FakeStock("TCS.NS", "Information Technology"),
    "RELIANCE.NS": FakeStock("RELIANCE.NS", "Oil Gas & Consumable Fuels"),
    "SUNPHARMA.NS": FakeStock("SUNPHARMA.NS", "Healthcare"),
}
PRICES = {
    "HDFCBANK.NS": 735.0,
    "ICICIBANK.NS": 1400.0,
    "INFY.NS": 1000.0,
    "TCS.NS": 2082.0,
    "RELIANCE.NS": 1226.0,
    "SUNPHARMA.NS": 1700.0,
}
REQ = Requirements(amount_inr=500_000, risk_tolerance="moderate", max_stocks=5)


def picks(*pairs):
    return [PickInput(ticker=t, target_weight=w) for t, w in pairs]


CLEAN = picks(
    ("HDFCBANK.NS", 0.25), ("INFY.NS", 0.25), ("RELIANCE.NS", 0.25), ("SUNPHARMA.NS", 0.25)
)


def codes(vs: list[Violation]) -> list[str]:
    return [v.code for v in vs]


def test_clean_portfolio_has_no_violations():
    assert check_rules(CLEAN, REQ, STOCKS, PRICES, set()) == []


def test_normalized_weights():
    assert normalized_weights(picks(("A", 0.25), ("B", 0.75))) == {"A": 0.25, "B": 0.75}
    nw = normalized_weights(picks(("A", 0.2), ("B", 0.6)))
    assert nw["A"] == pytest.approx(0.25) and nw["B"] == pytest.approx(0.75)


def test_duplicate_ticker():
    p = picks(
        ("HDFCBANK.NS", 0.2),
        ("HDFCBANK.NS", 0.2),
        ("INFY.NS", 0.2),
        ("RELIANCE.NS", 0.2),
        ("SUNPHARMA.NS", 0.2),
    )
    vs = check_rules(p, REQ, STOCKS, PRICES, set())
    assert codes(vs) == ["duplicate_ticker"]
    assert "HDFCBANK.NS" in vs[0].message


def test_unknown_ticker():
    p = picks(("NOPE.NS", 0.25), ("INFY.NS", 0.25), ("RELIANCE.NS", 0.25), ("SUNPHARMA.NS", 0.25))
    assert codes(check_rules(p, REQ, STOCKS, PRICES, set())) == ["unknown_ticker"]


def test_missing_data():
    prices = {k: v for k, v in PRICES.items() if k != "INFY.NS"}
    assert codes(check_rules(CLEAN, REQ, STOCKS, prices, set())) == ["missing_data"]


def test_excluded_sector():
    vs = check_rules(CLEAN, REQ, STOCKS, PRICES, {"Healthcare"})
    assert codes(vs) == ["excluded_sector"]
    assert "SUNPHARMA.NS" in vs[0].message and "Healthcare" in vs[0].message


def test_too_few_stocks():
    p = picks(
        ("HDFCBANK.NS", 0.25), ("INFY.NS", 0.25), ("RELIANCE.NS", 0.25), ("SUNPHARMA.NS", 0.25)
    )[:3]
    p = [PickInput(ticker=x.ticker, target_weight=1 / 3) for x in p]
    vs = check_rules(p, REQ, STOCKS, PRICES, set())
    assert "too_few_stocks" in codes(vs)
    assert [c for c in codes(vs) if c != "max_weight"] == ["too_few_stocks"]


def test_too_many_stocks():
    p = picks(*[(t, 1 / 6) for t in STOCKS])
    assert codes(check_rules(p, REQ, STOCKS, PRICES, set())) == ["too_many_stocks"]


def test_weight_sum_within_tolerance_is_fine():
    p = picks(
        ("HDFCBANK.NS", 0.251), ("INFY.NS", 0.251), ("RELIANCE.NS", 0.251), ("SUNPHARMA.NS", 0.251)
    )
    assert check_rules(p, REQ, STOCKS, PRICES, set()) == []


def test_weight_sum_violation():
    p = picks(("HDFCBANK.NS", 0.2), ("INFY.NS", 0.2), ("RELIANCE.NS", 0.2), ("SUNPHARMA.NS", 0.2))
    vs = check_rules(p, REQ, STOCKS, PRICES, set())
    assert codes(vs) == ["weight_sum"]
    assert "0.8000" in vs[0].message


def test_max_weight():
    p = picks(("HDFCBANK.NS", 0.4), ("INFY.NS", 0.2), ("RELIANCE.NS", 0.2), ("SUNPHARMA.NS", 0.2))
    vs = check_rules(p, REQ, STOCKS, PRICES, set())
    assert codes(vs) == ["max_weight"]
    assert "HDFCBANK.NS" in vs[0].message


def test_max_sector_weight():
    p = picks(
        ("HDFCBANK.NS", 0.25), ("ICICIBANK.NS", 0.25), ("INFY.NS", 0.25), ("SUNPHARMA.NS", 0.25)
    )
    vs = check_rules(p, REQ, STOCKS, PRICES, set())
    assert codes(vs) == ["max_sector_weight"]
    assert "Financial Services" in vs[0].message


def test_unaffordable():
    req = Requirements(amount_inr=10_000, risk_tolerance="low")
    prices = dict(PRICES, **{"TCS.NS": 50_000.0})
    p = picks(
        ("HDFCBANK.NS", 0.25), ("SUNPHARMA.NS", 0.25), ("RELIANCE.NS", 0.25), ("TCS.NS", 0.25)
    )
    vs = check_rules(p, req, STOCKS, prices, set())
    assert codes(vs) == ["unaffordable"]
    assert "TCS.NS" in vs[0].message
