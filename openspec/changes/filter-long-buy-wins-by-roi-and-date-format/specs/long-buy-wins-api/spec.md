## MODIFIED Requirements

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
