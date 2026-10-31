"""Unit tests for individual ProspectAIFlow phase methods (F-08)."""
import asyncio
import json
import threading
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from prospect_ai_flow import MissingToolCallError, ProspectAIFlow, _parse_crew_result
from utils.execution_tracker import ExecutionTracker
from schemas.agent_outputs import (
    MarketAnalysisOutput,
    TechnicalAnalysisOutput,
    FundamentalAnalysisOutput,
    InvestorStrategicOutput,
    CriticOutput,
)

ANTHROPIC_ENV = {
    "ANTHROPIC_API_KEY": "test-key",
    "MODEL": "claude-haiku-4-5-20251001",
    "REDDIT_CLIENT_ID": "test-id",
    "REDDIT_CLIENT_SECRET": "test-secret",
}


def _make_crew_result(pydantic_out=None, raw="{}"):
    task_out = MagicMock()
    task_out.pydantic = pydantic_out
    task_out.json_dict = None
    result = MagicMock()
    result.raw = raw
    result.tasks_output = [task_out]
    result.token_usage = MagicMock()
    return result


def _make_task():
    task = MagicMock()
    task.agent.llm.model = "claude-haiku-4-5-20251001"
    return task


def _final_stub(payload=None):
    """Stand-in for the validated final output that run_analysis serialises."""
    stub = MagicMock(spec=InvestorStrategicOutput)
    stub.model_dump.return_value = payload if payload is not None else {"positions": []}
    return stub


@pytest.fixture
def flow():
    """ProspectAIFlow with TaskFactory patched out — no live LLM or network calls."""
    with patch.dict("os.environ", ANTHROPIC_ENV), \
         patch("prospect_ai_flow.TaskFactory") as MockFactory:
        factory_instance = MagicMock()
        MockFactory.return_value = factory_instance
        f = ProspectAIFlow()
        f._tracker = None
        f.state.sector = "Technology"
        f.state.today = "2026-04-29"
        yield f


# ─── _check_error ──────────────────────────────────────────────────────────────

class TestCheckError:
    def test_raises_on_error_state(self, flow):
        flow.state.error = "upstream failure"
        with pytest.raises(RuntimeError, match="upstream failure"):
            flow._check_error()

    def test_noop_on_empty_error(self, flow):
        flow.state.error = ""
        flow._check_error()  # must not raise


# ─── _extract_pydantic ─────────────────────────────────────────────────────────

class TestExtractPydantic:
    def test_uses_pydantic_field_when_present(self, flow):
        model = MagicMock(spec=MarketAnalysisOutput)
        result = _make_crew_result(pydantic_out=model)
        out = ProspectAIFlow._extract_pydantic(result, MarketAnalysisOutput, "market_analysis")
        assert out is model

    def test_falls_back_to_raw_json(self, flow):
        payload = {
            "sector": "Technology",
            "summary": "Apple leads the Technology sector with strong institutional interest and robust earnings momentum driving bullish sentiment.",
            "candidate_stocks": [{
                "ticker": "AAPL",
                "mention_count": 10,
                "average_sentiment": 0.5,
                "relevance_score": 0.8,
                "rationale": "Strong earnings growth and ecosystem lock-in make AAPL a compelling candidate for this analysis cycle.",
            }],
        }
        task_out = MagicMock()
        task_out.pydantic = None
        result = MagicMock()
        result.raw = json.dumps(payload)
        result.tasks_output = [task_out]
        out = ProspectAIFlow._extract_pydantic(result, MarketAnalysisOutput, "market_analysis")
        assert out.sector == "Technology"
        assert out.candidate_stocks[0].ticker == "AAPL"

    def test_raises_on_invalid_raw(self, flow):
        task_out = MagicMock()
        task_out.pydantic = None
        result = MagicMock()
        result.raw = "not json at all"
        result.tasks_output = [task_out]
        with pytest.raises(RuntimeError, match="market_analysis: output failed schema validation") as info:
            ProspectAIFlow._extract_pydantic(result, MarketAnalysisOutput, "market_analysis")
        assert "not json at all" not in str(info.value)


# ─── _emit_progress ────────────────────────────────────────────────────────────

class TestEmitProgress:
    def test_fires_callback_with_correct_fields(self, flow):
        events = []
        flow._progress_callback = events.append
        mock_result = MagicMock()
        mock_result.raw = "test output"
        mock_result.tasks_output = []
        flow._emit_progress(0, mock_result)
        assert len(events) == 1
        evt = events[0]
        assert evt["event"] == "task_complete"
        assert evt["task_index"] == 0
        assert evt["agent"] == "MarketAnalyst"
        assert evt["preview"] == "test output"

    def test_noop_without_callback(self, flow):
        flow._progress_callback = None
        mock_result = MagicMock()
        mock_result.raw = "output"
        mock_result.tasks_output = []
        flow._emit_progress(0, mock_result)  # must not raise


# ─── _parse_crew_result ────────────────────────────────────────────────────────

class TestParsCrewResult:
    def test_parses_plain_json(self):
        result = MagicMock()
        result.json_dict = None
        result.tasks_output = None
        result.raw = json.dumps({"sector": "Technology", "positions": []})
        out = _parse_crew_result(result)
        assert out["sector"] == "Technology"

    def test_json_dict_shortcut(self):
        result = MagicMock()
        result.json_dict = {"sector": "Finance"}
        out = _parse_crew_result(result)
        assert out["sector"] == "Finance"

    def test_strips_markdown_fences(self):
        result = MagicMock()
        result.json_dict = None
        result.tasks_output = None
        result.raw = "```json\n" + json.dumps({"sector": "Energy"}) + "\n```"
        out = _parse_crew_result(result)
        assert out["sector"] == "Energy"

    def test_parse_error_on_bad_raw(self):
        result = MagicMock()
        result.json_dict = None
        result.tasks_output = None
        result.raw = "not json"
        out = _parse_crew_result(result)
        assert out.get("parse_error") is True


# ─── Phase methods ─────────────────────────────────────────────────────────────

class TestMarketAnalysisPhase:
    @pytest.mark.asyncio
    async def test_updates_market_output(self, flow):
        from tests.test_llm_role_audit import (
            market_tools, mkt_entry, mkt_payload, narrative_result, wire_tools,
        )

        wire_tools(flow, market_tools(), phase="market_analysis")
        flow._factory.build_task.return_value = _make_task()
        crew_result = narrative_result(mkt_payload(mkt_entry("AAA")))
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            await flow.market_analysis()
        assert isinstance(flow.state.market_output, MarketAnalysisOutput)
        assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["AAA"]
        args = flow._factory.build_task.call_args
        assert args.args[:3] == ("market_analysis", "Technology", "2026-04-29")
        assert "Market Data (collected by the pipeline)" in args.args[3]

    @pytest.mark.asyncio
    async def test_aborts_on_error_state(self, flow):
        flow.state.error = "upstream failure"
        with pytest.raises(RuntimeError, match="upstream failure"):
            await flow.market_analysis()


class TestTechnicalAnalysisPhase:
    @pytest.mark.asyncio
    async def test_updates_technical_output(self, flow):
        from tests.test_llm_role_audit import (
            market_output, tech_narrative_entry, tech_payload, narrative_result,
            tech_tools, wire_tools,
        )
        flow.state.market_output = market_output()
        wire_tools(flow, tech_tools(), phase="technical_analysis")
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(
                return_value=narrative_result(tech_payload(tech_narrative_entry("AAA")))
            )
            await flow.technical_analysis()
        assert isinstance(flow.state.technical_output, TechnicalAnalysisOutput)
        assert [a.ticker for a in flow.state.technical_output.technical_analysis] == ["AAA"]
        assert [f.ticker for f in flow.state.technical_output.failed_tickers] == ["BBB"]

    @pytest.mark.asyncio
    async def test_aborts_on_error_state(self, flow):
        flow.state.error = "fail"
        with pytest.raises(RuntimeError):
            await flow.technical_analysis()

    @pytest.mark.asyncio
    async def test_no_candidates_fails_clearly(self, flow):
        flow.state.market_output = None
        with pytest.raises(RuntimeError, match="technical_analysis"):
            await flow.technical_analysis()


class TestFundamentalAnalysisPhase:
    @pytest.mark.asyncio
    async def test_updates_fundamental_output(self, flow):
        from tests.test_llm_role_audit import (
            market_output, narrative_entry, narrative_payload, narrative_result,
            stub_tools, wire_tools,
        )
        flow.state.market_output = market_output()
        wire_tools(flow, stub_tools())
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(
                return_value=narrative_result(narrative_payload(narrative_entry("AAA")))
            )
            await flow.fundamental_analysis()
        assert isinstance(flow.state.fundamental_output, FundamentalAnalysisOutput)
        assert [a.ticker for a in flow.state.fundamental_output.fundamental_analysis] == ["AAA", "BBB"]


class TestDraftStrategyPhase:
    @pytest.mark.asyncio
    async def test_updates_draft_output(self, flow):
        from tests.test_llm_role_audit import (
            draft_entry, draft_payload, narrative_result, prime_draft, wire_tools,
        )
        wire_tools(flow, prime_draft(flow), phase="draft_strategy")
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(
                return_value=narrative_result(draft_payload(draft_entry("AAA"), draft_entry("BBB")))
            )
            await flow.draft_strategy()
        assert isinstance(flow.state.draft_output, InvestorStrategicOutput)
        assert [p.ticker for p in flow.state.draft_output.positions] == ["AAA", "BBB"]

    @pytest.mark.asyncio
    async def test_aborts_on_error_state(self, flow):
        flow.state.error = "upstream failure"
        with pytest.raises(RuntimeError, match="upstream failure"):
            await flow.draft_strategy()


class TestCritiqueReviewPhase:
    @pytest.mark.asyncio
    async def test_updates_critique_output(self, flow):
        pydantic_out = MagicMock(spec=CriticOutput)
        crew_result = _make_crew_result(pydantic_out=pydantic_out)
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            await flow.critique_review()
        assert flow.state.critique_output is pydantic_out


class TestFinalStrategyPhase:
    @pytest.mark.asyncio
    async def test_stores_validated_final_output(self, flow):
        pydantic_out = MagicMock(spec=InvestorStrategicOutput)
        crew_result = _make_crew_result(pydantic_out=pydantic_out)
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            await flow.final_strategy()
        assert flow.state.final_output is pydantic_out

    @pytest.mark.asyncio
    async def test_aborts_on_error_state(self, flow):
        flow.state.error = "upstream failure"
        with pytest.raises(RuntimeError, match="upstream failure"):
            await flow.final_strategy()


# ─── Partial metrics on failure (STALL-01, D-04) ──────────────────────────────

class TestPartialMetrics:
    def _failing_kickoff(self, flow):
        import time

        def kickoff(inputs=None):
            flow._tracker.start_phase("market_analysis")
            t0 = time.perf_counter()
            time.sleep(0.01)
            flow._tracker.record_tool_call(
                "market_analysis", "Search", t0, time.perf_counter(), False, "TimeoutError", None
            )
            time.sleep(0.01)
            raise RuntimeError("boom")

        return kickoff

    def test_kickoff_failure_attaches_partial_metrics(self, flow):
        flow.kickoff = self._failing_kickoff(flow)
        with pytest.raises(RuntimeError, match="boom") as info:
            flow.run_analysis({"sector": "Technology"})
        pm = info.value.partial_metrics
        assert pm["partial"] is True
        market = next(p for p in pm["phases"] if p["name"] == "market_analysis")
        assert market["status"] == "running"
        assert market["elapsed_sec"] > 0
        assert [c["tool"] for c in pm["tool_calls"]] == ["Search"]
        assert pm["tool_calls"][0]["error"] == "TimeoutError"
        assert pm["pipeline_elapsed_sec"] > 0

    def test_metrics_snapshot_none_before_run_and_partial_after_failure(self, flow):
        assert flow.metrics_snapshot() is None
        flow.kickoff = self._failing_kickoff(flow)
        with pytest.raises(RuntimeError):
            flow.run_analysis({"sector": "Technology"})
        snap = flow.metrics_snapshot()
        assert snap["partial"] is True
        assert len(snap["tool_calls"]) == 1

    def test_post_kickoff_failure_also_carries_partial_metrics(self, flow):
        from utils.portfolio_bounds_validator import BoundsViolationError

        def kickoff(inputs=None):
            flow._tracker.start_phase("final_strategy")
            flow.state.final_output = _final_stub()

        flow.kickoff = kickoff
        with patch.object(
                 flow, "_finalize_and_validate_portfolio",
                 side_effect=BoundsViolationError(
                     [{"ticker": "AAA", "rule": "max_allocation", "expected": 10, "actual": 20}]
                 ),
             ):
            with pytest.raises(BoundsViolationError) as info:
                flow.run_analysis({"sector": "Technology"})
        assert info.value.partial_metrics["partial"] is True

    def test_unattachable_exception_still_propagates_unchanged(self, flow, caplog):
        import logging

        class Sealed(Exception):
            def __setattr__(self, name, value):
                raise AttributeError("sealed")

        def kickoff(inputs=None):
            raise Sealed("sealed-failure")

        flow.kickoff = kickoff
        with caplog.at_level(logging.WARNING, logger="prospect_ai_flow"):
            with pytest.raises(Sealed, match="sealed-failure"):
                flow.run_analysis({"sector": "Technology"})
        assert any("could not attach partial_metrics" in r.getMessage() for r in caplog.records)

    def test_success_is_not_partial_and_includes_finalize_time(self, flow):
        import time

        def slow_finalize(structured, risk_profile):
            time.sleep(0.05)
            return {"positions": [], "overall_strategy": "ok"}

        def kickoff(inputs=None):
            flow.state.final_output = _final_stub()

        flow.kickoff = kickoff
        with patch.object(flow, "_finalize_and_validate_portfolio", side_effect=slow_finalize):
            out = flow.run_analysis({"sector": "Technology"})
        metrics = out["execution_metrics"]
        assert metrics["partial"] is False
        assert metrics["pipeline_elapsed_sec"] >= 0.05


# ─── Tool-call guard (plan 02-03, RESEARCH Pitfall 1 and 2d) ──────────────────

def _tool(name):
    from types import SimpleNamespace
    return SimpleNamespace(name=name)


def _task_with_tools(*names):
    task = _make_task()
    task.tools = [_tool(n) for n in names]
    return task


class TestToolCallCount:
    def test_counts_per_phase_and_zero_when_none(self):
        tracker = ExecutionTracker()
        tracker.record_tool_call("market_analysis", "Search", 0.0, 1.0, True)
        tracker.record_tool_call("market_analysis", "Reddit", 0.0, 1.0, False, "TimeoutError")
        tracker.record_tool_call("technical_analysis", "TA", 0.0, 1.0, True)
        assert tracker.tool_call_count("market_analysis") == 2
        assert tracker.tool_call_count("technical_analysis") == 1
        assert tracker.tool_call_count("draft_strategy") == 0


class TestToolCallGuard:
    def test_tool_phase_without_tool_calls_fails(self, flow):
        flow._tracker = ExecutionTracker()
        task = _task_with_tools("Reddit Sentiment", "Search")
        with pytest.raises(MissingToolCallError) as info:
            flow._require_tool_calls("market_analysis", task)
        msg = str(info.value)
        assert "market_analysis" in msg
        assert "Reddit Sentiment" in msg and "Search" in msg
        assert isinstance(info.value, RuntimeError)

    def test_tool_phase_with_tool_calls_passes(self, flow):
        flow._tracker = ExecutionTracker()
        flow._tracker.record_tool_call("market_analysis", "Search", 0.0, 1.0, True)
        flow._require_tool_calls("market_analysis", _task_with_tools("Search"))

    def test_failed_tool_call_still_counts_as_a_call(self, flow):
        flow._tracker = ExecutionTracker()
        flow._tracker.record_tool_call("market_analysis", "Search", 0.0, 1.0, False, "TimeoutError")
        flow._require_tool_calls("market_analysis", _task_with_tools("Search"))

    def test_toolless_phase_not_checked(self, flow):
        flow._tracker = ExecutionTracker()
        task = _make_task()
        task.tools = []
        flow._require_tool_calls("critique_review", task)
        flow._require_tool_calls("final_strategy", task)

    def test_none_tracker_skips_guard(self, flow):
        flow._tracker = None
        flow._require_tool_calls("market_analysis", _task_with_tools("Search"))

    def test_other_phase_calls_do_not_satisfy_the_guard(self, flow):
        flow._tracker = ExecutionTracker()
        flow._tracker.record_tool_call("technical_analysis", "TA", 0.0, 1.0, True)
        with pytest.raises(MissingToolCallError):
            flow._require_tool_calls("market_analysis", _task_with_tools("Search"))

    @pytest.mark.asyncio
    async def test_the_guard_runs_for_any_phase_whose_task_carries_tools(self, flow):
        """No phase gives its agent tools any more (CORR-10), but _run_phase still enforces the guard."""
        flow._tracker = ExecutionTracker()
        flow._tracker.start()
        flow._factory.build_task.return_value = _task_with_tools("Tool")
        crew_result = _make_crew_result(pydantic_out=MagicMock(spec=CriticOutput))
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            with pytest.raises(MissingToolCallError, match="critique_review"):
                await flow._run_phase("critique_review", 4, CriticOutput)

    def test_no_phase_gives_its_agent_tools(self, monkeypatch):
        """Every phase is Flow-owned or tool-less: the LLM never calls a tool, so it cannot skip one."""
        monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")
        monkeypatch.setenv("REDDIT_CLIENT_ID", "dummy-id")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "dummy-secret")
        from prospect_ai_crew import TaskFactory

        factory = TaskFactory()
        for phase, cfg in factory._phase_config.items():
            assert cfg["agent_tools"] == [], phase

    @pytest.mark.asyncio
    async def test_toolless_critic_and_final_bodies_run_with_tracker(self, flow):
        flow._tracker = ExecutionTracker()
        flow._tracker.start()
        task = _make_task()
        task.tools = []
        flow._factory.build_task.return_value = task
        crew_result = _make_crew_result(pydantic_out=MagicMock(spec=CriticOutput), raw="{}")
        with patch.object(flow, "_make_crew") as mc, \
             patch.object(flow, "_slim_draft", return_value=""), \
             patch.object(flow, "_critic_reference_table", return_value=""), \
             patch.object(flow, "_gated_slim_critique", return_value=""):
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            await flow.critique_review()
            await flow.final_strategy()
        assert flow.state.final_output is not None

    def test_run_analysis_attaches_partial_metrics_to_missing_tool_call(self, flow):
        def kickoff(inputs=None):
            flow._tracker.start_phase("market_analysis")
            raise MissingToolCallError("market_analysis: the agent finished without calling any of its tools (Search)")

        flow.kickoff = kickoff
        with pytest.raises(MissingToolCallError) as info:
            flow.run_analysis({"sector": "Technology"})
        assert info.value.partial_metrics["partial"] is True


# ─── Flow-owned phases keep the SSE step contract (plan 02-13, D-16) ──────────

class TestFlowOwnedStepContract:
    """agent_start first, tool steps with tool/tool_input/log, one task_complete."""

    @staticmethod
    def _wire(flow, *results):
        from tests.test_llm_role_audit import market_output, stub_tools, wire_tools

        events = []
        flow._progress_callback = lambda payload: events.append(("progress", payload))
        flow._step_callback = lambda index, step: events.append(("step", index, step))
        flow.state.market_output = market_output()
        wire_tools(flow, stub_tools())
        flow._factory.build_task.return_value = _make_task()
        return events

    @staticmethod
    def _run(flow, *results):
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(side_effect=list(results))
            asyncio.run(flow.fundamental_analysis())

    def test_fundamental_emits_contract_sequence(self, flow):
        from tests.test_llm_role_audit import narrative_entry, narrative_payload, narrative_result

        events = self._wire(flow)
        self._run(flow, narrative_result(narrative_payload(narrative_entry("AAA"))))

        kinds = [e[0] if e[0] == "step" else e[1]["event"] for e in events]
        assert kinds == ["agent_start", "step", "step", "task_complete"]
        assert events[0][1]["task_index"] == 2
        steps = [e for e in events if e[0] == "step"]
        assert [s[2].tool for s in steps] == ["fetch_fundamental_data", "grade_fundamental_data"]
        for _kind, phase_index, step in steps:
            assert phase_index == 2
            assert isinstance(step.tool_input, str) and len(step.tool_input) <= 400
            assert isinstance(step.log, str) and step.log
        done = events[-1][1]
        assert done["task_index"] == 2
        published = json.dumps(flow.state.fundamental_output.model_dump(mode="json"))
        assert published.startswith(done["preview"])
        assert set(done) >= {"event", "task_index", "agent", "preview", "tokens_est", "output_len"}

    def test_draft_emits_contract_sequence(self, flow):
        from tests.test_llm_role_audit import (
            draft_entry, draft_payload, narrative_result, prime_draft, wire_tools,
        )

        events = []
        flow._progress_callback = lambda payload: events.append(("progress", payload))
        flow._step_callback = lambda index, step: events.append(("step", index, step))
        wire_tools(flow, prime_draft(flow), phase="draft_strategy")
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(
                return_value=narrative_result(draft_payload(draft_entry("AAA"), draft_entry("BBB")))
            )
            asyncio.run(flow.draft_strategy())

        kinds = [e[0] if e[0] == "step" else e[1]["event"] for e in events]
        assert kinds == ["agent_start", "step", "step", "task_complete"]
        assert events[0][1]["task_index"] == 3
        steps = [e for e in events if e[0] == "step"]
        assert [s[2].tool for s in steps] == ["compute_composite_scores", "allocate_portfolio"]
        assert [s[2].log for s in steps] == ["Scoring 2 tickers", "Allocating capital"]
        for _kind, phase_index, step in steps:
            assert phase_index == 3
            assert isinstance(step.tool_input, str) and len(step.tool_input) <= 400
        done = events[-1][1]
        assert done["task_index"] == 3
        published = json.dumps(flow.state.draft_output.model_dump(mode="json"))
        assert published.startswith(done["preview"])
        assert set(done) >= {"event", "task_index", "agent", "preview", "tokens_est", "output_len"}

    def test_retry_does_not_duplicate_events(self, flow):
        from tests.test_llm_role_audit import narrative_entry, narrative_payload, narrative_result

        events = self._wire(flow)
        self._run(
            flow,
            narrative_result(narrative_payload(narrative_entry("BBB"))),
            narrative_result(narrative_payload(narrative_entry("AAA"))),
        )
        kinds = [e[0] if e[0] == "step" else e[1]["event"] for e in events]
        assert kinds.count("agent_start") == 1
        assert kinds.count("task_complete") == 1
        assert kinds.count("step") == 2
        assert kinds[0] == "agent_start" and kinds[-1] == "task_complete"


# ─── Technical phase: SSE contract and overlap with fundamental (plan 02-15, D-16, STALL-02) ──

class TestTechnicalFlowOwned:
    def test_technical_emits_contract_sequence(self, flow):
        from tests.test_llm_role_audit import (
            market_output, narrative_result, tech_narrative_entry, tech_payload, tech_tools, wire_tools,
        )

        events = []
        flow._progress_callback = lambda payload: events.append(("progress", payload))
        flow._step_callback = lambda index, step: events.append(("step", index, step))
        flow.state.market_output = market_output()
        wire_tools(flow, tech_tools(), phase="technical_analysis")
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(
                side_effect=[narrative_result(tech_payload(tech_narrative_entry("AAA")))]
            )
            asyncio.run(flow.technical_analysis())

        kinds = [e[0] if e[0] == "step" else e[1]["event"] for e in events]
        assert kinds == ["agent_start", "step", "task_complete"]
        assert events[0][1]["task_index"] == 1
        _kind, phase_index, step = events[1]
        assert phase_index == 1
        assert step.tool == "calculate_technical_indicators"
        assert isinstance(step.tool_input, str) and len(step.tool_input) <= 400
        assert isinstance(step.log, str) and step.log
        done = events[-1][1]
        assert done["task_index"] == 1
        published = json.dumps(flow.state.technical_output.model_dump(mode="json"))
        assert published.startswith(done["preview"])
        assert set(done) >= {"event", "task_index", "agent", "preview", "tokens_est", "output_len"}

    def test_technical_and_fundamental_tools_overlap(self, flow):
        """STALL-02: both phases' tool calls are in flight at the same time.

        Each stub tool waits on a shared two-party barrier. If the phases (or the
        tool calls) ran one after the other, the first would time out alone and the
        barrier would break.
        """
        from tests.test_llm_role_audit import (
            FETCH_JSON, GRADES_JSON, TECH_RESULT, StubTool, market_output, narrative_entry,
            narrative_payload, narrative_result, tech_narrative_entry, tech_payload, wire_tools,
        )

        barrier = threading.Barrier(2, timeout=2)

        class BarrierTool(StubTool):
            def _run(self, **kwargs):
                barrier.wait()
                return super()._run(**kwargs)

        tools = {
            "calculate_technical_indicators": BarrierTool("calculate_technical_indicators", TECH_RESULT),
            "fetch_fundamental_data": BarrierTool("fetch_fundamental_data", FETCH_JSON),
            "grade_fundamental_data": StubTool("grade_fundamental_data", GRADES_JSON),
        }
        flow.state.market_output = market_output()
        wire_tools(flow, tools)
        flow._factory.build_task.return_value = _make_task()
        answers = {
            1: narrative_result(tech_payload(tech_narrative_entry("AAA"))),
            2: narrative_result(narrative_payload(narrative_entry("AAA"))),
        }

        def make_crew(task, phase_index):
            crew = MagicMock()
            crew.akickoff = AsyncMock(return_value=answers[phase_index])
            return crew

        async def both():
            return await asyncio.gather(flow.technical_analysis(), flow.fundamental_analysis())

        with patch.object(flow, "_make_crew", side_effect=make_crew):
            asyncio.run(both())  # BrokenBarrierError would surface here
        assert barrier.n_waiting == 0
        assert flow.state.technical_output is not None and flow.state.fundamental_output is not None
