## MODIFIED Requirements

### Requirement: Response schema
The endpoint SHALL return JSON with shape `{ "wins": [...] }` where each item contains: `ticker` (string), `sector` (string), `recommended_at` (ISO 8601 string), `entry_zone_low` (float), `entry_zone_high` (float), `current_price` (float), `roi_pct` (float, rounded to 2 decimal places), `recommended_action` (string, always `"LONG-BUY"`), and optionally `trigger_price` (float | null).

#### Scenario: Response structure includes recommended_action
- **WHEN** a valid request is made to `GET /api/long-buy-wins`
- **THEN** the response body matches `{ "wins": [{ "ticker": "...", "sector": "...", "recommended_at": "...", "entry_zone_low": ..., "entry_zone_high": ..., "current_price": ..., "roi_pct": ..., "recommended_action": "LONG-BUY", "trigger_price": ... }] }`

#### Scenario: recommended_action is always LONG-BUY
- **WHEN** the endpoint returns any win item
- **THEN** the `recommended_action` field is always the string `"LONG-BUY"` (the endpoint only stores and returns LONG-BUY records)
