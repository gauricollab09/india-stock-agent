"""Download the current Nifty 50 constituent list and write data/nifty50.json.

Usage: uv run python scripts/refresh_universe.py [output_path]
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

from stock_advisor.universe import UNIVERSE_PATH, parse_nifty_csv

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0 Safari/537.36"
)
SOURCES: list[tuple[str, dict[str, str]]] = [
    ("https://archives.nseindia.com/content/indices/ind_nifty50list.csv", {}),
    (
        "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv",
        {"User-Agent": BROWSER_UA},
    ),
    (
        "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv",
        {"User-Agent": BROWSER_UA, "Referer": "https://www.niftyindices.com/"},
    ),
]


def fetch_csv() -> tuple[str, str]:
    last_error: Exception | None = None
    for url, headers in SOURCES:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8-sig"), url
        except Exception as exc:  # noqa: BLE001 - try the next source
            last_error = exc
            print(f"{url}: {exc}", file=sys.stderr)
    raise SystemExit(f"could not download the Nifty 50 list: {last_error}")


def main(out_path: Path = UNIVERSE_PATH) -> None:
    text, url = fetch_csv()
    stocks = sorted(parse_nifty_csv(text), key=lambda s: s["ticker"])
    if len(stocks) < 45:
        raise SystemExit(f"only {len(stocks)} EQ rows parsed; refusing to overwrite {out_path}")
    payload = {"as_of": dt.date.today().isoformat(), "source": url, "stocks": stocks}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(stocks)} stocks to {out_path} (source {url})")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else UNIVERSE_PATH)
