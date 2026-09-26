"""Hard portfolio rules, enforced in code (spec section 2)."""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from stock_advisor.schemas import PickInput, Requirements

if TYPE_CHECKING:
    from stock_advisor.universe import Stock

MAX_WEIGHT = 0.25
MAX_SECTOR_WEIGHT = 0.40
MIN_STOCKS = 4
WEIGHT_SUM_TOLERANCE = 0.005
_EPS = 1e-9


@dataclass(frozen=True)
class Violation:
    code: str
    message: str


def normalized_weights(picks: Sequence[PickInput]) -> dict[str, float]:
    """Ticker -> weight divided by the total (later duplicates overwrite earlier)."""
    raw = {p.ticker: float(p.target_weight) for p in picks}
    total = sum(raw.values())
    if total <= 0:
        return {t: 0.0 for t in raw}
    return {t: w / total for t, w in raw.items()}


def check_rules(
    picks: Sequence[PickInput],
    requirements: Requirements,
    stocks: Mapping[str, Stock],
    prices: Mapping[str, float],
    excluded: Collection[str],
) -> list[Violation]:
    violations: list[Violation] = []
    tickers = [p.ticker for p in picks]

    seen: set[str] = set()
    for t in tickers:
        if t in seen:
            violations.append(Violation("duplicate_ticker", f"{t} appears more than once"))
        seen.add(t)

    for t in dict.fromkeys(tickers):
        if t not in stocks:
            violations.append(Violation("unknown_ticker", f"{t} is not in the universe"))
        elif t not in prices:
            violations.append(Violation("missing_data", f"{t} has no market data; drop it"))

    banned = set(excluded)
    for t in dict.fromkeys(tickers):
        stock = stocks.get(t)
        if stock is not None and stock.sector in banned:
            violations.append(
                Violation("excluded_sector", f"{t} is in excluded sector {stock.sector}")
            )

    distinct = len(seen)
    if distinct < MIN_STOCKS:
        violations.append(
            Violation("too_few_stocks", f"{distinct} stocks; at least {MIN_STOCKS} required")
        )
    if distinct > requirements.max_stocks:
        violations.append(
            Violation(
                "too_many_stocks",
                f"{distinct} stocks; at most {requirements.max_stocks} allowed",
            )
        )

    total = sum(float(p.target_weight) for p in picks)
    if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
        violations.append(
            Violation("weight_sum", f"target weights sum to {total:.4f}; they must sum to 1.0")
        )

    norm = normalized_weights(picks)
    for t, w in norm.items():
        if w > MAX_WEIGHT + _EPS:
            violations.append(
                Violation(
                    "max_weight",
                    f"{t} weight {w:.4f} exceeds the {MAX_WEIGHT:.0%} per-stock maximum",
                )
            )

    sector_totals: dict[str, float] = {}
    for t, w in norm.items():
        stock = stocks.get(t)
        if stock is None:
            continue
        sector_totals[stock.sector] = sector_totals.get(stock.sector, 0.0) + w
    for sector, w in sector_totals.items():
        if w > MAX_SECTOR_WEIGHT + _EPS:
            violations.append(
                Violation(
                    "max_sector_weight",
                    f"sector {sector} weight {w:.4f} exceeds the "
                    f"{MAX_SECTOR_WEIGHT:.0%} per-sector maximum",
                )
            )

    for t, w in norm.items():
        price = prices.get(t)
        if price is None or price <= 0:
            continue
        shares = math.floor(w * requirements.amount_inr / price)
        if shares < 1:
            violations.append(
                Violation(
                    "unaffordable",
                    f"{t}: weight {w:.4f} of INR {requirements.amount_inr} buys 0 shares "
                    f"at INR {price:.2f}; raise its weight or drop it",
                )
            )

    return violations
