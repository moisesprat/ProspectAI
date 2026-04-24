## MODIFIED Requirements

### Requirement: Technical and Fundamental analysis phases execute concurrently
After Market Analysis completes, the Technical Analysis and Fundamental Analysis phases SHALL start simultaneously and run in parallel. Neither phase SHALL wait for the other to begin.

Within the `technical_analysis` phase, the `calculate_technical_indicators` tool SHALL be called once with a JSON array of all tickers. The LLM SHALL NOT call this tool once per ticker.

#### Scenario: Parallel start after Market Analysis
- **WHEN** the Market Analysis phase emits its output
- **THEN** Technical Analysis and Fundamental Analysis both start within the same scheduling tick, without one waiting for the other

#### Scenario: Draft Strategy waits for both parallel phases
- **WHEN** either Technical or Fundamental Analysis completes alone
- **THEN** the Draft Strategy phase SHALL NOT start
- **WHEN** both Technical and Fundamental Analysis have completed
- **THEN** the Draft Strategy phase SHALL start immediately

#### Scenario: Technical raw data fetched in one tool call
- **WHEN** the `technical_analysis` phase agentic loop runs
- **THEN** `calculate_technical_indicators` SHALL be called exactly once with a `tickers_json` argument containing all sector tickers as a JSON array
- **AND** the tool SHALL return `{"technical_analysis": [one entry per ticker]}`
- **AND** the LLM SHALL NOT call `calculate_technical_indicators` multiple times for the same tickers

#### Scenario: Per-ticker error does not abort batch
- **WHEN** `calculate_technical_indicators` is called with a ticker array and one ticker fails (e.g., yfinance returns no data)
- **THEN** the failed ticker's entry in `technical_analysis` SHALL contain `{"ticker": "...", "error": "..."}` 
- **AND** all other tickers' entries SHALL contain full indicator data
- **AND** the tool SHALL return without raising an exception
