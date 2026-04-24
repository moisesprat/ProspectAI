# Capability Spec: Typed Flow State

## Overview

This spec defines the requirements for storing and accessing inter-phase data in `ProspectAIFlow` as typed Pydantic models rather than raw JSON strings, eliminating silent re-parsing and restoring the validated data contracts that existed in `ProspectAICrew`.

---

## Requirements

### Requirement: Flow state stores typed Pydantic models for each phase output
`ProspectAIFlowState` SHALL declare each phase output field as `Optional[<TypedModel>]` initialized to `None`, where the type matches the `output_pydantic` schema set on the corresponding task. The five fields are:
- `market_output: Optional[MarketAnalysisOutput]`
- `technical_output: Optional[TechnicalAnalysisOutput]`
- `fundamental_output: Optional[FundamentalAnalysisOutput]`
- `draft_output: Optional[InvestorStrategicOutput]`
- `critique_output: Optional[CriticOutput]`

#### Scenario: State field type after market_analysis completes
- **WHEN** the `market_analysis` flow method completes successfully
- **THEN** `flow.state.market_output` SHALL be an instance of `MarketAnalysisOutput`, not a string

#### Scenario: State field before phase runs
- **WHEN** a flow method has not yet executed
- **THEN** its corresponding state field SHALL be `None`

### Requirement: Phase methods extract the validated Pydantic model from mini-Crew output
Each flow method (except `final_strategy`) SHALL assign the validated model from `result.tasks_output[0].pydantic` to its state field immediately after `akickoff()` returns.

#### Scenario: Validated model extracted, not raw string
- **WHEN** `technical_analysis` completes and `result.tasks_output[0].pydantic` is a `TechnicalAnalysisOutput`
- **THEN** `self.state.technical_output` SHALL equal that model instance
- **AND** `result.raw` SHALL NOT be stored anywhere in the flow state

### Requirement: Context slim helpers access model attributes directly
The `_slim_market_for_analysis`, `_slim_market_for_strategy`, `_slim_technical`, `_slim_fundamental`, `_slim_draft`, and `_slim_critique` helpers SHALL access the typed model's attributes (e.g., `mo.sector`, `s.ticker`) rather than parsing a JSON string.

#### Scenario: Slim helper with populated state
- **WHEN** `self.state.market_output` is a `MarketAnalysisOutput` instance
- **THEN** `_slim_market_for_analysis()` SHALL return a JSON string derived from model attribute access, with no call to `json.loads()`

#### Scenario: Slim helper with unpopulated state
- **WHEN** `self.state.market_output` is `None`
- **THEN** `_slim_market_for_analysis()` SHALL return an empty string `""`
- **AND** no exception SHALL be raised

### Requirement: Slim helper fallback paths to raw strings are removed
The `except Exception: return self.state.<field>` fallback branches in `_slim_*` helpers SHALL be removed. Validation is enforced at the mini-Crew boundary; if `pydantic` is `None`, the `None` guard in the helper is sufficient.

#### Scenario: No silent data corruption on field error
- **WHEN** a slim helper is invoked and the state model attribute has an unexpected value
- **THEN** the error SHALL propagate normally rather than silently returning a raw string blob as context

### Requirement: TechnicalAnalysisOutput schema captures all fields needed by downstream agents
`TechnicalAnalysisOutput` SHALL include the raw indicator readings and interpretation metadata that the draft strategy, critic, and final strategy agents reference by name. Specifically:

- A `RawIndicators` model SHALL be added with `Optional` fields: `rsi`, `stochastic_status`, `macd_status`, `ma_status`, `adx`.
- `StockTechnicalAnalysis` SHALL include `raw_indicators: Optional[RawIndicators]`.
- `MomentumAnalysis` SHALL include `overall_signal: Optional[str]`, `entry_zone_status: Optional[str]`, and `regime: Optional[str]`.

All new fields are `Optional` so that partial LLM output (e.g., a ticker with a price error) does not fail schema validation.

#### Scenario: Slim technical context contains raw indicators
- **WHEN** `_slim_technical()` is called with a populated `TechnicalAnalysisOutput` state
- **THEN** the returned JSON SHALL include a `raw_indicators` dict per ticker with `rsi`, `stochastic_status`, `macd_status`, `ma_status`, and `adx` keys
- **AND** the `interpretation` dict SHALL include `overall_signal`, `entry_zone_status`, and `regime` keys

#### Scenario: Missing raw indicators do not break slim
- **WHEN** a `StockTechnicalAnalysis` entry has `raw_indicators=None`
- **THEN** `_slim_technical()` SHALL emit `null` for each raw indicator field rather than raising an exception
