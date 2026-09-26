"""Deterministic synthetic market data for offline tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from stock_advisor.market_data.base import Fundamentals
from stock_advisor.market_data.fixture import write_fixture

SMALL_TICKERS = [
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "TCS.NS",
    "RELIANCE.NS",
    "SUNPHARMA.NS",
]


def _walk(rng: np.random.Generator, start: float, days: int) -> np.ndarray:
    returns = rng.normal(0.0004, 0.015, size=days - 1)
    return start * np.concatenate([[1.0], np.cumprod(1 + returns)])


def make_synthetic_fixture(
    directory: Path,
    tickers: Sequence[str],
    days: int = 260,
    seed: int = 7,
    as_of: date = date(2026, 9, 25),
    sparse: Sequence[str] = (),
) -> None:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(end=pd.Timestamp(as_of), periods=days, name="Date")
    starts = np.linspace(100, 3000, num=max(len(tickers), 1))
    closes = pd.DataFrame(
        {t: _walk(rng, float(starts[i]), days) for i, t in enumerate(tickers)}, index=index
    )
    index_closes = pd.Series(_walk(rng, 23000.0, days), index=index, name="^NSEI")
    fundamentals: dict[str, Fundamentals] = {}
    for t in tickers:
        if t in sparse:
            fundamentals[t] = Fundamentals()
            continue
        fundamentals[t] = Fundamentals(
            name=t.replace(".NS", "") + " Ltd.",
            trailing_pe=float(rng.uniform(15, 40)),
            market_cap=float(rng.uniform(1e12, 2e13)),
            dividend_yield_pct=float(rng.uniform(0.3, 3.0)),
            roe=float(rng.uniform(0.08, 0.45)),
            debt_to_equity=float(rng.uniform(5, 120)),
            beta=float(rng.uniform(0.5, 1.4)),
        )
    write_fixture(Path(directory), closes, index_closes, fundamentals, as_of)
