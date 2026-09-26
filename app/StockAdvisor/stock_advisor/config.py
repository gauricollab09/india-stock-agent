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
