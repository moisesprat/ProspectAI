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


# ─── agent_model_ids (plan 02-03, D-01) ────────────────────────────────────────

class TestAgentModelIds:
    def test_agent_model_ids_yaml_default(self, clean_env):
        ids = ProspectAIFlow().agent_model_ids()
        assert ids == ["claude-haiku-5-5"] * 6

    def test_agent_model_ids_env_override(self, clean_env):
        clean_env.setenv("AGENT_CRITIC_MODEL", HAIKU)
        ids = ProspectAIFlow().agent_model_ids()
        assert ids[4] == HAIKU
        assert [m for i, m in enumerate(ids) if i != 4] == ["claude-haiku-5-5"] * 5

    def test_global_model_changes_all_six(self, clean_env):
        clean_env.setenv("MODEL", "claude-x")
        assert ProspectAIFlow().agent_model_ids() == ["claude-x"] * 6

    def test_provider_prefix_is_stripped(self, clean_env):
        flow = ProspectAIFlow()
        for phase in _PHASES:
            flow._factory._phase_config[phase]["agent"].llm.model = "ollama/qwen3"
        assert flow.agent_model_ids() == ["qwen3"] * 6


# ─── CLI (main.py) ─────────────────────────────────────────────────────────────

def _run_main(monkeypatch, argv):
    import main
    import prospect_ai_flow
    from unittest.mock import MagicMock

    flow_cls = MagicMock()
    flow_cls.return_value.run_analysis.return_value = {"summary": "s", "execution_metrics": {}}
    flow_cls.return_value.agent_model_ids.return_value = ["claude-haiku-5-5"] * 6
    monkeypatch.setattr(prospect_ai_flow, "ProspectAIFlow", flow_cls)
    monkeypatch.setattr(main, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["prospectai", *argv])
    main.main()
    return flow_cls


class TestCli:
    def test_model_flag_passed_not_written(self, clean_env):
        before = dict(os.environ)
        flow_cls = _run_main(clean_env, ["--model", "claude-x", "--sector", "Technology"])
        _, kwargs = flow_cls.call_args
        assert kwargs["model"] == "claude-x"
        assert kwargs["provider"] == "anthropic"
        assert dict(os.environ) == before

    def test_ollama_and_url_passed_not_written(self, clean_env):
        before = dict(os.environ)
        flow_cls = _run_main(
            clean_env, ["--ollama", "--url", "http://host:1", "--model", "qwen", "--sector", "Technology"]
        )
        _, kwargs = flow_cls.call_args
        assert kwargs["provider"] == "ollama"
        assert kwargs["ollama_base_url"] == "http://host:1"
        assert kwargs["model"] == "qwen"
        assert dict(os.environ) == before

    def test_anthropic_without_model_runs(self, clean_env, capsys):
        import main

        clean_env.setattr(main, "load_dotenv", lambda *a, **k: None)
        before = dict(os.environ)
        main.load_and_validate_env("anthropic", None, None)  # must not exit
        assert "MODEL" not in capsys.readouterr().out
        assert dict(os.environ) == before

    def test_anthropic_without_model_still_checks_other_keys(self, clean_env, capsys):
        import main

        clean_env.setattr(main, "load_dotenv", lambda *a, **k: None)
        clean_env.delenv("ANTHROPIC_API_KEY")
        with pytest.raises(SystemExit) as exc:
            main.load_and_validate_env("anthropic", None, None)
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "ANTHROPIC_API_KEY" in out
        assert "MODEL (or legacy" not in out

    def test_cli_anthropic_without_model_prints_yaml_models(self, clean_env, capsys):
        before = dict(os.environ)
        flow_cls = _run_main(clean_env, ["--sector", "Technology"])
        _, kwargs = flow_cls.call_args
        assert kwargs["model"] is None
        assert "claude-haiku-5-5" in capsys.readouterr().out
        assert dict(os.environ) == before

    def test_ollama_without_model_exits_1(self, clean_env, capsys):
        before = dict(os.environ)
        with pytest.raises(SystemExit) as exc:
            _run_main(clean_env, ["--ollama", "--url", "http://host:1", "--sector", "Technology"])
        assert exc.value.code == 1
        assert "MODEL (or legacy ANTHROPIC_MODEL / OLLAMA_MODEL)" in capsys.readouterr().out
        assert dict(os.environ) == before
