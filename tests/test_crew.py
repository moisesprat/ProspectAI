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
    result.tasks_output = None  # prevent MagicMock auto-attr from hijacking _parse_result
    return result


def _patched_crew():
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = _mock_crew_result(SAMPLE_PIPELINE_OUTPUT)
    # Patch where Crew is actually used (prospect_ai_crew imports it directly)
    return (patch("prospect_ai_crew.Crew", return_value=mock_crew_instance),)


# ── Initialization ────────────────────────────────────────────────────────────





# ── Deprecation warning ───────────────────────────────────────────────────────

