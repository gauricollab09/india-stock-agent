from __future__ import annotations

import json
import logging
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from langgraph.errors import GraphRecursionError
from pydantic import ValidationError

from stock_advisor.agent import build_agent, run_agent
from stock_advisor.config import Settings
from stock_advisor.market_context import build_market_context
from stock_advisor.market_data import get_source
from stock_advisor.market_data.base import MarketDataError
from stock_advisor.portfolio import DISCLAIMER, evaluate, holdings_from
from stock_advisor.prompts import render_requirements
from stock_advisor.schemas import ErrorType, Meta, Portfolio, Requirements, error_response
from stock_advisor.sectors import UnknownSectorError, resolve_sectors
from stock_advisor.tools import make_tools
from stock_advisor.universe import Universe, load_universe

log = logging.getLogger("stock_advisor")

EXPECTED_SHAPE = (
    'expected a JSON object like {"amount_inr": 500000, "risk_tolerance": "moderate", '
    '"horizon_years": 5, "max_stocks": 8, "preferred_sectors": [], "excluded_sectors": []}'
)


def parse_payload(payload: Any) -> Requirements:
    if not isinstance(payload, dict):
        raise ValueError(f"payload must be a JSON object; {EXPECTED_SHAPE}")
    body = payload
    if "prompt" in payload:
        prompt = payload["prompt"]
        if not isinstance(prompt, str):
            raise ValueError(f"prompt must be a string; {EXPECTED_SHAPE}")
        try:
            body = json.loads(prompt)
        except ValueError as exc:
            raise ValueError(f"prompt is not valid JSON ({exc}); {EXPECTED_SHAPE}") from exc
        if not isinstance(body, dict) or "prompt" in body:
            raise ValueError(f"prompt must decode to a requirements object; {EXPECTED_SHAPE}")
    return Requirements.model_validate(body)


def _validation_details(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in e['loc']) or 'body'}: {e['msg']}" for e in exc.errors()]


def recommend(
    payload: Any,
    model,
    settings: Settings | None = None,
    source=None,
    universe: Universe | None = None,
) -> dict:
    settings = settings or Settings.from_env()
    try:
        req = parse_payload(payload)
    except ValidationError as exc:
        return error_response(
            ErrorType.invalid_request, "invalid request", _validation_details(exc)
        )
    except ValueError as exc:
        return error_response(ErrorType.invalid_request, str(exc))

    universe = universe or load_universe()
    try:
        preferred = resolve_sectors(req.preferred_sectors, universe.sectors)
        excluded = resolve_sectors(req.excluded_sectors, universe.sectors)
    except UnknownSectorError as exc:
        return error_response(ErrorType.invalid_request, str(exc))

    source = source or get_source(settings)
    try:
        ctx = build_market_context(universe, source)
    except MarketDataError as exc:
        return error_response(ErrorType.market_data_unavailable, f"market data unavailable: {exc}")
    if len(ctx.missing) * 2 > len(universe.stocks):
        return error_response(
            ErrorType.market_data_unavailable,
            f"price data missing for {len(ctx.missing)} of {len(universe.stocks)} stocks",
            ctx.missing,
        )

    tools = make_tools(ctx, req, excluded)
    agent = build_agent(model, tools)
    try:
        decision, trace = run_agent(
            agent, render_requirements(req, preferred, excluded), settings.max_agent_steps
        )
    except GraphRecursionError:
        return error_response(
            ErrorType.no_valid_portfolio,
            "the agent could not produce a valid portfolio within "
            f"{settings.max_agent_steps} steps",
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        msg = (
            f"Bedrock call failed ({code}). "
            "If AccessDenied, enable the model in the Bedrock console."
        )
        return error_response(ErrorType.model_unavailable, msg, [str(exc)])
    except BotoCoreError as exc:
        return error_response(ErrorType.model_unavailable, f"Bedrock unreachable: {exc}")
    except Exception as exc:  # noqa: BLE001
        log.exception("agent run failed")
        return error_response(ErrorType.internal, f"{type(exc).__name__}: {exc}")

    ev = evaluate(decision.picks, req, ctx, excluded)
    if not ev.ok:
        return error_response(
            ErrorType.no_valid_portfolio,
            "the final portfolio breaks the hard rules",
            [f"{v.code}: {v.message}" for v in ev.violations],
        )
    rationales = {p.ticker: p.rationale for p in decision.picks}
    portfolio = Portfolio(
        portfolio=holdings_from(ev, ctx, rationales),
        cash_inr=ev.cash_inr,
        risk_summary=ev.risk_summary,
        strategy_summary=decision.strategy_summary,
        assumptions=[f"Prices as of {ctx.as_of} close", f"Universe as of {universe.as_of}"]
        + list(decision.assumptions),
        disclaimer=DISCLAIMER,
        meta=Meta(
            model=settings.model_id,
            data_source=settings.market_data_source,
            as_of=ctx.as_of,
            tool_calls=trace.tool_calls,
            evaluate_attempts=trace.evaluate_attempts,
            evaluate_failures=trace.evaluate_failures,
            input_tokens=trace.input_tokens,
            output_tokens=trace.output_tokens,
            latency_ms=trace.latency_ms,
        ),
    )
    return portfolio.model_dump(mode="json")
