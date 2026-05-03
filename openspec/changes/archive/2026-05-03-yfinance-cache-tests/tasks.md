## 1. Test file scaffolding

- [x] 1.1 Create `tests/test_yfinance_cache.py` with imports and an autouse `clear()` fixture

## 2. Cache deduplication tests

- [x] 2.1 Add test: `get_history` calls yfinance exactly once on repeated invocations
- [x] 2.2 Add test: `get_info` calls yfinance exactly once on repeated invocations
- [x] 2.3 Add test: `get_financials` calls yfinance exactly once on repeated invocations
- [x] 2.4 Add test: `get_cashflow` calls yfinance exactly once on repeated invocations

## 3. Case-insensitivity test

- [x] 3.1 Add test: lowercase and uppercase ticker share the same cache entry

## 4. clear() test

- [x] 4.1 Add test: after `clear()`, the next call fetches from yfinance again

## 5. Verify

- [x] 5.1 Run `pytest tests/test_yfinance_cache.py -v` and confirm all tests pass
