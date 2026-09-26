import pytest
from pydantic import ValidationError

from stock_advisor.schemas import (
    Decision,
    ErrorType,
    Pick,
    PickInput,
    Requirements,
    RiskTolerance,
    error_response,
)


def test_requirements_required_fields_and_defaults():
    r = Requirements(amount_inr=500_000, risk_tolerance="moderate")
    assert r.risk_tolerance is RiskTolerance.moderate
    assert r.horizon_years == 5
    assert r.goals == ""
    assert r.preferred_sectors == []
    assert r.excluded_sectors == []
    assert r.max_stocks == 8
    assert r.notes == ""


def test_requirements_missing_required():
    with pytest.raises(ValidationError):
        Requirements(risk_tolerance="low")
    with pytest.raises(ValidationError):
        Requirements(amount_inr=50_000)


def test_requirements_bounds():
    with pytest.raises(ValidationError):
        Requirements(amount_inr=9_999, risk_tolerance="low")
    with pytest.raises(ValidationError):
        Requirements(amount_inr=50_000, risk_tolerance="low", max_stocks=3)
    with pytest.raises(ValidationError):
        Requirements(amount_inr=50_000, risk_tolerance="low", max_stocks=16)
    with pytest.raises(ValidationError):
        Requirements(amount_inr=50_000, risk_tolerance="low", horizon_years=0)
    with pytest.raises(ValidationError):
        Requirements(amount_inr=50_000, risk_tolerance="silly")


def test_requirements_ignores_extra_keys():
    r = Requirements(amount_inr=50_000, risk_tolerance="high", user_id="x")
    assert not hasattr(r, "user_id")


def test_pick_and_decision():
    with pytest.raises(ValidationError):
        PickInput(ticker="INFY.NS", target_weight=0)
    with pytest.raises(ValidationError):
        Pick(ticker="INFY.NS", target_weight=0.2, rationale="")
    d = Decision(
        picks=[Pick(ticker="INFY.NS", target_weight=0.5, rationale="cheap")],
        strategy_summary="one stock",
    )
    assert d.assumptions == []
    with pytest.raises(ValidationError):
        Decision(picks=[], strategy_summary="none")


def test_error_response_shape():
    body = error_response(ErrorType.invalid_request, "bad", ["amount_inr: too small"])
    assert body == {
        "error": {
            "type": "invalid_request",
            "message": "bad",
            "details": ["amount_inr: too small"],
        }
    }
    assert error_response("internal", "boom")["error"]["details"] == []
