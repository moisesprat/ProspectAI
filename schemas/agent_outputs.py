"""
ProspectAI v1.2.0 — Pydantic output schemas for inter-agent data contracts.
These schemas replace freeform text passing between agents with validated,
typed structures. The Investor Strategic Agent reads these directly.
"""

from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# MARKET ANALYST OUTPUT
# ---------------------------------------------------------------------------

class CandidateStock(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol, e.g. AAPL")
    mention_count: int = Field(..., ge=0)
    average_sentiment: float = Field(..., ge=-1.0, le=1.0)
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., min_length=50)


class MarketAnalysisOutput(BaseModel):
    sector: str
    candidate_stocks: List[CandidateStock] = Field(..., min_length=1, max_length=10)
    summary: str = Field(..., min_length=100)


# ---------------------------------------------------------------------------
# TECHNICAL ANALYST OUTPUT
# ---------------------------------------------------------------------------

class SupportResistance(BaseModel):
    support: Optional[float] = None
    resistance: Optional[float] = None

    @model_validator(mode="after")
    def support_below_resistance(self) -> SupportResistance:
        if self.support is not None and self.resistance is not None:
            if self.support >= self.resistance:
                raise ValueError(
                    f"support {self.support} must be strictly less than "
                    f"resistance {self.resistance}"
                )
        return self


class MomentumAnalysis(BaseModel):
    momentum_score: float = Field(..., ge=0.0, le=10.0)
    risk_level: Literal["Low", "Medium", "High"]
    trend_strength: Literal["Very Weak", "Weak", "Neutral", "Strong", "Very Strong"]
    key_signals: List[str]
    support_resistance: SupportResistance
    comprehensive_analysis: str = Field(..., min_length=50)


class TechnicalScore(BaseModel):
    percentage: float = Field(..., ge=0.0, le=100.0)
    grade: str
    recommendation: Literal["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]


class StockTechnicalAnalysis(BaseModel):
    ticker: str
    current_price: float = Field(..., gt=0)
    momentum_analysis: MomentumAnalysis
    technical_score: TechnicalScore
    investment_recommendation: str = Field(..., min_length=50)


class TechnicalAnalysisOutput(BaseModel):
    sector: str
    technical_analysis: List[StockTechnicalAnalysis] = Field(..., min_length=1)
    summary: str = Field(..., min_length=100)


# ---------------------------------------------------------------------------
# FUNDAMENTAL ANALYST OUTPUT
# ---------------------------------------------------------------------------

class ValuationMetrics(BaseModel):
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    price_to_sales: Optional[float] = None
    debt_to_equity: Optional[float] = None
    roe: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    earnings_growth_yoy: Optional[float] = None
    free_cash_flow: Optional[float] = None
    dividend_yield: Optional[float] = Field(None, ge=0.0)


class FundamentalRating(BaseModel):
    valuation: Literal["Undervalued", "Fairly Valued", "Overvalued"]
    quality: Literal["Low", "Medium", "High"]
    growth: Literal["Declining", "Stable", "Moderate Growth", "High Growth"]
    overall: Literal["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]


class StockFundamentalAnalysis(BaseModel):
    ticker: str
    company_name: str
    valuation_metrics: ValuationMetrics
    fundamental_rating: FundamentalRating
    key_strengths: List[str] = Field(..., min_length=1)
    key_risks: List[str] = Field(..., min_length=1)
    investment_thesis: str = Field(..., min_length=50)


class FundamentalAnalysisOutput(BaseModel):
    sector: str
    fundamental_analysis: List[StockFundamentalAnalysis] = Field(..., min_length=1)
    summary: str = Field(..., min_length=100)


# ---------------------------------------------------------------------------
# INVESTOR STRATEGIC OUTPUT (used for final report validation)
# ---------------------------------------------------------------------------

class TradeSetup(BaseModel):
    direction: Literal["LONG-BUY"]
    entry_zone_low: float = Field(..., gt=0)
    entry_zone_high: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    take_profit: float = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_long_trade_structure(self) -> TradeSetup:
        if not (self.stop_loss < self.entry_zone_low):
            raise ValueError(
                f"LONG-BUY invariant violated: "
                f"stop_loss ({self.stop_loss}) must be < "
                f"entry_zone_low ({self.entry_zone_low}). "
                f"Required: stop_loss < entry_zone_low <= entry_zone_high < take_profit."
            )
        if not (self.entry_zone_low <= self.entry_zone_high):
            raise ValueError(
                f"entry_zone_low ({self.entry_zone_low}) must be <= "
                f"entry_zone_high ({self.entry_zone_high})"
            )
        if not (self.entry_zone_high < self.take_profit):
            raise ValueError(
                f"entry_zone_high ({self.entry_zone_high}) must be < "
                f"take_profit ({self.take_profit})"
            )
        return self


class PositionRecommendation(BaseModel):
    ticker: str
    action: Literal["LONG-BUY", "SCALED-ENTRY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID"]
    allocation_pct: float = Field(..., ge=0.0, le=100.0)
    current_price: Optional[float] = Field(None, gt=0)
    trade_setup: Optional[TradeSetup] = None
    scaled_entry_setups: Optional[List[TradeSetup]] = None
    rationale: str = Field(..., min_length=50)
    monitoring_triggers: List[str] = Field(..., min_length=1)
    review_frequency: Literal["DAILY", "WEEKLY", "MONTHLY"]

    @model_validator(mode="after")
    def validate_setup_fields_by_action(self) -> "PositionRecommendation":
        if self.action == "SCALED-ENTRY":
            n = len(self.scaled_entry_setups) if self.scaled_entry_setups else 0
            if n != 2:
                raise ValueError(
                    f"SCALED-ENTRY requires exactly 2 scaled_entry_setups "
                    f"[immediate_tranche, pullback_tranche]; got {n}"
                )
            if self.trade_setup is not None:
                raise ValueError(
                    "SCALED-ENTRY must have trade_setup=null; "
                    "execution details go in scaled_entry_setups"
                )
        return self


class InvestorStrategicOutput(BaseModel):
    sector: str
    positions: List[PositionRecommendation] = Field(..., min_length=1)
    deployed_pct: float = Field(..., ge=0.0, le=100.0)
    reserved_pct: float = Field(..., ge=0.0, le=100.0)
    total_allocated_pct: float = Field(..., ge=0.0, le=100.0)
    cash_reserve_pct: float = Field(..., ge=0.0, le=100.0)
    overall_strategy: str = Field(..., min_length=100)
    risk_level: Literal["Low", "Medium", "High", "Very High"]

    @model_validator(mode="after")
    def validate_capital_buckets(self) -> "InvestorStrategicOutput":
        total = sum(p.allocation_pct for p in self.positions)
        if abs(total - self.total_allocated_pct) > 0.5:
            raise ValueError(
                f"sum of position allocations ({total:.1f}%) does not match "
                f"total_allocated_pct ({self.total_allocated_pct}%)"
            )
        bucket_sum = round(self.deployed_pct + self.reserved_pct + self.cash_reserve_pct, 1)
        if abs(bucket_sum - 100.0) > 0.5:
            raise ValueError(
                f"deployed ({self.deployed_pct}%) + reserved ({self.reserved_pct}%) "
                f"+ cash ({self.cash_reserve_pct}%) = {bucket_sum}% ≠ 100%"
            )
        return self


# ---------------------------------------------------------------------------
# CRITIC OUTPUT
# ---------------------------------------------------------------------------

class CritiqueItem(BaseModel):
    ticker: str
    severity: Literal["CRITICAL", "MAJOR", "MINOR"]
    issue_type: str = Field(..., min_length=3)
    finding: str = Field(..., min_length=30)
    instruction: str = Field(..., min_length=30)


class CriticOutput(BaseModel):
    sector: str
    draft_assessment: str = Field(..., min_length=50)
    per_ticker_critiques: List[CritiqueItem] = Field(..., min_length=1)
    portfolio_level_issues: List[str]
    revision_directives: List[str] = Field(..., min_length=1)
    approved_positions: List[str]
