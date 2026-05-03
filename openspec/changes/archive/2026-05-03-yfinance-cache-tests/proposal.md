## Why

`utils/yfinance_cache.py` is a module-level singleton cache shared by `TechnicalAnalysisTool` and `FundamentalDataTool` to prevent duplicate yfinance network calls within a pipeline run — but it has zero test coverage. Adding tests ensures the deduplication contract and `clear()` behavior hold as the module evolves.

## What Changes

- New test file `tests/test_yfinance_cache.py` covering all four cache functions and `clear()`
- No production code changes

## Capabilities

### New Capabilities
- `yfinance-cache-behavior`: Tests verifying the fetch-once/cache-hit/case-insensitive/clear contract of `yfinance_cache.py`

### Modified Capabilities
*(none)*

## Impact

- `tests/test_yfinance_cache.py`: new file, ~30 lines, no network required (yfinance mocked)
