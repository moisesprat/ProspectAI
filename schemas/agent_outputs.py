"""
ProspectAI v1.2.0 — Pydantic output schemas for inter-agent data contracts.
These schemas replace freeform text passing between agents with validated,
typed structures. The Investor Strategic Agent reads these directly.
"""

from __future__ import annotations
from datetime import datetime
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
    analysis_timestamp: Optional[datetime] = None


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


class RawIndicators(BaseModel):
    rsi: Optional[float] = None
    stochastic_status: Optional[str] = None
    macd_status: Optional[str] = None
    ma_status: Optional[str] = None
    adx: Optional[float] = None


_RISK_LEVEL_MAP = {v.lower(): v for v in ("Low", "Medium", "High")}


class MomentumAnalysis(BaseModel):
    momentum_score: float = Field(..., ge=0.0, le=10.0)
    risk_level: Literal["Low", "Medium", "High"]
    trend_strength: Literal["Very Weak", "Weak", "Neutral", "Strong", "Very Strong"]

    @field_validator("risk_level", mode="before")
    @classmethod
    def normalize_risk_level(cls, v: str) -> str:
        return _RISK_LEVEL_MAP.get(str(v).lower(), v)
    key_signals: List[str]
    support_resistance: SupportResistance
    comprehensive_analysis: str = Field(..., min_length=50)
    overall_signal: Optional[str] = None       # "BULLISH", "BEARISH", "MIXED", "NEUTRAL"
    entry_zone_status: Optional[str] = None    # "PULLBACK_ENTRY", "CURRENT_ENTRY", "BELOW_ZONE"
    entry_zone_low: Optional[float] = None     # copied verbatim from interpret_technical_indicators
    entry_zone_high: Optional[float] = None    # copied verbatim from interpret_technical_indicators
    regime: Optional[str] = None               # "TRENDING", "REVERTING", "NEUTRAL"


class TechnicalScore(BaseModel):
    percentage: float = Field(..., ge=0.0, le=100.0)
    grade: str
    recommendation: Literal["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]


class StockTechnicalAnalysis(BaseModel):
    ticker: str
    current_price: Optional[float] = Field(None, gt=0)
    price_data_error: Optional[str] = None
    raw_indicators: Optional[RawIndicators] = None
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
    valuation: Literal["CHEAP", "FAIR", "EXPENSIVE", "VERY_EXPENSIVE"]
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
    investment_thesis: str = Field(..., min_length=10)


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

    @field_validator("direction", mode="before")
    @classmethod
    def _upper(cls, v: object) -> object:
        return v.upper().replace(" ", "") if isinstance(v, str) else v

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
    composite_score: float = Field(..., ge=0.0, le=100.0)
    allocation_pct: float = Field(..., ge=0.0, le=100.0)
    current_price: Optional[float] = Field(None, gt=0)
    trade_setup: Optional[TradeSetup] = None
    scaled_entry_setups: Optional[List[TradeSetup]] = None
    rationale: str = Field(..., min_length=50)
    monitoring_triggers: List[str] = Field(..., min_length=1)
    review_frequency: Literal["DAILY", "WEEKLY", "MONTHLY"]

    @field_validator("action", "review_frequency", mode="before")
    @classmethod
    def _upper(cls, v: object) -> object:
        return v.upper().replace(" ", "") if isinstance(v, str) else v

    @model_validator(mode="after")
    def validate_setup_fields_by_action(self) -> "PositionRecommendation":
        if self.action in ("LONG-BUY", "WAIT-FOR-ENTRY"):
            if self.trade_setup is None:
                price = self.current_price
                if price:
                    stop = round(price * 0.97, 2)
                    tp   = round(price + (price - stop) * 2, 2)
                    self.trade_setup = TradeSetup(
                        direction="LONG-BUY",
                        entry_zone_low=price,
                        entry_zone_high=price,
                        stop_loss=stop,
                        take_profit=tp,
                    )
        if self.action == "SCALED-ENTRY":
            setups = self.scaled_entry_setups or []
            if len(setups) != 2:
                price = self.current_price
                if price:
                    stop_imm = round(price * 0.97, 2)
                    tp_imm   = round(price + (price - stop_imm) * 2, 2)
                    immediate = TradeSetup(
                        direction="LONG-BUY",
                        entry_zone_low=price,
                        entry_zone_high=price,
                        stop_loss=stop_imm,
                        take_profit=tp_imm,
                    )
                    # Use zone from existing setup if present, else fall back to current_price
                    zone_low  = setups[0].entry_zone_low  if setups else price
                    zone_high = setups[0].entry_zone_high if setups else price
                    stop_pb = round(zone_low * 0.97, 2)
                    tp_pb   = round(zone_high + (zone_low - stop_pb) * 2, 2)
                    pullback = TradeSetup(
                        direction="LONG-BUY",
                        entry_zone_low=zone_low,
                        entry_zone_high=zone_high,
                        stop_loss=stop_pb,
                        take_profit=tp_pb,
                    )
                    self.scaled_entry_setups = [immediate, pullback]
                else:
                    raise ValueError(
                        "SCALED-ENTRY requires exactly 2 scaled_entry_setups; "
                        "current_price not available to auto-construct them"
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

    @field_validator("deployed_pct", "reserved_pct", "total_allocated_pct", "cash_reserve_pct", mode="before")
    @classmethod
    def _clamp_pct(cls, v: object) -> object:
        # LLM float arithmetic can produce values like 100.1 or -0.1 due to rounding.
        # Clamp to [0, 100] before Pydantic's ge/le constraints run.
        if isinstance(v, (int, float)):
            return round(min(100.0, max(0.0, float(v))), 2)
        return v

    @model_validator(mode="after")
    def validate_capital_buckets(self) -> "InvestorStrategicOutput":
        # total_allocated_pct is purely derived from position allocations.
        # Auto-correct it so a LLM copy-paste discrepancy doesn't fail the run.
        computed_total = round(sum(p.allocation_pct for p in self.positions), 1)
        if abs(computed_total - self.total_allocated_pct) > 0.5:
            self.total_allocated_pct = computed_total

        bucket_sum = round(self.deployed_pct + self.reserved_pct + self.cash_reserve_pct, 1)
        if abs(bucket_sum - 100.0) > 0.5:
            # LLM arithmetic errors (e.g. double-counting cash) are corrected automatically.
            # Prefer deriving cash from the other two; if deployed+reserved already exceed 100,
            # normalize all three proportionally.
            dr_sum = self.deployed_pct + self.reserved_pct
            if dr_sum <= 100.0:
                self.cash_reserve_pct = round(100.0 - dr_sum, 2)
            elif bucket_sum > 0:
                scale = 100.0 / bucket_sum
                self.deployed_pct = round(self.deployed_pct * scale, 2)
                self.reserved_pct = round(self.reserved_pct * scale, 2)
                self.cash_reserve_pct = round(100.0 - self.deployed_pct - self.reserved_pct, 2)
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

    @field_validator("severity", mode="before")
    @classmethod
    def _upper(cls, v: object) -> object:
        return v.upper() if isinstance(v, str) else v


class CriticOutput(BaseModel):
    sector: str
    draft_assessment: str = Field(..., min_length=50)
    per_ticker_critiques: List[CritiqueItem] = Field(..., min_length=1)
    portfolio_level_issues: List[str]
    revision_directives: List[str] = Field(..., min_length=1)
    approved_positions: List[str]
