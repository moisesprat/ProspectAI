"""
Integration tests for ProspectAIFlow's Flow-authoritative allocator
re-invocation and bounds validation (change deterministic-enforcement-v1-9-1).
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from prospect_ai_flow import ProspectAIFlow
from utils.portfolio_bounds_validator import BoundsViolationError
from schemas.agent_outputs import (
    MomentumAnalysis,
    RawIndicators,
    StockTechnicalAnalysis,
    SupportResistance,
    TechnicalAnalysisOutput,
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


# ── Regression: Final Strategist assigns WAIT-FOR-ENTRY at CURRENT_ENTRY ────
# Real bug found via live validation (reasoning-depth-action-selection): the
# Final Strategist independently chose WAIT-FOR-ENTRY for a position the
# deterministic technical output classified as entry_zone_status=CURRENT_ENTRY.
# ActionPolicyGate only filters Critic directives on their way to the Final
# Strategist -- it never checks what the Final Strategist itself decides --
# so this reached publication uncaught until PortfolioBoundsValidator gained
# this check.

class TestWaitForEntryAtCurrentEntryCaught:
    def test_flow_raises_bounds_violation_for_wait_for_entry_at_current_entry(self, flow):
        technical = _technical_output("ABBV", 241.0, 249.69, 250.94)
        technical.technical_analysis[0].momentum_analysis.entry_zone_status = "CURRENT_ENTRY"
        flow.state.technical_output = technical

        structured = {
            "positions": [{
                "ticker": "ABBV",
                "action": "WAIT-FOR-ENTRY",
                "composite_score": 80.0,
                "current_price": 250.94,
                "trade_setup": {
                    "direction": "LONG-BUY",
                    "entry_zone_low": 241.0,
                    "entry_zone_high": 249.69,
                    "stop_loss": 233.0,
                    "take_profit": 270.0,
                },
            }],
            "deployed_pct": 0.0, "reserved_pct": 15.0, "cash_reserve_pct": 85.0,
        }

        with pytest.raises(BoundsViolationError) as exc_info:
            flow._finalize_and_validate_portfolio(structured, "conservative")
        assert any(
            v["rule"] == "wait_for_entry_at_current_entry" and v["ticker"] == "ABBV"
            for v in exc_info.value.violations
        )

    def test_flow_allows_wait_for_entry_at_pullback_entry(self, flow):
        # PULLBACK_ENTRY is fully open per reasoning-depth-action-selection --
        # WAIT-FOR-ENTRY there must not trip the CURRENT_ENTRY-only check.
        flow.state.technical_output = _technical_output("MRK", 100.0, 105.0, 108.0)  # PULLBACK_ENTRY by default

        structured = {
            "positions": [{
                "ticker": "MRK",
                "action": "WAIT-FOR-ENTRY",
                "composite_score": 80.0,
                "current_price": 108.0,
                "trade_setup": {
                    "direction": "LONG-BUY",
                    "entry_zone_low": 100.0,
                    "entry_zone_high": 105.0,
                    "stop_loss": 97.0,
                    "take_profit": 115.0,
                },
            }],
            "deployed_pct": 0.0, "reserved_pct": 15.0, "cash_reserve_pct": 85.0,
        }

        repriced = flow._finalize_and_validate_portfolio(structured, "conservative")
        assert repriced["positions"][0]["action"] == "WAIT-FOR-ENTRY"


# ── D-08: fundamentals_status stamped and buy-on-UNKNOWN fails closed ────────

def _fundamental_output(ticker, quality, growth):
    from schemas.agent_outputs import (
        FundamentalAnalysisOutput, FundamentalRating, StockFundamentalAnalysis, ValuationMetrics,
    )
    return FundamentalAnalysisOutput(
        sector="Energy",
        summary="S" * 100,
        fundamental_analysis=[StockFundamentalAnalysis(
            ticker=ticker, company_name=f"{ticker} Inc", valuation_metrics=ValuationMetrics(),
            fundamental_rating=FundamentalRating(valuation="FAIR", quality=quality, growth=growth),
            key_strengths=["s"], key_risks=["r"], investment_thesis="T" * 20,
        )],
    )


def _buy_structured(ticker, action="LONG-BUY", status=None):
    pos = {
        "ticker": ticker, "action": action, "composite_score": 80.0, "current_price": 108.0,
        "trade_setup": {"direction": "LONG-BUY", "entry_zone_low": 100.0, "entry_zone_high": 105.0,
                        "stop_loss": 97.0, "take_profit": 115.0},
    }
    if status is not None:
        pos["fundamentals_status"] = status
    return {"positions": [pos], "deployed_pct": 0.0, "reserved_pct": 0.0, "cash_reserve_pct": 100.0}


class TestFundamentalsStatusStamped:
    def test_flow_stamps_fundamentals_status(self, flow):
        flow.state.technical_output = _technical_output("MRK", 100.0, 105.0, 108.0)
        flow.state.fundamental_output = _fundamental_output("MRK", "Medium", "Stable")

        # An LLM-written UNKNOWN is overwritten by the deterministic AVAILABLE.
        repriced = flow._finalize_and_validate_portfolio(_buy_structured("MRK", status="UNKNOWN"), "conservative")

        assert repriced["positions"][0]["fundamentals_status"] == "AVAILABLE"

    def test_ticker_without_fundamental_record_gets_none(self, flow):
        flow.state.technical_output = _technical_output("MRK", 100.0, 105.0, 108.0)
        flow.state.fundamental_output = None

        repriced = flow._finalize_and_validate_portfolio(_buy_structured("MRK", status="AVAILABLE"), "conservative")

        assert repriced["positions"][0]["fundamentals_status"] is None

    def test_monitor_on_unknown_publishes_with_unknown_status(self, flow):
        flow.state.technical_output = _technical_output("MRK", 100.0, 105.0, 108.0)
        flow.state.fundamental_output = _fundamental_output("MRK", "UNKNOWN", "Stable")

        repriced = flow._finalize_and_validate_portfolio(_buy_structured("MRK", action="MONITOR"), "conservative")

        assert repriced["positions"][0]["fundamentals_status"] == "UNKNOWN"


class TestBuyOnUnknownFundamentalsCaught:
    @pytest.mark.parametrize("action", ["LONG-BUY", "WAIT-FOR-ENTRY"])
    def test_flow_raises_for_buy_on_unknown(self, flow, action):
        flow.state.technical_output = _technical_output("MRK", 100.0, 105.0, 108.0)
        flow.state.fundamental_output = _fundamental_output("MRK", "Low", "UNKNOWN")

        with pytest.raises(BoundsViolationError) as exc_info:
            flow._finalize_and_validate_portfolio(_buy_structured("MRK", action=action), "conservative")

        assert any(
            v["rule"] == "buy_with_unknown_fundamentals" and v["ticker"] == "MRK"
            for v in exc_info.value.violations
        )


# ── Composite score comes from Flow state, never from the LLM's dict (plan 02-18, T-02-46) ──

class TestRepriceUsesFlowComposite:
    @staticmethod
    def _structured(composite):
        return {
            "sector": "Energy", "risk_profile": "conservative",
            "positions": [{
                "ticker": "XOM", "action": "LONG-BUY", "composite_score": composite,
                "allocation_pct": 0.0, "current_price": 118.0, "trade_setup": None,
            }],
        }

    def test_reprice_uses_flow_composite(self, flow):
        from utils.portfolio_allocator_tool import PortfolioAllocatorTool

        flow.state.technical_output = _technical_output("XOM", 114.0, 116.5, 118.0)
        flow.state.composite_scores = {"XOM": {"ticker": "XOM", "composite_score": 61.5}}
        sent = []
        real = PortfolioAllocatorTool._run

        def spy(self, stocks_json):
            sent.append(json.loads(stocks_json))
            return real(self, stocks_json)

        with patch.object(PortfolioAllocatorTool, "_run", spy):
            flow._reprice_final_output(self._structured(composite=99.0), "conservative")
        assert [s["composite_score"] for s in sent[0]["stocks"]] == [61.5]

    def test_a_ticker_without_a_flow_score_fails_closed(self, flow):
        flow.state.technical_output = _technical_output("XOM", 114.0, 116.5, 118.0)
        flow.state.composite_scores = {}
        with pytest.raises(BoundsViolationError) as info:
            flow._reprice_final_output(self._structured(composite=99.0), "conservative")
        [violation] = info.value.violations
        assert violation["rule"] == "composite_score_missing" and violation["ticker"] == "XOM"

    def test_no_zero_default_for_a_missing_score(self, flow):
        flow.state.technical_output = _technical_output("XOM", 114.0, 116.5, 118.0)
        flow.state.composite_scores = {"OTHER": {"ticker": "OTHER", "composite_score": 70.0}}
        with pytest.raises(BoundsViolationError):
            flow._finalize_and_validate_portfolio(self._structured(composite=70.0), "conservative")
