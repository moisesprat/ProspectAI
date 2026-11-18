"""Tests for utils.task_factory (phase 5, DEBT-01, D-01)."""
import ast
from pathlib import Path
from unittest.mock import patch

import pytest

import prospect_ai_flow
from prospect_ai_flow import ProspectAIFlow
from utils.task_factory import PHASE_OUTPUT_MODELS, TaskFactory


# ── Flow wiring ────────────────────────────────────────────────────────────────

def test_flow_namespace_holds_the_moved_factory():
    assert prospect_ai_flow.TaskFactory is TaskFactory


def test_flow_imports_the_factory_from_utils():
    tree = ast.parse(Path(prospect_ai_flow.__file__).read_text(encoding="utf-8"))
    imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "utils.task_factory"
    ]
    assert any(alias.name == "TaskFactory" for node in imports for alias in node.names)


def test_patching_the_flow_name_reaches_the_flow(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with patch("prospect_ai_flow.TaskFactory") as factory_cls:
        flow = ProspectAIFlow()
    assert flow._factory is factory_cls.return_value


def test_phase_output_models_cover_every_phase():
    assert list(PHASE_OUTPUT_MODELS) == prospect_ai_flow.PHASES


# ── TaskFactory wiring ─────────────────────────────────────────────────────────

@pytest.fixture
def real_factory(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")
    from utils.task_factory import TaskFactory

    return TaskFactory()


def test_agents_have_no_crewai_retry(real_factory):
    agents = {cfg["agent"] for cfg in real_factory._phase_config.values()}
    assert len(agents) == 5
    assert all(a.max_retry_limit == 0 for a in agents)


def test_build_task_appends_feedback_after_context(real_factory):
    task = real_factory.build_task(
        "technical_analysis", "Technology", "2026-04-29", "=== CTX ===\nctx",
        feedback="FEEDBACK-BLOCK",
    )
    assert task.description.index("=== CTX ===") < task.description.index("FEEDBACK-BLOCK")
    plain = real_factory.build_task("technical_analysis", "Technology", "2026-04-29", "=== CTX ===\nctx")
    assert "FEEDBACK-BLOCK" not in plain.description
