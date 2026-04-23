## 1. Tighten existing slim helpers

- [ ] 1.1 In `_slim_draft()`: remove `overall_strategy` from the returned dict/string and truncate per-position `rationale` to 100 characters
- [ ] 1.2 In `_slim_critique()`: truncate each finding's `explanation` field to 80 characters while preserving `severity`, `field`, and `directive` in full

## 2. Add `_slim_for_final()` helper

- [ ] 2.1 Add `_slim_market_for_final()` private method returning `{"sector_signal": ..., "top_tickers": [{"ticker":..., "composite_score":...}]}` for top-3 tickers only
- [ ] 2.2 Add `_slim_for_final()` private method that assembles and returns a formatted context string: critic findings (from `_slim_critique()`), slim draft positions (ticker/action/allocation_pct/entry_zone/stop_loss only), and minimal market signal (from `_slim_market_for_final()`)

## 3. Update `final_strategy()` phase

- [ ] 3.1 Replace the 5-context `"\n\n".join([...])` in `final_strategy()` with a single call to `_slim_for_final()`

## 4. Verification

- [ ] 4.1 Run one full pipeline sector analysis and confirm `execution_metrics.phases` shows Final Strategy input tokens below 50,000
- [ ] 4.2 Review the generated report to confirm output quality is unchanged (sector signal, stock picks, allocation rationale present)
