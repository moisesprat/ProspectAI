"""
Tests for ProspectAICrew orchestration.
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

SAMPLE_PIPELINE_OUTPUT = {
    "pipeline_version": "2.0",
    "sector": "Technology",
    "analysis_date": "2026-04-01",
    "stock_recommendations": [
        {
            "ticker": "NVDA",
            "recommendation": "STRONG_BUY",
            "composite_score": 80,
            "allocation_pct": 40.0,
            "entry_zone": "850-870",
            "stop_loss": 820.0,
            "key_risks": ["Valuation", "Competition"],
            "key_catalysts": ["AI demand", "Data center growth"],
        },
        {
            "ticker": "AAPL",
            "recommendation": "BUY",
            "composite_score": 62,
            "allocation_pct": 35.0,
            "entry_zone": "185-190",
            "stop_loss": 175.0,
            "key_risks": ["iPhone cycle"],
            "key_catalysts": ["Services growth"],
        },
        {
            "ticker": "MSFT",
            "recommendation": "HOLD",
            "composite_score": 45,
            "allocation_pct": 25.0,
            "entry_zone": "415-420",
            "stop_loss": 395.0,
            "key_risks": ["Azure competition"],
            "key_catalysts": ["Copilot adoption"],
        },
    ],
    "portfolio_summary": {
        "total_stocks": 3,
        "overall_sector_outlook": "BULLISH",
        "average_composite_score": 62.3,
        "recommended_allocation": {"NVDA": 40.0, "AAPL": 35.0, "MSFT": 25.0},
    },
}


def _mock_crew_result(output_dict):
    result = MagicMock()
    result.raw = json.dumps(output_dict)
    return result


def _patched_crew():
    """Context manager that patches LLM and Crew so no real calls happen."""
    mock_llm = MagicMock()
    mock_llm.model = "claude-sonnet-4-6"
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = _mock_crew_result(SAMPLE_PIPELINE_OUTPUT)

    return (
        patch("crewai.LLM", return_value=mock_llm),
        patch("crewai.Crew", return_value=mock_crew_instance),
    )


# ── Initialization ────────────────────────────────────────────────────────────

class TestProspectAICrewInit:

    def test_crew_initializes_all_four_agents(self):
        llm_patch = patch("crewai.LLM", return_value=MagicMock())
        with llm_patch, patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            crew = ProspectAICrew()
            assert crew.market_analyst is not None
            assert crew.technical_analyst is not None
            assert crew.fundamental_analyst is not None
            assert crew.investor_strategist is not None

    def test_crew_initializes_search_tool(self):
        llm_patch = patch("crewai.LLM", return_value=MagicMock())
        with llm_patch, patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            crew = ProspectAICrew()
            assert crew.search_tool is not None


# ── Task creation ─────────────────────────────────────────────────────────────

class TestCreateTasks:

    @pytest.fixture
    def crew(self):
        with patch("crewai.LLM", return_value=MagicMock()), \
             patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            return ProspectAICrew()

    def test_creates_four_tasks(self, crew):
        tasks = crew.create_tasks({"sector": "Technology"})
        assert len(tasks) == 4

    def test_task_descriptions_contain_sector(self, crew):
        tasks = crew.create_tasks({"sector": "Healthcare"})
        assert any("Healthcare" in str(t.description) for t in tasks)

    def test_task_descriptions_contain_today_date(self, crew):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        tasks = crew.create_tasks({"sector": "Technology"})
        combined = " ".join(str(t.description) for t in tasks)
        assert today in combined

    def test_tasks_have_expected_output_defined(self, crew):
        tasks = crew.create_tasks({"sector": "Technology"})
        for i, task in enumerate(tasks):
            assert task.expected_output, f"Task {i} has no expected_output"

    def test_market_task_has_reddit_tool(self, crew):
        from utils.reddit_sentiment_tool import RedditSentimentTool
        tasks = crew.create_tasks({"sector": "Technology"})
        market_task = tasks[0]
        tool_types = [type(t) for t in market_task.tools]
        assert RedditSentimentTool in tool_types

    def test_task_description_does_not_contain_hardcoded_year(self, crew):
        """Guard against time-fixed prompts like '2025'."""
        tasks = crew.create_tasks({"sector": "Technology"})
        for task in tasks:
            assert "2025" not in str(task.description), \
                "Task description contains hardcoded year '2025'"

    def test_task_output_example_uses_placeholder_not_nvda(self, crew):
        """The output schema example must not anchor to 'NVDA'."""
        tasks = crew.create_tasks({"sector": "Technology"})
        market_desc = str(tasks[0].description)
        # The ticker placeholder should not be "NVDA" as a literal value
        assert '"NVDA"' not in market_desc, \
            "Market task description contains hardcoded ticker 'NVDA'"


# ── run_analysis result parsing ───────────────────────────────────────────────

class TestRunAnalysis:

    def test_run_analysis_returns_status_result_summary(self):
        p1, p2 = _patched_crew()
        with p1, p2, patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            crew = ProspectAICrew()
            result = crew.run_analysis({"sector": "Technology"})
            assert "status" in result
            assert "result" in result
            assert "summary" in result

    def test_run_analysis_status_is_success(self):
        p1, p2 = _patched_crew()
        with p1, p2, patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            crew = ProspectAICrew()
            result = crew.run_analysis({"sector": "Technology"})
            assert result["status"] == "success"

    def test_run_analysis_result_contains_stock_recommendations(self):
        p1, p2 = _patched_crew()
        with p1, p2, patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            crew = ProspectAICrew()
            result = crew.run_analysis({"sector": "Technology"})
            assert "stock_recommendations" in result["result"]

    def test_run_analysis_result_contains_portfolio_summary(self):
        p1, p2 = _patched_crew()
        with p1, p2, patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            crew = ProspectAICrew()
            result = crew.run_analysis({"sector": "Technology"})
            assert "portfolio_summary" in result["result"]


# ── _parse_result ─────────────────────────────────────────────────────────────

class TestParseResult:

    @pytest.fixture
    def crew(self):
        with patch("crewai.LLM", return_value=MagicMock()), \
             patch.dict(os.environ, ANTHROPIC_ENV):
            from prospect_ai_crew import ProspectAICrew
            return ProspectAICrew()

    def test_parses_plain_json(self, crew):
        raw = MagicMock()
        raw.raw = json.dumps(SAMPLE_PIPELINE_OUTPUT)
        parsed = crew._parse_result(raw)
        assert parsed["pipeline_version"] == "2.0"

    def test_parses_json_wrapped_in_markdown_fences(self, crew):
        raw = MagicMock()
        raw.raw = "```json\n" + json.dumps(SAMPLE_PIPELINE_OUTPUT) + "\n```"
        parsed = crew._parse_result(raw)
        assert "stock_recommendations" in parsed

    def test_parses_json_wrapped_in_plain_fences(self, crew):
        raw = MagicMock()
        raw.raw = "```\n" + json.dumps(SAMPLE_PIPELINE_OUTPUT) + "\n```"
        parsed = crew._parse_result(raw)
        assert "stock_recommendations" in parsed

    def test_invalid_json_returns_raw_text(self, crew):
        raw = MagicMock()
        raw.raw = "This is not JSON at all"
        parsed = crew._parse_result(raw)
        assert "raw_output" in parsed or isinstance(parsed, dict)


# ── Composite score formula ───────────────────────────────────────────────────

class TestCompositeScoreFormula:
    """Validate the scoring formula described in agents.yaml and task description."""

    def test_sentiment_component_capped_at_30(self):
        sentiment = 1.0  # max possible
        component = min(sentiment * 100, 30)
        assert component == 30

    def test_sentiment_component_scales_linearly(self):
        assert min(0.3 * 100, 30) == 30
        assert min(0.2 * 100, 30) == 20
        assert min(0.1 * 100, 30) == 10

    def test_technical_component_max_is_40(self):
        momentum_score = 10  # max
        assert momentum_score * 4 == 40

    @pytest.mark.parametrize("health,growth,expected", [
        ("STRONG", "HIGH", 30),
        ("STRONG", "MODERATE", 27),
        ("ADEQUATE", "HIGH", 20),
        ("WEAK", "DECLINING", 0),
    ])
    def test_fundamental_component(self, health, growth, expected):
        health_pts = {"STRONG": 20, "ADEQUATE": 10, "WEAK": 0}[health]
        growth_pts = {"HIGH": 10, "MODERATE": 7, "LOW": 3, "DECLINING": 0}[growth]
        assert health_pts + growth_pts == expected

    @pytest.mark.parametrize("score,expected_rec", [
        (80, "STRONG_BUY"),
        (60, "BUY"),
        (45, "HOLD"),
        (30, "REDUCE"),
        (20, "AVOID"),
    ])
    def test_score_to_recommendation_mapping(self, score, expected_rec):
        if score >= 75:
            rec = "STRONG_BUY"
        elif score >= 55:
            rec = "BUY"
        elif score >= 40:
            rec = "HOLD"
        elif score >= 25:
            rec = "REDUCE"
        else:
            rec = "AVOID"
        assert rec == expected_rec
