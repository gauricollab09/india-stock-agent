"""yfinance-backed market data with in-process caching."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from stock_advisor.market_data.base import Fundamentals, MarketDataError

log = logging.getLogger(__name__)

INDEX_TICKER = "^NSEI"


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def fundamentals_from_info(info: dict) -> Fundamentals:
    """Map a yfinance ``Ticker.info`` dict to Fundamentals.

    ``dividendYield`` is passed through as-is: yfinance >= 1.7 reports it in
    percent units (0.49 means 0.49%).
    """
    name = info.get("shortName")
    return Fundamentals(
        name=str(name) if name else None,
        trailing_pe=_to_float(info.get("trailingPE")),
        market_cap=_to_float(info.get("marketCap")),
        dividend_yield_pct=_to_float(info.get("dividendYield")),
        roe=_to_float(info.get("returnOnEquity")),
        debt_to_equity=_to_float(info.get("debtToEquity")),
        beta=_to_float(info.get("beta")),
    )


class YahooMarketData:
    def __init__(self, cache_dir: str = "/tmp/py-yfinance", retries: int = 2) -> None:
        try:
            yf.set_tz_cache_location(cache_dir)
        except Exception as exc:  # noqa: BLE001 - cache location is best effort
            log.warning("could not set yfinance cache location %s: %s", cache_dir, exc)
        try:
            yf.config.network.retries = retries
        except Exception as exc:  # noqa: BLE001 - older yfinance without config
            log.warning("could not set yfinance retries: %s", exc)
        self._closes: pd.DataFrame | None = None
        self._index: pd.Series | None = None
        self._fundamentals: dict[str, Fundamentals] = {}
        self._as_of: date | None = None

    def _download(self, tickers: list[str]) -> pd.DataFrame:
        try:
            raw = yf.download(
                list(tickers),
                period="1y",
                interval="1d",
                auto_adjust=True,
                threads=True,
                progress=False,
                group_by="column",
            )
        except Exception as exc:  # noqa: BLE001 - normalise every yfinance failure
            raise MarketDataError(f"yfinance download failed: {exc}") from exc
        if raw is None or raw.empty or "Close" not in raw:
            raise MarketDataError("yfinance returned no data")
        close = raw["Close"]
        if isinstance(close, pd.Series):
            close = close.to_frame(tickers[0])
        close = close.dropna(axis=1, how="all")
        if close.empty:
            raise MarketDataError("yfinance returned no usable closes")
        idx = pd.to_datetime(close.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        close.index = idx
        close.index.name = "Date"
        close.columns = [str(c) for c in close.columns]
        last = close.index.max()
        self._as_of = last.date() if hasattr(last, "date") else self._as_of
        return close

    def closes(self, tickers: Sequence[str]) -> pd.DataFrame:
        wanted = list(dict.fromkeys(tickers))
        cached = set(self._closes.columns) if self._closes is not None else set()
        missing = [t for t in wanted if t not in cached]
        if missing:
            fresh = self._download(missing)
            if self._closes is None:
                self._closes = fresh
            else:
                self._closes = pd.concat([self._closes, fresh], axis=1)
        assert self._closes is not None
        cols = [t for t in wanted if t in self._closes.columns]
        return self._closes[cols].copy()

    def index_closes(self) -> pd.Series:
        if self._index is None:
            frame = self._download([INDEX_TICKER])
            self._index = frame[INDEX_TICKER].rename(INDEX_TICKER)
        return self._index.copy()

    def fundamentals(self, tickers: Sequence[str]) -> dict[str, Fundamentals]:
        out: dict[str, Fundamentals] = {}
        for t in dict.fromkeys(tickers):
            if t in self._fundamentals:
                out[t] = self._fundamentals[t]
                continue
            try:
                info = yf.Ticker(t).info or {}
            except YFRateLimitError:
                log.warning("yfinance rate limited while fetching %s; stopping", t)
                break
            except Exception as exc:  # noqa: BLE001 - one bad ticker must not sink the request
                log.warning("fundamentals unavailable for %s: %s", t, exc)
                info = {}
            f = fundamentals_from_info(info)
            self._fundamentals[t] = f
            out[t] = f
        return out

    def as_of(self) -> date:
        return self._as_of or date.today()
