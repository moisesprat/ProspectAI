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


def _wire_technical(flow):
    """The technical phase is Flow-owned (plan 02-15): it needs candidates and a flow tool."""
    from tests.test_llm_role_audit import market_output, tech_tools, wire_tools

    flow.state.market_output = market_output()
    wire_tools(flow, tech_tools(), phase="technical_analysis")


def _technical_ok_result():
    """A complete technical narrative answer (what the LLM now produces)."""
    from tests.test_llm_role_audit import narrative_result, tech_narrative_entry, tech_payload

    return narrative_result(tech_payload(tech_narrative_entry("AAA")))


def test_run_analysis_error_carries_phase_and_partial_metrics(flow):
    bad = _validation_error(_payload(*[_stock(t, trend="Moderate") for t in ("AAA", "BBB", "CCC")]))
    flow._factory.build_task.return_value = _task()
    _wire_technical(flow)
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
    _wire_technical(flow)
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=[bad, _technical_ok_result()])
        asyncio.run(flow.technical_analysis())
    first, second = flow._factory.build_task.call_args_list
    assert "feedback" not in first.kwargs
    assert "trend_strength" in second.kwargs["feedback"]
    assert isinstance(flow.state.technical_output, TechnicalAnalysisOutput)


# ── All six phases through run_phase (plan 02-12 task 2) ───────────────────────

from schemas.agent_outputs import (  # noqa: E402
    CriticOutput,
    FundamentalNarrativeOutput,
    InvestorStrategicOutput,
    MarketNarrativeOutput,
    StrategyNarrativeOutput,
    TechnicalNarrativeOutput,
)
from tests.test_llm_role_audit import (  # noqa: E402
    draft_entry,
    draft_payload,
    market_output,
    market_tools,
    mkt_entry,
    mkt_payload,
    narrative_entry,
    narrative_payload,
    prime_draft,
    stub_tools,
    tech_narrative_entry,
    tech_payload,
    tech_tools,
    wire_tools,
)
from tests.test_schemas import _portfolio  # noqa: E402
from utils.execution_tracker import ExecutionTracker  # noqa: E402

_PHASE_METHODS = [
    ("market_analysis", MarketNarrativeOutput),
    ("technical_analysis", TechnicalNarrativeOutput),
    ("fundamental_analysis", FundamentalNarrativeOutput),
    ("draft_strategy", StrategyNarrativeOutput),
    ("critique_review", CriticOutput),
    ("final_strategy", InvestorStrategicOutput),
]


def _stub_result(schema):
    """Crew result whose pydantic payload is a spec'd stand-in for ``schema``."""
    if schema is MarketNarrativeOutput:
        # A real model: the Flow-owned market phase checks the pick against the Reddit corpus.
        model = MarketNarrativeOutput.model_validate(mkt_payload(mkt_entry("AAA")))
    elif schema is FundamentalNarrativeOutput:
        # A real model: the Flow-owned fundamental phase checks narrative coverage.
        model = FundamentalNarrativeOutput.model_validate(narrative_payload(narrative_entry("AAA")))
    elif schema is TechnicalNarrativeOutput:
        # A real model: the Flow-owned technical phase checks narrative coverage.
        model = TechnicalNarrativeOutput.model_validate(tech_payload(tech_narrative_entry("AAA")))
    elif schema is StrategyNarrativeOutput:
        # A real model: the Flow-owned draft phase checks position coverage (tracked_flow primes AAA and BBB).
        model = StrategyNarrativeOutput.model_validate(draft_payload(draft_entry("AAA"), draft_entry("BBB")))
    else:
        model = MagicMock(spec=schema)
    task_out = SimpleNamespace(pydantic=model, json_dict=None)
    return SimpleNamespace(raw="{}", tasks_output=[task_out], token_usage=MagicMock())


def _patch_context(flow):
    stack = [
        patch.object(flow, "_slim_market_for_analysis", return_value=""),
        patch.object(flow, "_slim_market_for_strategy", return_value=""),
        patch.object(flow, "_slim_technical", return_value=""),
        patch.object(flow, "_slim_fundamental", return_value=""),
        patch.object(flow, "_slim_draft", return_value=""),
        patch.object(flow, "_critic_reference_table", return_value=""),
        patch.object(flow, "_gated_slim_critique", return_value=""),
    ]
    for p in stack:
        p.start()
    return stack


@pytest.fixture
def tracked_flow(flow):
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    flow._factory.build_task.return_value = _task()
    # The market, fundamental, technical and draft phases are Flow-owned (plans 02-16, 02-13,
    # 02-15, 02-17): they need flow tools, and the later ones need candidates and prior outputs.
    flow.state.market_output = market_output()
    draft = prime_draft(flow)
    wire_tools(flow, {**stub_tools(), **tech_tools(), **market_tools(), **draft})
    stack = _patch_context(flow)
    yield flow
    for p in stack:
        p.stop()


def _phase_metrics(flow, phase):
    return next(p for p in flow._tracker.to_dict()["phases"] if p["name"] == phase)


@pytest.mark.parametrize("phase,schema", _PHASE_METHODS)
def test_each_phase_uses_run_phase(tracked_flow, phase, schema):
    flow = tracked_flow
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=[_bad_trend_error(), _stub_result(schema)])
        asyncio.run(getattr(flow, phase)())
    assert mc.return_value.akickoff.await_count == 2
    assert _phase_metrics(flow, phase)["attempts"] == 2
    assert _phase_metrics(flow, phase)["status"] == "completed"


@pytest.mark.parametrize("phase,schema", _PHASE_METHODS)
def test_each_phase_fails_after_three_attempts(tracked_flow, phase, schema):
    flow = tracked_flow
    bad = _bad_trend_error()
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=[bad, bad, bad, _stub_result(schema)])
        with pytest.raises(PhaseSchemaError) as info:
            asyncio.run(getattr(flow, phase)())
    assert mc.return_value.akickoff.await_count == 3
    assert info.value.phase == phase


def test_final_phase_validated(tracked_flow):
    """An invalid final payload exhausts retries; there is no lenient parse fallback (D-12)."""
    flow = tracked_flow
    payload = _portfolio().model_dump(mode="json")
    payload["positions"][0]["action"] = "HOLD"
    task_out = SimpleNamespace(pydantic=None, json_dict=None)
    invalid = SimpleNamespace(raw=json.dumps(payload), tasks_output=[task_out], token_usage=MagicMock())
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(return_value=invalid)
        with pytest.raises(PhaseSchemaError) as info:
            asyncio.run(flow.final_strategy())
    assert mc.return_value.akickoff.await_count == 3
    assert "final_strategy" in str(info.value)
    assert "HOLD" not in str(info.value)
    assert flow.state.final_output is None


def test_final_phase_stores_validated_model_and_run_analysis_uses_it(flow):
    valid = _portfolio()
    task_out = SimpleNamespace(pydantic=None, json_dict=None)
    result = SimpleNamespace(raw=valid.model_dump_json(), tasks_output=[task_out], token_usage=MagicMock())
    flow._factory.build_task.return_value = _task()
    seen = {}

    def kickoff(inputs=None):
        with patch.object(flow, "_make_crew") as mc, \
             patch.object(flow, "_slim_draft", return_value=""), \
             patch.object(flow, "_gated_slim_critique", return_value=""):
            mc.return_value.akickoff = AsyncMock(return_value=result)
            asyncio.run(flow.final_strategy())

    def finalize(structured, risk_profile):
        seen["structured"] = structured
        return structured

    flow.kickoff = kickoff
    with patch.object(flow, "_finalize_and_validate_portfolio", side_effect=finalize):
        flow.run_analysis({"sector": "Technology"})
    assert isinstance(flow.state.final_output, InvestorStrategicOutput)
    assert seen["structured"] == flow.state.final_output.model_dump(mode="json")
    assert "parse_error" not in seen["structured"]


def test_run_analysis_without_final_output_fails_clearly(flow):
    flow.kickoff = lambda inputs=None: None
    with pytest.raises(RuntimeError, match="final_strategy"):
        flow.run_analysis({"sector": "Technology"})


def test_draft_and_final_budgets_independent(tracked_flow):
    flow = tracked_flow
    bad = _bad_trend_error()
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=[
            bad, bad, _stub_result(StrategyNarrativeOutput),   # draft: 2 failures, then ok
            bad, bad, _stub_result(InvestorStrategicOutput),   # final: full budget again
        ])
        asyncio.run(flow.draft_strategy())
        asyncio.run(flow.final_strategy())
    assert _phase_metrics(flow, "draft_strategy")["attempts"] == 3
    assert _phase_metrics(flow, "final_strategy")["attempts"] == 3


def test_attempts_in_metrics(tracked_flow):
    flow = tracked_flow
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(return_value=_stub_result(CriticOutput))
        asyncio.run(flow.critique_review())
    phases = flow._tracker.to_dict()["phases"]
    assert all(isinstance(p["attempts"], int) for p in phases)
    assert _phase_metrics(flow, "critique_review")["attempts"] == 1
    assert _phase_metrics(flow, "market_analysis")["attempts"] == 0


def test_emit_order_unchanged_with_a_retry(flow):
    events = []
    flow._progress_callback = events.append
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    task = _task()

    def build_task(*args, **kwargs):
        events.append({"event": "build_task"})
        return task

    flow._factory.build_task.side_effect = build_task
    _wire_technical(flow)
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=[_bad_trend_error(), _technical_ok_result()])
        asyncio.run(flow.technical_analysis())
    assert [e["event"] for e in events] == ["agent_start", "build_task", "build_task", "task_complete"]
    assert sum(e["event"] == "agent_start" for e in events) == 1
    assert sum(e["event"] == "task_complete" for e in events) == 1


# ── Tool-call guard through the retry path (plan 02-03 contract) ───────────────

def _tool_task(name="TA"):
    task = _task()
    task.tools = [SimpleNamespace(name=name)]
    return task


def _critic_ok_result():
    model = CriticOutput(
        sector="Technology", draft_assessment="d" * 60, portfolio_level_issues=[], approved_positions=[],
    )
    task_out = SimpleNamespace(pydantic=model, json_dict=None)
    return SimpleNamespace(raw=model.model_dump_json(), tasks_output=[task_out], token_usage=MagicMock())


def _run_tool_phase(flow, akickoff):
    """The per-attempt tool-call guard lives in _run_phase, so it applies to any task that carries tools.

    No phase gives its agent tools any more (CORR-10): the guard is exercised on a phase body that
    calls _run_phase directly with a tool-carrying task.
    """
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = akickoff
        return asyncio.run(flow._run_phase("critique_review", 4, CriticOutput))


def test_retry_cannot_pass_on_an_earlier_attempts_tool_calls(flow):
    """Attempt 1 calls the tool and fails schema; attempt 2 calls nothing -> MissingToolCallError."""
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    flow._factory.build_task.return_value = _tool_task()
    calls = {"n": 0}

    async def akickoff():
        calls["n"] += 1
        if calls["n"] == 1:
            flow._tracker.record_tool_call("critique_review", "TA", 0.0, 1.0, True)
            raise _bad_trend_error()
        return _critic_ok_result()

    with pytest.raises(MissingToolCallError, match="critique_review"):
        _run_tool_phase(flow, akickoff)
    assert calls["n"] == 2


def test_retry_with_tool_calls_in_each_attempt_passes(flow):
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    flow._factory.build_task.return_value = _tool_task()
    calls = {"n": 0}

    async def akickoff():
        calls["n"] += 1
        flow._tracker.record_tool_call("critique_review", "TA", 0.0, 1.0, True)
        if calls["n"] == 1:
            raise _bad_trend_error()
        return _critic_ok_result()

    _result, model = _run_tool_phase(flow, akickoff)
    assert calls["n"] == 2
    assert isinstance(model, CriticOutput)
