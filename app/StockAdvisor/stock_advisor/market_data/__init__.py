"""Pluggable market data sources."""

from __future__ import annotations

from stock_advisor.market_data.base import Fundamentals, MarketDataError, MarketDataSource

__all__ = ["Fundamentals", "MarketDataError", "MarketDataSource", "get_source"]


def get_source(settings) -> MarketDataSource:
    """Build the market data source named by ``settings.market_data_source``."""
    kind = settings.market_data_source
    if kind == "yahoo":
        from stock_advisor.market_data.yahoo import YahooMarketData

        return YahooMarketData()
    if kind == "fixture":
        from stock_advisor.market_data.fixture import FixtureMarketData

        return FixtureMarketData(settings.fixture_dir)
    raise ValueError(f"unknown MARKET_DATA_SOURCE {kind!r}; use 'yahoo' or 'fixture'")
