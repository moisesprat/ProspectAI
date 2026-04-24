## 1. Update Flow State Schema

- [x] 1.1 Import `MarketAnalysisOutput`, `TechnicalAnalysisOutput`, `FundamentalAnalysisOutput`, `InvestorStrategicOutput`, `CriticOutput` at the top of `prospect_ai_flow.py`
- [x] 1.2 Change `ProspectAIFlowState` fields from `str` to `Optional[<TypedModel>]` with `None` defaults for the five phase output fields

## 2. Extract Typed Model After Each Mini-Crew

- [x] 2.1 In `market_analysis()`: replace `self.state.market_output = result.raw or ""` with `self.state.market_output = result.tasks_output[0].pydantic`
- [x] 2.2 In `technical_analysis()`: replace raw string assignment with `result.tasks_output[0].pydantic`
- [x] 2.3 In `fundamental_analysis()`: replace raw string assignment with `result.tasks_output[0].pydantic`
- [x] 2.4 In `draft_strategy()`: replace raw string assignment with `result.tasks_output[0].pydantic`
- [x] 2.5 In `critique_review()`: replace raw string assignment with `result.tasks_output[0].pydantic`

## 3. Rewrite Slim Helpers

- [x] 3.1 Rewrite `_slim_market_for_analysis()` to access `self.state.market_output` as `MarketAnalysisOutput`; add `None` guard returning `""`; remove `json.loads()` and `except` fallback
- [x] 3.2 Rewrite `_slim_market_for_strategy()` with same pattern, including `mention_count` and `rationale` fields
- [x] 3.3 Rewrite `_slim_technical()` to access `self.state.technical_output` as `TechnicalAnalysisOutput`; map `StockTechnicalAnalysis` fields to the slim dict structure downstream tasks expect
- [x] 3.4 Rewrite `_slim_fundamental()` to access `self.state.fundamental_output` as `FundamentalAnalysisOutput`; map `FundamentalRating` enum values to the `assessment` keys downstream tasks expect
- [x] 3.5 Rewrite `_slim_draft()` to access `self.state.draft_output` as `InvestorStrategicOutput`; map `PositionRecommendation` fields; truncate `rationale` and `overall_strategy` as before
- [x] 3.6 Rewrite `_slim_critique()` to access `self.state.critique_output` as `CriticOutput`; map fields; remove `except` fallback

## 4. Extend TechnicalAnalysisOutput Schema

- [x] 4.1 Add `RawIndicators` model to `schemas/agent_outputs.py` with Optional fields: `rsi`, `stochastic_status`, `macd_status`, `ma_status`, `adx`
- [x] 4.2 Add `raw_indicators: Optional[RawIndicators]` to `StockTechnicalAnalysis`
- [x] 4.3 Add `overall_signal`, `entry_zone_status`, `regime` as `Optional[str]` to `MomentumAnalysis`
- [x] 4.4 Update `_slim_technical()` to emit `raw_indicators` dict and full `interpretation` dict from typed model attributes

## 5. Verify and Test

- [x] 5.1 Run `python tests/test_crew.py` and `python tests/test_schemas.py` to confirm no regressions
- [ ] 5.2 Run a dry-run smoke test (`python main.py --sector Technology`) and verify the final result dict shape is unchanged
