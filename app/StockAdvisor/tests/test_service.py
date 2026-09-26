from __future__ import annotations

import json

from stock_advisor import service
from stock_advisor.schemas import Portfolio
from tests.fake_model import ScriptedChatModel, standard_script

REQ = {
    "amount_inr": 500000,
    "risk_tolerance": "moderate",
    "preferred_sectors": ["IT"],
    "excluded_sectors": ["Healthcare"],
    "max_stocks": 6,
}
PICKS = [
    {"ticker": "INFY.NS", "target_weight": 0.2, "rationale": "IT leader, P/E cited"},
    {"ticker": "TCS.NS", "target_weight": 0.15, "rationale": "steady IT"},
    {"ticker": "HDFCBANK.NS", "target_weight": 0.25, "rationale": "bank"},
    {"ticker": "ICICIBANK.NS", "target_weight": 0.15, "rationale": "second bank"},
    {"ticker": "RELIANCE.NS", "target_weight": 0.25, "rationale": "energy"},
]


def run(payload, script, settings, source, universe):
    model = ScriptedChatModel(responses=script)
    return service.recommend(payload, model, settings=settings, source=source, universe=universe)


def test_success_raw_payload(settings, source, universe):
    out = run(REQ, standard_script(PICKS), settings, source, universe)
    assert "error" not in out, out
    p = Portfolio.model_validate(out)
    assert {h.ticker for h in p.portfolio} == {"INFY.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "RELIANCE.NS"}
    assert sum(h.amount_inr for h in p.portfolio) + p.cash_inr == 500000
    assert all(h.approx_shares >= 1 for h in p.portfolio)
    assert p.risk_summary.annual_volatility is not None
    assert p.meta.tool_calls == 3 and p.meta.evaluate_attempts == 1
    assert p.meta.evaluate_failures == 0
    assert "SEBI" in p.disclaimer


def test_success_prompt_wrapped_and_revision_counted(settings, source, universe):
    bad_first = [{"ticker": "INFY.NS", "target_weight": 0.6}, {"ticker": "TCS.NS", "target_weight": 0.4}]
    out = run({"prompt": json.dumps(REQ)}, standard_script(PICKS, bad_first), settings, source, universe)
    assert "error" not in out, out
    assert out["meta"]["evaluate_attempts"] == 2 and out["meta"]["evaluate_failures"] == 1


def test_invalid_request_details(settings, source, universe):
    out = run({"amount_inr": 5000, "risk_tolerance": "wild"}, [], settings, source, universe)
    assert out["error"]["type"] == "invalid_request"
    assert any("amount_inr" in d for d in out["error"]["details"])


def test_prompt_must_be_object(settings, source, universe):
    for bad in ({"prompt": 5}, {"prompt": "[1,2]"}, {"prompt": "not json"}, {"prompt": '{"prompt": "x"}'}):
        out = run(bad, [], settings, source, universe)
        assert out["error"]["type"] == "invalid_request", bad


def test_unknown_sector(settings, source, universe):
    out = run({**REQ, "excluded_sectors": ["Tobacco"]}, [], settings, source, universe)
    assert out["error"]["type"] == "invalid_request"
    assert "Valid sectors" in out["error"]["message"]


def test_no_valid_portfolio_when_final_decision_breaks_rules(settings, source, universe):
    bad = [{"ticker": "INFY.NS", "target_weight": 0.5, "rationale": "x"},
           {"ticker": "TCS.NS", "target_weight": 0.5, "rationale": "y"}]
    script = standard_script(bad)
    out = run(REQ, script, settings, source, universe)
    assert out["error"]["type"] == "no_valid_portfolio"
    assert any(d.startswith("too_few_stocks") or d.startswith("max_weight") for d in out["error"]["details"])
