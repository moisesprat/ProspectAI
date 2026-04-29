"""Unit tests for individual ProspectAIFlow phase methods (F-08)."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from prospect_ai_flow import ProspectAIFlow, _parse_crew_result
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
        flow._emit_progress(0, "test output")
        assert len(events) == 1
        evt = events[0]
        assert evt["event"] == "task_complete"
        assert evt["task_index"] == 0
        assert evt["agent"] == "MarketAnalyst"
        assert evt["output_snippet"] == "test output"

    def test_noop_without_callback(self, flow):
        flow._progress_callback = None
        flow._emit_progress(0, "output")  # must not raise


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
