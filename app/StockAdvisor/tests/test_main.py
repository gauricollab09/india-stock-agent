from __future__ import annotations

import json

from starlette.testclient import TestClient

import main
from tests.fake_model import ScriptedChatModel, standard_script
from tests.test_service import PICKS, REQ


def test_ping():
    assert TestClient(main.app).get("/ping").json()["status"] in ("Healthy", "HealthyBusy")


def test_invocations_end_to_end(monkeypatch, settings, universe, source):
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(
        main, "get_model", lambda: ScriptedChatModel(responses=standard_script(PICKS))
    )
    monkeypatch.setattr(main.service, "load_universe", lambda: universe)
    monkeypatch.setattr(main.service, "get_source", lambda s: source)
    r = TestClient(main.app).post("/invocations", json={"prompt": json.dumps(REQ)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "portfolio" in body and body["cash_inr"] >= 0


def test_model_construction_failure_is_a_clean_error(monkeypatch):
    def boom():
        raise RuntimeError("Could not load credentials")

    monkeypatch.setattr(main, "get_model", boom)
    r = TestClient(main.app).post("/invocations", json={"amount_inr": 100000, "risk_tolerance": "low"})
    assert r.status_code == 200
    assert r.json()["error"]["type"] == "model_unavailable"
    assert "credentials" in r.json()["error"]["message"].lower()
