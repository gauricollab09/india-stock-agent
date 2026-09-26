from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import asdict, dataclass

from stock_advisor import analytics
from stock_advisor.allocation import Allocation, allocate
from stock_advisor.market_context import MarketContext
from stock_advisor.rules import Violation, check_rules, normalized_weights
from stock_advisor.schemas import Holding, PickInput, Requirements, RiskSummary

DISCLAIMER = (
    "This output is generated automatically by an AI model (Claude, via Amazon Bedrock) for "
    "educational and informational purposes only. The operator of this tool is not registered "
    "with SEBI as an Investment Adviser or Research Analyst. Nothing here is investment advice, "
    "a research report, a model portfolio, a trading call, or a recommendation to buy, sell or "
    "hold any security. Price and fundamental data are sourced from third parties (Yahoo Finance "
    "via yfinance, NSE) and may be delayed, incomplete or incorrect. Investments in securities "
    "markets are subject to market risks; past performance is not indicative of future returns. "
    "Consult a SEBI-registered Investment Adviser or Research Analyst before making any "
    "investment decision, and verify registration at https://www.sebi.gov.in."
)


@dataclass
class Evaluation:
    ok: bool
    violations: list[Violation]
    allocations: list[Allocation]
    cash_inr: int
    risk_summary: RiskSummary | None


def evaluate(
    picks: Sequence[PickInput],
    requirements: Requirements,
    ctx: MarketContext,
    excluded: Collection[str],
) -> Evaluation:
    prices = ctx.last_prices()
    violations = check_rules(picks, requirements, ctx.universe.by_ticker(), prices, excluded)
    if violations:
        return Evaluation(False, violations, [], requirements.amount_inr, None)
    weights = normalized_weights(picks)
    allocations, cash = allocate(weights, prices, requirements.amount_inr)
    actual = {a.ticker: a.weight for a in allocations if a.weight > 0}
    stocks = ctx.universe.by_ticker()
    sectors = {t: stocks[t].sector for t in actual}
    funds = ctx.fundamentals_for(list(actual))
    yields = [(w, funds[t].dividend_yield_pct) for t, w in actual.items()]
    known = [(w, y) for w, y in yields if y is not None]
    dy = sum(w * y for w, y in known) / sum(w for w, _ in known) if known else None
    closes = ctx.closes[list(actual)]
    risk = RiskSummary(
        annual_volatility=analytics.to_float(analytics.portfolio_volatility(closes, actual)),
        portfolio_beta=analytics.to_float(
            analytics.portfolio_beta(closes, actual, ctx.index_closes)
        ),
        max_drawdown_1y=analytics.to_float(analytics.portfolio_max_drawdown(closes, actual)),
        dividend_yield_pct=analytics.to_float(dy),
        avg_pairwise_correlation=analytics.to_float(analytics.avg_pairwise_correlation(closes)),
        sector_weights=analytics.sector_weights(actual, sectors),
    )
    return Evaluation(True, [], allocations, cash, risk)


def evaluation_to_tool_result(ev: Evaluation) -> dict:
    if not ev.ok:
        return {"ok": False, "violations": [asdict(v) for v in ev.violations]}
    return {
        "ok": True,
        "violations": [],
        "holdings": [asdict(a) for a in ev.allocations],
        "cash_inr": ev.cash_inr,
        "risk_summary": ev.risk_summary.model_dump() if ev.risk_summary else None,
    }


def holdings_from(ev: Evaluation, ctx: MarketContext, rationales: dict[str, str]) -> list[Holding]:
    stocks = ctx.universe.by_ticker()
    prices = ctx.last_prices()
    out = []
    for a in ev.allocations:
        s = stocks[a.ticker]
        out.append(
            Holding(
                ticker=a.ticker,
                name=s.name,
                sector=s.sector,
                target_weight=round(a.target_weight, 4),
                weight=round(a.weight, 4),
                amount_inr=a.amount_inr,
                approx_shares=a.shares,
                last_price=round(prices[a.ticker], 2),
                rationale=rationales.get(a.ticker, ""),
            )
        )
    return out
