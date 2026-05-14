## ADDED Requirements

### Requirement: Endpoint returns positive-ROI LONG-BUY recommendations
The backend SHALL expose `GET /api/long-buy-wins` which reads all records from the `long-buy-history` Modal Dict, filters to recommendations made within the last 30 days that have positive ROI, and returns them sorted by ROI descending, capped at 5 results.

#### Scenario: Multiple winning picks exist
- **WHEN** the `long-buy-history` dict contains 4 recommendations from the last 30 days with positive ROI and 2 with negative ROI
- **THEN** the endpoint returns exactly 4 items, each with fields `ticker`, `sector`, `recommended_at`, `entry_zone_low`, `entry_zone_high`, `current_price`, `roi_pct`, sorted by `roi_pct` descending

#### Scenario: More than 5 winning picks
- **WHEN** the dict contains 8 positive-ROI recommendations from the last 30 days
- **THEN** the endpoint returns exactly 5 items (the top 5 by ROI)

#### Scenario: No positive-ROI picks exist
- **WHEN** all recommendations in the dict have negative ROI or are older than 30 days
- **THEN** the endpoint returns an empty array `[]`

#### Scenario: Dict is empty or unreachable
- **WHEN** the `long-buy-history` Modal Dict is empty or the read fails
- **THEN** the endpoint returns an empty array `[]` with HTTP 200 (never errors)

### Requirement: ROI computation uses entry zone midpoint
The endpoint SHALL compute ROI as `(current_price - entry_zone_mid) / entry_zone_mid * 100` where `entry_zone_mid` is `(entry_zone_low + entry_zone_high) / 2`. If a `trigger_price` field exists on the record, it SHALL be included in the response but NOT used for ROI computation (ROI is always relative to entry zone midpoint).

#### Scenario: ROI calculation
- **WHEN** a record has `entry_zone_low=100`, `entry_zone_high=110`, and the current price is `115`
- **THEN** `roi_pct` SHALL be `((115 - 105) / 105) * 100 ≈ 9.52`

### Requirement: Current price fetched via yfinance
The endpoint SHALL fetch the latest available price for each ticker using yfinance. If yfinance fails for a specific ticker, that ticker SHALL be excluded from the response rather than returning stale or zero data.

#### Scenario: yfinance partial failure
- **WHEN** the dict has records for MSFT, META, and JNJ but yfinance fails to return a price for JNJ
- **THEN** the response includes only MSFT and META (JNJ is excluded)

### Requirement: Response schema
The endpoint SHALL return JSON with shape `{ "wins": [...] }` where each item contains: `ticker` (string), `sector` (string), `recommended_at` (ISO 8601 string), `entry_zone_low` (float), `entry_zone_high` (float), `current_price` (float), `roi_pct` (float, rounded to 2 decimal places), and optionally `trigger_price` (float | null).

#### Scenario: Response structure
- **WHEN** a valid request is made to `GET /api/long-buy-wins`
- **THEN** the response body matches `{ "wins": [{ "ticker": "...", "sector": "...", "recommended_at": "...", "entry_zone_low": ..., "entry_zone_high": ..., "current_price": ..., "roi_pct": ..., "trigger_price": ... }] }`
