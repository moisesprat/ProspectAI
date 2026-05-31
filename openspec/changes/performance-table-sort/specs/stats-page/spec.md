## MODIFIED Requirements

### Requirement: Performance table supports sorting by Return and Signal Date
The Return and Signal Date column headers SHALL be interactive sort controls. The table SHALL default to Return descending on load. Clicking a sortable header SHALL re-sort the table client-side. The active sort column SHALL display a directional arrow (↓ for descending, ↑ for ascending). Inactive sortable headers SHALL show a dim ↕ indicator to communicate they are clickable.

#### Scenario: Default sort is Return descending
- **WHEN** the Performance tab loads with data
- **THEN** the table rows are ordered by `roi_pct` descending (highest ROI first, null ROI last) and the Return header shows a ↓ indicator in amber

#### Scenario: Clicking Return header toggles direction
- **WHEN** the Return header is clicked while Return descending is active
- **THEN** the table re-renders with rows ordered by `roi_pct` ascending (lowest first, null last) and the header shows ↑

#### Scenario: Clicking Signal Date sorts by date descending
- **WHEN** the Signal Date header is clicked while Return sort is active
- **THEN** the table re-renders ordered by `recommended_at` descending (newest signal first) and the Signal Date header shows ↓; the Return header shows a dim ↕

#### Scenario: Clicking Signal Date again toggles to ascending
- **WHEN** the Signal Date header is clicked while Signal Date descending is active
- **THEN** the table re-renders ordered by `recommended_at` ascending (oldest first) and the Signal Date header shows ↑

#### Scenario: Null ROI rows always appear last when sorting by Return
- **WHEN** the table is sorted by Return in either direction
- **THEN** rows with `roi_pct: null` appear after all rows with a valid ROI value regardless of sort direction
