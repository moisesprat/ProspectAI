# Spec: long-buy-wins-api

## Purpose

Expose a read endpoint that surfaces recent LONG-BUY recommendations with positive ROI so that the frontend can display a "Recent Wins" section.

## Requirements

### Requirement: Endpoint returns positive-ROI LONG-BUY recommendations
The backend SHALL expose `GET /api/long-buy-wins` which reads all records from the `long-buy-history` Modal Dict, filters to recommendations made within the last 30 days whose `roi_pct` is strictly greater than `2.5`, and returns them sorted by ROI descending, capped at 5 results.

#### Scenario: Multiple winning picks above threshold
- **WHEN** the `long-buy-history` dict contains 4 recommendations from the last 30 days with `roi_pct` values of `7.5`, `4.2`, `3.8`, and `12.0`, plus 2 with negative ROI
- **THEN** the endpoint returns exactly 4 items (the four `> 2.5%` picks), each with fields `ticker`, `sector`, `recommended_at`, `entry_zone_low`, `entry_zone_high`, `current_price`, `roi_pct`, `recommended_action`, and `trigger_price`, sorted by `roi_pct` descending

#### Scenario: Picks at or below the 2.5% threshold are excluded
- **WHEN** the dict contains recommendations with `roi_pct` values of `0.0`, `1.5`, `2.5`, and `2.51`
- **THEN** the endpoint returns exactly 1 item (the `2.51` pick); the `0.0`, `1.5`, and `2.5` picks SHALL NOT appear

#### Scenario: More than 5 winning picks above threshold
- **WHEN** the dict contains 8 recommendations from the last 30 days, all with `roi_pct > 2.5`
- **THEN** the endpoint returns exactly 5 items (the top 5 by ROI)

#### Scenario: No picks above threshold exist
- **WHEN** every recommendation in the dict has `roi_pct <= 2.5` or is older than 30 days
- **THEN** the endpoint returns an empty array `[]`

#### Scenario: Dict is empty or unreachable
- **WHEN** the `long-buy-history` Modal Dict is empty or the read fails
- **THEN** the endpoint returns an empty array `[]` with HTTP 200 (never errors)

### Requirement: ROI computation uses trigger price
The endpoint SHALL compute ROI as `(current_price - trigger_price) / trigger_price * 100`, where `trigger_price` is the suggested entry price stored on the record by `PortfolioAllocatorTool`. Records that have no `trigger_price` (null or missing) SHALL be filtered out before ROI computation and SHALL NOT appear in the response, regardless of where their `current_price` sits relative to the entry zone. The `entry_zone_low` and `entry_zone_high` fields remain in the response payload for context but do not participate in ROI computation.

#### Scenario: ROI calculation against trigger
- **WHEN** a record has `trigger_price=100` and the current price is `115`
- **THEN** `roi_pct` SHALL be `((115 - 100) / 100) * 100 = 15.0`

#### Scenario: Record without trigger_price is excluded
- **WHEN** a record has `trigger_price: null` (or the field is absent) and its `current_price` is above the entry zone midpoint
- **THEN** the record SHALL NOT appear in the response, even though it would have shown positive ROI under the prior midpoint formula

#### Scenario: Mixed records — some with trigger, some without
- **WHEN** the dict contains 6 records from the last 30 days, of which 4 have a `trigger_price` (3 with positive trigger-based ROI, 1 negative) and 2 have `trigger_price: null` (both with positive midpoint-based ROI)
- **THEN** the endpoint returns exactly 3 items — the 3 positive-trigger-ROI records — sorted by `roi_pct` descending

### Requirement: Current price fetched via yfinance
The endpoint SHALL fetch the latest available price for each ticker using yfinance. If yfinance fails for a specific ticker, that ticker SHALL be excluded from the response rather than returning stale or zero data.

#### Scenario: yfinance partial failure
- **WHEN** the dict has records for MSFT, META, and JNJ but yfinance fails to return a price for JNJ
- **THEN** the response includes only MSFT and META (JNJ is excluded)

### Requirement: Response schema
The endpoint SHALL return JSON with shape `{ "wins": [...] }` where each item contains: `ticker` (string), `sector` (string), `recommended_at` (ISO 8601 string), `entry_zone_low` (float), `entry_zone_high` (float), `current_price` (float), `roi_pct` (float, rounded to 2 decimal places), `recommended_action` (string, always `"LONG-BUY"`), and optionally `trigger_price` (float | null).

#### Scenario: Response structure includes recommended_action
- **WHEN** a valid request is made to `GET /api/long-buy-wins`
- **THEN** the response body matches `{ "wins": [{ "ticker": "...", "sector": "...", "recommended_at": "...", "entry_zone_low": ..., "entry_zone_high": ..., "current_price": ..., "roi_pct": ..., "recommended_action": "LONG-BUY", "trigger_price": ... }] }`

#### Scenario: recommended_action is always LONG-BUY
- **WHEN** the endpoint returns any win item
- **THEN** the `recommended_action` field is always the string `"LONG-BUY"` (the endpoint only stores and returns LONG-BUY records)
