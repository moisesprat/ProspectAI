## MODIFIED Requirements

### Requirement: Performance tab displays four KPI cards above the track record table
The Performance tab SHALL render four headline KPI cards before the table: **Win Rate**, **Avg Return**, **Best Pick**, and **Worst Pick**. All values SHALL be computed client-side from the subset of `/api/long-buy-history` entries that match the active sector filter selection (or all entries when "All Sectors" is selected). Data rules (deduplication and 5-day exclusion) are applied before KPI computation.

#### Scenario: KPI cards populate when history data is available and no sector filter is active
- **WHEN** `/api/long-buy-history` returns 20 entries, 14 of which have a valid `roi_pct`, and the sector dropdown is set to "All Sectors"
- **THEN** all four KPI cards are rendered with values computed from all 14 valid entries, before the track record table

#### Scenario: KPI cards reflect active sector filter
- **WHEN** the user selects "Technology" and 6 of the 20 entries are Technology entries with valid `roi_pct`
- **THEN** all four KPI cards recompute using only those 6 entries

#### Scenario: KPI cards show placeholders when history fetch fails
- **WHEN** `/api/long-buy-history` fails
- **THEN** all four KPI cards display "—" and no error is thrown

#### Scenario: KPI cards show placeholders when filtered subset is empty
- **WHEN** the selected sector has no qualifying entries after data rules
- **THEN** all four KPI cards display "—"
