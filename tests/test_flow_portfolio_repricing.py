"""
Integration tests for ProspectAIFlow's Flow-authoritative allocator
re-invocation and bounds validation (change deterministic-enforcement-v1-9-1).
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from prospect_ai_flow import ProspectAIFlow
from schemas.agent_outputs import (
    MomentumAnalysis,
    RawIndicators,
    StockTechnicalAnalysis,
    SupportResistance,
    TechnicalAnalysisOutput,
    TechnicalScore,
)
from utils.portfolio_bounds_validator import validate
from tests.fixtures_deterministic_enforcement import (
    FINAL_OUTPUT_SKIPPED_ALLOCATOR,
    ZERO_WIDTH_TRENDING_RAW_INDICATORS,
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
        f.state.sector = "Energy"
        f.state.today = "2026-04-29"
        yield f


def _technical_output(ticker, entry_zone_low, entry_zone_high, current_price):
    return TechnicalAnalysisOutput(
        sector="Energy",
        summary="A" * 100,
        technical_analysis=[
            StockTechnicalAnalysis(
                ticker=ticker,
                current_price=current_price,
                raw_indicators=RawIndicators(rsi=55.0, adx=20.0),
                momentum_analysis=MomentumAnalysis(
                    momentum_score=7.0,
                    risk_level="Medium",
                    trend_strength="Strong",
                    key_signals=["RSI neutral", "MACD bullish crossover"],
                    support_resistance=SupportResistance(support=entry_zone_low, resistance=entry_zone_high),
                    comprehensive_analysis="C" * 60,
                    entry_zone_status="PULLBACK_ENTRY",
                    entry_zone_low=entry_zone_low,
                    entry_zone_high=entry_zone_high,
                    regime="REVERTING",
                ),
                technical_score=TechnicalScore(percentage=70.0, grade="B", recommendation="Buy"),
                investment_recommendation="B" * 60,
            ),
        ],
    )


# ── Fixture 1.1: Final Strategist skipped the allocator ─────────────────────

class TestFinalStrategistSkippedAllocator:
    def test_flow_overwrites_fabricated_numbers_with_allocator_result(self, flow):
        flow.state.technical_output = _technical_output("XOM", 114.0, 116.5, 118.0)

        repriced = flow._finalize_and_validate_portfolio(FINAL_OUTPUT_SKIPPED_ALLOCATOR, "conservative")

        xom = next(p for p in repriced["positions"] if p["ticker"] == "XOM")
        # The fabricated allocation (22.0%) and fabricated zone (117-119) must be
        # gone. current_price (118.0) is above the real technical zone
        # (114.0-116.5), so the tool correctly price-anchors the setup to
        # current_price rather than reusing either the fabricated or the
        # technical zone verbatim.
        assert xom["allocation_pct"] != 22.0
        assert xom["trade_setup"]["entry_zone_low"] == 118.0
        assert xom["trade_setup"]["entry_zone_high"] == 118.0
        assert xom["trade_setup"]["entry_zone_low"] != 117.0  # fabricated value is gone
        # And the result must pass the deterministic bounds validator.
        assert validate(repriced, "conservative") == []

    def test_flow_reinvokes_allocator_even_when_action_unchanged(self, flow):
        # Actions identical to what's already in the (hand-written) final output --
        # per Decision 1 the Flow still recomputes unconditionally.
        flow.state.technical_output = _technical_output("XOM", 114.0, 116.5, 118.0)
        unchanged = json.loads(json.dumps(FINAL_OUTPUT_SKIPPED_ALLOCATOR))
        unchanged["positions"][0]["action"] = "LONG-BUY"  # already LONG-BUY, no change vs itself

        repriced = flow._finalize_and_validate_portfolio(unchanged, "conservative")

        # Numeric fields still come from the tool, not from the hand-written input.
        assert repriced["positions"][0]["trade_setup"]["entry_zone_low"] == 118.0
        assert repriced["positions"][0]["allocation_pct"] != 22.0


# ── Fixture 1.3: zero-width TRENDING entry zone is caught before publication ─

class TestZeroWidthEntryZoneCaught:
    def test_degenerate_technical_zone_is_widened_before_validation_passes(self, flow):
        from utils.technical_interpretation_tool import TechnicalInterpretationTool

        raw = ZERO_WIDTH_TRENDING_RAW_INDICATORS
        indicators_json = json.dumps({
            "current_price":      raw["current_price"],
            "sma_20":             raw["sma_20"],
            "sma_50":             raw["sma_50"],
            "sma_200":            raw["sma_200"],
            "adx":                raw["adx"],
            "atr":                raw["atr"],
            "rsi":                raw["rsi"],
            "macd_status":        raw["macd_signal"],
            "stochastic_status":  raw["stochastic_status"],
        })
        result = json.loads(TechnicalInterpretationTool()._run(raw["ticker"], indicators_json))

        # The tool's own minimum-width clamp must produce a non-degenerate zone.
        assert result["entry_zone_high"] - result["entry_zone_low"] > 0

        flow.state.technical_output = _technical_output(
            raw["ticker"], result["entry_zone_low"], result["entry_zone_high"], raw["current_price"],
        )
        structured = {
            "positions": [{
                "ticker": raw["ticker"],
                "action": "LONG-BUY",
                "composite_score": 80.0,
                "current_price": raw["current_price"],
                "trade_setup": {
                    "direction": "LONG-BUY",
                    "entry_zone_low": result["entry_zone_low"],
                    "entry_zone_high": result["entry_zone_low"],  # simulate the old zero-width bug
                    "stop_loss": result["entry_zone_low"] * 0.9,
                    "take_profit": result["entry_zone_low"] * 1.2,
                },
            }],
            "deployed_pct": 0.0, "reserved_pct": 0.0, "cash_reserve_pct": 100.0,
        }

        repriced = flow._finalize_and_validate_portfolio(structured, "conservative")
        assert validate(repriced, "conservative") == []
