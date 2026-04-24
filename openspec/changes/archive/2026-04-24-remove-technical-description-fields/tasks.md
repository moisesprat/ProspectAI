## 1. Remove description fields from TechnicalAnalysisTool

- [x] 1.1 In `_calculate_momentum_indicators()`: remove `"description"` from `rsi`, `macd`, `stochastic`, `williams_r`, and `cci` dicts
- [x] 1.2 In `_calculate_trend_indicators()`: remove `"description"` from `moving_averages`, `exponential_moving_averages`, `adx`, and `parabolic_sar` dicts
- [x] 1.3 In `_calculate_volatility_indicators()`: remove `"description"` from `bollinger_bands`, `atr`, and `standard_deviation` dicts
- [x] 1.4 In `_calculate_volume_indicators()`: remove `"description"` from `volume_sma`, `obv`, and `vwap` dicts

## 2. Verify

- [x] 2.1 Run `python tests/test_schemas.py` and `python tests/test_crew.py` to confirm no regressions
- [x] 2.2 Manually invoke the tool and confirm no `"description"` key appears in the output
