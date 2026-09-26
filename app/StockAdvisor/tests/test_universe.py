from pathlib import Path

from stock_advisor.universe import Universe, load_universe, parse_nifty_csv

SMALL = Path(__file__).parent / "universe_small.json"

CSV = """Company Name,Industry,Symbol,Series,ISIN Code
Infosys Ltd.,Information Technology,INFY,EQ,INE009A01021
Mahindra & Mahindra Ltd.,Automobile and Auto Components,M&M,EQ,INE101A01026
Some Odd Ltd.,Services,ODD,BE,INE000000000
"""


def test_parse_nifty_csv_keeps_eq_series_and_maps_tickers():
    rows = parse_nifty_csv(CSV)
    assert [r["ticker"] for r in rows] == ["INFY.NS", "M&M.NS"]
    assert rows[1] == {
        "ticker": "M&M.NS",
        "symbol": "M&M",
        "name": "Mahindra & Mahindra Ltd.",
        "sector": "Automobile and Auto Components",
        "isin": "INE101A01026",
    }


def test_parse_nifty_csv_handles_bom_and_blank_lines():
    rows = parse_nifty_csv("﻿" + CSV + "\n\n")
    assert len(rows) == 2


def test_load_universe():
    u = load_universe(SMALL)
    assert isinstance(u, Universe)
    assert u.as_of == "2026-09-25"
    assert len(u.stocks) == 6
    assert u.tickers == [
        "HDFCBANK.NS",
        "ICICIBANK.NS",
        "INFY.NS",
        "TCS.NS",
        "RELIANCE.NS",
        "SUNPHARMA.NS",
    ]
    assert u.sectors == [
        "Financial Services",
        "Healthcare",
        "Information Technology",
        "Oil Gas & Consumable Fuels",
    ]
    assert u.by_ticker()["TCS.NS"].name == "Tata Consultancy Services Ltd."


def test_excluding_removes_sectors_and_keeps_order():
    u = load_universe(SMALL).excluding({"Financial Services"})
    assert u.tickers == ["INFY.NS", "TCS.NS", "RELIANCE.NS", "SUNPHARMA.NS"]
    assert u.as_of == "2026-09-25"


def test_real_universe_file_is_present_and_sane():
    u = load_universe()
    assert 45 <= len(u.stocks) <= 55
    assert all(s.ticker.endswith(".NS") for s in u.stocks)
    assert len({s.ticker for s in u.stocks}) == len(u.stocks)
