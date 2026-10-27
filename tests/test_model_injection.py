"""Tests for DEPL-03 explicit model injection: no os.environ writes, env read once."""
import os

import pytest

from config.config import Config, AGENT_MODEL_ENV_KEYS
from prospect_ai_flow import ProspectAIFlow

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"

_PHASES = [
    "market_analysis", "technical_analysis", "fundamental_analysis",
    "draft_strategy", "critique_review", "final_strategy",
]


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SERPER_API_KEY", "test-serper")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "test-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "test-secret")
    for name in ("MODEL", "MODEL_PROVIDER", "ANTHROPIC_MODEL", "OLLAMA_MODEL", "OLLAMA_BASE_URL",
                 *AGENT_MODEL_ENV_KEYS.values()):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _agent_models(flow):
    return {p: flow._factory._phase_config[p]["agent"].llm.model for p in _PHASES}


# ─── Config ────────────────────────────────────────────────────────────────────

class TestConfig:
    def test_explicit_model_strips_provider_prefix(self, clean_env):
        assert Config(model="anthropic/claude-x").default_model_id() == "claude-x"

    def test_explicit_provider_and_url_beat_env(self, clean_env):
        clean_env.setenv("MODEL_PROVIDER", "anthropic")
        clean_env.setenv("OLLAMA_BASE_URL", "http://env:9")
        cfg = Config(provider="ollama", ollama_base_url="http://host:1")
        assert cfg.provider == "ollama"
        assert cfg.OLLAMA_BASE_URL == "http://host:1"

    def test_env_read_once_at_construction(self, clean_env):
        clean_env.setenv("MODEL", "claude-before")
        cfg = Config()
        clean_env.setenv("MODEL", "claude-after")
        assert cfg.default_model_id() == "claude-before"

    def test_provider_defaults_to_anthropic(self, clean_env):
        assert Config().provider == "anthropic"

    def test_per_agent_override_beats_explicit_model(self, clean_env):
        clean_env.setenv("AGENT_CRITIC_MODEL", SONNET)
        cfg = Config(model=HAIKU)
        assert cfg.model_id_for_agent("critic") == SONNET
        assert cfg.model_id_for_agent("market_analyst") == HAIKU


# ─── Flow injection ────────────────────────────────────────────────────────────

class TestFlowInjection:
    def test_two_flows_same_model_env_untouched(self, clean_env):
        before = dict(os.environ)
        f1 = ProspectAIFlow(model=HAIKU)
        f2 = ProspectAIFlow(model=HAIKU)
        for flow in (f1, f2):
            models = _agent_models(flow)
            assert all(m.endswith(HAIKU) for m in models.values()), models
        assert dict(os.environ) == before

    def test_per_agent_override_in_flow(self, clean_env):
        clean_env.setenv("AGENT_CRITIC_MODEL", SONNET)
        flow = ProspectAIFlow(model=HAIKU)
        models = _agent_models(flow)
        assert models["critique_review"].endswith(SONNET)
        for phase in _PHASES:
            if phase != "critique_review":
                assert models[phase].endswith(HAIKU), (phase, models[phase])

    def test_config_instance_used_as_is(self, clean_env):
        cfg = Config(model=HAIKU)
        assert ProspectAIFlow(config=cfg).pipeline_config is cfg

    def test_config_with_model_raises(self, clean_env):
        with pytest.raises(ValueError):
            ProspectAIFlow(config=Config(model=HAIKU), model=HAIKU)

    def test_zero_arg_construction(self, clean_env):
        clean_env.setenv("MODEL", HAIKU)
        assert isinstance(ProspectAIFlow().pipeline_config, Config)
