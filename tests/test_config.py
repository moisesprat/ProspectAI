"""
Tests for Config class and AgentConfigLoader.
These tests are pure unit tests — no network, no LLM, no .env required.
"""

import os
import pytest
from unittest.mock import patch


class TestConfig:
    """Tests for config/config.py — reads env vars, no defaults."""

    def test_anthropic_api_key_from_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            from config.config import Config
            assert Config().ANTHROPIC_API_KEY == "test-key"

    def test_anthropic_api_key_missing_returns_none(self):
        with patch.dict(os.environ, {}, clear=True):
            from config.config import Config
            assert Config().ANTHROPIC_API_KEY is None

    def test_anthropic_model_from_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": "claude-opus-4-6"}):
            from config.config import Config
            assert Config().ANTHROPIC_MODEL == "claude-opus-4-6"

    def test_ollama_base_url_from_env(self):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://remote:11434"}):
            from config.config import Config
            assert Config().OLLAMA_BASE_URL == "http://remote:11434"

    def test_ollama_model_from_env(self):
        with patch.dict(os.environ, {"OLLAMA_MODEL": "qwen3.5:9b"}):
            from config.config import Config
            assert Config().OLLAMA_MODEL == "qwen3.5:9b"

    def test_class_constants_are_defined(self):
        from config.config import Config
        assert isinstance(Config.MARKET_DATA_SOURCES, list)
        assert isinstance(Config.TECHNICAL_INDICATORS, list)
        assert isinstance(Config.FUNDAMENTAL_METRICS, list)
        assert isinstance(Config.RISK_LEVELS, list)
        assert Config.OUTPUT_FORMAT == "json"

    def test_no_hardcoded_defaults_for_api_keys(self):
        """API keys must return None when not set — no silent defaults."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL",
                            "OLLAMA_BASE_URL", "OLLAMA_MODEL")}
        with patch.dict(os.environ, env, clear=True):
            from config.config import Config
            c = Config()
            assert c.ANTHROPIC_API_KEY is None
            assert c.ANTHROPIC_MODEL is None
            assert c.OLLAMA_BASE_URL is None
            assert c.OLLAMA_MODEL is None


class TestAgentConfigLoader:
    """Tests for config/agent_config_loader.py."""

    def test_all_four_agents_are_present(self):
        from config.agent_config_loader import AgentConfigLoader
        loader = AgentConfigLoader()
        keys = loader.get_all_agent_keys()
        for expected in ("market_analyst", "technical_analyst",
                         "fundamental_analyst", "investor_strategic"):
            assert expected in keys

    def test_required_fields_present_for_each_agent(self):
        from config.agent_config_loader import AgentConfigLoader
        loader = AgentConfigLoader()
        for key in loader.get_all_agent_keys():
            cfg = loader.get_agent_config(key)
            for field in ("name", "role", "goal", "backstory"):
                assert field in cfg, f"Agent '{key}' missing field '{field}'"
                assert cfg[field], f"Agent '{key}' has empty '{field}'"

    def test_llm_block_present_and_valid(self):
        from config.agent_config_loader import AgentConfigLoader
        loader = AgentConfigLoader()
        for key in loader.get_all_agent_keys():
            settings = loader.get_agent_settings(key)
            llm = settings.get("llm", {})
            assert "provider" in llm, f"Agent '{key}' missing llm.provider"
            assert llm["provider"] in ("anthropic", "ollama"), \
                f"Agent '{key}' has unsupported provider '{llm['provider']}'"

    def test_validate_config_passes(self):
        from config.agent_config_loader import AgentConfigLoader
        loader = AgentConfigLoader()
        assert loader.validate_config() is True

    def test_unknown_agent_key_raises(self):
        from config.agent_config_loader import AgentConfigLoader
        loader = AgentConfigLoader()
        with pytest.raises((KeyError, Exception)):
            loader.get_agent_config("nonexistent_agent")

    def test_reload_config_does_not_lose_agents(self):
        from config.agent_config_loader import AgentConfigLoader
        loader = AgentConfigLoader()
        before = set(loader.get_all_agent_keys())
        loader.reload_config()
        after = set(loader.get_all_agent_keys())
        assert before == after
