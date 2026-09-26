from datetime import date

import numpy as np
import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

from stock_advisor.market_data import get_source, yahoo
from stock_advisor.market_data.base import MarketDataError
from stock_advisor.market_data.fixture import FixtureMarketData
from stock_advisor.market_data.yahoo import YahooMarketData, fundamentals_from_info
from tests.synthetic import make_synthetic_fixture


def _multiindex_frame(tickers, days=20, nan_ticker=None, tz="Asia/Kolkata"):
    index = pd.bdate_range(end=pd.Timestamp("2026-09-25"), periods=days, name="Date")
    if tz:
        index = index.tz_localize(tz)
    rng = np.random.default_rng(1)
    data = {}
    for t in tickers:
        for field in ["Open", "High", "Low", "Close", "Volume"]:
            col = np.full(days, np.nan) if t == nan_ticker else rng.uniform(100, 200, days)
            data[(field, t)] = col
    frame = pd.DataFrame(data, index=index)
    frame.columns = pd.MultiIndex.from_tuples(frame.columns, names=["Price", "Ticker"])
    return frame


@pytest.fixture
def quiet_yf(monkeypatch):
    monkeypatch.setattr(yahoo.yf, "set_tz_cache_location", lambda *_a, **_k: None)


def test_yahoo_drops_all_nan_columns(monkeypatch, quiet_yf):
    calls = []

    def fake_download(tickers, **kwargs):
        calls.append(list(tickers))
        return _multiindex_frame(tickers, nan_ticker="DEAD.NS")

    monkeypatch.setattr(yahoo.yf, "download", fake_download)
    src = YahooMarketData(cache_dir="/tmp/unused")
    closes = src.closes(["INFY.NS", "DEAD.NS", "TCS.NS"])
    assert list(closes.columns) == ["INFY.NS", "TCS.NS"]
    assert closes.index.tz is None
    assert closes.index.name == "Date"
    assert src.as_of() == date(2026, 9, 25)
    assert calls == [["INFY.NS", "DEAD.NS", "TCS.NS"]]

    # cached: a second call for a subset triggers no download
    again = src.closes(["TCS.NS"])
    assert list(again.columns) == ["TCS.NS"]
    assert len(calls) == 1


def test_yahoo_index_closes(monkeypatch, quiet_yf):
    monkeypatch.setattr(yahoo.yf, "download", lambda tickers, **k: _multiindex_frame(tickers))
    src = YahooMarketData()
    idx = src.index_closes()
    assert idx.name == "^NSEI"
    assert idx.index.tz is None
    assert len(idx) == 20


def test_yahoo_empty_download_raises(monkeypatch, quiet_yf):
    monkeypatch.setattr(yahoo.yf, "download", lambda tickers, **k: pd.DataFrame())
    with pytest.raises(MarketDataError):
        YahooMarketData().closes(["INFY.NS"])


def test_yahoo_download_exception_wrapped(monkeypatch, quiet_yf):
    def boom(tickers, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(yahoo.yf, "download", boom)
    with pytest.raises(MarketDataError):
        YahooMarketData().closes(["INFY.NS"])


def test_fundamentals_from_info_mapping():
    f = fundamentals_from_info(
        {
            "shortName": "Infosys",
            "trailingPE": 22.5,
            "marketCap": 6.5e12,
            "dividendYield": 2.9,
            "returnOnEquity": 0.32,
            "debtToEquity": 8.1,
            "beta": "0.7",
        }
    )
    assert f.name == "Infosys"
    assert f.trailing_pe == 22.5
    assert f.market_cap == 6.5e12
    assert f.dividend_yield_pct == 2.9  # percent units, passed through
    assert f.roe == 0.32
    assert f.debt_to_equity == 8.1
    assert f.beta == 0.7


def test_fundamentals_from_info_none_coercion():
    f = fundamentals_from_info({"trailingPE": None, "marketCap": "n/a", "beta": float("nan")})
    assert f.name is None
    assert f.trailing_pe is None
    assert f.market_cap is None
    assert f.beta is None
    assert f.dividend_yield_pct is None


def test_yahoo_fundamentals_stops_on_rate_limit(monkeypatch, quiet_yf):
    seen = []

    class StubTicker:
        def __init__(self, ticker):
            self.ticker = ticker
            seen.append(ticker)

        @property
        def info(self):
            if self.ticker == "TCS.NS":
                raise YFRateLimitError()
            return {"shortName": self.ticker, "trailingPE": 20.0}

    monkeypatch.setattr(yahoo.yf, "Ticker", StubTicker)
    src = YahooMarketData()
    out = src.fundamentals(["INFY.NS", "TCS.NS", "HDFCBANK.NS"])
    assert list(out) == ["INFY.NS"]
    assert out["INFY.NS"].trailing_pe == 20.0
    assert seen == ["INFY.NS", "TCS.NS"]  # stopped before HDFCBANK


def test_yahoo_fundamentals_other_errors_become_empty(monkeypatch, quiet_yf):
    class StubTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        @property
        def info(self):
            raise KeyError("currentTradingPeriod")

    monkeypatch.setattr(yahoo.yf, "Ticker", StubTicker)
    out = YahooMarketData().fundamentals(["INFY.NS"])
    assert out["INFY.NS"].trailing_pe is None


class _Settings:
    def __init__(self, kind, fixture_dir=None):
        self.market_data_source = kind
        self.fixture_dir = fixture_dir


def test_get_source_dispatch(tmp_path, monkeypatch, quiet_yf):
    make_synthetic_fixture(tmp_path, ["INFY.NS"], days=5)
    assert isinstance(get_source(_Settings("fixture", tmp_path)), FixtureMarketData)
    assert isinstance(get_source(_Settings("yahoo")), YahooMarketData)
    with pytest.raises(ValueError):
        get_source(_Settings("csv"))
