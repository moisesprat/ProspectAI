"""
Integration test: ProspectAIFlow.market_analysis() excludes sector-benchmark
ETFs from candidates regardless of data source (change deterministic-enforcement-v1-9-1).
"""
from unittest.mock import AsyncMock, MagicMock, patch

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
        f.state.sector = "Energy"
        f.state.today = "2026-04-29"
        yield f


def _crew_result_with(candidates):
    market_output = MarketAnalysisOutput(
        sector="Energy",
        candidate_stocks=candidates,
        summary="S" * 150,
    )
    task_out = MagicMock()
    task_out.pydantic = market_output
    task_out.json_dict = None
    result = MagicMock()
    result.raw = "{}"
    result.tasks_output = [task_out]
    result.token_usage = MagicMock()
    return result


@pytest.mark.asyncio
async def test_sector_benchmark_etf_is_excluded_from_serper_fallback_candidates(flow):
    candidates = [
        CandidateStock(
            ticker="XLE", mention_count=0, average_sentiment=0.4, relevance_score=0.5,
            rationale="XLE tracks the broader energy sector and was mentioned as a proxy in coverage.",
        ),
        CandidateStock(
            ticker="XOM", mention_count=12, average_sentiment=0.3, relevance_score=0.8,
            rationale="Exxon Mobil is the most-discussed energy stock this week among retail investors.",
        ),
    ]
    crew_result = _crew_result_with(candidates)
    flow._factory.build_task.return_value = MagicMock()
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(return_value=crew_result)
        await flow.market_analysis()

    tickers = [c.ticker for c in flow.state.market_output.candidate_stocks]
    assert "XLE" not in tickers
    assert "XOM" in tickers
