# ProspectAI Agent Output Schemas

This package defines the typed Pydantic data contracts between the four agents in the ProspectAI pipeline. Each upstream agent's CrewAI `Task` is wired with `output_pydantic=` to enforce these schemas at runtime.

## Schemas

### `MarketAnalysisOutput` (Task 1 — Market Analyst)

Captures the top candidate stocks identified from Reddit sentiment and web search. Each `CandidateStock` includes mention count, average sentiment score (−1.0 to 1.0), a relevance score (0.0 to 1.0), and a rationale.

### `TechnicalAnalysisOutput` (Task 2 — Technical Analyst)

One `StockTechnicalAnalysis` entry per candidate ticker. Contains:
- `MomentumAnalysis`: momentum score (0–10), risk level, trend strength, key signals, support/resistance levels
- `TechnicalScore`: percentage score (0–100), letter grade, and buy/sell recommendation

### `FundamentalAnalysisOutput` (Task 3 — Fundamental Analyst)

One `StockFundamentalAnalysis` entry per candidate ticker. Contains valuation metrics (P/E, P/B, EV/EBITDA, etc.), a `FundamentalRating` (valuation, quality, growth, overall), key strengths, key risks, and investment thesis.

### `InvestorStrategicOutput` (Task 4 — Investor Strategic Agent)

Final portfolio synthesis. Each `PositionRecommendation` may include a `TradeSetup` with entry zone, stop loss, and take profit.

## Trade Structure Invariants

### LONG-BUY
```
stop_loss < entry_zone_low <= entry_zone_high < take_profit
```
The stop loss must be below the entry zone, and the take profit must be above it.

### SHORT-SELL
```
stop_loss > entry_zone_high
```
The stop loss must be above the entry zone high for short positions.

## Allocation Validation

`InvestorStrategicOutput` validates that:
- The sum of all `allocation_pct` values matches `total_allocated_pct` (within 0.5% tolerance)
- `total_allocated_pct + cash_reserve_pct` does not exceed 100.5%
