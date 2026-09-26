"""Frozen on-disk market data: reproducible tests, evals and offline demos."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import pandas as pd

from stock_advisor.market_data.base import Fundamentals

CLOSES_FILE = "closes.csv"
INDEX_FILE = "index_closes.csv"
FUNDAMENTALS_FILE = "fundamentals.json"
META_FILE = "meta.json"


def write_fixture(
    directory: Path,
    closes: pd.DataFrame,
    index_closes: pd.Series,
    fundamentals: Mapping[str, Fundamentals],
    as_of: date,
) -> None:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    closes.to_csv(directory / CLOSES_FILE, index_label="Date")
    idx = index_closes.rename("close")
    idx.to_csv(directory / INDEX_FILE, index_label="Date")
    (directory / FUNDAMENTALS_FILE).write_text(
        json.dumps({t: dataclasses.asdict(f) for t, f in fundamentals.items()}, indent=2),
        encoding="utf-8",
    )
    (directory / META_FILE).write_text(
        json.dumps({"as_of": as_of.isoformat()}), encoding="utf-8"
    )


class FixtureMarketData:
    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        closes = pd.read_csv(self._dir / CLOSES_FILE, index_col="Date", parse_dates=True)
        closes.index = pd.to_datetime(closes.index).tz_localize(None)
        closes.index.name = "Date"
        self._closes = closes
        idx = pd.read_csv(self._dir / INDEX_FILE, index_col="Date", parse_dates=True)["close"]
        idx.index = pd.to_datetime(idx.index).tz_localize(None)
        idx.index.name = "Date"
        self._index = idx.rename("^NSEI")
        raw = json.loads((self._dir / FUNDAMENTALS_FILE).read_text(encoding="utf-8"))
        self._fundamentals = {t: Fundamentals(**v) for t, v in raw.items()}
        meta = json.loads((self._dir / META_FILE).read_text(encoding="utf-8"))
        self._as_of = date.fromisoformat(meta["as_of"])

    def closes(self, tickers: Sequence[str]) -> pd.DataFrame:
        cols = [t for t in tickers if t in self._closes.columns]
        return self._closes[cols].copy()

    def index_closes(self) -> pd.Series:
        return self._index.copy()

    def fundamentals(self, tickers: Sequence[str]) -> dict[str, Fundamentals]:
        return {t: self._fundamentals[t] for t in tickers if t in self._fundamentals}

    def as_of(self) -> date:
        return self._as_of
