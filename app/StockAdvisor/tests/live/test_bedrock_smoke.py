"""One real run against Claude on Bedrock with live Yahoo data.

Runs only with `RUN_LIVE=1 uv run pytest -m live` and AWS credentials that can invoke
the configured Bedrock model. Costs a few rupees per run.
"""

from __future__ import annotations

import os
from pathlib import Path

import boto3
import pytest

from stock_advisor import service
from stock_advisor.config import Settings
from stock_advisor.llm import make_bedrock_model
from stock_advisor.schemas import Portfolio
from stock_advisor.universe import load_universe

pytestmark = pytest.mark.live

_has_creds = boto3.Session().get_credentials() is not None
if os.environ.get("RUN_LIVE") != "1" or not _has_creds:
    pytest.skip(
        "live Bedrock smoke test: set RUN_LIVE=1 and configure AWS credentials",
        allow_module_level=True,
    )

SMALL_UNIVERSE = Path(__file__).resolve().parent.parent / "universe_small.json"


def test_bedrock_smoke():
    settings = Settings.from_env({**os.environ, "MARKET_DATA_SOURCE": "yahoo"})
    universe = load_universe(SMALL_UNIVERSE)
    model = make_bedrock_model(settings)
    out = service.recommend(
        {"amount_inr": 200000, "risk_tolerance": "moderate", "max_stocks": 4},
        model,
        settings=settings,
        universe=universe,
    )
    assert "error" not in out, out
    portfolio = Portfolio.model_validate(out)
    assert len(portfolio.portfolio) >= 4
    assert portfolio.cash_inr >= 0
    assert "SEBI" in portfolio.disclaimer
    print("meta:", portfolio.meta.model_dump())
