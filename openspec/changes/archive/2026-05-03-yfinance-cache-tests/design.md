## Context

`utils/yfinance_cache.py` uses module-level dicts as singletons. Because they live at
module scope, tests must reset state between cases — `clear()` is the mechanism for
that. The existing test suite mocks yfinance via `unittest.mock.patch` (see
`test_tools_fundamental.py`), so we follow the same pattern.

## Goals / Non-Goals

**Goals:**
- Cover the four `get_*` functions for fetch-once + cache-hit behavior
- Cover case normalization (ticker uppercasing)
- Cover `clear()` resetting all caches

**Non-Goals:**
- Testing yfinance itself or network behavior
- Covering `TechnicalAnalysisTool` / `FundamentalDataTool` integration (those have their own test files)

## Decisions

### Decision: Patch `yf.Ticker` at the `yfinance_cache` module level

Patch `utils.yfinance_cache.yf.Ticker` rather than `yfinance.Ticker` globally.
This keeps each test isolated to the module under test and matches how the rest of
the test suite patches yfinance.

### Decision: Call `clear()` in a `setUp`/autouse fixture

Since the caches are module-level singletons, a test that populates the cache will
leak state into the next test. An autouse `pytest` fixture that calls `clear()` before
each test prevents ordering-dependent failures.

## Risks / Trade-offs

- Module-level state → test isolation depends entirely on `clear()` being called.
  Mitigation: autouse fixture makes this automatic.
