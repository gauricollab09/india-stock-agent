"""Whole-share allocation: turns target weights into share counts, rupee amounts and cash."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Allocation:
    ticker: str
    target_weight: float
    shares: int
    amount_inr: int
    weight: float


def allocate(
    weights: Mapping[str, float], prices: Mapping[str, float], amount_inr: int
) -> tuple[list[Allocation], int]:
    """Floor to whole shares; leftover money is cash. Order follows `weights`."""
    rows: list[tuple[str, float, int, int]] = []
    for ticker, w in weights.items():
        price = float(prices[ticker])
        shares = math.floor(float(w) * amount_inr / price) if price > 0 else 0
        amount = int(round(shares * price))
        rows.append((ticker, float(w), shares, amount))

    invested = sum(a for _, _, _, a in rows)
    allocations = [
        Allocation(
            ticker=t,
            target_weight=w,
            shares=s,
            amount_inr=a,
            weight=round(a / invested, 6) if invested > 0 else 0.0,
        )
        for t, w, s, a in rows
    ]
    cash = amount_inr - invested
    return allocations, cash
