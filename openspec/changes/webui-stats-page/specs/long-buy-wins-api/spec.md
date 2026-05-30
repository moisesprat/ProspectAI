## ADDED Requirements

### Requirement: Endpoint returns full LONG-BUY history with live ROI
The backend SHALL expose `GET /api/long-buy-history` which reads **all** records from the `long-buy-history` Modal Dict (no date window, no ROI threshold, no deduplication), fetches the current price for each ticker via yfinance, computes `roi_pct` where a `trigger_price` is available, and returns results sorted by `roi_pct` descending with `null`-ROI entries at the bottom.

#### Scenario: All entries returned regardless of ROI
- **WHEN** the dict contains 10 records — 3 with positive ROI, 4 with negative ROI, and 3 with no `trigger_price`
- **THEN** the endpoint returns all 10 rows; positive-ROI rows appear first (sorted descending), negative-ROI rows next, and null-ROI rows last

#### Scenario: Same ticker appearing multiple times is not deduplicated
- **WHEN** the dict contains 3 records for ticker "AMD" with different `recommended_at` dates
- **THEN** all 3 AMD rows appear in the response as separate entries

#### Scenario: No ROI floor — negative ROI entries are included
- **WHEN** a record has `trigger_price: 100` and the current price is `85`
- **THEN** the entry appears in the response with `roi_pct: -15.0`

#### Scenario: Dict is empty or unreachable
- **WHEN** the `long-buy-history` Modal Dict is empty or the read fails
- **THEN** the endpoint returns `{ "history": [] }` with HTTP 200

### Requirement: ROI computation and null handling
`roi_pct` SHALL be computed as `(current_price - trigger_price) / trigger_price * 100`, rounded to 2 decimal places, only when `trigger_price` is a non-null, non-zero value. Records without a valid `trigger_price` SHALL still appear in the response with `roi_pct: null` and `current_price` populated (if yfinance returns a price) or `null` (if not).

#### Scenario: ROI computed correctly
- **WHEN** a record has `trigger_price: 200` and the current price is `250`
- **THEN** `roi_pct` is `25.0`

#### Scenario: Record with null trigger_price returns roi_pct null
- **WHEN** a record has `trigger_price: null`
- **THEN** the response item has `roi_pct: null` and the record still appears in the response

### Requirement: Response schema for long-buy-history
The endpoint SHALL return JSON with shape `{ "history": [...] }` where each item contains: `ticker` (string), `sector` (string), `recommended_at` (ISO 8601 string), `trigger_price` (float | null), `current_price` (float | null), `roi_pct` (float | null), `risk_profile` (string).

#### Scenario: Response structure
- **WHEN** a valid request is made to `GET /api/long-buy-history`
- **THEN** the response body matches `{ "history": [{ "ticker": "...", "sector": "...", "recommended_at": "...", "trigger_price": ..., "current_price": ..., "roi_pct": ..., "risk_profile": "..." }] }`
