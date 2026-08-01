"""
Integration tests: ActionPolicyGate wired into ProspectAIFlow between
critique_review and final_strategy (change deterministic-enforcement-v1-9-1).
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from prospect_ai_flow import ProspectAIFlow
from schemas.agent_outputs import (
    CriticOutput,
    MomentumAnalysis,
    RawIndicators,
    StockTechnicalAnalysis,
    SupportResistance,
    TechnicalAnalysisOutput,
    TechnicalScore,
)
from tests.fixtures_deterministic_enforcement import (
    CRITIC_OUTPUT_INVERTED_CURRENT_ENTRY_BUG,
    CRITIC_OUTPUT_POLICY_VIOLATING_DIRECTIVE,
)

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
        f.state.risk_profile = "conservative"
        yield f


def _technical_output_for(ticker, entry_zone_status):
    return TechnicalAnalysisOutput(
        sector="Technology",
        summary="A" * 100,
        technical_analysis=[
            StockTechnicalAnalysis(
                ticker=ticker,
                current_price=200.0,
                raw_indicators=RawIndicators(rsi=60.0, adx=22.0),
                momentum_analysis=MomentumAnalysis(
                    momentum_score=6.0,
                    risk_level="Medium",
                    trend_strength="Strong",
                    key_signals=["RSI neutral"],
                    support_resistance=SupportResistance(support=195.0, resistance=205.0),
                    comprehensive_analysis="C" * 60,
                    entry_zone_status=entry_zone_status,
                    entry_zone_low=195.0,
                    entry_zone_high=200.0,
                    regime="TRENDING",
                ),
                technical_score=TechnicalScore(percentage=75.0, grade="B", recommendation="Buy"),
                investment_recommendation="B" * 60,
            ),
        ],
    )


def test_policy_violating_directive_is_dropped_from_final_strategist_context(flow):
    flow.state.technical_output = _technical_output_for("AAPL", "CURRENT_ENTRY")
    flow.state.critique_output = CriticOutput(**CRITIC_OUTPUT_POLICY_VIOLATING_DIRECTIVE)

    gated_ctx = json.loads(flow._gated_slim_critique())

    assert gated_ctx["revision_directives"] == []


def test_policy_permitted_directive_passes_through(flow):
    flow.state.technical_output = _technical_output_for("AAPL", "PULLBACK_ENTRY")
    flow.state.risk_profile = "aggressive"
    critique = dict(CRITIC_OUTPUT_POLICY_VIOLATING_DIRECTIVE)
    critique["revision_directives"] = ["AAPL: change action to LONG-BUY -- momentum confirms bullish thesis."]
    flow.state.critique_output = CriticOutput(**critique)

    gated_ctx = json.loads(flow._gated_slim_critique())

    assert gated_ctx["revision_directives"] == critique["revision_directives"]


def test_inverted_current_entry_bug_is_dropped_from_both_channels(flow):
    """Regression test for the exact production incident in
    logs/deterministic-enforcement-v1-9-1/run4_technology_aggressive.log: the
    Critic's inverted CURRENT_ENTRY rule must be dropped from BOTH
    revision_directives and per_ticker_critiques, not just one.
    """
    flow.state.technical_output = _technical_output_for("NVDA", "CURRENT_ENTRY")
    flow.state.risk_profile = "aggressive"
    flow.state.critique_output = CriticOutput(**CRITIC_OUTPUT_INVERTED_CURRENT_ENTRY_BUG)

    gated_ctx = json.loads(flow._gated_slim_critique())

    assert gated_ctx["revision_directives"] == []
    assert gated_ctx["per_ticker_critiques"] == []
