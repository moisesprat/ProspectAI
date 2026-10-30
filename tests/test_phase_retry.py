"""Bounded per-phase schema retries (STALL-04; D-11, D-12).

A phase whose output fails schema validation is retried by the Flow at most
MAX_SCHEMA_RETRIES times with the failing field paths fed back to the model,
then fails with PhaseSchemaError. There is no deterministic fallback (D-12).
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from prospect_ai_flow import MissingToolCallError, ProspectAIFlow
from schemas.agent_outputs import TechnicalAnalysisOutput
from utils.phase_runner import (
    MAX_SCHEMA_RETRIES,
    PhaseOutputError,
    PhaseSchemaError,
    extract_model,
    feedback_from,
    field_paths,
    run_phase,
)

ANTHROPIC_ENV = {
    "ANTHROPIC_API_KEY": "test-key",
    "MODEL": "claude-haiku-4-5-20251001",
    "REDDIT_CLIENT_ID": "test-id",
    "REDDIT_CLIENT_SECRET": "test-secret",
}

ALLOWED_TRENDS = ["Very Weak", "Weak", "Neutral", "Strong", "Very Strong"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _stock(ticker, trend="Strong", risk="Medium"):
    return {
        "ticker": ticker,
        "current_price": 100.0,
        "momentum_analysis": {
            "momentum_score": 5.0,
            "risk_level": risk,
            "trend_strength": trend,
            "key_signals": ["RSI neutral"],
            "support_resistance": {"support": 90.0, "resistance": 110.0},
            "comprehensive_analysis": "x" * 60,
        },
        "technical_score": {"percentage": 50.0, "grade": "B", "recommendation": "Buy"},
        "investment_recommendation": "y" * 60,
    }


def _payload(*stocks):
    return {
        "sector": "Technology",
        "technical_analysis": list(stocks) or [_stock("AAA"), _stock("BBB")],
        "summary": "z" * 120,
    }


def _validation_error(payload):
    with pytest.raises(ValidationError) as info:
        TechnicalAnalysisOutput.model_validate(payload)
    return info.value


def _bad_trend_error():
    return _validation_error(_payload(_stock("AAA"), _stock("BBB", trend="Moderate")))


def _ok_result():
    model = TechnicalAnalysisOutput.model_validate(_payload())
    task_out = SimpleNamespace(pydantic=model, json_dict=None)
    return SimpleNamespace(
        raw=json.dumps(_payload()), tasks_output=[task_out], token_usage=MagicMock()
    )


def _builder():
    """build_task stand-in: records the feedback each attempt received."""
    seen = []

    def build(feedback=""):
        seen.append(feedback)
        desc = "BASE" + (("\n\n" + feedback) if feedback else "")
        return SimpleNamespace(description=desc)

    return build, seen


def _kickoff(*outcomes):
    """async kickoff stand-in: raise exceptions, return results, in order."""
    queue = list(outcomes)
    calls = []

    async def kickoff(task):
        calls.append(task)
        outcome = queue.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    kickoff.calls = calls
    return kickoff


def _run(**kw):
    return asyncio.run(run_phase(phase="technical_analysis", model_cls=TechnicalAnalysisOutput, **kw))


# ── run_phase ──────────────────────────────────────────────────────────────────

def test_constant_is_two_retries():
    assert MAX_SCHEMA_RETRIES == 2


def test_success_first_attempt():
    build, seen = _builder()
    kickoff = _kickoff(_ok_result())
    result, model = _run(build_task=build, kickoff=kickoff)
    assert len(kickoff.calls) == 1
    assert seen == [""]
    assert isinstance(model, TechnicalAnalysisOutput)


def test_retry_with_feedback_then_success():
    build, seen = _builder()
    kickoff = _kickoff(_bad_trend_error(), _ok_result())
    result, model = _run(build_task=build, kickoff=kickoff)
    assert len(kickoff.calls) == 2
    assert seen[0] == ""
    description = kickoff.calls[1].description
    assert "technical_analysis.1.momentum_analysis.trend_strength" in description
    for value in ALLOWED_TRENDS:
        assert f"'{value}'" in description
    assert isinstance(model, TechnicalAnalysisOutput)


def test_case_variant_spends_budget():
    """D-11: no normaliser; a case or whitespace variant is a validation error."""
    lower = _validation_error(_payload(_stock("AAA", trend="strong")))
    padded = _validation_error(_payload(_stock("AAA", risk=" High")))
    assert "trend_strength" in field_paths(lower)[0]
    assert "risk_level" in field_paths(padded)[0]
    build, _ = _builder()
    kickoff = _kickoff(lower, _ok_result())
    _run(build_task=build, kickoff=kickoff)
    assert len(kickoff.calls) == 2


def test_failure_a_regression():
    """Phase 1 Failure A: trend_strength 'Moderate' three times."""
    bad = _validation_error(_payload(*[_stock(t, trend="Moderate") for t in ("AAA", "BBB", "CCC")]))
    build, _ = _builder()
    kickoff = _kickoff(bad, bad, bad)
    with pytest.raises(PhaseSchemaError) as info:
        _run(build_task=build, kickoff=kickoff)
    assert len(kickoff.calls) == 3
    message = str(info.value)
    assert "technical_analysis" in message
    assert "3 attempts" in message
    assert "trend_strength" in message
    assert "Moderate" not in message
    assert len(message) <= 400
    assert info.value.phase == "technical_analysis"
    assert info.value.attempts == 3
    assert any("trend_strength" in f for f in info.value.fields)


def test_error_message_is_capped_for_many_fields():
    many = _validation_error(_payload(*[_stock(f"T{i}", trend="Moderate") for i in range(30)]))
    build, _ = _builder()
    with pytest.raises(PhaseSchemaError) as info:
        _run(build_task=build, kickoff=_kickoff(many, many, many))
    assert len(str(info.value)) <= 400
    assert "technical_analysis" in str(info.value)


def test_wrapped_validation_error_is_retried():
    wrapped = RuntimeError("agent failed")
    wrapped.__cause__ = _bad_trend_error()
    build, _ = _builder()
    kickoff = _kickoff(wrapped, _ok_result())
    _run(build_task=build, kickoff=kickoff)
    assert len(kickoff.calls) == 2


def test_non_schema_error_not_retried():
    build, _ = _builder()
    kickoff = _kickoff(RuntimeError("api down"), _ok_result())
    with pytest.raises(RuntimeError, match="api down"):
        _run(build_task=build, kickoff=kickoff)
    assert len(kickoff.calls) == 1


def test_missing_tool_call_error_is_not_retried():
    build, _ = _builder()
    kickoff = _kickoff(MissingToolCallError("technical_analysis: no tools"), _ok_result())
    with pytest.raises(MissingToolCallError):
        _run(build_task=build, kickoff=kickoff)
    assert len(kickoff.calls) == 1


def test_unparseable_result_is_retried_as_output_error():
    garbage = SimpleNamespace(
        raw="not json at all", tasks_output=[SimpleNamespace(pydantic=None)], token_usage=None
    )
    build, _ = _builder()
    kickoff = _kickoff(garbage, _ok_result())
    _run(build_task=build, kickoff=kickoff)
    assert len(kickoff.calls) == 2


def test_validate_callback_failure_spends_budget():
    calls = []

    def validate(model):
        calls.append(model)
        if len(calls) == 1:
            raise PhaseOutputError("coverage", ["technical_analysis"])

    build, seen = _builder()
    kickoff = _kickoff(_ok_result(), _ok_result())
    _run(build_task=build, kickoff=kickoff, validate=validate)
    assert len(kickoff.calls) == 2
    assert "technical_analysis" in seen[1]


def test_max_retries_zero_means_one_attempt():
    build, _ = _builder()
    kickoff = _kickoff(_bad_trend_error(), _ok_result())
    with pytest.raises(PhaseSchemaError) as info:
        _run(build_task=build, kickoff=kickoff, max_retries=0)
    assert info.value.attempts == 1
    assert len(kickoff.calls) == 1


def test_records_attempts_on_tracker():
    tracker = MagicMock()
    build, _ = _builder()
    _run(build_task=build, kickoff=_kickoff(_bad_trend_error(), _ok_result()), tracker=tracker)
    tracker.record_phase_attempts.assert_called_once_with("technical_analysis", 2)


# ── helpers ────────────────────────────────────────────────────────────────────

def test_feedback_is_bounded_and_names_fields():
    many = _validation_error(_payload(*[_stock(f"T{i}", trend="Moderate") for i in range(30)]))
    text = feedback_from(many.errors())
    lines = text.splitlines()
    assert lines[0].startswith("Your previous answer failed validation")
    assert len(lines) <= 11
    assert all(len(line) <= 200 for line in lines[1:])


def test_extract_model_error_has_no_raw_text():
    result = SimpleNamespace(raw="SECRET-RAW", tasks_output=[SimpleNamespace(pydantic=None)])
    with pytest.raises(PhaseOutputError) as info:
        extract_model(result, TechnicalAnalysisOutput, "technical_analysis")
    assert "SECRET-RAW" not in str(info.value)
    assert "technical_analysis" in str(info.value)


# ── TaskFactory wiring ─────────────────────────────────────────────────────────

@pytest.fixture
def real_factory(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "dummy-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "dummy-secret")
    from prospect_ai_crew import TaskFactory

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


# ── Flow integration (tracer) ──────────────────────────────────────────────────

@pytest.fixture
def flow():
    with patch.dict("os.environ", ANTHROPIC_ENV), \
         patch("prospect_ai_flow.TaskFactory") as MockFactory:
        MockFactory.return_value = MagicMock()
        f = ProspectAIFlow()
        f._tracker = None
        f.state.sector = "Technology"
        f.state.today = "2026-04-29"
        yield f


def _task():
    task = MagicMock()
    task.agent.llm.model = "claude-haiku-4-5-20251001"
    task.tools = []
    return task


def test_run_analysis_error_carries_phase_and_partial_metrics(flow):
    bad = _validation_error(_payload(*[_stock(t, trend="Moderate") for t in ("AAA", "BBB", "CCC")]))
    flow._factory.build_task.return_value = _task()
    flow.kickoff = lambda inputs=None: asyncio.run(flow.technical_analysis())
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=[bad, bad, bad])
        with pytest.raises(PhaseSchemaError) as info:
            flow.run_analysis({"sector": "Technology"})
    assert mc.return_value.akickoff.await_count == 3
    message = str(info.value)
    assert "technical_analysis" in message and "trend_strength" in message
    pm = info.value.partial_metrics
    assert pm["partial"] is True
    technical = next(p for p in pm["phases"] if p["name"] == "technical_analysis")
    assert technical["status"] != "not_started"


def test_flow_retry_passes_feedback_to_build_task(flow):
    bad = _bad_trend_error()
    flow._factory.build_task.return_value = _task()
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=[bad, _ok_result()])
        asyncio.run(flow.technical_analysis())
    first, second = flow._factory.build_task.call_args_list
    assert "feedback" not in first.kwargs
    assert "trend_strength" in second.kwargs["feedback"]
    assert isinstance(flow.state.technical_output, TechnicalAnalysisOutput)
