"""
Tests for all four agents and BaseAgent.
Mocks crewai.LLM so no API calls are made.
"""

import os
import pytest
from unittest.mock import patch, MagicMock


# ── fixtures ──────────────────────────────────────────────────────────────────

ANTHROPIC_ENV = {
    "MODEL_PROVIDER": "anthropic",
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "ANTHROPIC_MODEL": "claude-sonnet-4-6",
}

OLLAMA_ENV = {
    "MODEL_PROVIDER": "ollama",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_MODEL": "qwen3.5:9b",
}


def _mock_llm():
    m = MagicMock()
    m.model = "claude-sonnet-4-6"
    return m


# ── BaseAgent ─────────────────────────────────────────────────────────────────

class TestBaseAgent:

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_agent_loads_name_from_yaml(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.market_analyst_agent import MarketAnalystAgent
            a = MarketAnalystAgent()
            assert a.name, "name should not be empty"

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_agent_loads_role_from_yaml(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.market_analyst_agent import MarketAnalystAgent
            a = MarketAnalystAgent()
            assert a.role, "role should not be empty"

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_agent_loads_goal_from_yaml(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.market_analyst_agent import MarketAnalystAgent
            a = MarketAnalystAgent()
            assert a.goal, "goal should not be empty"

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_agent_loads_backstory_from_yaml(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.market_analyst_agent import MarketAnalystAgent
            a = MarketAnalystAgent()
            assert a.backstory, "backstory should not be empty"

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_get_config_returns_dict(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.market_analyst_agent import MarketAnalystAgent
            a = MarketAnalystAgent()
            cfg = a.get_config()
            assert isinstance(cfg, dict)

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_get_llm_anthropic_builds_correct_model_string(self, mock_llm_cls):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.market_analyst_agent import MarketAnalystAgent
            a = MarketAnalystAgent()
            a._get_llm()
            call_kwargs = mock_llm_cls.call_args
            model_arg = call_kwargs[1].get("model") or call_kwargs[0][0]
            assert "anthropic/" in model_arg

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_get_llm_ollama_builds_correct_model_string(self, mock_llm_cls):
        with patch.dict(os.environ, OLLAMA_ENV):
            from agents.market_analyst_agent import MarketAnalystAgent
            a = MarketAnalystAgent()
            a._get_llm()
            call_kwargs = mock_llm_cls.call_args
            model_arg = call_kwargs[1].get("model") or call_kwargs[0][0]
            assert "ollama/" in model_arg

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_get_llm_ollama_passes_base_url(self, mock_llm_cls):
        with patch.dict(os.environ, OLLAMA_ENV):
            from agents.market_analyst_agent import MarketAnalystAgent
            a = MarketAnalystAgent()
            a._get_llm()
            call_kwargs = mock_llm_cls.call_args
            base_url = call_kwargs[1].get("base_url")
            assert base_url == "http://localhost:11434"


# ── Individual agents ─────────────────────────────────────────────────────────

class TestMarketAnalystAgent:

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_create_agent_returns_crewai_agent(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.market_analyst_agent import MarketAnalystAgent
            from crewai import Agent
            a = MarketAnalystAgent()
            agent = a.create_agent()
            assert isinstance(agent, Agent)

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_get_agent_is_idempotent(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.market_analyst_agent import MarketAnalystAgent
            a = MarketAnalystAgent()
            assert a.get_agent() is a.get_agent()

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_allow_delegation_is_false(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.market_analyst_agent import MarketAnalystAgent
            a = MarketAnalystAgent()
            assert a.allow_delegation is False


class TestTechnicalAnalystAgent:

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_create_agent_returns_crewai_agent(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.technical_analyst_agent import TechnicalAnalystAgent
            from crewai import Agent
            a = TechnicalAnalystAgent()
            assert isinstance(a.create_agent(), Agent)

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_temperature_is_low(self, _mock):
        """Technical analysis should use a low temperature for determinism."""
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.technical_analyst_agent import TechnicalAnalystAgent
            a = TechnicalAnalystAgent()
            assert a.temperature <= 0.2


class TestFundamentalAnalystAgent:

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_create_agent_returns_crewai_agent(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.fundamental_analyst_agent import FundamentalAnalystAgent
            from crewai import Agent
            a = FundamentalAnalystAgent()
            assert isinstance(a.create_agent(), Agent)


class TestInvestorStrategicAgent:

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_create_agent_returns_crewai_agent(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.investor_strategic_agent import InvestorStrategicAgent
            from crewai import Agent
            a = InvestorStrategicAgent()
            assert isinstance(a.create_agent(), Agent)

    @patch("crewai.LLM", return_value=_mock_llm())
    def test_max_tokens_is_set(self, _mock):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from agents.investor_strategic_agent import InvestorStrategicAgent
            a = InvestorStrategicAgent()
            assert a.max_tokens is not None and a.max_tokens > 0
