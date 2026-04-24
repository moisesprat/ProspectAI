# Capability Spec: Remove Technical Description Fields

## Overview

This spec defines the requirement that `TechnicalAnalysisTool` does not include verbose English `"description"` strings in its indicator output. These strings add no signal for the LLM agent and waste input tokens.

---

## Requirements

### Requirement: TechnicalAnalysisTool output contains no description strings
`TechnicalAnalysisTool._run()` SHALL NOT include a `"description"` key in any indicator sub-dict. All numeric values, status strings, and nested structure SHALL be preserved.

#### Scenario: RSI output has no description field
- **WHEN** `TechnicalAnalysisTool._run(ticker="AAPL")` is called
- **THEN** the returned dict's `technical_indicators.momentum.rsi` object SHALL contain `current` and `status` keys
- **AND** it SHALL NOT contain a `"description"` key

#### Scenario: All 15 indicator groups have no description field
- **WHEN** `TechnicalAnalysisTool._run()` returns a successful result
- **THEN** none of the following indicator groups SHALL contain a `"description"` key: `rsi`, `macd`, `stochastic`, `williams_r`, `cci`, `moving_averages`, `exponential_moving_averages`, `adx`, `parabolic_sar`, `bollinger_bands`, `atr`, `standard_deviation`, `volume_sma`, `obv`, `vwap`

#### Scenario: Numeric and status values are unchanged
- **WHEN** `TechnicalAnalysisTool._run()` returns a result before and after this change
- **THEN** all numeric fields (`current`, `macd_line`, `signal_line`, `histogram`, `k_percent`, `d_percent`, `upper_band`, etc.) and all `status` fields SHALL have the same values
