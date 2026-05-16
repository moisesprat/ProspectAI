## MODIFIED Requirements

### Requirement: Each win card displays key data
Each card in the wins section SHALL display: the ticker symbol, the sector name, the ROI percentage (formatted with sign and 1 decimal place, e.g., "+9.5%"), the time since recommendation (e.g., "3d ago", "2w ago"), a recommendation label in the format "Recommended as LONG-BUY by ProspectAI · [date]" (using the `recommended_action` field from the API), the current stock price (from `current_price`), and — when `trigger_price` is present and non-null — the suggested entry price. When `trigger_price` is null or absent, the trigger price row SHALL be omitted entirely (no placeholder, no dash, no label).

#### Scenario: Card content with trigger price
- **WHEN** a win item has `ticker: "MSFT"`, `sector: "Technology"`, `roi_pct: 4.21`, `recommended_at: "2026-05-10T07:00:00Z"`, `recommended_action: "LONG-BUY"`, `trigger_price: 415.00`, `current_price: 432.00`
- **THEN** the card displays "MSFT", "Technology", "+4.2%", a relative time like "5d ago", the label "Recommended as LONG-BUY by ProspectAI · May 10", the trigger price row showing "$415.00", and the current price row showing "$432.00"

#### Scenario: Card content without trigger price
- **WHEN** a win item has `trigger_price: null` (or trigger_price absent)
- **THEN** the card displays the ticker, sector, ROI, time ago, recommendation label, and current price — but no trigger price row is rendered

#### Scenario: Recommendation label uses API field
- **WHEN** the API returns `recommended_action: "LONG-BUY"`
- **THEN** the card label reads "Recommended as LONG-BUY by ProspectAI · [formatted date]" using the API value, not a hard-coded string
