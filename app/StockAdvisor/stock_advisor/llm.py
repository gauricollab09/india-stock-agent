from __future__ import annotations

from botocore.config import Config
from langchain_aws import ChatBedrockConverse

from stock_advisor.config import Settings


def make_bedrock_model(settings: Settings) -> ChatBedrockConverse:
    """Claude on Bedrock via the Converse API. No temperature: Claude 5 rejects sampling params."""
    return ChatBedrockConverse(
        model=settings.model_id,
        region_name=settings.region,
        max_tokens=settings.max_tokens,
        config=Config(retries={"max_attempts": 5, "mode": "adaptive"}, read_timeout=300),
    )
