# India Stock Agent — Design Spec

Date: 2026-09-26
Status: draft for review
Owner: Gauri Tulsulkar

## 1. Goal

A simple, deployable agent that recommends a combination of Indian equities
(NSE, Nifty 50 universe) based on a user's stated requirements. Built with
LangChain 1.x and Claude on Amazon Bedrock, packaged for Amazon Bedrock
AgentCore Runtime, and fully testable offline before an AWS account exists.

Success looks like:

- One HTTP request with requirements returns a validated portfolio JSON in
  under about two minutes.
- Every hard constraint is enforced by code, never by the model.
- `uv run pytest` passes with no network and no AWS credentials.
- `agentcore deploy` publishes the agent to `ap-south-1` with no code changes.
- A deterministic eval suite reports pass rates that can be compared across
  prompt or model changes.

### Decisions already made

| Topic | Decision |
|---|---|
| Market | India, NSE tickers (`.NS`), universe = Nifty 50 |
| Interaction | Single request/response, not conversational |
| LLM | Claude on Amazon Bedrock only, via `langchain-aws` `ChatBedrockConverse` |
| Default model | `global.anthropic.claude-opus-5` (env-switchable to `global.anthropic.claude-sonnet-5`) |
| Region | `ap-south-1` (Mumbai) by default, env-switchable |
| Deploy tooling | AgentCore CLI `@aws/agentcore` 0.30.0 (Node), CodeZip build, no Docker |
| Python | 3.12, managed by `uv` |
| Data | yfinance 1.7.x for prices and fundamentals; NSE archives CSV for constituents |
| Evals | Deterministic (Layer 1) only in v1 |
| AWS status | No account yet. Everything runs offline against a fake model; real runs wait for the account |

### Non-goals for v1

Multi-turn conversation, markets other than NSE, intraday data, backtesting,
model-judged evals, AgentCore Memory/Gateway/Identity, a UI, and any claim of
being a SEBI-compliant advisory product. The tool is for personal,
educational use.

## 2. Request and response contract

### Request

The AgentCore `/invocations` body is JSON. Two shapes are accepted:

1. The requirements object itself.
2. `{"prompt": "<requirements object as a JSON string>"}` — this is what
   `agentcore invoke "<text>"`, `agentcore dev "<text>"` and
   `agentcore invoke --prompt-file file.json` send (the CLI wraps the text as
   `prompt`).

If `prompt` is present it must be a string (AWS's guidance: a non-string
`prompt` can smuggle tool-use blocks past the model); anything else, or a
string that is not valid JSON, is an `invalid_request` error that shows the
expected shape.

```json
{
  "amount_inr": 500000,
  "horizon_years": 5,
  "risk_tolerance": "moderate",
  "goals": "long-term growth, some dividend income",
  "preferred_sectors": ["Information Technology", "Financial Services"],
  "excluded_sectors": ["Tobacco"],
  "max_stocks": 8,
  "notes": "avoid heavily indebted companies"
}
```

| Field | Type | Required | Default | Validation |
|---|---|---|---|---|
| `amount_inr` | int | yes | — | ≥ 10,000 |
| `risk_tolerance` | enum | yes | — | `low` / `moderate` / `high` |
| `horizon_years` | int | no | 5 | 1–30 |
| `goals` | str | no | `""` | ≤ 500 chars |
| `preferred_sectors` | list[str] | no | `[]` | each resolves to a known sector |
| `excluded_sectors` | list[str] | no | `[]` | each resolves to a known sector |
| `max_stocks` | int | no | 8 | 4–15 |
| `notes` | str | no | `""` | ≤ 500 chars |

Sector names resolve against the vocabulary in the universe file
(the NSE "Industry" column), case-insensitively, with a small alias table
(`IT` → Information Technology, `Banking`/`Banks` → Financial Services,
`Pharma` → Healthcare, `FMCG` → Fast Moving Consumer Goods, `Auto` →
Automobile and Auto Components, `Energy`/`Oil` → Oil Gas & Consumable Fuels,
`Telecom` → Telecommunication). An unknown sector is an `invalid_request`
error whose message lists the valid names.

### Response (success)

```json
{
  "portfolio": [
    {
      "ticker": "INFY.NS",
      "name": "Infosys Ltd.",
      "sector": "Information Technology",
      "target_weight": 0.15,
      "weight": 0.1496,
      "amount_inr": 74800,
      "approx_shares": 48,
      "last_price": 1558.33,
      "rationale": "..."
    }
  ],
  "cash_inr": 1850,
  "risk_summary": {
    "annual_volatility": 0.16,
    "portfolio_beta": 0.92,
    "max_drawdown_1y": -0.14,
    "dividend_yield_pct": 1.4,
    "avg_pairwise_correlation": 0.31,
    "sector_weights": {"Information Technology": 0.30, "Financial Services": 0.25}
  },
  "strategy_summary": "...",
  "assumptions": ["Prices as of 2026-09-26 close", "..."],
  "disclaimer": "...",
  "meta": {
    "model": "global.anthropic.claude-opus-5",
    "data_source": "yahoo",
    "as_of": "2026-09-26",
    "tool_calls": 4,
    "evaluate_attempts": 2,
    "evaluate_failures": 1,
    "input_tokens": 41230,
    "output_tokens": 3120,
    "latency_ms": 58000
  }
}
```

`target_weight` is what Claude decided. `weight` is the actual weight after
whole-share rounding (`amount_inr / amount invested`). `meta` is new relative
to the approved section 1; it costs nothing and the evals depend on it.

### Response (error)

```json
{"error": {"type": "invalid_request", "message": "...", "details": ["amount_inr: must be >= 10000"]}}
```

Error types: `invalid_request`, `market_data_unavailable`,
`no_valid_portfolio`, `model_unavailable` (Bedrock access or throttling that
retries could not fix), `internal`.

### Hard rules (enforced in code)

| Rule | Value |
|---|---|
| Weights sum to 1 | tolerance ±0.005, then renormalised (the only silent repair) |
| Max weight per stock | 25% |
| Max weight per sector | 40% |
| Number of stocks | ≥ 4 and ≤ `max_stocks` |
| Excluded sectors | never present |
| Tickers | must be in the universe and must have complete snapshot data |
| Shares | whole numbers, `floor(weight × amount / price)`; leftover is `cash_inr` |
| Every pick affordable | at least one whole share per pick |

The rules live in one place (`rules.py`) and are used both by the
`evaluate_portfolio` tool during the agent loop and by the final assembly
step. `evaluate_portfolio` reports violations to the model so it can revise;
the final check turns a persisting violation into a `no_valid_portfolio`
error rather than a silently altered answer.

## 3. Architecture

### Project layout

The project directory is generated by the AgentCore CLI and then extended.
The CLI's own files (`agentcore/`, `app/StockAdvisor/main.py`,
`pyproject.toml`, `README.md`, `AGENTS.md`) are kept; its sample MCP client,
its `model/load.py` and its `create_react_agent` template code are replaced.

```
india-stock-agent/
├── README.md                     run, test, deploy guide (rewritten)
├── AGENTS.md                     CLI-generated notes for coding agents
├── docs/superpowers/specs/       this spec
├── agentcore/                    CLI config + CDK project (generated)
│   ├── agentcore.json            runtime: CodeZip, entrypoint main.py, PYTHON_3_12
│   ├── aws-targets.json
│   └── cdk/
└── app/StockAdvisor/             the deployable unit (codeLocation)
    ├── main.py                   AgentCore entrypoint
    ├── pyproject.toml            uv project, Python 3.12, pinned deps
    ├── .python-version           3.12
    ├── stock_advisor/
    │   ├── config.py             Settings from env
    │   ├── schemas.py            Requirements, Decision, Portfolio, errors
    │   ├── sectors.py            sector vocabulary + alias resolution
    │   ├── universe.py           load Nifty 50 file, apply exclusions
    │   ├── market_data/
    │   │   ├── base.py           MarketDataSource protocol
    │   │   ├── yahoo.py          yfinance implementation with cache + retries
    │   │   └── fixture.py        reads a frozen snapshot from disk
    │   ├── analytics.py          pure pandas/numpy statistics
    │   ├── rules.py              hard-rule checks → list of violations
    │   ├── allocation.py         whole-share rounding, cash, actual weights
    │   ├── tools.py              LangChain tools (factory over a data source)
    │   ├── prompts.py            system prompt + requirements rendering
    │   ├── llm.py                ChatBedrockConverse factory
    │   ├── agent.py              build_agent(model, tools) → runnable
    │   └── service.py            recommend(payload, model) → dict
    ├── data/
    │   ├── nifty50.json          universe (ticker, symbol, name, sector, isin)
    │   └── fixtures/             full 50-ticker frozen snapshot for evals
    ├── examples/request.json
    ├── scripts/
    │   ├── refresh_universe.py   NSE archives CSV → data/nifty50.json
    │   ├── build_fixture.py      live yfinance pull → data/fixtures/
    │   └── invoke.py             boto3 client for the deployed agent
    ├── evals/
    │   ├── cases.json            ~25 requirement profiles with expectations
    │   ├── metrics.py            pure metric functions
    │   ├── run.py                runner → evals/reports/<run-id>.{json,md}
    │   └── reports/
    └── tests/
        ├── conftest.py           fixture data source, fake model, env
        ├── fixtures/             tiny 6-ticker snapshot for unit tests
        ├── test_analytics.py, test_rules.py, test_allocation.py,
        ├── test_schemas.py, test_sectors.py, test_universe.py,
        ├── test_market_data_fixture.py, test_market_data_yahoo.py,
        ├── test_tools.py, test_agent.py, test_service.py, test_main.py,
        ├── test_evals_metrics.py
        └── live/test_bedrock_smoke.py   skipped without AWS credentials
```

`main.py` sits at the root of the code location, so `stock_advisor` is
importable without packaging tricks, both under `python main.py` and inside
the CodeZip deployment.

### Components and responsibilities

**`main.py`** — creates `BedrockAgentCoreApp()`, keeps the scaffold's
OpenTelemetry instrumentation, and defines:

```python
@app.entrypoint
def handler(payload, context):
    return service.recommend(payload, model=get_model())
```

`get_model()` lazily builds the Bedrock model once per process. Running
`python main.py` serves `/invocations` and `/ping` on port 8080.

**`config.py`** — a `Settings` dataclass read from environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `BEDROCK_MODEL_ID` | `global.anthropic.claude-opus-5` | inference profile id |
| `AWS_REGION` | `ap-south-1` | Bedrock region |
| `MARKET_DATA_SOURCE` | `yahoo` | `yahoo` or `fixture` |
| `FIXTURE_DIR` | `data/fixtures` | used when source is `fixture` |
| `MAX_AGENT_STEPS` | `40` | LangGraph `recursion_limit` |
| `LOG_LEVEL` | `INFO` | |

**`schemas.py`** — Pydantic v2 models:

- `Requirements` (validated request, section 2).
- `Pick` (`ticker`, `target_weight`, `rationale`) and `Decision`
  (`picks`, `strategy_summary`, `assumptions`) — what Claude returns.
- `Holding`, `RiskSummary`, `Meta`, `Portfolio` — the response.
- `ErrorResponse`.

**`universe.py` / `sectors.py`** — load `data/nifty50.json`
(`{"as_of", "source", "stocks": [{ticker, symbol, name, sector, isin}]}`),
expose the sector vocabulary, resolve user sector strings, and filter by
exclusions. Sectors always come from this file (NSE's "Industry" column),
never from Yahoo, so the vocabulary is stable. The file is a snapshot:
`scripts/refresh_universe.py` downloads `ind_nifty50list.csv` from
`archives.nseindia.com` (works without special headers), falling back to
`nsearchives.nseindia.com` with a browser User-Agent, keeps `Series == "EQ"`,
maps `Symbol` to `<Symbol>.NS`, and records `as_of`. The index composition
changes on 2026-09-30 (Wipro out, BSE Ltd in), so the script runs during
implementation and again before any real use; the README says so.

**`market_data/base.py`** — the one seam to the outside world:

```python
class MarketDataSource(Protocol):
    def closes(self, tickers: list[str], days: int = 365) -> pd.DataFrame: ...   # wide, tz-naive daily adjusted closes in INR
    def index_closes(self, days: int = 365) -> pd.Series: ...                    # ^NSEI
    def fundamentals(self, tickers: list[str]) -> dict[str, Fundamentals]: ...
    def as_of(self) -> date: ...
```

`yahoo.py` uses one `yf.download([...tickers, "^NSEI"], period="1y",
auto_adjust=True, threads=True, progress=False)` for prices and
`yf.Ticker(t).info` per ticker for fundamentals (`trailingPE`, `marketCap`,
`dividendYield` — percent units in yfinance ≥ 1.7 —, `beta`, `returnOnEquity`,
`debtToEquity`, `sector`, `industry`, `shortName`). Results are cached in
process for the life of the container, yfinance's built-in retries are set to
2, the tz cache is pointed at `/tmp`, and per-ticker failures are recorded as
missing rather than raised. `fixture.py` reads `closes.csv`,
`index_closes.csv`, `fundamentals.json` and `meta.json` from `FIXTURE_DIR`.

**`analytics.py`** — pure functions over DataFrames, no I/O
(`pct_change(fill_method=None)` for pandas 3 compatibility):
`daily_returns`, `annual_return`, `annual_volatility`, `beta` (covariance with
index over variance of index), `max_drawdown`, `correlation_matrix`,
`portfolio_volatility(weights, returns)`, `portfolio_beta`,
`portfolio_drawdown`, `avg_pairwise_correlation`, `sector_weights`.
Trading days per year = 252.

**`rules.py`** — `check(picks, snapshots, requirements) -> list[Violation]`
with the table from section 2. `Violation` has a `code` and a human message
that the model can act on.

**`allocation.py`** — `allocate(picks, prices, amount) -> (holdings, cash)`
with whole-share rounding and actual weights.

**`tools.py`** — `make_tools(source, universe, requirements)` returns three
LangChain tools bound to the current request:

| Tool | Input | Output |
|---|---|---|
| `get_universe` | none | `{stocks: [{ticker, name, sector}], sectors: [...]}` with excluded sectors already removed |
| `get_stock_snapshots` | `tickers: list[str]` (empty = whole universe) | `{as_of, snapshots: [{ticker, name, sector, last_price, ret_1y, vol_1y, beta_1y, max_drawdown_1y, trailing_pe, market_cap, dividend_yield_pct, roe, debt_to_equity}], missing: [...]}` |
| `evaluate_portfolio` | `picks: [{ticker, target_weight}]` | `{ok, violations: [...], holdings, cash_inr, risk_summary}` |

A snapshot for all 50 stocks is about 5k tokens, so the model may fetch the
whole universe in one call.

**`prompts.py`** — the system prompt. Key instructions: you are constructing
an educational, non-advisory portfolio of NSE large caps; call `get_universe`
then `get_stock_snapshots`; respect the risk guidance (low → prefer beta
below 0.9, low volatility, dividend payers; moderate → balanced; high →
growth names and higher beta allowed); honour preferred and excluded
sectors and the user's goals and notes; propose target weights; always run
`evaluate_portfolio` and revise until `ok` is true; each rationale must cite
at least one number from the snapshot; never promise returns; never compute
rupee amounts yourself. The user message renders the `Requirements` as a
short bullet list.

**`llm.py`** — `ChatBedrockConverse(model=settings.model_id,
region_name=settings.region, max_tokens=8000)`. No `temperature`: Claude 5
models on Bedrock run adaptive thinking by default and reject sampling
parameters. Determinism is measured by the stability eval rather than forced.
Bedrock throttling is retried by boto3's adaptive retry mode (5 attempts).

**`agent.py`** —

```python
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

agent = create_agent(model, tools=tools, system_prompt=SYSTEM_PROMPT,
                     response_format=ToolStrategy(Decision))
result = agent.invoke({"messages": [{"role": "user", "content": rendered}]},
                      config={"recursion_limit": settings.max_agent_steps})
decision: Decision = result["structured_response"]
```

`ToolStrategy` is chosen explicitly because LangChain's auto-selection is
inconsistent across Bedrock Claude profiles (it would pick a native
JSON-schema strategy for some models that Bedrock does not support). Its
default `handle_errors=True` feeds schema validation errors back to the
model for a retry. `run(requirements, model, tools)` returns the `Decision`
plus a `RunTrace` (tool call count, `evaluate_portfolio` attempts and how
many failed, token usage summed from the AI messages' `usage_metadata`, wall
time).

**`service.py`** — the orchestrator, called by `main.py`, the tests and the
evals:

1. If `prompt` is present, require a string and parse it as JSON; otherwise
   use the payload itself. Validate into `Requirements`. Failure →
   `invalid_request`.
2. Build the data source from settings, load the universe, build tools.
3. Pre-flight: fetch closes for the universe. If more than half the tickers
   are missing → `market_data_unavailable`.
4. Run the agent. Bedrock access/throttling errors → `model_unavailable`;
   anything else → `internal` (logged with traceback).
5. Assemble: `rules.check` on the decision (renormalise if only the sum is
   off by rounding), `allocation.allocate`, `analytics` for the risk summary,
   look up names/sectors, attach disclaimer and `meta`. A persisting
   violation → `no_valid_portfolio` with the violations.
6. Return a plain dict.

### Data flow of one request

```
client ──JSON──▶ main.handler ──▶ service.recommend
                                   ├─ validate Requirements
                                   ├─ market data pre-flight (cache)
                                   ├─ agent loop (Claude via Bedrock)
                                   │    get_universe → get_stock_snapshots → evaluate_portfolio ↺ → Decision
                                   └─ assemble: rules → allocation → analytics → Portfolio
client ◀──JSON── {portfolio…} | {error…}
```

Claude decides *which* stocks and *what* target weights, and writes the
rationale. Code computes every number the user sees.

## 4. Error handling and logging

| Situation | Behaviour |
|---|---|
| Bad JSON / bad field | `invalid_request` with per-field details, before any model call |
| A ticker fails in yfinance | marked `missing`; system prompt says to drop it |
| > 50% of universe missing | `market_data_unavailable` |
| Model proposes rule violation | `evaluate_portfolio` returns violations; model revises; `recursion_limit` caps the loop |
| Final decision still violates | `no_valid_portfolio` with violations (weights off by ≤ 0.005 are renormalised) |
| Bedrock `AccessDeniedException` / model not enabled | `model_unavailable` with a message naming the Bedrock model-access console page |
| Bedrock throttling | boto3 adaptive retries, then `model_unavailable` |
| Unexpected exception | `internal`, logged with traceback; the process stays up |

Logging uses `app.logger` from the AgentCore SDK: one line per request start
and end (with `meta` fields), one line per tool call with duration, one line
per violation batch. No request payloads or prompts are logged at INFO.
CloudWatch collects stdout once deployed; the scaffold's OpenTelemetry
instrumentation stays enabled for AgentCore Observability.

## 5. Testing

All tests run with `uv run pytest` from `app/StockAdvisor/`, offline, in a
few seconds. `conftest.py` forces `MARKET_DATA_SOURCE=fixture`,
`FIXTURE_DIR=tests/fixtures`, and provides a scripted fake chat model.

| Layer | What is checked |
|---|---|
| `analytics` | hand-computed returns, volatility, beta, drawdown, correlation on a 5-row toy series; portfolio metrics for known weights |
| `rules` | each rule violated in isolation produces exactly its violation; a clean portfolio produces none; sum-off-by-rounding is not a violation |
| `allocation` | whole shares, cash, actual weights; a pick that cannot afford one share |
| `schemas` / `sectors` | required fields, bounds, enum, alias resolution, unknown sector error text |
| `universe` | loads the file, applies exclusions, stable ordering |
| `market_data/fixture` | reads the tiny fixture; missing ticker reported, not raised |
| `market_data/yahoo` | `yf.download` and `yf.Ticker` monkeypatched with fixture frames; percent-unit dividend yield handled; failures become `missing` |
| `tools` | each tool's JSON contract; `evaluate_portfolio` returns violations and risk stats |
| `agent` | fake model scripted to call `get_universe`, `get_stock_snapshots`, `evaluate_portfolio` (first with a violation, then clean) and finish with a `Decision`; asserts the loop wiring, the structured response and the `RunTrace` counts |
| `service` | both request shapes; every error type; full success path with the fake model; `meta` populated |
| `main` | `handler(payload, context)` directly, and `/invocations` + `/ping` through Starlette's `TestClient` |
| `evals/metrics` | each metric on hand-built portfolios |
| `live` | one real Bedrock + real yfinance run for a 3-stock request, `@pytest.mark.live`, skipped unless boto3 finds credentials |

The fake chat model is a small `BaseChatModel` subclass whose `_generate`
returns pre-scripted `AIMessage`s (with `tool_calls`) in order and whose
`bind_tools` returns itself. It lives in `tests/fake_model.py` and is reused
by the eval runner's `--dry-run` mode.

Development follows test-first: each module's tests are written before the
module. `ruff` runs on everything.

## 6. Evals (Layer 1, deterministic)

Purpose: measure whether the agent behaves like a rule-following adviser
given the data it had, and detect regressions after prompt or model changes.
There is no attempt to score future returns.

**Dataset** `evals/cases.json`: about 25 cases. Each case has an `id`, a
`request`, optional `group` (for monotonicity ladders), optional `repeat`
(for stability), and an `expect` block. Personas include: conservative
retiree; aggressive young investor; dividend seeker; ₹50,000 budget where
rounding bites; ₹50 lakh budget; contradictory inputs (`low` risk with
"double my money in a year"); several sector preferences and exclusions;
`max_stocks` at 4 and at 15; a case whose fixture is missing data for some
tickers; three risk ladders (`low`/`moderate`/`high` with everything else
equal); invalid requests that must error.

**Data**: the full-universe fixture in `data/fixtures/` (built once by
`scripts/build_fixture.py`, committed), so every run sees identical market
data. Only the model call is live.

**Metrics** (each a pure function in `evals/metrics.py` returning pass/fail
or a number):

| Metric | Definition |
|---|---|
| `schema_valid` | response validates as `Portfolio` (or as the expected error) |
| `first_pass_compliance` | `meta.evaluate_failures == 0` |
| `exclusions_respected` | no holding in an excluded sector (redundant with code, kept as a canary) |
| `preferred_overweight` | combined weight of preferred sectors ≥ their weight in the universe |
| `stock_count_in_bounds` | 4 ≤ n ≤ `max_stocks` |
| `risk_bounds` | beta and volatility within the case's `expect` bounds |
| `risk_monotonic` | within a `group`, beta and volatility are non-decreasing from low to high |
| `grounding` | share of numbers in rationales that match a snapshot field for that ticker within 5% relative (or 0.05 absolute) |
| `stability` | Jaccard overlap of ticker sets across `repeat` runs ≥ 0.6 |
| `language_safe` | no banned phrases (`guaranteed`, `will double`, `risk-free`, `sure shot`, `cannot lose`) and disclaimer present |
| `tool_calls`, `latency_ms`, `input_tokens`, `output_tokens` | recorded from `meta` |

**Runner** `evals/run.py`: `uv run python -m evals.run --cases evals/cases.json
[--ids a,b] [--repeat 2] [--model ...] [--dry-run]`. It calls
`service.recommend` directly, writes `evals/reports/<timestamp>-<model>.json`
(per-case results and metrics) and a markdown summary with pass rates per
metric and the median latency and tokens. `--dry-run` uses the fake model to
prove the harness works before spending money. A full run costs roughly
30–40 model requests; on Opus 5 that is in the order of ₹1,000, on Sonnet 5
about a third of that (estimate, to be measured on the first run).

The runner cannot produce real numbers until the AWS account exists; the
harness itself is covered by tests and the dry run.

## 7. Deployment and operations

### Local

```
cd app/StockAdvisor
uv sync
uv run pytest
uv run python main.py                      # serves :8080
curl -X POST localhost:8080/invocations -H 'Content-Type: application/json' -d @examples/request.json
# or, from the project root, via the CLI:
agentcore dev --no-browser --skip-deploy --logs
agentcore dev "$(cat app/StockAdvisor/examples/request.json)"
```

Local runs still need AWS credentials for Bedrock. Without them the request
returns `model_unavailable` with a clear message; the fixture source and the
fake model make everything else runnable.

### AWS prerequisites (one time, when the account exists)

1. Create the AWS account. New accounts get up to $200 in Free Tier credits;
   AgentCore itself has no free tier.
2. Create an IAM identity for yourself. For a personal sandbox,
   `AdministratorAccess` avoids friction; the minimum is
   `BedrockAgentCoreFullAccess` plus IAM role management and CDK bootstrap
   permissions (CloudFormation, S3, ECR, SSM, IAM).
3. `brew install awscli node` (Node 20+; Node 25 is already installed here),
   `aws configure` with region `ap-south-1`.
4. Bedrock: model access is enabled by default in commercial regions, but the
   first use of an Anthropic model requires a one-time use-case form in the
   Bedrock console. Claude in Mumbai is served only through `global.*`
   inference profiles, which may route the request to any AWS commercial
   region; the requirements payload contains no personal data.
5. `npm install -g @aws/agentcore@0.30.0` (a 1.0 release is imminent; pin
   until the README is re-validated against it).

### Deploy, invoke, observe, remove

```
agentcore deploy -y                                   # CodeZip via CDK; first run bootstraps CDK
agentcore status
agentcore invoke --prompt-file app/StockAdvisor/examples/request.json
agentcore logs --since 30m
uv run python scripts/invoke.py examples/request.json # boto3 client, uuid4 session id (≥ 33 chars)
agentcore remove all && agentcore deploy -y           # tear down (there is no `destroy` command)
```

`agentcore.json` is edited once after `agentcore create`: `runtimeVersion`
becomes `PYTHON_3_12`. CodeZip packaging runs `uv pip install` with
`--python-platform aarch64-manylinux…` and `--only-binary :all:`; every
dependency in this design ships a pure-Python or aarch64 wheel (checked on
PyPI on 2026-09-26, including `peewee`, `curl_cffi`, `lxml`, `numpy`,
`pandas`).

The execution role that the CDK stack creates allows Bedrock model
invocation. If a deployed invoke fails with `AccessDeniedException`, the
fix is to extend that role in `agentcore/cdk/lib/cdk-stack.ts` with the
three-statement global cross-region inference policy from the Bedrock docs
(inference-profile ARN plus the two foundation-model ARN forms); the research
sheet in `docs/superpowers/research/` has the exact statements. Nothing else
is needed because the agent only calls Bedrock and the public internet.

Python is 3.12 rather than the newest supported 3.14 because uv already
manages 3.12 on this machine and every binary dependency was checked for
cp312 aarch64 wheels.

### Cost (order of magnitude)

AgentCore Runtime: $0.1276 per vCPU-hour and $0.0169 per GB-hour, billed
while a request is running. Bedrock: Opus 5 at $5 / $25 per million input /
output tokens, Sonnet 5 at $2 / $10. A request is roughly 40k input and 4k
output tokens, so about ₹25–30 on Opus 5 and ₹10 on Sonnet 5, plus a few
paise of runtime.

## 8. Dependencies

`app/StockAdvisor/pyproject.toml`, `requires-python = ">=3.12"`:

```
bedrock-agentcore>=1.23,<2
langchain>=1.4,<2
langgraph>=1.2,<2
langchain-aws>=1.7,<2
boto3>=1.43
botocore[crt]>=1.35
pydantic>=2.10,<3
yfinance>=1.7,<2
pandas>=2.2,<4
numpy>=2,<3
aws-opentelemetry-distro~=0.18.0
opentelemetry-instrumentation-langchain>=0.59
```

Dev: `pytest`, `ruff`, `httpx` (for Starlette's `TestClient`). The
scaffold's `mcp` and `langchain-mcp-adapters` are removed.

## 9. Regulatory and data notes

- Output carries this disclaimer verbatim: "This output is generated
  automatically by an AI model (Claude, via Amazon Bedrock) for educational
  and informational purposes only. The operator of this tool is not
  registered with SEBI as an Investment Adviser or Research Analyst. Nothing
  here is investment advice, a research report, a model portfolio, a trading
  call, or a recommendation to buy, sell or hold any security. Price and
  fundamental data are sourced from third parties (Yahoo Finance via
  yfinance, NSE) and may be delayed, incomplete or incorrect. Investments in
  securities markets are subject to market risks; past performance is not
  indicative of future returns. Consult a SEBI-registered Investment Adviser
  or Research Analyst before making any investment decision, and verify
  registration at https://www.sebi.gov.in."
- SEBI's Investment Adviser and Research Analyst regulations apply to
  persons acting *for consideration* or holding themselves out as advisers,
  and a weighted stock basket issued to others counts as a model portfolio
  under the Research Analyst rules. The regulations contain no explicit
  carve-out for a private tool used only by its author, and a disclaimer
  does not change the regulatory characterisation. This project is therefore
  strictly for the author's own use: not published, not shared, not charged
  for, not associated with any SEBI-regulated entity. Exposing it to anyone
  else needs a legal opinion first. The README states this.
- Yahoo's data is licensed for personal use; yfinance is used accordingly.
- Global inference profiles may process the request in any AWS commercial
  region. The request contains no personal data (amounts and preferences
  only), so no data-protection issue arises for personal use.
- Prices are previous-close, adjusted, in INR; NSE trades 09:15–15:30 IST.

## 10. Risks and open questions

| Risk | Mitigation |
|---|---|
| Yahoo throttles or blocks AWS egress addresses (reported for some data-centre IPs) | in-process cache and retries; `MARKET_DATA_SOURCE=fixture` keeps the agent usable; the `MarketDataSource` seam allows an NSE-native source later |
| `yfinance` `info` keys are sometimes `None` for NSE stocks (`returnOnEquity` for Reliance and ITC, `debtToEquity` for banks) | snapshots carry `null`; the prompt treats null as unknown; rules never depend on nullable fields |
| Nifty 50 membership changes on 2026-09-30 and periodically after | `refresh_universe.py` re-run before real use; `as_of` echoed in `assumptions` |
| AgentCore CLI 1.0 changes commands or config | pin 0.30.0; re-validate README on upgrade |
| Opus 5 request latency (adaptive thinking) pushes a request past a minute | acceptable for v1; Sonnet 5 switch; `MAX_AGENT_STEPS` cap |
| Structured-output strategy behaves differently on Bedrock | `ToolStrategy` chosen explicitly; covered by the live smoke test |
| Deployed role lacks a global-profile permission | extend the CDK stack's role with the documented three-statement policy |

Reference material: the two verified research sheets in
`docs/superpowers/research/` (AgentCore + LangChain facts; India data,
SEBI and AWS-region facts) hold the exact signatures, commands and URLs
behind this spec.

## 11. Implementation order (for the plan)

1. Generate the project with `agentcore create` in a scratch directory and
   move `agentcore/`, `app/`, `README.md`, `AGENTS.md`, `.gitignore` into
   this repo; set Python 3.12; trim dependencies; `uv sync`.
2. Universe file and refresh script; sector resolution.
3. Schemas.
4. Analytics, rules, allocation (pure, test-first).
5. Market data: fixture source, tiny test fixture, then yahoo source.
6. Tools, prompt, fake model, agent, service.
7. `main.py`, examples, HTTP tests.
8. `build_fixture.py` and the full fixture; evals metrics, cases, runner,
   dry run.
9. README deploy guide, `scripts/invoke.py`, live smoke test.
