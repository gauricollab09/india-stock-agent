"""Pure pandas/numpy portfolio statistics. No I/O, no network."""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def to_float(x) -> float | None:
    """Convert to a finite float, or None for None/NaN/inf."""
    if x is None:
        return None
    try:
        value = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def daily_returns(closes: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Simple daily returns; rows that are entirely NaN are dropped."""
    r = closes.pct_change(fill_method=None)
    if isinstance(r, pd.DataFrame):
        return r.dropna(how="all")
    return r.dropna()


def annual_return(closes: pd.Series) -> float:
    r = daily_returns(closes.dropna())
    if len(r) == 0:
        return float("nan")
    return float((1 + r).prod() ** (TRADING_DAYS / len(r)) - 1)


def annual_volatility(closes: pd.Series) -> float:
    r = daily_returns(closes.dropna())
    if len(r) < 2:
        return float("nan")
    return float(r.std(ddof=1) * math.sqrt(TRADING_DAYS))


def _beta_from_returns(r_stock: pd.Series, r_index: pd.Series) -> float:
    joined = pd.concat([r_stock, r_index], axis=1, join="inner").dropna()
    if len(joined) < 2:
        return float("nan")
    rs, ri = joined.iloc[:, 0], joined.iloc[:, 1]
    var = float(ri.var(ddof=1))
    if var <= 0 or math.isnan(var):
        return float("nan")
    return float(rs.cov(ri) / var)


def beta(closes: pd.Series, index_closes: pd.Series) -> float:
    return _beta_from_returns(daily_returns(closes.dropna()), daily_returns(index_closes.dropna()))


def max_drawdown(closes: pd.Series) -> float:
    c = closes.dropna()
    if len(c) == 0:
        return float("nan")
    return float((c / c.cummax() - 1).min())


def avg_pairwise_correlation(closes: pd.DataFrame) -> float:
    if closes.shape[1] < 2:
        return 0.0
    corr = daily_returns(closes).corr().to_numpy()
    upper = corr[np.triu_indices_from(corr, k=1)]
    upper = upper[~np.isnan(upper)]
    if upper.size == 0:
        return 0.0
    return float(upper.mean())


def portfolio_daily_returns(closes: pd.DataFrame, weights: Mapping[str, float]) -> pd.Series:
    """Constant-weight daily portfolio returns over the given closes."""
    tickers = [t for t in weights if t in closes.columns]
    r = daily_returns(closes[tickers]).dropna()
    w = pd.Series({t: float(weights[t]) for t in tickers})
    return (r * w).sum(axis=1)


def portfolio_volatility(closes: pd.DataFrame, weights: Mapping[str, float]) -> float:
    r = portfolio_daily_returns(closes, weights)
    if len(r) < 2:
        return float("nan")
    return float(r.std(ddof=1) * math.sqrt(TRADING_DAYS))


def portfolio_beta(
    closes: pd.DataFrame, weights: Mapping[str, float], index_closes: pd.Series
) -> float:
    return _beta_from_returns(
        portfolio_daily_returns(closes, weights), daily_returns(index_closes.dropna())
    )


def portfolio_max_drawdown(closes: pd.DataFrame, weights: Mapping[str, float]) -> float:
    r = portfolio_daily_returns(closes, weights)
    if len(r) == 0:
        return float("nan")
    path = (1 + r).cumprod()
    return float((path / path.cummax() - 1).min())


def sector_weights(weights: Mapping[str, float], sectors: Mapping[str, str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for ticker, w in weights.items():
        sector = sectors.get(ticker, "Unknown")
        out[sector] = out.get(sector, 0.0) + float(w)
    return {s: round(w, 4) for s, w in out.items()}
