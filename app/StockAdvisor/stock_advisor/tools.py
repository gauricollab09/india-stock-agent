from __future__ import annotations

from collections.abc import Collection

from langchain.tools import BaseTool, tool

from stock_advisor.market_context import MarketContext, snapshot
from stock_advisor.portfolio import evaluate, evaluation_to_tool_result
from stock_advisor.schemas import PickInput, Requirements


def make_tools(ctx: MarketContext, requirements: Requirements, excluded: Collection[str]) -> list[BaseTool]:
    banned = set(excluded)
    allowed = [s for s in ctx.universe.stocks if s.sector not in banned and s.ticker not in ctx.missing]
    allowed_tickers = {s.ticker for s in allowed}

    @tool
    def get_universe() -> dict:
        """Return the investable universe (Nifty 50 minus excluded sectors and stocks without data): \
ticker, name and sector for each stock, plus the list of sector names."""
        return {
            "as_of": ctx.as_of,
            "stocks": [{"ticker": s.ticker, "name": s.name, "sector": s.sector} for s in allowed],
            "sectors": sorted({s.sector for s in allowed}),
            "excluded_sectors": sorted(banned),
        }

    @tool
    def get_stock_snapshots(tickers: list[str]) -> dict:
        """Return, per ticker, last price (INR), 1-year return, annualised volatility, beta versus \
NIFTY 50, 1-year max drawdown, trailing P/E, market cap, dividend yield in percent, ROE as a \
fraction and debt/equity in percent. Pass an empty list for every stock in the universe. \
Fields are null when unavailable; tickers not in the universe are listed under missing."""
        wanted = list(tickers) if tickers else sorted(allowed_tickers)
        snaps, missing = [], []
        for t in wanted:
            if t in allowed_tickers and t in ctx.closes.columns:
                snaps.append(snapshot(ctx, t))
            else:
                missing.append(t)
        return {"as_of": ctx.as_of, "snapshots": snaps, "missing": missing}

    @tool
    def evaluate_portfolio(picks: list[PickInput]) -> dict:
        """Check a proposed portfolio against the hard rules and compute its risk statistics. \
picks = [{"ticker": "INFY.NS", "target_weight": 0.15}, ...] with weights summing to 1. Returns \
ok=true with holdings (whole shares, rupee amounts), cash_inr and risk_summary, or ok=false with the \
violations you must fix before finishing."""
        return evaluation_to_tool_result(evaluate(picks, requirements, ctx, banned))

    return [get_universe, get_stock_snapshots, evaluate_portfolio]
