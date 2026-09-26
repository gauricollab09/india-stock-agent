from pathlib import Path

from stock_advisor.config import APP_DIR, Settings


def test_defaults():
    s = Settings.from_env({})
    assert s.model_id == "global.anthropic.claude-opus-5"
    assert s.region == "ap-south-1"
    assert s.market_data_source == "yahoo"
    assert s.fixture_dir == APP_DIR / "data" / "fixtures"
    assert s.max_agent_steps == 40
    assert s.max_tokens == 8000
    assert s.log_level == "INFO"


def test_env_overrides():
    s = Settings.from_env(
        {
            "BEDROCK_MODEL_ID": "global.anthropic.claude-sonnet-5",
            "AWS_REGION": "ap-southeast-1",
            "MARKET_DATA_SOURCE": "fixture",
            "FIXTURE_DIR": "/tmp/fx",
            "MAX_AGENT_STEPS": "12",
            "MAX_TOKENS": "2000",
            "LOG_LEVEL": "DEBUG",
        }
    )
    assert s.model_id == "global.anthropic.claude-sonnet-5"
    assert s.region == "ap-southeast-1"
    assert s.market_data_source == "fixture"
    assert s.fixture_dir == Path("/tmp/fx")
    assert s.max_agent_steps == 12
    assert s.max_tokens == 2000
    assert s.log_level == "DEBUG"


def test_app_dir_is_the_agent_folder():
    assert (APP_DIR / "pyproject.toml").exists()
