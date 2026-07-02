## ADDED Requirements

### Requirement: Performance tab has a sector filter dropdown
The Performance tab SHALL render a `<select>` dropdown above the KPI cards. The first option SHALL be "All Sectors" (selected by default). Subsequent options SHALL be unique `sector` values extracted from the raw `/api/long-buy-history` response, sorted alphabetically. If no sector values are present in the data, only "All Sectors" SHALL be shown and the dropdown MAY be hidden or disabled.

#### Scenario: Dropdown renders with sectors from data
- **WHEN** `/api/long-buy-history` returns entries spanning sectors "Technology", "Finance", "Energy"
- **THEN** the dropdown shows four options: "All Sectors", "Energy", "Finance", "Technology" (alphabetical after the default)

#### Scenario: Dropdown defaults to All Sectors
- **WHEN** the Performance tab first renders
- **THEN** "All Sectors" is selected and KPI cards and table show the full dataset (same as before this change)

#### Scenario: No sector data present
- **WHEN** all history entries have `sector: null`
- **THEN** the dropdown shows only "All Sectors" and all KPIs and table rows are still shown

### Requirement: Selecting a sector filters KPI cards and table
When the user selects a specific sector from the dropdown, the Performance tab SHALL recompute all four KPI cards (Win Rate, Avg Return, Best Pick, Worst Pick) and re-render the track record table using only entries that match the selected sector. The existing data rules (deduplication, 5-day exclusion) SHALL be applied to the filtered subset. The row-count subtitle SHALL update to reflect the filtered count.

#### Scenario: Sector filter narrows KPI cards
- **WHEN** the user selects "Technology" and history contains 10 Technology entries and 5 Finance entries
- **THEN** Win Rate, Avg Return, Best Pick, and Worst Pick are recomputed from only the 10 Technology entries (after dedup and 5-day exclusion)

#### Scenario: Sector filter narrows the table
- **WHEN** the user selects "Finance"
- **THEN** only rows with `sector: "Finance"` appear in the track record table; all Finance data rules still apply

#### Scenario: Subtitle updates with filtered row count
- **WHEN** "Technology" is selected and yields 8 qualifying rows
- **THEN** the subtitle reads "8 signals · entries within 5 days and duplicates excluded"

#### Scenario: Switching back to All Sectors restores full view
- **WHEN** the user selects "All Sectors" after having a sector active
- **THEN** KPI cards and table revert to the full dataset (same as initial render)

### Requirement: Empty sector selection shows graceful empty state
When a selected sector has no qualifying entries (after data rules), the Performance tab SHALL display "—" in all KPI cards and show an empty-state message in place of the table, without throwing a JS error.

#### Scenario: Sector with no qualifying entries
- **WHEN** the user selects "Real Estate" and no Real Estate entries survive dedup and 5-day exclusion
- **THEN** all four KPI cards show "—" and the table area shows "No signals yet for this sector."
