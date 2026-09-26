from __future__ import annotations

from pathlib import Path

import pytest

from stock_advisor.config import Settings
from stock_advisor.market_data.fixture import FixtureMarketData
from stock_advisor.universe import load_universe
from tests.synthetic import SMALL_TICKERS, make_synthetic_fixture

SMALL_UNIVERSE = Path(__file__).parent / "universe_small.json"


@pytest.fixture(scope="session")
def fixture_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("fixture")
    make_synthetic_fixture(d, SMALL_TICKERS)
    return d


@pytest.fixture
def source(fixture_dir):
    return FixtureMarketData(fixture_dir)


@pytest.fixture
def universe():
    return load_universe(SMALL_UNIVERSE)


@pytest.fixture
def settings(fixture_dir):
    return Settings(market_data_source="fixture", fixture_dir=fixture_dir, model_id="fake-model")
