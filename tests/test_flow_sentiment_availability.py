"""
Sentiment-availability sentinel propagation through ProspectAIFlow context
builders (change deterministic-enforcement-v1-9-1).
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prospect_ai_flow import ProspectAIFlow
from schemas.agent_outputs import CandidateStock, MarketAnalysisOutput

ANTHROPIC_ENV = {
    "ANTHROPIC_API_KEY": "test-key",
    "MODEL": "claude-haiku-4-5-20251001",
    "REDDIT_CLIENT_ID": "test-id",
    "REDDIT_CLIENT_SECRET": "test-secret",
}


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


def _unavailable_market_output():
    return MarketAnalysisOutput(
        sector="Technology",
        sentiment_available=False,
        candidate_stocks=[CandidateStock(
            ticker="AAPL", mention_count=0, average_sentiment=None, relevance_score=0.5,
            rationale="Sentiment data unavailable this run; falling back to a well-known sector leader.",
        )],
        summary="S" * 150,
    )


def test_slim_market_for_analysis_surfaces_sentiment_unavailable(flow):
    import json
    flow.state.market_output = _unavailable_market_output()
    ctx = json.loads(flow._slim_market_for_analysis())
    assert ctx["sentiment_available"] is False
    assert ctx["candidate_stocks"][0]["average_sentiment"] is None


def test_slim_market_for_strategy_surfaces_sentiment_unavailable(flow):
    import json
    flow.state.market_output = _unavailable_market_output()
    ctx = json.loads(flow._slim_market_for_strategy())
    assert ctx["sentiment_available"] is False
    assert ctx["candidate_stocks"][0]["average_sentiment"] is None


def test_critic_task_description_scopes_out_sentiment_when_unavailable():
    tasks_yaml = Path(__file__).parent.parent / "config" / "tasks.yaml"
    text = tasks_yaml.read_text()
    critique_section = text.split("critique_review:")[1].split("final_strategy:")[0]
    assert "sentiment_available=false" in critique_section
    assert "do NOT raise any" in critique_section or "do NOT raise any\n" in critique_section


def test_critic_task_description_checks_wait_entry_alloc_against_reserved_allocations():
    tasks_yaml = Path(__file__).parent.parent / "config" / "tasks.yaml"
    text = tasks_yaml.read_text()
    critique_section = text.split("critique_review:")[1].split("final_strategy:")[0]
    assert "WAIT_ENTRY_ZERO_ALLOC" in critique_section
    assert "reserved_allocations" in critique_section
    assert "aggregate" in critique_section
