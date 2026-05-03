## Why

`utils/portfolio_allocator_tool.py` is the most critical deterministic component in the pipeline — it computes allocation percentages, stop losses, take-profit targets, and the three-bucket capital breakdown — yet it has only 6% test coverage. Given that this tool's output feeds directly into investment recommendations, its math must be verified against known inputs.

## What Changes

- New test file `tests/test_tools_portfolio_allocator.py` with comprehensive coverage of all action types, allocation caps, trade setup formulas, capital bucket calculation, edge cases, and error handling
- No production code changes

## Capabilities

### New Capabilities
- `portfolio-allocator-allocation`: Tests for proportional allocation logic, per-action caps (LONG-BUY 40%, SCALED-ENTRY 20%, WAIT-FOR-ENTRY 15%), and iterative cap redistribution
- `portfolio-allocator-trade-setups`: Tests for zone-anchored stop/TP formula (LONG-BUY, WAIT-FOR-ENTRY) and current-price-anchored R/R 2:1 formula (SCALED-ENTRY immediate tranche)
- `portfolio-allocator-capital-buckets`: Tests for deployed/reserved/cash_reserve three-bucket breakdown across all action mixes
- `portfolio-allocator-edge-cases`: Tests for MONITOR/AVOID (zero allocation), invalid JSON, empty input, missing fields, and entry zone fallback to current_price

### Modified Capabilities
*(none)*

## Impact

- `tests/test_tools_portfolio_allocator.py`: new file, ~150 lines, no network required (pure math, no mocking needed)
