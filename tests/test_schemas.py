"""
Unit tests for schemas/agent_outputs.py.
Covers all five output schemas, key validation rules, and the new
composite_score / deployed_pct / reserved_pct fields added in v1.5+.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from schemas.agent_outputs import (
    CandidateStock,
    MarketAnalysisOutput,
    SupportResistance,
    MomentumAnalysis,
    TechnicalScore,
    StockTechnicalAnalysis,
    TechnicalAnalysisOutput,
    ValuationMetrics,
    FundamentalRating,
    StockFundamentalAnalysis,
    FundamentalAnalysisOutput,
    TradeSetup,
    PositionRecommendation,
    InvestorStrategicOutput,
    CriticOutput,
    CritiqueItem,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _trade_setup(**kwargs) -> TradeSetup:
    defaults = dict(direction="LONG-BUY", entry_zone_low=180.0,
                    entry_zone_high=186.0, stop_loss=174.0, take_profit=205.0)
    defaults.update(kwargs)
    return TradeSetup(**defaults)


def _position(**kwargs) -> PositionRecommendation:
    defaults = dict(
        ticker="AAPL",
        action="LONG-BUY",
        composite_score=75.0,
        allocation_pct=15.0,
        current_price=183.0,
        trade_setup=_trade_setup(),
        scaled_entry_setups=None,
        rationale=(
            "AAPL RSI=64, momentum_score=7.2, ADEQUATE health, MODERATE growth. "
            "Composite 75.0 supports LONG-BUY within entry zone 180-186."
        ),
        monitoring_triggers=["RSI crosses above 76", "Weekly close below SMA50"],
        review_frequency="WEEKLY",
    )
    defaults.update(kwargs)
    return PositionRecommendation(**defaults)


def _portfolio(**kwargs) -> InvestorStrategicOutput:
    defaults = dict(
        sector="Technology",
        positions=[_position()],
        deployed_pct=15.0,
        reserved_pct=0.0,
        total_allocated_pct=15.0,
        cash_reserve_pct=85.0,
        overall_strategy=(
            "Conservative single-position entry. Capital distributed proportionally "
            "to composite scores, capped per action type. deployed 15% + reserved 0% "
            "+ cash 85% = 100%."
        ),
        risk_level="Low",
    )
    defaults.update(kwargs)
    return InvestorStrategicOutput(**defaults)


# ── MarketAnalysisOutput ──────────────────────────────────────────────────────

def test_market_analysis_output_valid():
    ts = datetime(2026, 4, 20, 12, 0, 0)
    output = MarketAnalysisOutput(
        sector="Technology",
        candidate_stocks=[
            CandidateStock(
                ticker="AAPL",
                mention_count=120,
                average_sentiment=0.65,
                relevance_score=0.9,
                rationale="Apple dominates consumer tech with strong brand loyalty and consistent earnings growth.",
            )
        ],
        summary=(
            "The Technology sector shows strong bullish momentum driven by AI adoption. "
            "Apple leads mentions with positive sentiment across major subreddits including "
            "r/investing and r/stocks, supported by robust earnings expectations."
        ),
        analysis_timestamp=ts,
    )
    assert output.sector == "Technology"
    assert output.candidate_stocks[0].ticker == "AAPL"
    assert output.analysis_timestamp == ts


def test_market_analysis_output_timestamp_optional():
    output = MarketAnalysisOutput(
        sector="Technology",
        candidate_stocks=[
            CandidateStock(
                ticker="AAPL",
                mention_count=120,
                average_sentiment=0.65,
                relevance_score=0.9,
                rationale="Apple dominates consumer tech with strong brand loyalty and consistent earnings growth.",
            )
        ],
        summary=(
            "The Technology sector shows strong bullish momentum driven by AI adoption. "
            "Apple leads mentions with positive sentiment across major subreddits including "
            "r/investing and r/stocks, supported by robust earnings expectations."
        ),
    )
    assert output.analysis_timestamp is None


# ── TechnicalAnalysisOutput ───────────────────────────────────────────────────

def test_technical_analysis_output_valid():
    output = TechnicalAnalysisOutput(
        sector="Technology",
        technical_analysis=[
            StockTechnicalAnalysis(
                ticker="AAPL",
                current_price=185.50,
                momentum_analysis=MomentumAnalysis(
                    momentum_score=7.5,
                    risk_level="Medium",
                    trend_strength="Strong",
                    key_signals=["RSI 58 — neutral/bullish", "MACD positive crossover"],
                    support_resistance=SupportResistance(support=178.0, resistance=195.0),
                    comprehensive_analysis=(
                        "AAPL shows a strong uptrend with RSI in healthy territory and "
                        "MACD confirming bullish momentum above the signal line."
                    ),
                ),
                technical_score=TechnicalScore(
                    percentage=72.0, grade="B+", recommendation="Buy"
                ),
                investment_recommendation=(
                    "AAPL is technically sound with a confirmed uptrend and favorable "
                    "risk/reward at current levels near the support zone."
                ),
            )
        ],
        summary=(
            "Technology sector technical picture is constructive. Most candidates display "
            "bullish momentum indicators with key support levels holding."
        ),
    )
    assert output.technical_analysis[0].current_price == 185.50


def test_support_resistance_invalid():
    with pytest.raises(ValidationError):
        SupportResistance(support=200.0, resistance=150.0)


# ── FundamentalAnalysisOutput ─────────────────────────────────────────────────

def test_fundamental_analysis_output_valid():
    output = FundamentalAnalysisOutput(
        sector="Technology",
        fundamental_analysis=[
            StockFundamentalAnalysis(
                ticker="AAPL",
                company_name="Apple Inc.",
                valuation_metrics=ValuationMetrics(pe_ratio=28.5, pb_ratio=45.2),
                fundamental_rating=FundamentalRating(
                    valuation="EXPENSIVE", quality="High",
                    growth="Moderate Growth", overall="Buy"
                ),
                key_strengths=["Industry-leading margins"],
                key_risks=["China revenue concentration"],
                investment_thesis=(
                    "Apple's ecosystem lock-in and services revenue diversification "
                    "provide a durable competitive moat supporting a premium valuation."
                ),
            )
        ],
        summary=(
            "Technology sector fundamentals remain solid with strong balance sheets "
            "and improving margins across most candidates."
        ),
    )
    assert output.fundamental_analysis[0].ticker == "AAPL"


# ── TradeSetup invariants ─────────────────────────────────────────────────────

def test_trade_setup_valid():
    ts = _trade_setup()
    assert ts.stop_loss < ts.entry_zone_low <= ts.entry_zone_high < ts.take_profit


def test_trade_setup_stop_above_entry_fails():
    with pytest.raises(ValidationError) as exc:
        _trade_setup(stop_loss=190.0)  # stop_loss > entry_zone_low
    assert "LONG-BUY invariant violated" in str(exc.value)


def test_trade_setup_entry_zone_inverted_fails():
    with pytest.raises(ValidationError):
        _trade_setup(entry_zone_low=190.0, entry_zone_high=180.0,
                     stop_loss=175.0, take_profit=210.0)


def test_trade_setup_take_profit_below_zone_fails():
    with pytest.raises(ValidationError):
        _trade_setup(entry_zone_low=180.0, entry_zone_high=186.0,
                     stop_loss=174.0, take_profit=183.0)  # TP < entry_zone_high


# ── PositionRecommendation ────────────────────────────────────────────────────

def test_position_long_buy_valid():
    p = _position()
    assert p.action == "LONG-BUY"
    assert p.composite_score == 75.0
    assert p.trade_setup is not None
    assert p.scaled_entry_setups is None


def test_position_composite_score_required():
    with pytest.raises(ValidationError):
        PositionRecommendation(
            ticker="AAPL", action="LONG-BUY",
            allocation_pct=15.0, current_price=183.0,
            trade_setup=_trade_setup(), scaled_entry_setups=None,
            rationale="x" * 60,
            monitoring_triggers=["RSI above 76"],
            review_frequency="WEEKLY",
            # composite_score intentionally omitted
        )


def test_position_hold_rejected():
    with pytest.raises(ValidationError):
        _position(action="HOLD")


def test_position_short_sell_rejected():
    with pytest.raises(ValidationError):
        _position(action="SHORT-SELL")


def test_position_monitor_valid_no_setup():
    p = _position(
        action="MONITOR",
        composite_score=52.0,
        allocation_pct=0.0,
        trade_setup=None,
        scaled_entry_setups=None,
        rationale=(
            "MSFT RSI=72 VERY_EXPENSIVE valuation. composite_score=52.0 below "
            "threshold. Watching for pullback and valuation reset before deploying capital."
        ),
        monitoring_triggers=["RSI drops below 55", "PE below 28"],
    )
    assert p.action == "MONITOR"
    assert p.allocation_pct == 0.0
    assert p.trade_setup is None


def test_position_avoid_valid():
    p = _position(
        action="AVOID",
        composite_score=35.0,
        allocation_pct=0.0,
        trade_setup=None,
        scaled_entry_setups=None,
        rationale=(
            "WEAK balance sheet, negative revenue growth, negative sentiment. "
            "composite_score=35.0 disqualifies from any capital deployment."
        ),
        monitoring_triggers=["Revenue growth turns positive for two consecutive quarters"],
    )
    assert p.action == "AVOID"


def test_position_scaled_entry_auto_constructs_setups_from_price():
    # Validator auto-constructs 2 setups from current_price when none provided
    p = _position(
        action="SCALED-ENTRY",
        composite_score=78.0,
        current_price=183.0,
        trade_setup=None,
        scaled_entry_setups=None,
    )
    assert p.scaled_entry_setups is not None
    assert len(p.scaled_entry_setups) == 2


def test_position_scaled_entry_requires_two_setups_without_price():
    # No current_price and no setups — validator cannot auto-construct, must raise
    with pytest.raises(ValidationError) as exc:
        _position(
            action="SCALED-ENTRY",
            composite_score=78.0,
            current_price=None,
            trade_setup=None,
            scaled_entry_setups=None,
        )
    assert "2 scaled_entry_setups" in str(exc.value)


def test_position_scaled_entry_trade_setup_must_be_null():
    imm = _trade_setup(entry_zone_low=122.0, entry_zone_high=122.0,
                       stop_loss=118.34, take_profit=129.32)
    plb = _trade_setup(entry_zone_low=110.0, entry_zone_high=115.0,
                       stop_loss=106.7, take_profit=121.9)
    with pytest.raises(ValidationError) as exc:
        _position(
            action="SCALED-ENTRY",
            composite_score=78.0,
            trade_setup=imm,               # must be null for SCALED-ENTRY
            scaled_entry_setups=[imm, plb],
        )
    assert "trade_setup=null" in str(exc.value)


def test_position_scaled_entry_valid_with_two_setups():
    imm = _trade_setup(entry_zone_low=122.0, entry_zone_high=122.0,
                       stop_loss=118.34, take_profit=129.32)
    plb = _trade_setup(entry_zone_low=110.0, entry_zone_high=115.0,
                       stop_loss=106.7, take_profit=121.9)
    p = _position(
        action="SCALED-ENTRY",
        composite_score=78.0,
        allocation_pct=18.5,
        current_price=122.0,
        trade_setup=None,
        scaled_entry_setups=[imm, plb],
    )
    assert len(p.scaled_entry_setups) == 2


def test_position_wait_for_entry_valid():
    p = _position(
        action="WAIT-FOR-ENTRY",
        composite_score=68.0,
        allocation_pct=12.0,
        trade_setup=_trade_setup(),
        scaled_entry_setups=None,
    )
    assert p.action == "WAIT-FOR-ENTRY"
    assert p.allocation_pct == 12.0


# ── InvestorStrategicOutput ───────────────────────────────────────────────────

def test_investor_strategic_output_valid():
    output = _portfolio()
    assert output.total_allocated_pct == 15.0
    assert output.cash_reserve_pct == 85.0
    assert output.deployed_pct == 15.0
    assert output.reserved_pct == 0.0


def test_three_bucket_sum_must_equal_100():
    with pytest.raises(ValidationError) as exc:
        _portfolio(deployed_pct=40.0, reserved_pct=20.0, cash_reserve_pct=50.0)
        # 40 + 20 + 50 = 110 ≠ 100
    assert "100" in str(exc.value)


def test_position_allocation_sum_auto_corrects_total_allocated():
    # The validator auto-corrects total_allocated_pct from position sums
    # rather than raising, so a LLM copy-paste discrepancy doesn't fail the run.
    output = _portfolio(
        positions=[_position(allocation_pct=20.0)],
        deployed_pct=20.0,
        reserved_pct=0.0,
        total_allocated_pct=30.0,  # wrong — positions only sum to 20
        cash_reserve_pct=80.0,
    )
    assert output.total_allocated_pct == 20.0


def test_investor_strategic_with_scaled_entry_position():
    imm = _trade_setup(entry_zone_low=122.0, entry_zone_high=122.0,
                       stop_loss=118.34, take_profit=129.32)
    plb = _trade_setup(entry_zone_low=110.0, entry_zone_high=115.0,
                       stop_loss=106.7, take_profit=121.9)
    scaled_pos = _position(
        ticker="XOM",
        action="SCALED-ENTRY",
        composite_score=73.5,
        allocation_pct=20.0,
        current_price=122.0,
        trade_setup=None,
        scaled_entry_setups=[imm, plb],
    )
    output = _portfolio(
        positions=[scaled_pos],
        deployed_pct=10.0,   # half of 20% SCALED-ENTRY
        reserved_pct=10.0,
        total_allocated_pct=20.0,
        cash_reserve_pct=80.0,
    )
    assert output.positions[0].action == "SCALED-ENTRY"
    assert len(output.positions[0].scaled_entry_setups) == 2


# ── CriticOutput ─────────────────────────────────────────────────────────────

def test_critic_output_valid():
    output = CriticOutput(
        sector="Technology",
        draft_assessment=(
            "Draft portfolio has LONG-BUY on AAPL despite RSI=74 above overbought "
            "threshold. Rationale does not acknowledge overbought conditions."
        ),
        per_ticker_critiques=[
            CritiqueItem(
                ticker="AAPL",
                severity="CRITICAL",
                issue_type="OVERBOUGHT_IGNORED",
                finding="RSI=74 and Stochastic=82 but action is LONG-BUY with no acknowledgment.",
                instruction="Change action to WAIT-FOR-ENTRY or add overbought caveat and exit trigger.",
            )
        ],
        portfolio_level_issues=[
            "deployed_pct + reserved_pct + cash_reserve_pct = 101% — bucket sum error."
        ],
        revision_directives=[
            "AAPL: Change action to WAIT-FOR-ENTRY because RSI=74 and Stochastic=82."
        ],
        approved_positions=[],
    )
    assert output.per_ticker_critiques[0].severity == "CRITICAL"
    assert output.per_ticker_critiques[0].issue_type == "OVERBOUGHT_IGNORED"
