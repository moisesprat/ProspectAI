"""Unit tests for individual ProspectAIFlow phase methods (F-08)."""
import json
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
        with pytest.raises(RuntimeError, match="Pydantic validation failed"):
            ProspectAIFlow._extract_pydantic(result, MarketAnalysisOutput, "market_analysis")


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
        pydantic_out = MagicMock(spec=MarketAnalysisOutput)
        pydantic_out.candidate_stocks = []
        crew_result = _make_crew_result(pydantic_out=pydantic_out)
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            await flow.market_analysis()
        assert flow.state.market_output is pydantic_out
        flow._factory.build_task.assert_called_once_with(
            "market_analysis", "Technology", "2026-04-29"
        )

    @pytest.mark.asyncio
    async def test_aborts_on_error_state(self, flow):
        flow.state.error = "upstream failure"
        with pytest.raises(RuntimeError, match="upstream failure"):
            await flow.market_analysis()


class TestTechnicalAnalysisPhase:
    @pytest.mark.asyncio
    async def test_updates_technical_output(self, flow):
        pydantic_out = MagicMock(spec=TechnicalAnalysisOutput)
        crew_result = _make_crew_result(pydantic_out=pydantic_out)
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            await flow.technical_analysis()
        assert flow.state.technical_output is pydantic_out

    @pytest.mark.asyncio
    async def test_aborts_on_error_state(self, flow):
        flow.state.error = "fail"
        with pytest.raises(RuntimeError):
            await flow.technical_analysis()


class TestFundamentalAnalysisPhase:
    @pytest.mark.asyncio
    async def test_updates_fundamental_output(self, flow):
        pydantic_out = MagicMock(spec=FundamentalAnalysisOutput)
        crew_result = _make_crew_result(pydantic_out=pydantic_out)
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            await flow.fundamental_analysis()
        assert flow.state.fundamental_output is pydantic_out


class TestDraftStrategyPhase:
    @pytest.mark.asyncio
    async def test_updates_draft_output(self, flow):
        pydantic_out = MagicMock(spec=InvestorStrategicOutput)
        crew_result = _make_crew_result(pydantic_out=pydantic_out)
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            await flow.draft_strategy()
        assert flow.state.draft_output is pydantic_out


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
    async def test_stores_final_crew_result(self, flow):
        crew_result = _make_crew_result(raw="{}")
        flow._factory.build_task.return_value = _make_task()
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            await flow.final_strategy()
        assert flow._final_crew_result is crew_result

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

        flow.kickoff = lambda inputs=None: flow._tracker.start_phase("final_strategy")
        with patch("prospect_ai_flow._parse_crew_result", return_value={"positions": []}), \
             patch.object(
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

        flow.kickoff = lambda inputs=None: None
        with patch("prospect_ai_flow._parse_crew_result", return_value={"positions": []}), \
             patch.object(flow, "_finalize_and_validate_portfolio", side_effect=slow_finalize):
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
    async def test_market_phase_body_raises_before_extracting(self, flow):
        flow._tracker = ExecutionTracker()
        flow._tracker.start()
        flow._factory.build_task.return_value = _task_with_tools("Search")
        crew_result = _make_crew_result(pydantic_out=MagicMock(spec=MarketAnalysisOutput))
        with patch.object(flow, "_make_crew") as mc:
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            with pytest.raises(MissingToolCallError, match="market_analysis"):
                await flow.market_analysis()
        assert flow.state.market_output is None

    @pytest.mark.parametrize(
        "phase,schema",
        [
            ("technical_analysis", TechnicalAnalysisOutput),
            ("fundamental_analysis", FundamentalAnalysisOutput),
            ("draft_strategy", InvestorStrategicOutput),
        ],
    )
    @pytest.mark.asyncio
    async def test_every_tool_phase_body_is_guarded(self, flow, phase, schema):
        flow._tracker = ExecutionTracker()
        flow._tracker.start()
        flow._factory.build_task.return_value = _task_with_tools("Tool")
        crew_result = _make_crew_result(pydantic_out=MagicMock(spec=schema))
        with patch.object(flow, "_make_crew") as mc, \
             patch.object(flow, "_slim_market_for_analysis", return_value=""), \
             patch.object(flow, "_slim_market_for_strategy", return_value=""), \
             patch.object(flow, "_slim_technical", return_value=""), \
             patch.object(flow, "_slim_fundamental", return_value=""):
            mc.return_value.akickoff = AsyncMock(return_value=crew_result)
            with pytest.raises(MissingToolCallError, match=phase):
                await getattr(flow, phase)()

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
        assert flow._final_crew_result is crew_result

    def test_run_analysis_attaches_partial_metrics_to_missing_tool_call(self, flow):
        def kickoff(inputs=None):
            flow._tracker.start_phase("market_analysis")
            raise MissingToolCallError("market_analysis: the agent finished without calling any of its tools (Search)")

        flow.kickoff = kickoff
        with pytest.raises(MissingToolCallError) as info:
            flow.run_analysis({"sector": "Technology"})
        assert info.value.partial_metrics["partial"] is True
