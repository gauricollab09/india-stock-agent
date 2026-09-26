from __future__ import annotations

import csv
import io
import json
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

from stock_advisor.config import APP_DIR

DATA_DIR = APP_DIR / "data"
UNIVERSE_PATH = DATA_DIR / "nifty50.json"


@dataclass(frozen=True)
class Stock:
    ticker: str
    symbol: str
    name: str
    sector: str
    isin: str


@dataclass(frozen=True)
class Universe:
    as_of: str
    source: str
    stocks: tuple[Stock, ...]

    @property
    def tickers(self) -> list[str]:
        return [s.ticker for s in self.stocks]

    @property
    def sectors(self) -> list[str]:
        return sorted({s.sector for s in self.stocks})

    def by_ticker(self) -> dict[str, Stock]:
        return {s.ticker: s for s in self.stocks}

    def excluding(self, sectors: Collection[str]) -> Universe:
        banned = set(sectors)
        return Universe(
            as_of=self.as_of,
            source=self.source,
            stocks=tuple(s for s in self.stocks if s.sector not in banned),
        )


def parse_nifty_csv(text: str) -> list[dict]:
    """Turn NSE's ind_nifty50list.csv into rows of {ticker, symbol, name, sector, isin}."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    rows: list[dict] = []
    for r in reader:
        if not r.get("Symbol") or (r.get("Series") or "").strip() != "EQ":
            continue
        symbol = r["Symbol"].strip()
        rows.append(
            {
                "ticker": f"{symbol}.NS",
                "symbol": symbol,
                "name": r["Company Name"].strip(),
                "sector": r["Industry"].strip(),
                "isin": (r.get("ISIN Code") or "").strip(),
            }
        )
    return rows


def load_universe(path: Path = UNIVERSE_PATH) -> Universe:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    stocks = tuple(Stock(**s) for s in raw["stocks"])
    return Universe(as_of=raw["as_of"], source=raw["source"], stocks=stocks)
