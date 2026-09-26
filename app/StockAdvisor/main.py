"""AgentCore Runtime entrypoint for the Nifty 50 portfolio recommendation agent."""

from __future__ import annotations

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from stock_advisor import service
from stock_advisor.config import Settings
from stock_advisor.llm import make_bedrock_model

try:  # observability is optional locally
    from opentelemetry.instrumentation.langchain import LangchainInstrumentor

    LangchainInstrumentor().instrument()
except Exception:  # noqa: BLE001
    pass

app = BedrockAgentCoreApp()
settings = Settings.from_env()
logging.getLogger("stock_advisor").setLevel(settings.log_level)
_model = None


def get_model():
    global _model
    if _model is None:
        _model = make_bedrock_model(settings)
    return _model


@app.entrypoint
def handler(payload, context):
    app.logger.info("recommend request received")
    result = service.recommend(payload, model=get_model(), settings=settings)
    app.logger.info("recommend request finished: %s", "error" if "error" in result else "ok")
    return result


if __name__ == "__main__":
    app.run()
