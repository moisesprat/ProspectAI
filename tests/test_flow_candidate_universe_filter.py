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
        _organic, market_tools, wire_tools,
    )

    serper = _organic("XLE tracks the sector, XOM leads it", "XOM and XLE both rallied", "XOM earnings")
    wire_tools(flow, market_tools(serper=serper), phase="market_analysis")
    flow._factory.build_task.return_value = MagicMock()
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(return_value=_narrative_result("XLE", "XOM"))
        await flow.market_analysis()

    tickers = [c.ticker for c in flow.state.market_output.candidate_stocks]
    assert "XLE" not in tickers
    assert "XOM" in tickers


# ─── Gap review WR-01: ETFs are dropped inside the pick check ───

def _wire_energy_market(flow, serper):
    from tests.test_llm_role_audit import market_tools, wire_tools

    wire_tools(flow, market_tools(serper=serper), phase="market_analysis")
    flow._factory.build_task.return_value = MagicMock()


@pytest.mark.asyncio
async def test_etf_only_picks_spend_a_retry_instead_of_emptying_the_list(flow):
    from tests.test_llm_role_audit import _organic

    serper = _organic("XLE tracks the sector, SPY too", "XLE and SPY rallied", "XOM earnings beat")
    _wire_energy_market(flow, serper)
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(
            side_effect=[_narrative_result("XLE", "SPY"), _narrative_result("XOM")]
        )
        await flow.market_analysis()

    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["XOM"]
    assert mc.return_value.akickoff.await_count == 2


@pytest.mark.asyncio
async def test_etf_pick_does_not_set_the_relevance_scale(flow):
    from tests.test_llm_role_audit import _organic

    serper = _organic("XLE tracks the sector as XLE and XLE rally", "XOM earnings beat")
    _wire_energy_market(flow, serper)
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(return_value=_narrative_result("XLE", "XOM"))
        await flow.market_analysis()

    candidates = flow.state.market_output.candidate_stocks
    assert [c.ticker for c in candidates] == ["XOM"]
    assert candidates[0].mention_count == 1
    assert candidates[0].relevance_score == 1.0


def test_etf_only_answer_fails_validation_with_fixed_text(caplog):
    from schemas.agent_outputs import MarketNarrativeOutput
    from tests.test_llm_role_audit import (
        _organic, mkt_entry, mkt_payload,
    )
    from utils.market_records import build_market_corpus, require_market_picks
    from utils.phase_runner import PhaseOutputError

    serper = _organic("XLE tracks the sector, SPY too", "XLE and SPY rallied", "XOM earnings beat")
    corpus = build_market_corpus(serper, "Energy")
    narrative = MarketNarrativeOutput(**mkt_payload(mkt_entry("XLE"), mkt_entry("SPY")))

    with caplog.at_level("WARNING"):
        with pytest.raises(PhaseOutputError) as excinfo:
            require_market_picks(narrative, corpus)

    assert excinfo.value.fields == ["candidates"]
    assert "excluded_etf" in caplog.text
    visible = str(excinfo.value) + repr(excinfo.value.errors)
    assert "XLE" not in visible and "SPY" not in visible
    assert "ETF" in visible


# ─── Alias sector names (phase 4 CORR-06) ───

@pytest.mark.asyncio
async def test_flow_filter_backstop_drops_the_alias_benchmark_etf(flow, caplog):
    """If an ETF reaches filter_candidates under the SPA's sector name, the backstop still reduces it."""
    from schemas.agent_outputs import MarketAnalysisOutput
    from tests.test_llm_role_audit import _candidate, _organic

    flow.state.sector = "Consumer Discretionary"
    _wire_energy_market(flow, _organic("AMZN earnings beat", "XLY and AMZN rally", "AMZN guidance"))
    merged = MarketAnalysisOutput(
        sector="Consumer Discretionary",
        candidate_stocks=[_candidate("XLY"), _candidate("AMZN")],
        summary="s" * 120,
    )
    with caplog.at_level("WARNING"), \
         patch.object(flow, "_make_crew") as mc, \
         patch("prospect_ai_flow.merge_market", return_value=merged):
        mc.return_value.akickoff = AsyncMock(return_value=_narrative_result("AMZN"))
        await flow.market_analysis()

    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["AMZN"]
    assert "Excluded sector-benchmark/broad-market ETF candidates: ['XLY']" in caplog.text
