## 1. Update TechnicalAnalysisTool to accept a ticker array

- [ ] 1.1 Change `_run()` signature from `(self, ticker: str, period: str = "1y")` to `(self, tickers_json: str, period: str = "1y")`
- [ ] 1.2 Parse `tickers_json` as a JSON array at the start of `_run()`; return an error dict if parsing fails or the array is empty
- [ ] 1.3 Loop over the tickers array, calling `_fetch_stock_data()` and `_calculate_all_indicators()` per ticker inside `_run()`, accumulating results
- [ ] 1.4 Return `{"technical_analysis": [per-ticker result dicts]}` instead of a single ticker dict
- [ ] 1.5 Per-ticker errors (yfinance failure) return `{"ticker": "...", "error": "..."}` in the array without aborting the batch
- [ ] 1.6 Update the `description` class field on `TechnicalAnalysisTool` to document the new array input interface and show an example call

## 2. Update tasks.yaml technical_analysis task description

- [ ] 2.1 Rewrite STEP 2 in the `technical_analysis` task description to instruct the LLM to call `calculate_technical_indicators` once with a JSON array of all tickers (mirror the `fundamental_analysis` STEP 2 pattern)
- [ ] 2.2 Ensure STEP 3 (`interpret_technical_indicators`) still loops per-ticker over the results from STEP 2

## 3. Verify

- [ ] 3.1 Run `python tests/test_schemas.py` and `python tests/test_crew.py` to confirm no regressions
- [ ] 3.2 Run a smoke test (`python main.py --sector Technology`) and verify `technical_analysis` phase token count drops relative to pre-change baseline
