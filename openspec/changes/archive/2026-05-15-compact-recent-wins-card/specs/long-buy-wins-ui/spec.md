## MODIFIED Requirements

### Requirement: Each win card displays key data
Each card in the wins section SHALL display, in a compact 4-row layout:
- **Row 1** — the ticker symbol alongside a `LONG-BUY` action tag sourced from the `recommended_action` API field.
- **Row 2** — the sector name and the time since recommendation (e.g., "Technology · 5d ago"), separated by a middle-dot.
- **Row 3** — the ROI percentage (formatted with sign and 1 decimal place, e.g., "+4.2%").
- **Row 4** — the price line. When `trigger_price` is present and non-null, render `$trigger → $current` (e.g., "$415.00 → $432.00"). When `trigger_price` is null or absent, render only `$current` (no arrow, no placeholder).

The action tag text SHALL come from `recommended_action`, not a hard-coded string. No verbose recommendation label, separate trigger price row, or separate current price row SHALL be rendered.

#### Scenario: Card content with trigger price
- **WHEN** a win item has `ticker: "MSFT"`, `sector: "Technology"`, `roi_pct: 4.21`, `recommended_at: "2026-05-10T07:00:00Z"`, `recommended_action: "LONG-BUY"`, `trigger_price: 415.00`, `current_price: 432.00`
- **THEN** the card displays row 1 with "MSFT" and a "LONG-BUY" tag, row 2 with "Technology · 5d ago", row 3 with "+4.2%", and row 4 with "$415.00 → $432.00"

#### Scenario: Card content without trigger price
- **WHEN** a win item has `trigger_price: null` (or trigger_price absent), with all other fields populated
- **THEN** rows 1, 2, and 3 render as above; row 4 displays only the current price (e.g., "$432.00") with no arrow and no placeholder

#### Scenario: Action tag uses API field
- **WHEN** the API returns `recommended_action: "LONG-BUY"`
- **THEN** the row 1 tag text reads "LONG-BUY" from the API value, not a hard-coded string
