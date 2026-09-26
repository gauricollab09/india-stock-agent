from datetime import date

import pandas as pd

from stock_advisor.market_data.fixture import FixtureMarketData
from tests.synthetic import SMALL_TICKERS, make_synthetic_fixture


def test_fixture_round_trip(tmp_path):
    make_synthetic_fixture(tmp_path, SMALL_TICKERS, days=30, sparse=["SUNPHARMA.NS"])
    src = FixtureMarketData(tmp_path)

    closes = src.closes(["TCS.NS", "INFY.NS", "NOPE.NS"])
    assert list(closes.columns) == ["TCS.NS", "INFY.NS"]
    assert len(closes) == 30
    assert isinstance(closes.index, pd.DatetimeIndex)
    assert closes.index.tz is None
    assert closes.index.name == "Date"
    assert closes.index.max() == pd.Timestamp(date(2026, 9, 25))

    idx = src.index_closes()
    assert idx.name == "^NSEI"
    assert idx.index.tz is None
    assert len(idx) == 30

    assert src.as_of() == date(2026, 9, 25)

    fund = src.fundamentals(["TCS.NS", "SUNPHARMA.NS", "NOPE.NS"])
    assert set(fund) == {"TCS.NS", "SUNPHARMA.NS"}
    assert fund["TCS.NS"].trailing_pe is not None
    assert fund["SUNPHARMA.NS"].trailing_pe is None
    assert fund["SUNPHARMA.NS"].name is None


def test_fixture_returns_copies(tmp_path):
    make_synthetic_fixture(tmp_path, SMALL_TICKERS[:2], days=10)
    src = FixtureMarketData(tmp_path)
    a = src.closes(SMALL_TICKERS[:2])
    a.iloc[0, 0] = -1.0
    assert src.closes(SMALL_TICKERS[:2]).iloc[0, 0] > 0
