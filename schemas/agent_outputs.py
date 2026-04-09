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
    direction: Literal["LONG-BUY", "SHORT-SELL"]
    entry_zone_low: float = Field(..., gt=0)
    entry_zone_high: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    take_profit: float = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_long_trade_structure(self) -> TradeSetup:
        if self.direction == "LONG-BUY":
            if not (self.stop_loss < self.entry_zone_low):
                raise ValueError(
                    f"LONG-BUY invariant violated for trade: "
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
        if self.direction == "SHORT-SELL":
            if not (self.stop_loss > self.entry_zone_high):
                raise ValueError(
                    f"SHORT-SELL invariant violated: "
                    f"stop_loss ({self.stop_loss}) must be > "
                    f"entry_zone_high ({self.entry_zone_high})"
                )
        return self


class PositionRecommendation(BaseModel):
    ticker: str
    action: Literal["LONG-BUY", "SHORT-SELL", "HOLD", "WAIT-FOR-ENTRY", "AVOID"]
    allocation_pct: float = Field(..., ge=0.0, le=100.0)
    trade_setup: Optional[TradeSetup] = None
    rationale: str = Field(..., min_length=50)
    monitoring_triggers: List[str] = Field(..., min_length=1)
    review_frequency: Literal["DAILY", "WEEKLY", "MONTHLY"]


class InvestorStrategicOutput(BaseModel):
    sector: str
    positions: List[PositionRecommendation] = Field(..., min_length=1)
    total_allocated_pct: float = Field(..., ge=0.0, le=100.0)
    cash_reserve_pct: float = Field(..., ge=0.0, le=100.0)
    overall_strategy: str = Field(..., min_length=100)
    risk_level: Literal["Low", "Medium", "High", "Very High"]

    @model_validator(mode="after")
    def allocations_plus_cash_lte_100(self) -> InvestorStrategicOutput:
        total = sum(p.allocation_pct for p in self.positions)
        if abs(total - self.total_allocated_pct) > 0.5:
            raise ValueError(
                f"sum of position allocations ({total:.1f}%) does not match "
                f"total_allocated_pct ({self.total_allocated_pct}%)"
            )
        if total + self.cash_reserve_pct > 100.5:
            raise ValueError(
                f"total allocation ({total:.1f}%) + cash reserve "
                f"({self.cash_reserve_pct}%) exceeds 100%"
            )
        return self
