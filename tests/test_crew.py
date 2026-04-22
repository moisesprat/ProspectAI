"""
Tests for ProspectAICrew (legacy) and ProspectAIFlow orchestration.
All LLM calls and Crew execution are mocked — no real AI inference.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock

ANTHROPIC_ENV = {
    "MODEL_PROVIDER": "anthropic",
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "ANTHROPIC_MODEL": "claude-sonnet-4-6",
    "MODEL": "anthropic/claude-sonnet-4-6",
}

# Matches InvestorStrategicOutput schema (current pipeline v1.5+)
SAMPLE_PIPELINE_OUTPUT = {
    "sector": "Technology",
    "positions": [
        {
            "ticker": "NVDA",
            "action": "LONG-BUY",
            "composite_score": 81.0,
            "allocation_pct": 40.0,
            "current_price": 875.50,
            "trade_setup": {
                "direction": "LONG-BUY",
                "entry_zone_low": 834.0,
                "entry_zone_high": 851.0,
                "stop_loss": 809.0,
                "take_profit": 885.0,
            },
            "scaled_entry_setups": None,
            "rationale": (
                "NVDA shows RSI=67 momentum_score=8.1 STRONG health HIGH growth. "
                "Composite 81.0 supports LONG-BUY with entry zone 834-851. "
                "Data-center AI demand drives multiple expansion. "
                "Trade setup validated by allocator tool output verbatim copy."
            ),
            "monitoring_triggers": [
                "RSI crosses above 76 — overbought signal",
                "Weekly close below SMA50 at $820",
            ],
            "review_frequency": "WEEKLY",
        },
        {
            "ticker": "AAPL",
            "action": "WAIT-FOR-ENTRY",
            "composite_score": 65.0,
            "allocation_pct": 12.5,
            "current_price": 195.0,
            "trade_setup": {
                "direction": "LONG-BUY",
                "entry_zone_low": 178.0,
                "entry_zone_high": 182.0,
                "stop_loss": 172.7,
                "take_profit": 199.6,
            },
            "scaled_entry_setups": None,
            "rationale": (
                "AAPL RSI=73 above overbought threshold. Earmarking 12.5% pending "
                "pullback to zone 178-182. momentum_score=6.5, ADEQUATE health. "
                "Services revenue growth provides durable support. "
                "Will enter on retracement confirming healthy pullback."
            ),
            "monitoring_triggers": [
                "Price retraces to entry_zone_high of $182.00",
                "RSI drops below 60 confirming healthy retracement",
            ],
            "review_frequency": "WEEKLY",
        },
        {
            "ticker": "MSFT",
            "action": "MONITOR",
            "composite_score": 58.0,
            "allocation_pct": 0.0,
            "current_price": 420.0,
            "trade_setup": None,
            "scaled_entry_setups": None,
            "rationale": (
                "MSFT composite_score=58.0 below threshold for deployment. "
                "RSI=72 and VERY_EXPENSIVE PE=35. Watching for pullback and "
                "valuation reset before committing capital. momentum_score=5.2. "
                "No capital allocated — watch-list only pending conditions."
            ),
            "monitoring_triggers": [
                "RSI drops below 55",
                "PE ratio contracts below 28",
            ],
            "review_frequency": "MONTHLY",
        },
    ],
    "deployed_pct": 40.0,
    "reserved_pct": 12.5,
    "total_allocated_pct": 52.5,
    "cash_reserve_pct": 47.5,
    "overall_strategy": (
        "Technology sector portfolio allocates 40% to NVDA (LONG-BUY) as highest-conviction "
        "position. 12.5% earmarked for AAPL pending pullback to zone. MSFT on watch-list. "
        "Capital is distributed proportionally to composite scores among eligible actions, "
        "capped per action type. deployed_pct=40% + reserved_pct=12.5% + cash=47.5% = 100%."
    ),
    "risk_level": "Medium",
}


def _mock_crew_result(output_dict):
    result = MagicMock()
    result.raw = json.dumps(output_dict)
    result.json_dict = None
    return result


def _patched_crew():
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = _mock_crew_result(SAMPLE_PIPELINE_OUTPUT)
    # Patch where Crew is actually used (prospect_ai_crew imports it directly)
    return (patch("prospect_ai_crew.Crew", return_value=mock_crew_instance),)


# ── Initialization ────────────────────────────────────────────────────────────

class TestProspectAICrewInit:

    def test_crew_has_five_agent_objects(self):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            crew = ProspectAICrew()
        assert crew.market_analyst is not None
        assert crew.technical_analyst is not None
        assert crew.fundamental_analyst is not None
        assert crew.investor_strategist is not None
        assert crew.critic is not None

    def test_crew_initializes_search_tool(self):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            crew = ProspectAICrew()
        assert crew.search_tool is not None


# ── Task creation ─────────────────────────────────────────────────────────────

class TestCreateTasks:

    @pytest.fixture
    def crew(self):
        # Use yield so ANTHROPIC_ENV stays active during create_tasks() calls
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            yield ProspectAICrew()

    def test_creates_six_tasks(self, crew):
        tasks = crew.create_tasks({"sector": "Technology"})
        assert len(tasks) == 6

    def test_task_descriptions_contain_sector(self, crew):
        tasks = crew.create_tasks({"sector": "Healthcare"})
        assert any("Healthcare" in str(t.description) for t in tasks)

    def test_task_descriptions_contain_today_date(self, crew):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        tasks = crew.create_tasks({"sector": "Technology"})
        combined = " ".join(str(t.description) for t in tasks)
        assert today in combined

    def test_all_tasks_have_expected_output_defined(self, crew):
        tasks = crew.create_tasks({"sector": "Technology"})
        for i, task in enumerate(tasks):
            assert task.expected_output, f"Task {i} has no expected_output"

    def test_market_task_has_reddit_tool(self, crew):
        from utils.reddit_sentiment_tool import RedditSentimentTool
        tasks = crew.create_tasks({"sector": "Technology"})
        tool_types = [type(t) for t in tasks[0].tools]
        assert RedditSentimentTool in tool_types

    def test_draft_task_has_composite_and_allocator_tools(self, crew):
        from utils.composite_score_tool import CompositeScoreTool
        from utils.portfolio_allocator_tool import PortfolioAllocatorTool
        tasks = crew.create_tasks({"sector": "Technology"})
        draft_task = tasks[3]
        tool_types = [type(t) for t in draft_task.tools]
        assert CompositeScoreTool in tool_types
        assert PortfolioAllocatorTool in tool_types

    def test_critic_task_has_no_tools(self, crew):
        tasks = crew.create_tasks({"sector": "Technology"})
        critique_task = tasks[4]
        assert len(critique_task.tools) == 0

    def test_final_task_has_composite_and_allocator_tools(self, crew):
        from utils.composite_score_tool import CompositeScoreTool
        from utils.portfolio_allocator_tool import PortfolioAllocatorTool
        tasks = crew.create_tasks({"sector": "Technology"})
        final_task = tasks[5]
        tool_types = [type(t) for t in final_task.tools]
        assert CompositeScoreTool in tool_types
        assert PortfolioAllocatorTool in tool_types

    def test_no_hardcoded_year_in_descriptions(self, crew):
        tasks = crew.create_tasks({"sector": "Technology"})
        for task in tasks:
            assert "2025" not in str(task.description), \
                "Task description contains hardcoded year '2025'"


# ── run_analysis ──────────────────────────────────────────────────────────────

class TestRunAnalysis:

    @pytest.fixture
    def result(self):
        (p_crew,) = _patched_crew()
        with p_crew, patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            yield ProspectAICrew().run_analysis({"sector": "Technology"})

    def test_run_analysis_returns_required_keys(self, result):
        assert "status" in result
        assert "result" in result
        assert "summary" in result

    def test_run_analysis_status_is_success(self, result):
        assert result["status"] == "success"

    def test_run_analysis_result_contains_positions(self, result):
        assert "positions" in result["result"]

    def test_run_analysis_result_contains_capital_buckets(self, result):
        r = result["result"]
        assert "deployed_pct" in r
        assert "reserved_pct" in r
        assert "cash_reserve_pct" in r

    def test_run_analysis_result_contains_overall_strategy(self, result):
        assert "overall_strategy" in result["result"]


# ── _parse_result ─────────────────────────────────────────────────────────────

class TestParseResult:

    @pytest.fixture
    def crew(self):
        with patch("crewai.LLM", return_value="claude-sonnet-4-6"), \
             patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            return ProspectAICrew()

    def test_parses_plain_json(self, crew):
        raw = MagicMock()
        raw.raw = json.dumps(SAMPLE_PIPELINE_OUTPUT)
        raw.json_dict = None
        parsed = crew._parse_result(raw)
        assert parsed["sector"] == "Technology"
        assert "positions" in parsed

    def test_parses_json_wrapped_in_markdown_fences(self, crew):
        raw = MagicMock()
        raw.raw = "```json\n" + json.dumps(SAMPLE_PIPELINE_OUTPUT) + "\n```"
        raw.json_dict = None
        parsed = crew._parse_result(raw)
        assert "positions" in parsed

    def test_parses_json_wrapped_in_plain_fences(self, crew):
        raw = MagicMock()
        raw.raw = "```\n" + json.dumps(SAMPLE_PIPELINE_OUTPUT) + "\n```"
        raw.json_dict = None
        parsed = crew._parse_result(raw)
        assert "positions" in parsed

    def test_invalid_json_returns_parse_error_dict(self, crew):
        raw = MagicMock()
        raw.raw = "This is not JSON at all"
        raw.json_dict = None
        parsed = crew._parse_result(raw)
        assert isinstance(parsed, dict)
        assert parsed.get("parse_error") is True or "raw_output" in parsed

    def test_json_dict_shortcut_used_when_available(self, crew):
        raw = MagicMock()
        raw.json_dict = {"sector": "Energy", "positions": []}
        parsed = crew._parse_result(raw)
        assert parsed["sector"] == "Energy"


# ── ProspectAIFlow.run_analysis ───────────────────────────────────────────────

class TestProspectAIFlowRunAnalysis:
    """run_analysis on ProspectAIFlow returns the same contract as ProspectAICrew."""

    @pytest.fixture
    def result(self):
        mock_crew_out = _mock_crew_result(SAMPLE_PIPELINE_OUTPUT)
        with patch.dict(os.environ, ANTHROPIC_ENV):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                from prospect_ai_flow import ProspectAIFlow
                flow = ProspectAIFlow()
        # Pre-set the final result so kickoff (mocked to no-op) doesn't need to run.
        flow._final_crew_result = mock_crew_out
        flow.kickoff = lambda *_, **__: None
        yield flow.run_analysis({"sector": "Technology"})

    def test_returns_status_success(self, result):
        assert result["status"] == "success"

    def test_returns_required_keys(self, result):
        assert "status" in result
        assert "result" in result
        assert "summary" in result

    def test_result_contains_positions(self, result):
        assert "positions" in result["result"]

    def test_result_contains_capital_buckets(self, result):
        r = result["result"]
        assert "deployed_pct" in r
        assert "reserved_pct" in r
        assert "cash_reserve_pct" in r

    def test_result_contains_overall_strategy(self, result):
        assert "overall_strategy" in result["result"]


# ── Deprecation warning ───────────────────────────────────────────────────────

class TestProspectAICrewDeprecation:

    def test_instantiation_raises_deprecation_warning(self):
        with patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            with pytest.warns(DeprecationWarning, match="ProspectAICrew is deprecated"):
                ProspectAICrew()


# ── Smoke: CrewAI Flow imports ────────────────────────────────────────────────

class TestCrewAIFlowImports:

    def test_flow_symbols_importable(self):
        from crewai.flow.flow import Flow, listen, start, and_
        assert Flow is not None
        assert listen is not None
        assert start is not None
        assert and_ is not None

    def test_prospect_ai_flow_importable(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with patch.dict(os.environ, ANTHROPIC_ENV):
                from prospect_ai_flow import ProspectAIFlow, ProspectAIFlowState
        assert ProspectAIFlow is not None
        assert ProspectAIFlowState is not None
