"""Market data seam: the only place the agent touches the outside world."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class Fundamentals:
    """Per-stock fundamentals. Any field may be None when the source lacks it.

    Units: dividend_yield_pct is a percentage (1.2 == 1.2%), roe is a fraction
    (0.18 == 18%), debt_to_equity is a percentage-style ratio as reported by Yahoo.
    """

    name: str | None = None
    trailing_pe: float | None = None
    market_cap: float | None = None
    dividend_yield_pct: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    beta: float | None = None


class MarketDataError(Exception):
    """Raised when a source cannot provide any usable data."""


class MarketDataSource(Protocol):
    def closes(self, tickers: Sequence[str]) -> pd.DataFrame:
        """Daily adjusted closes in INR.

        tz-naive DatetimeIndex named "Date"; columns only for tickers that have
        data, in the requested order.
        """
        ...

    def index_closes(self) -> pd.Series:
        """NIFTY 50 daily closes, tz-naive, Series named "^NSEI"."""
        ...

    def fundamentals(self, tickers: Sequence[str]) -> dict[str, Fundamentals]:
        """Fundamentals for the tickers the source could fetch."""
        ...

    def as_of(self) -> date:
        """The date the price data is current to."""
        ...
