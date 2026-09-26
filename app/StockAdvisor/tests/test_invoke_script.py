from __future__ import annotations

import io
import json

import pytest

from scripts.invoke import invoke, resolve_arn


class StubClient:
    def __init__(self, body: bytes = b'{"portfolio": []}'):
        self.calls: list[dict] = []
        self._body = body

    def invoke_agent_runtime(self, **kwargs):
        self.calls.append(kwargs)
        return {"response": io.BytesIO(self._body)}


def test_invoke_sends_json_payload_with_long_session_id():
    client = StubClient()
    body = {"amount_inr": 100000, "risk_tolerance": "low"}
    text = invoke("arn:aws:bedrock-agentcore:ap-south-1:1:runtime/x", body, client=client)
    assert json.loads(text) == {"portfolio": []}
    call = client.calls[0]
    assert call["agentRuntimeArn"].endswith("runtime/x")
    assert json.loads(call["payload"].decode("utf-8")) == body
    assert isinstance(call["payload"], bytes)
    assert len(call["runtimeSessionId"]) >= 33
    assert call["contentType"] == "application/json"
    assert call["accept"] == "application/json"


def test_invoke_reuses_given_session_id_and_rejects_short_ones():
    client = StubClient()
    sid = "a" * 40
    invoke("arn", {}, session_id=sid, client=client)
    assert client.calls[0]["runtimeSessionId"] == sid
    with pytest.raises(ValueError, match="33"):
        invoke("arn", {}, session_id="short", client=client)


def test_missing_arn_exits_with_message(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME_ARN", raising=False)
    with pytest.raises(SystemExit, match="AGENT_RUNTIME_ARN"):
        resolve_arn(None)
    monkeypatch.setenv("AGENT_RUNTIME_ARN", "arn:from-env")
    assert resolve_arn(None) == "arn:from-env"
    assert resolve_arn("arn:explicit") == "arn:explicit"
