## MODIFIED Requirements

### Requirement: Donut chart legends show percentage only
All donut chart legends in `stats.html` (risk profile donut on the Activity tab, and the decisions donut on the Decisions tab) SHALL display each slice's label and its percentage share only. Raw counts SHALL NOT appear in legend items.

#### Scenario: Risk profile legend shows percentage, no count
- **WHEN** the Activity tab renders with `{conservative: 72, aggressive: 226}`
- **THEN** each legend item shows the label (e.g., "Aggressive") and percentage (e.g., "75.9%") but NOT the raw number 226

#### Scenario: Decisions donut legend shows percentage, no count
- **WHEN** the Decisions tab renders the Overall donut with LONG-BUY: 40, MONITOR: 60
- **THEN** each legend item shows "LONG-BUY · 40.0%" and "MONITOR · 60.0%" without displaying the raw numbers 40 or 60

#### Scenario: Sector-filtered donut legend also shows percentage only
- **WHEN** the user selects a specific sector in the Decisions dropdown
- **THEN** the updated legend items show only label and percentage, no raw counts
