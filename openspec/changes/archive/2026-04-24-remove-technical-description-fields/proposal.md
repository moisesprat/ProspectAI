## Why

`TechnicalAnalysisTool._run()` embeds a verbose `"description"` string in every indicator sub-object (15 descriptions per ticker × 5 tickers = 75 strings per run). These strings repeat human-readable definitions the LLM already knows ("Relative Strength Index - measures speed and magnitude of price changes") and consume 3-5K input tokens per analysis run with zero informational value.

## What Changes

- Remove the `"description"` key from every indicator dict returned by `TechnicalAnalysisTool`: `rsi`, `macd`, `stochastic`, `williams_r`, `cci`, `moving_averages`, `exponential_moving_averages`, `adx`, `parabolic_sar`, `bollinger_bands`, `atr`, `standard_deviation`, `volume_sma`, `obv`, `vwap`
- No other fields change — all numeric values and status strings are preserved

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

_(none — this is a pure token-cost reduction with no spec-level behavior change. The tool's contract is the numeric indicator values; description strings are not part of any downstream requirement.)_

## Impact

- `utils/technical_analysis_tool.py` — remove `"description"` keys from all 15 indicator dicts across four `_calculate_*` methods
- No downstream code reads the `"description"` fields — they are consumed only by the LLM agent as part of its tool result context
- No schema changes, no task description changes, no test fixture changes
