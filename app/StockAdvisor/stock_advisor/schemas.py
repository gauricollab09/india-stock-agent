"""Pydantic models for requests, the model's decision, the response, and errors."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RiskTolerance(StrEnum):
    low = "low"
    moderate = "moderate"
    high = "high"


class Requirements(BaseModel):
    """The validated request (see spec section 2)."""

    model_config = ConfigDict(extra="ignore")

    amount_inr: int = Field(ge=10_000)
    risk_tolerance: RiskTolerance
    horizon_years: int = Field(5, ge=1, le=30)
    goals: str = Field("", max_length=500)
    preferred_sectors: list[str] = Field(default_factory=list)
    excluded_sectors: list[str] = Field(default_factory=list)
    max_stocks: int = Field(8, ge=4, le=15)
    notes: str = Field("", max_length=500)


class PickInput(BaseModel):
    """A ticker and its target weight, as passed to evaluate_portfolio."""

    ticker: str
    target_weight: float = Field(gt=0, le=1)


class Pick(PickInput):
    """A pick in the model's final decision, with its rationale."""

    rationale: str = Field(min_length=1, max_length=600)


class Decision(BaseModel):
    """What Claude returns: picks, weights, rationale. Code computes everything else."""

    picks: list[Pick] = Field(min_length=1)
    strategy_summary: str
    assumptions: list[str] = Field(default_factory=list)


class Holding(BaseModel):
    ticker: str
    name: str
    sector: str
    target_weight: float
    weight: float
    amount_inr: int
    approx_shares: int
    last_price: float
    rationale: str


class RiskSummary(BaseModel):
    annual_volatility: float | None
    portfolio_beta: float | None
    max_drawdown_1y: float | None
    dividend_yield_pct: float | None
    avg_pairwise_correlation: float | None
    sector_weights: dict[str, float]


class Meta(BaseModel):
    model: str
    data_source: str
    as_of: str
    tool_calls: int
    evaluate_attempts: int
    evaluate_failures: int
    input_tokens: int
    output_tokens: int
    latency_ms: int


class Portfolio(BaseModel):
    portfolio: list[Holding]
    cash_inr: int
    risk_summary: RiskSummary
    strategy_summary: str
    assumptions: list[str]
    disclaimer: str
    meta: Meta


class ErrorType(StrEnum):
    invalid_request = "invalid_request"
    market_data_unavailable = "market_data_unavailable"
    no_valid_portfolio = "no_valid_portfolio"
    model_unavailable = "model_unavailable"
    internal = "internal"


class ErrorBody(BaseModel):
    type: ErrorType
    message: str
    details: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_response(type_: ErrorType | str, message: str, details: list[str] | None = None) -> dict:
    """Build the JSON-ready error body returned by the service."""
    body = ErrorBody(type=ErrorType(type_), message=message, details=list(details or []))
    return ErrorResponse(error=body).model_dump(mode="json")
