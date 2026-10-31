# ProspectAI Agent Output Schemas

This package defines the typed Pydantic data contracts between the four agents in the ProspectAI pipeline. Each upstream agent's CrewAI `Task` is wired with `output_pydantic=` to enforce these schemas at runtime.

## Schemas

### `MarketAnalysisOutput` (Task 1 — Market Analyst)

Captures the top candidate stocks identified from Reddit sentiment and web search. Each `CandidateStock` includes mention count, average sentiment score (−1.0 to 1.0), a relevance score (0.0 to 1.0), and a rationale. `mention_count`, `average_sentiment` and `relevance_score` are optional: null means no source measured them (never 0 and never 0.5).
- The Flow calls Reddit and, when Reddit asks for fallback, Serper, and measures every number, `sentiment_available` and the timestamp (`utils/market_records.py`); the LLM writes only `MarketNarrativeOutput` (up to 5 `{ticker, rationale}` picks from the supplied corpus, and the summary). Serper-path sentiment is null (plan 02-16, operator decision A).

### `TechnicalAnalysisOutput` (Task 2 — Technical Analyst)

One `StockTechnicalAnalysis` entry per candidate ticker. Contains:
- `MomentumAnalysis`: momentum score (0–10), risk level, trend strength (derived from ADX, null when ADX is missing), key signals, entry zone and regime; `support_resistance` is optional and null because no tool computes it
- `failed_tickers`: tickers whose indicators could not be computed (excluded from the analyses)
- The Flow builds every number and label from the indicator tool; the LLM writes only `TechnicalNarrativeOutput` (`overall_signal`, key signals, analysis text). `TechnicalScore` was removed in plan 02-15.

### `FundamentalAnalysisOutput` (Task 3 — Fundamental Analyst)

One `StockFundamentalAnalysis` entry per candidate ticker. Contains valuation metrics (P/E, P/B, EV/EBITDA, etc.), a `FundamentalRating` (valuation, quality, growth, overall), key strengths, key risks, and investment thesis.

### `InvestorStrategicOutput` (Task 4 — Investor Strategic Agent)

Final portfolio synthesis. Each `PositionRecommendation` may include a `TradeSetup` with entry zone, stop loss, and take profit.
- Draft phase (plan 02-17): the Flow computes the composite scores before the LLM, then allocates after it, and assembles this model (`utils/strategy_assembly.py`). The LLM writes only `StrategyNarrativeOutput`: per ticker an `action`, a `rationale`, `monitoring_triggers` and a `review_frequency`, plus `overall_strategy`. An action outside the ticker's eligible set (the action policy table, including the `FUNDAMENTALS_UNKNOWN` row) becomes `MONITOR` with a fixed rationale sentence and a validation warning. The portfolio `risk_level` is derived from the allocation-weighted technical risk of the deployed positions (rule in the module docstring). `action`, `review_frequency` and `TradeSetup.direction` are strict Literals: a case or whitespace variant is a validation error.

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
