"""
Integration test: ProspectAIFlow.market_analysis() excludes sector-benchmark
ETFs from candidates regardless of data source (change deterministic-enforcement-v1-9-1).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prospect_ai_flow import ProspectAIFlow

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


def _narrative_result(*tickers):
    """Crew result carrying the market narrative as raw JSON (parsed by extract_model)."""
    from tests.test_llm_role_audit import mkt_entry, mkt_payload, narrative_result

    return narrative_result(mkt_payload(*[mkt_entry(t) for t in tickers]))


@pytest.mark.asyncio
async def test_sector_benchmark_etf_is_excluded_from_serper_fallback_candidates(flow):
    from tests.test_llm_role_audit import (
        REDDIT_FALLBACK, _organic, market_tools, wire_tools,
    )

    serper = _organic("XLE tracks the sector, XOM leads it", "XOM and XLE both rallied", "XOM earnings")
    wire_tools(flow, market_tools(reddit=REDDIT_FALLBACK, serper=serper), phase="market_analysis")
    flow._factory.build_task.return_value = MagicMock()
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(return_value=_narrative_result("XLE", "XOM"))
        await flow.market_analysis()

    tickers = [c.ticker for c in flow.state.market_output.candidate_stocks]
    assert "XLE" not in tickers
    assert "XOM" in tickers
