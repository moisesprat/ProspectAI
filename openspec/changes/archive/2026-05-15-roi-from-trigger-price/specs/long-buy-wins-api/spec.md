## MODIFIED Requirements

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
