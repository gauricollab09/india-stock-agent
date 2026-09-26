"""Pull a real snapshot of the whole universe from Yahoo and freeze it to data/fixtures.

Usage: uv run python scripts/build_fixture.py [output_dir]
Needs network access; run from a residential connection.
"""

from __future__ import annotations

import sys
from pathlib import Path

from stock_advisor.market_data.fixture import write_fixture
from stock_advisor.market_data.yahoo import YahooMarketData
from stock_advisor.universe import DATA_DIR, load_universe


def main(out_dir: Path) -> None:
    universe = load_universe()
    source = YahooMarketData()
    closes = source.closes(universe.tickers)
    index_closes = source.index_closes()
    fundamentals = source.fundamentals(list(closes.columns))
    write_fixture(out_dir, closes, index_closes, fundamentals, source.as_of())
    missing = [t for t in universe.tickers if t not in closes.columns]
    print(
        f"wrote {len(closes.columns)} tickers, {len(closes)} rows, "
        f"{len(fundamentals)} fundamentals to {out_dir} (as of {source.as_of()})"
    )
    if missing:
        print(f"missing closes: {missing}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR / "fixtures")
