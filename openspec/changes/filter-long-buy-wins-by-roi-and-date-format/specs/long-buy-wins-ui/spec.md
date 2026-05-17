## MODIFIED Requirements

### Requirement: Each win card displays key data
Each card in the wins section SHALL display, in a compact 4-row layout:
- **Row 1** — the ticker symbol, followed by an action tag sourced from the `recommended_action` API field, followed by the recommendation date formatted as `dd-MMM-yy` (two-digit day, hyphen, three-letter English month abbreviation, hyphen, two-digit year, e.g., `15-May-26`). The date SHALL be visually adjacent to the action tag (e.g., separated by a middle-dot or comparable separator) and SHALL be derived from the API `recommended_at` ISO timestamp using UTC date components so every viewer sees the same calendar day as the stored timestamp.
- **Row 2** — the sector name alone. No relative-time string (e.g., `today`, `2d ago`, `1w ago`) SHALL appear anywhere on the card.
- **Row 3** — the ROI percentage (formatted with sign and 1 decimal place, e.g., `+4.2%`).
- **Row 4** — the price line. When `trigger_price` is present and non-null, render `$trigger → $current` (e.g., `$415.00 → $432.00`). When `trigger_price` is null or absent, render only `$current` (no arrow, no placeholder).

The action tag text SHALL come from `recommended_action`, not a hard-coded string. No verbose recommendation label, separate trigger price row, or separate current price row SHALL be rendered.

#### Scenario: Card content with trigger price
- **WHEN** a win item has `ticker: "MSFT"`, `sector: "Technology"`, `roi_pct: 4.21`, `recommended_at: "2026-05-10T07:00:00Z"`, `recommended_action: "LONG-BUY"`, `trigger_price: 415.00`, `current_price: 432.00`
- **THEN** the card displays row 1 with `MSFT`, a `LONG-BUY` tag, and the date `10-May-26` adjacent to that tag; row 2 with `Technology` (no relative time); row 3 with `+4.2%`; and row 4 with `$415.00 → $432.00`

#### Scenario: Card content without trigger price
- **WHEN** a win item has `trigger_price: null` (or trigger_price absent), with all other fields populated
- **THEN** rows 1, 2, and 3 render per the format above; row 4 displays only the current price (e.g., `$432.00`) with no arrow and no placeholder

#### Scenario: Action tag uses API field
- **WHEN** the API returns `recommended_action: "LONG-BUY"`
- **THEN** the row 1 tag text reads `LONG-BUY` from the API value, not a hard-coded string

#### Scenario: Date uses UTC components
- **WHEN** a win item has `recommended_at: "2026-05-15T23:30:00Z"` and the viewer is in timezone `UTC+2`
- **THEN** the rendered date is `15-May-26` (matching the UTC date of the stored timestamp), not `16-May-26`

#### Scenario: No relative-time string is shown
- **WHEN** a win item has `recommended_at` set to the current day
- **THEN** the card does NOT display the strings `today`, `1d ago`, `2d ago`, or any `Nd ago` / `Nw ago` variant; only the `dd-MMM-yy` date is shown
