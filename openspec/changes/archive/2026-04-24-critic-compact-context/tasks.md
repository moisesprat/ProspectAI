## 1. Add `_critic_reference_table()` helper to ProspectAIFlow

- [x] 1.1 Add `_critic_reference_table()` method to `ProspectAIFlow` in `prospect_ai_flow.py` that builds lookup dicts from `self.state.market_output`, `self.state.technical_output`, and `self.state.fundamental_output` and returns a JSON string with `reference_table` array
- [x] 1.2 Guard against `None` state fields: return `json.dumps({"reference_table": []})` if any required state is missing
- [x] 1.3 Map `FundamentalRating.quality` through the existing `quality_map` so `financial_health` values are "STRONG/ADEQUATE/WEAK", not raw Pydantic Literal values

## 2. Update `critique_review()` context assembly

- [x] 2.1 In `critique_review()`, remove the three slim helper calls (`_slim_market_for_strategy()`, `_slim_technical()`, `_slim_fundamental()`) from the context string
- [x] 2.2 Replace with two-section context: `_fmt_ctx("Draft Strategy Output", _slim_draft())` and `_fmt_ctx("Ticker Reference Table", _critic_reference_table())`

## 3. Update `tasks.yaml` critique_review description

- [x] 3.1 In `config/tasks.yaml`, update the `critique_review` task description STEP 1 to reference `reference_table` instead of `stock_analyses`
- [x] 3.2 Ensure all field names cited in the issue-type checklist (`rsi`, `stochastic_status`, `macd_status`, `entry_zone_status`, `momentum_score`, `average_sentiment`, `valuation_grade`, `financial_health`) match the keys present in the reference table JSON

## 4. Scope Final Strategist context to Tasks 4+5 only

- [x] 4.1 In `finalize_strategy()` in `prospect_ai_flow.py`, remove `_slim_market_for_strategy()`, `_slim_technical()`, and `_slim_fundamental()` from the context string — keep only the Draft Strategy output and the Critic output
- [x] 4.2 Confirm the two retained sections are `_fmt_ctx("Draft Strategy Output", _slim_draft())` and `_fmt_ctx("Critic Review", _slim_critic())`

## 5. Verify and Test

- [x] 5.1 Run `python tests/test_crew.py` and `python tests/test_schemas.py` to confirm no regressions
- [ ] 5.2 Run a dry-run smoke test (`python main.py --sector Technology`) and verify the Critic's output is coherent and issue types reference the compact reference table fields
