# India Stock Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-request LangChain agent that turns an investor's requirements into a validated Nifty 50 portfolio, runs offline against a fake model, and deploys unchanged to Amazon Bedrock AgentCore Runtime.

**Architecture:** An AgentCore entrypoint (`app/StockAdvisor/main.py`) hands the JSON payload to `service.recommend`, which validates it, builds a per-request `MarketContext` from a pluggable data source (yfinance or a frozen fixture), runs a `create_agent` loop where Claude calls three tools and returns a structured `Decision`, then recomputes every number in code (`rules`, `allocation`, `analytics`) before returning a `Portfolio`. Claude chooses and weights stocks; code does all arithmetic.

**Tech Stack:** Python 3.12 (uv), LangChain 1.4 (`create_agent`, `ToolStrategy`), `langchain-aws` `ChatBedrockConverse`, `bedrock-agentcore` SDK, AgentCore CLI `@aws/agentcore` 0.30.0 (Node, run via `npx`), yfinance 1.7, pandas 3, numpy 2, pydantic 2, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-09-26-india-stock-agent-design.md` (read it first; the research sheets in `docs/superpowers/research/` hold the verified API details behind it).

## Global Constraints

- Python `>=3.12`; `.python-version` is `3.12`; `agentcore/agentcore.json` `runtimeVersion` is `PYTHON_3_12`.
- Only Claude on Amazon Bedrock: `ChatBedrockConverse`, default model `global.anthropic.claude-opus-5`, default region `ap-south-1`. Never set `temperature` (Claude 5 on Bedrock rejects sampling params).
- `create_agent` from `langchain.agents` with `response_format=ToolStrategy(Decision)`; never `create_react_agent`, never `ChatBedrock`.
- Hard rules (code-enforced): weights sum to 1 (±0.005 then renormalise), max 25% per stock, max 40% per sector, 4 ≤ stocks ≤ `max_stocks`, no excluded sector, tickers in universe with data, whole shares, at least one share per pick.
- `uv run pytest` must pass offline with no AWS credentials. Tests never touch the network.
- Every dependency must ship a pure-Python or `aarch64` manylinux wheel (CodeZip packaging uses `--only-binary :all:`); do not add dependencies beyond the spec's list without checking PyPI.
- The disclaimer text in the spec §9 is used verbatim.
- All work happens in `/Users/gauritulsulkar/AI_proj/india-stock-agent` on branch `main`; commit after every task and `git push` after every commit (the user asked for continuous pushing). Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Run Python commands from `app/StockAdvisor/` with `uv run ...`.

## Review Focus

1. A request whose `prompt` is a JSON string that itself contains a `prompt` key, or is a JSON list, must produce `invalid_request`, never an exception (Task 10 tests `test_prompt_must_be_object`).
2. A `Decision` that names the same ticker twice must be a `duplicate_ticker` violation, not double-counted weight (Task 6 tests `test_duplicate_ticker`).
3. An `amount_inr` too small to buy one share of every pick must surface as `unaffordable` violations, and if the model cannot fix it, `no_valid_portfolio` (Task 6 `test_unaffordable`, Task 10 `test_no_valid_portfolio`).
4. A ticker whose closes exist but whose fundamentals are all `None` must still yield a snapshot with nulls, not a crash (Task 8 `test_snapshot_with_missing_fundamentals`).
5. `yf.download` returning a frame with a whole-NaN column (delisted ticker) must mark that ticker missing rather than propagate NaN into risk numbers (Task 7 `test_yahoo_drops_all_nan_columns`).

---

### Task 1: Project scaffold, dependencies, settings

**Files:**
- Create (via CLI, then edit): `agentcore/`, `app/StockAdvisor/main.py`, `app/StockAdvisor/pyproject.toml`, `app/StockAdvisor/.python-version`, `AGENTS.md`, `README.md`, `.gitignore`
- Create: `app/StockAdvisor/stock_advisor/__init__.py`, `app/StockAdvisor/stock_advisor/config.py`
- Test: `app/StockAdvisor/tests/test_config.py`

**Interfaces:**
- Produces: `Settings` dataclass with fields `model_id`, `region`, `market_data_source`, `fixture_dir: Path`, `max_agent_steps`, `max_tokens`, `log_level`; `Settings.from_env(env: dict | None = None) -> Settings`; constant `APP_DIR: Path` (the `app/StockAdvisor` directory).

- [ ] **Step 1: Generate the AgentCore scaffold in a scratch directory and move it in**

```bash
SCRATCH="$(mktemp -d)" && cd "$SCRATCH" && \
npx -y @aws/agentcore@0.30.0 create --project-name IndiaStockAgent --name StockAdvisor \
  --language Python --framework LangChain_LangGraph --model-provider Bedrock \
  --memory none --build CodeZip --protocol HTTP
cd /Users/gauritulsulkar/AI_proj/india-stock-agent
cp -R "$SCRATCH/IndiaStockAgent/agentcore" "$SCRATCH/IndiaStockAgent/app" "$SCRATCH/IndiaStockAgent/AGENTS.md" .
cp "$SCRATCH/IndiaStockAgent/README.md" README.md
rm -rf app/StockAdvisor/mcp_client app/StockAdvisor/model app/StockAdvisor/.venv app/StockAdvisor/uv.lock
ls agentcore app/StockAdvisor
```

Expected: `agentcore/agentcore.json`, `agentcore/cdk/`, `app/StockAdvisor/main.py`, `app/StockAdvisor/pyproject.toml` exist. The CLI's `main.py` will be replaced in Task 11; for now it is only a placeholder.

- [ ] **Step 2: Pin the runtime to Python 3.12**

Edit `agentcore/agentcore.json`: change `"runtimeVersion": "PYTHON_3_14"` to `"runtimeVersion": "PYTHON_3_12"`. Then:

```bash
cd app/StockAdvisor && echo "3.12" > .python-version
```

- [ ] **Step 3: Replace `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stock-advisor"
version = "0.1.0"
description = "Nifty 50 portfolio recommendation agent on Amazon Bedrock AgentCore"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "bedrock-agentcore>=1.23,<2",
    "langchain>=1.4,<2",
    "langgraph>=1.2,<2",
    "langchain-aws>=1.7,<2",
    "boto3>=1.43",
    "botocore[crt]>=1.35",
    "pydantic>=2.10,<3",
    "yfinance>=1.7,<2",
    "pandas>=2.2,<4",
    "numpy>=2,<3",
    "aws-opentelemetry-distro~=0.18.0",
    "opentelemetry-instrumentation-langchain>=0.59",
]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "httpx>=0.27"]

[tool.hatch.build.targets.wheel]
packages = ["stock_advisor"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["live: needs AWS credentials and network access"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 4: Root `.gitignore` and placeholder package**

Create `/Users/gauritulsulkar/AI_proj/india-stock-agent/.gitignore`:

```
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.DS_Store
.env
app/StockAdvisor/evals/reports/*.json
app/StockAdvisor/evals/reports/*.md
agentcore/cdk/node_modules/
agentcore/cdk/cdk.out/
```

Create empty `app/StockAdvisor/stock_advisor/__init__.py` and empty `app/StockAdvisor/tests/__init__.py`.

- [ ] **Step 5: Write the failing settings test**

`app/StockAdvisor/tests/test_config.py`:

```python
from pathlib import Path

from stock_advisor.config import APP_DIR, Settings


def test_defaults():
    s = Settings.from_env({})
    assert s.model_id == "global.anthropic.claude-opus-5"
    assert s.region == "ap-south-1"
    assert s.market_data_source == "yahoo"
    assert s.fixture_dir == APP_DIR / "data" / "fixtures"
    assert s.max_agent_steps == 40
    assert s.max_tokens == 8000
    assert s.log_level == "INFO"


def test_env_overrides():
    s = Settings.from_env(
        {
            "BEDROCK_MODEL_ID": "global.anthropic.claude-sonnet-5",
            "AWS_REGION": "ap-southeast-1",
            "MARKET_DATA_SOURCE": "fixture",
            "FIXTURE_DIR": "/tmp/fx",
            "MAX_AGENT_STEPS": "12",
            "MAX_TOKENS": "2000",
            "LOG_LEVEL": "DEBUG",
        }
    )
    assert s.model_id == "global.anthropic.claude-sonnet-5"
    assert s.region == "ap-southeast-1"
    assert s.market_data_source == "fixture"
    assert s.fixture_dir == Path("/tmp/fx")
    assert s.max_agent_steps == 12
    assert s.max_tokens == 2000
    assert s.log_level == "DEBUG"


def test_app_dir_is_the_agent_folder():
    assert (APP_DIR / "pyproject.toml").exists()
```

- [ ] **Step 6: Install and run the test to verify it fails**

```bash
cd /Users/gauritulsulkar/AI_proj/india-stock-agent/app/StockAdvisor && uv sync --python 3.12 && uv run pytest tests/test_config.py -v
```

Expected: `uv sync` succeeds (resolves langchain 1.4.x, langchain-aws 1.7.x, bedrock-agentcore 1.23.x, yfinance 1.7.x). Pytest FAILS with `ModuleNotFoundError: No module named 'stock_advisor.config'`.

- [ ] **Step 7: Implement `stock_advisor/config.py`**

```python
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    model_id: str = "global.anthropic.claude-opus-5"
    region: str = "ap-south-1"
    market_data_source: str = "yahoo"
    fixture_dir: Path = APP_DIR / "data" / "fixtures"
    max_agent_steps: int = 40
    max_tokens: int = 8000
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e: Mapping[str, str] = os.environ if env is None else env
        return cls(
            model_id=e.get("BEDROCK_MODEL_ID", cls.model_id),
            region=e.get("AWS_REGION", cls.region),
            market_data_source=e.get("MARKET_DATA_SOURCE", cls.market_data_source),
            fixture_dir=Path(e.get("FIXTURE_DIR", str(cls.fixture_dir))),
            max_agent_steps=int(e.get("MAX_AGENT_STEPS", cls.max_agent_steps)),
            max_tokens=int(e.get("MAX_TOKENS", cls.max_tokens)),
            log_level=e.get("LOG_LEVEL", cls.log_level),
        )
```

- [ ] **Step 8: Run tests, ruff, CLI validation**

```bash
uv run pytest tests/test_config.py -v && uv run ruff check . && uv run python -c "import langchain, langchain_aws, bedrock_agentcore, yfinance, pandas; print('imports ok')"
cd /Users/gauritulsulkar/AI_proj/india-stock-agent && npx -y @aws/agentcore@0.30.0 validate
```

Expected: 3 tests PASS; ruff clean; imports ok; `agentcore validate` reports the config as valid (the project directory name differs from `IndiaStockAgent`; the CLI reads `agentcore/agentcore.json` from the current directory, so this must still pass — if it does not, report it rather than working around it).

- [ ] **Step 9: Commit and push**

```bash
cd /Users/gauritulsulkar/AI_proj/india-stock-agent && git add -A && git commit -m "Scaffold AgentCore project with settings module

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git push
```

---

### Task 2: Universe loader and refresh script

**Files:**
- Create: `app/StockAdvisor/stock_advisor/universe.py`, `app/StockAdvisor/scripts/__init__.py` (empty), `app/StockAdvisor/scripts/refresh_universe.py`, `app/StockAdvisor/data/nifty50.json` (generated)
- Test: `app/StockAdvisor/tests/test_universe.py`, `app/StockAdvisor/tests/universe_small.json`

**Interfaces:**
- Produces: `Stock(ticker, symbol, name, sector, isin)` frozen dataclass; `Universe(as_of: str, source: str, stocks: tuple[Stock, ...])` with `.sectors -> list[str]`, `.by_ticker() -> dict[str, Stock]`, `.tickers -> list[str]`, `.excluding(sectors: Collection[str]) -> Universe`; `load_universe(path: Path = UNIVERSE_PATH) -> Universe`; `parse_nifty_csv(text: str) -> list[dict]`; constants `DATA_DIR`, `UNIVERSE_PATH`.

- [ ] **Step 1: Write the small test universe**

`app/StockAdvisor/tests/universe_small.json`:

```json
{
  "as_of": "2026-09-25",
  "source": "tests/universe_small.json",
  "stocks": [
    {"ticker": "HDFCBANK.NS", "symbol": "HDFCBANK", "name": "HDFC Bank Ltd.", "sector": "Financial Services", "isin": "INE040A01034"},
    {"ticker": "ICICIBANK.NS", "symbol": "ICICIBANK", "name": "ICICI Bank Ltd.", "sector": "Financial Services", "isin": "INE090A01021"},
    {"ticker": "INFY.NS", "symbol": "INFY", "name": "Infosys Ltd.", "sector": "Information Technology", "isin": "INE009A01021"},
    {"ticker": "TCS.NS", "symbol": "TCS", "name": "Tata Consultancy Services Ltd.", "sector": "Information Technology", "isin": "INE467B01029"},
    {"ticker": "RELIANCE.NS", "symbol": "RELIANCE", "name": "Reliance Industries Ltd.", "sector": "Oil Gas & Consumable Fuels", "isin": "INE002A01018"},
    {"ticker": "SUNPHARMA.NS", "symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Industries Ltd.", "sector": "Healthcare", "isin": "INE044A01036"}
  ]
}
```

- [ ] **Step 2: Write the failing tests**

`app/StockAdvisor/tests/test_universe.py`:

```python
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
        "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS", "RELIANCE.NS", "SUNPHARMA.NS",
    ]
    assert u.sectors == [
        "Financial Services", "Healthcare", "Information Technology", "Oil Gas & Consumable Fuels",
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_universe.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stock_advisor.universe'`.

- [ ] **Step 4: Implement `stock_advisor/universe.py`**

```python
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
```

- [ ] **Step 5: Implement `scripts/refresh_universe.py`**

```python
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
```

- [ ] **Step 6: Generate the real universe file (this needs the network, run from this Mac)**

Run: `uv run python scripts/refresh_universe.py`
Expected: `wrote 50 stocks to .../data/nifty50.json`. Open the file and check a few rows: `RELIANCE.NS` has sector `Oil Gas & Consumable Fuels`, `M&M.NS` and `BAJAJ-AUTO.NS` are present. If the download fails from both sources, stop and report; do not hand-type the list.

- [ ] **Step 7: Run tests and ruff**

Run: `uv run pytest tests/test_universe.py -v && uv run ruff check .`
Expected: 5 PASS, ruff clean.

- [ ] **Step 8: Commit and push**

```bash
cd /Users/gauritulsulkar/AI_proj/india-stock-agent && git add -A && git commit -m "Add Nifty 50 universe loader and refresh script

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git push
```

---
