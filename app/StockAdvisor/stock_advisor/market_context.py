from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from stock_advisor import analytics
from stock_advisor.market_data.base import Fundamentals, MarketDataError, MarketDataSource
from stock_advisor.universe import Universe

MIN_ROWS = 60


@dataclass
class MarketContext:
    universe: Universe
    source: MarketDataSource
    closes: pd.DataFrame
    index_closes: pd.Series
    missing: list[str]
    as_of: str
    fundamentals: dict[str, Fundamentals] = field(default_factory=dict)

    @property
    def available(self) -> list[str]:
        return list(self.closes.columns)

    def last_prices(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for t in self.closes.columns:
            s = self.closes[t].dropna()
            if len(s):
                out[t] = float(s.iloc[-1])
        return out

    def fundamentals_for(self, tickers: list[str]) -> dict[str, Fundamentals]:
        need = [t for t in tickers if t not in self.fundamentals]
        if need:
            self.fundamentals.update(self.source.fundamentals(need))
        return {t: self.fundamentals.get(t, Fundamentals()) for t in tickers}


def build_market_context(universe: Universe, source: MarketDataSource) -> MarketContext:
    tickers = universe.tickers
    closes = source.closes(tickers)
    if closes is None or closes.empty:
        raise MarketDataError("no price data returned for the universe")
    good = [t for t in tickers if t in closes.columns and closes[t].notna().sum() >= MIN_ROWS]
    missing = [t for t in tickers if t not in good]
    index_closes = source.index_closes()
    return MarketContext(
        universe=universe,
        source=source,
        closes=closes[good].dropna(how="all"),
        index_closes=index_closes,
        missing=missing,
        as_of=source.as_of().isoformat(),
    )


def snapshot(ctx: MarketContext, ticker: str) -> dict:
    stock = ctx.universe.by_ticker().get(ticker)
    f = ctx.fundamentals_for([ticker])[ticker]
    s = ctx.closes[ticker].dropna()
    return {
        "ticker": ticker,
        "name": (stock.name if stock else None) or f.name,
        "sector": stock.sector if stock else None,
        "last_price": analytics.to_float(s.iloc[-1]) if len(s) else None,
        "ret_1y": analytics.to_float(analytics.annual_return(s)),
        "vol_1y": analytics.to_float(analytics.annual_volatility(s)),
        "beta_1y": analytics.to_float(analytics.beta(s, ctx.index_closes)),
        "max_drawdown_1y": analytics.to_float(analytics.max_drawdown(s)),
        "trailing_pe": analytics.to_float(f.trailing_pe),
        "market_cap": analytics.to_float(f.market_cap),
        "dividend_yield_pct": analytics.to_float(f.dividend_yield_pct),
        "roe": analytics.to_float(f.roe),
        "debt_to_equity": analytics.to_float(f.debt_to_equity),
    }
