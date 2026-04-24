## ADDED Requirements

### Requirement: Critic receives a compact per-ticker reference table instead of full slim outputs
The `critique_review()` flow method SHALL build the Critic's context from two inputs only: the full `_slim_draft()` output and a compact per-ticker reference table produced by `_critic_reference_table()`. The three full slim outputs (`_slim_market_for_strategy()`, `_slim_technical()`, `_slim_fundamental()`) SHALL NOT be included in the Critic's context.

#### Scenario: Critic context contains reference_table not stock_analyses
- **WHEN** `critique_review()` assembles the task description context
- **THEN** the injected JSON SHALL contain a `reference_table` key with one object per ticker
- **AND** the injected JSON SHALL NOT contain `market_analysis`, `stock_analyses`, or `fundamental_analysis` keys from the full slim outputs

#### Scenario: Reference table contains only checklist-referenced fields
- **WHEN** `_critic_reference_table()` is called with populated state
- **THEN** each ticker object in `reference_table` SHALL contain exactly: `ticker`, `rsi`, `stochastic_status`, `macd_status`, `entry_zone_status`, `momentum_score`, `average_sentiment`, `valuation_grade`, `financial_health`
- **AND** no other fields (raw ATR, SMA, Bollinger Band, EV/EBITDA, investment thesis text) SHALL be present

### Requirement: `_critic_reference_table()` builds from typed state models
A new `_critic_reference_table()` method SHALL be added to `ProspectAIFlow`. It SHALL access `self.state.market_output`, `self.state.technical_output`, and `self.state.fundamental_output` as typed Pydantic models and build the reference table from their attributes directly — no `json.loads()` or string parsing.

#### Scenario: Reference table populated from typed state
- **WHEN** all three upstream state fields are populated Pydantic model instances
- **THEN** `_critic_reference_table()` SHALL return a JSON string with `reference_table` containing one row per ticker found in `technical_output.technical_analysis`
- **AND** each row SHALL include `rsi` from `StockTechnicalAnalysis.raw_indicators.rsi`, `stochastic_status` from `raw_indicators.stochastic_status`, `macd_status` from `raw_indicators.macd_status`, `entry_zone_status` from `MomentumAnalysis.entry_zone_status`, `momentum_score` from `MomentumAnalysis.momentum_score`, `average_sentiment` from `MarketAnalysisOutput.candidate_stocks`, `valuation_grade` from `FundamentalRating.valuation`, and `financial_health` from `FundamentalRating.quality`

#### Scenario: None state fields produce empty table gracefully
- **WHEN** any of `market_output`, `technical_output`, or `fundamental_output` is `None`
- **THEN** `_critic_reference_table()` SHALL return a JSON string with an empty `reference_table` array rather than raising an exception

#### Scenario: Missing raw_indicators per ticker does not break table
- **WHEN** a `StockTechnicalAnalysis` entry has `raw_indicators=None`
- **THEN** the corresponding reference table row SHALL contain `null` for `rsi`, `stochastic_status`, and `macd_status` rather than raising an exception

### Requirement: `critique_review` task description references `reference_table` field names
The `critique_review` task description in `config/tasks.yaml` SHALL reference the field names present in the compact reference table (`reference_table`, `rsi`, `stochastic_status`, `entry_zone_status`, `average_sentiment`, `valuation_grade`, `financial_health`) and SHALL NOT reference `stock_analyses` or other fields from the full slim outputs.

#### Scenario: Task description matches context shape
- **WHEN** the Critic agent reads its task description
- **THEN** the STEP 1 instruction SHALL direct it to read `reference_table` for verification data, not `stock_analyses`
- **AND** the field names cited in the issue-type checklist SHALL match the field names present in the injected reference table JSON
