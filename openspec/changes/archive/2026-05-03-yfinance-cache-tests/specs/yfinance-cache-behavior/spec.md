## ADDED Requirements

### Requirement: Cache deduplicates yfinance network calls

The cache module SHALL fetch data from yfinance exactly once per unique key within a
pipeline run. Subsequent calls with the same key SHALL return the cached value without
making additional network requests.

#### Scenario: get_history fetches only once for the same ticker/period/interval

- **WHEN** `get_history("AAPL", "1mo")` is called twice in succession
- **THEN** `yf.Ticker().history()` is called exactly once
- **AND** both calls return the same DataFrame

#### Scenario: get_info fetches only once for the same ticker

- **WHEN** `get_info("AAPL")` is called twice in succession
- **THEN** `yf.Ticker().info` is accessed exactly once
- **AND** both calls return the same dict

#### Scenario: get_financials fetches only once for the same ticker

- **WHEN** `get_financials("AAPL")` is called twice in succession
- **THEN** `yf.Ticker().financials` is accessed exactly once

#### Scenario: get_cashflow fetches only once for the same ticker

- **WHEN** `get_cashflow("AAPL")` is called twice in succession
- **THEN** `yf.Ticker().cashflow` is accessed exactly once

### Requirement: Cache is case-insensitive on ticker symbols

The cache module SHALL normalize ticker symbols to uppercase so that `"aapl"` and
`"AAPL"` resolve to the same cache entry.

#### Scenario: Lowercase and uppercase ticker share one cache entry

- **WHEN** `get_info("aapl")` is called followed by `get_info("AAPL")`
- **THEN** `yf.Ticker().info` is accessed exactly once

### Requirement: clear() resets all caches

`clear()` SHALL discard all cached data so that the next call for any key triggers a
fresh yfinance fetch.

#### Scenario: Fetch after clear hits yfinance again

- **WHEN** `get_info("AAPL")` is called, then `clear()` is called, then `get_info("AAPL")` is called again
- **THEN** `yf.Ticker().info` is accessed exactly twice (once before clear, once after)
