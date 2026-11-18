"""Tests for cached YAML config loads (phase 5, DEBT-04, D-07)."""

import os

import pytest
import yaml

from config.agent_config_loader import AgentConfigLoader
from config.task_config_loader import TaskConfigLoader
from config.yaml_cache import clear_yaml_cache, load_yaml
from prospect_ai_flow import PHASES


@pytest.fixture(autouse=True)
def reset_cache():
    """Earlier tests in the process warm the cache, so every test starts and ends cold."""
    clear_yaml_cache()
    yield
    clear_yaml_cache()


@pytest.fixture
def parse_counter(monkeypatch):
    """Counts yaml.safe_load calls (the cache calls it through the module attribute)."""
    calls = {"n": 0}
    real = yaml.safe_load

    def counting(stream):
        calls["n"] += 1
        return real(stream)

    monkeypatch.setattr(yaml, "safe_load", counting)
    return calls


def _make_factory():
    from config.config import Config
    from utils.task_factory import TaskFactory

    return TaskFactory(config=Config())


def _build_all(factory):
    for phase in PHASES:
        factory.build_task(phase, "Technology", "2026-11-16")


@pytest.fixture
def serper_key(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")


def test_second_run_does_not_reparse_yaml(parse_counter, serper_key):
    first = _make_factory()
    _build_all(first)
    assert parse_counter["n"] == 2  # agents.yaml once, tasks.yaml once

    second = _make_factory()
    _build_all(second)
    assert parse_counter["n"] == 2


def test_one_task_loader_per_factory(monkeypatch, serper_key):
    constructed = {"n": 0}
    real_init = TaskConfigLoader.__init__

    def counting_init(self, *args, **kwargs):
        constructed["n"] += 1
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(TaskConfigLoader, "__init__", counting_init)
    factory = _make_factory()
    _build_all(factory)
    assert constructed["n"] == 1


def test_loaded_config_is_a_private_copy():
    first = AgentConfigLoader()
    original_role = first.get_agent_role("critic")
    first.config_data["agents"]["critic"]["role"] = "MUTATED"
    assert AgentConfigLoader().get_agent_role("critic") == original_role

    task_a = TaskConfigLoader()
    original = task_a.get_task_config("market_analysis")["description"]
    task_a.config_data["tasks"]["market_analysis"]["description"] = "MUTATED"
    assert TaskConfigLoader().get_task_config("market_analysis")["description"] == original


def test_cache_sees_a_changed_file(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text("tasks:\n  t:\n    description: aaaa\n    expected_output: x\n", encoding="utf-8")
    assert load_yaml(path)["tasks"]["t"]["description"] == "aaaa"

    # Different size.
    path.write_text("tasks:\n  t:\n    description: bbbbbbbb\n    expected_output: x\n", encoding="utf-8")
    assert load_yaml(path)["tasks"]["t"]["description"] == "bbbbbbbb"

    # Same size, mtime_ns moved forward.
    stat = path.stat()
    path.write_text("tasks:\n  t:\n    description: cccccccc\n    expected_output: x\n", encoding="utf-8")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
    assert load_yaml(path)["tasks"]["t"]["description"] == "cccccccc"


def test_reload_config_reparses(parse_counter):
    loader = AgentConfigLoader()
    assert parse_counter["n"] == 1
    AgentConfigLoader()
    assert parse_counter["n"] == 1  # served from cache
    loader.reload_config()
    assert parse_counter["n"] == 2


def test_parse_errors_are_not_cached(tmp_path, parse_counter):
    path = tmp_path / "bad.yaml"
    path.write_text("tasks: [unclosed\n  - : :\n", encoding="utf-8")

    for _ in range(2):
        with pytest.raises(yaml.YAMLError):
            TaskConfigLoader(str(path))
    assert parse_counter["n"] == 2

    for _ in range(2):
        with pytest.raises((ValueError, RuntimeError)):
            AgentConfigLoader(str(path))
    assert parse_counter["n"] == 4


def test_factories_share_no_run_bound_objects(serper_key):
    from utils.task_factory import PHASE_OUTPUT_MODELS

    first, second = _make_factory(), _make_factory()
    assert first._tracker_getter is not second._tracker_getter
    assert first._phase_config is not second._phase_config
    for phase in PHASES:
        a, b = first._phase_config[phase], second._phase_config[phase]
        assert a["agent"] is not b["agent"]
        for name, tool in a["flow_tools"].items():
            assert tool is not b["flow_tools"][name]
        task_a = first.build_task(phase, "Technology", "2026-11-16")
        task_b = second.build_task(phase, "Technology", "2026-11-16")
        assert task_a.output_pydantic is PHASE_OUTPUT_MODELS[phase]
        assert task_b.output_pydantic is PHASE_OUTPUT_MODELS[phase]
