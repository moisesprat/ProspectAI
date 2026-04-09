"""
Unit tests for schemas/agent_outputs.py.
Verifies module import, valid instantiation of all four schemas,
and that trade-structure invariant violations raise ValidationError.
"""
import pytest
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
)


# ---------------------------------------------------------------------------
# MarketAnalysisOutput
# ---------------------------------------------------------------------------

def test_market_analysis_output_valid():
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
    assert output.sector == "Technology"
    assert len(output.candidate_stocks) == 1
    assert output.candidate_stocks[0].ticker == "AAPL"


# ---------------------------------------------------------------------------
# TechnicalAnalysisOutput
# ---------------------------------------------------------------------------

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
                    percentage=72.0,
                    grade="B+",
                    recommendation="Buy",
                ),
                investment_recommendation=(
                    "AAPL is technically sound with a confirmed uptrend, moderate risk, "
                    "and favorable risk/reward at current levels near the support zone."
                ),
            )
        ],
        summary=(
            "Technology sector technical picture is constructive. Most candidates display "
            "bullish momentum indicators, with AAPL leading in technical score. Key support "
            "levels are holding and volume patterns confirm institutional accumulation."
        ),
    )
    assert output.technical_analysis[0].current_price == 185.50


# ---------------------------------------------------------------------------
# FundamentalAnalysisOutput
# ---------------------------------------------------------------------------

def test_fundamental_analysis_output_valid():
    output = FundamentalAnalysisOutput(
        sector="Technology",
        fundamental_analysis=[
            StockFundamentalAnalysis(
                ticker="AAPL",
                company_name="Apple Inc.",
                valuation_metrics=ValuationMetrics(
                    pe_ratio=28.5,
                    pb_ratio=45.2,
                    ev_ebitda=22.1,
                    price_to_sales=7.3,
                    debt_to_equity=1.8,
                    roe=0.145,
                    revenue_growth_yoy=0.062,
                    earnings_growth_yoy=0.08,
                    free_cash_flow=95_000_000_000.0,
                    dividend_yield=0.005,
                ),
                fundamental_rating=FundamentalRating(
                    valuation="Fairly Valued",
                    quality="High",
                    growth="Moderate Growth",
                    overall="Buy",
                ),
                key_strengths=["Industry-leading margins", "Strong free cash flow generation"],
                key_risks=["China revenue concentration", "Slowing iPhone upgrade cycle"],
                investment_thesis=(
                    "Apple's ecosystem lock-in and services revenue diversification provide "
                    "a durable competitive moat supporting a premium valuation."
                ),
            )
        ],
        summary=(
            "Technology sector fundamentals remain solid with strong balance sheets and "
            "improving margins across most candidates. AAPL stands out for its cash generation "
            "and return on equity, though premium valuations limit upside relative to peers."
        ),
    )
    assert output.fundamental_analysis[0].ticker == "AAPL"


# ---------------------------------------------------------------------------
# InvestorStrategicOutput
# ---------------------------------------------------------------------------

def test_investor_strategic_output_valid():
    output = InvestorStrategicOutput(
        sector="Technology",
        positions=[
            PositionRecommendation(
                ticker="AAPL",
                action="LONG-BUY",
                allocation_pct=15.0,
                trade_setup=TradeSetup(
                    direction="LONG-BUY",
                    entry_zone_low=182.0,
                    entry_zone_high=186.0,
                    stop_loss=175.0,
                    take_profit=205.0,
                ),
                rationale=(
                    "AAPL offers a compelling risk/reward within a diversified tech allocation. "
                    "Strong fundamentals, technical confirmation, and positive sentiment align."
                ),
                monitoring_triggers=["Weekly RSI cross below 45", "Revenue miss >5%"],
                review_frequency="WEEKLY",
            )
        ],
        total_allocated_pct=15.0,
        cash_reserve_pct=85.0,
        overall_strategy=(
            "Conservative single-position entry in Technology sector. Concentrate in highest-"
            "conviction name (AAPL) while maintaining elevated cash reserves to average down "
            "on weakness or add new positions as technical setups emerge over the next 4–6 weeks."
        ),
        risk_level="Low",
    )
    assert output.total_allocated_pct == 15.0
    assert output.cash_reserve_pct == 85.0


# ---------------------------------------------------------------------------
# TradeSetup invariant — LONG-BUY with stop_loss > entry_zone_low must fail
# ---------------------------------------------------------------------------

def test_trade_setup_long_buy_invalid_stop_loss():
    with pytest.raises(ValidationError) as exc_info:
        TradeSetup(
            direction="LONG-BUY",
            entry_zone_low=182.0,
            entry_zone_high=186.0,
            stop_loss=190.0,  # invalid: stop_loss > entry_zone_low
            take_profit=205.0,
        )
    assert "LONG-BUY invariant violated" in str(exc_info.value)


# ---------------------------------------------------------------------------
# SupportResistance invariant
# ---------------------------------------------------------------------------

def test_support_resistance_invalid():
    with pytest.raises(ValidationError):
        SupportResistance(support=200.0, resistance=150.0)


# ---------------------------------------------------------------------------
# InvestorStrategicOutput allocation mismatch
# ---------------------------------------------------------------------------

def test_investor_strategic_allocation_mismatch():
    with pytest.raises(ValidationError) as exc_info:
        InvestorStrategicOutput(
            sector="Technology",
            positions=[
                PositionRecommendation(
                    ticker="AAPL",
                    action="LONG-BUY",
                    allocation_pct=20.0,
                    rationale=(
                        "Strong fundamentals and technical confirmation align for a high-"
                        "conviction entry at current levels within the defined entry zone."
                    ),
                    monitoring_triggers=["RSI below 40"],
                    review_frequency="WEEKLY",
                )
            ],
            total_allocated_pct=30.0,  # mismatch: positions sum to 20.0
            cash_reserve_pct=70.0,
            overall_strategy=(
                "Selective single-name allocation with significant cash reserve to manage "
                "downside risk and capitalize on further pullbacks across the sector."
            ),
            risk_level="Medium",
        )
    assert "does not match" in str(exc_info.value)
