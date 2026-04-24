## Why

`TechnicalAnalysisTool` is called once per ticker, resulting in 5 separate tool calls for a standard 5-ticker run. Each call result is fed back to the LLM as an input message, compounding token usage. `FundamentalDataTool` already accepts a ticker array and loops internally — the same pattern applied to the technical tool would cut 10 tool call round-trips (5 raw + 5 interpret) down to 2, matching the fundamental analysis baseline.

## What Changes

- **BREAKING**: Change `TechnicalAnalysisTool._run()` signature from `(ticker: str, period: str)` to `(tickers_json: str, period: str)` — accepts a JSON array of ticker strings, returns all results in one call under a `"technical_analysis"` key
- Update `config/tasks.yaml` `technical_analysis` STEP 2 to call the tool once with the full ticker array, mirroring the fundamental analysis task description pattern
- The per-ticker `interpret_technical_indicators` calls (STEP 3) are not batched in this change — only the raw data fetch is batched

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `parallel-analysis-flow`: The `technical_analysis` phase now invokes `calculate_technical_indicators` once for all tickers instead of once per ticker, reducing tool call round-trips from 5 to 1 for the raw data phase

## Impact

- `utils/technical_analysis_tool.py` — `_run()` signature change; add outer loop over tickers; return `{"technical_analysis": [per-ticker results]}`
- `config/tasks.yaml` `technical_analysis` task description — STEP 2 rewritten to call tool once with array input
- **BREAKING for any caller passing a single ticker string** — the tool description must be updated to reflect the new interface so the LLM agent uses it correctly
- No schema changes to `TechnicalAnalysisOutput`
