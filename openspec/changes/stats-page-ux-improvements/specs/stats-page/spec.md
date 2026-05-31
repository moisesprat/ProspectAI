## MODIFIED Requirements

### Requirement: Stats page renders usage summary cards
The Activity tab SHALL display sector coverage as a **horizontal bar chart** (one row per sector, bar width proportional to run count relative to the maximum sector count). The risk profile SHALL be displayed as an **SVG donut chart** using the same `renderDonut()` helper as the Decisions tab, with Conservative mapped to `#4a7c59` and Aggressive to `#e0a040`, plus a mini legend. The plain list rendering for both is REMOVED.

#### Scenario: Sector coverage renders as horizontal bars
- **WHEN** `/api/analytics` returns sector counts `{Technology: 114, Semiconductors: 79, Energy: 70}`
- **THEN** the Activity tab renders three bar rows; the Technology bar is the widest (100% of track width), Semiconductors is `69%`, and Energy is `61%`; each row shows the sector name and count as text

#### Scenario: Risk profile renders as SVG donut
- **WHEN** `/api/analytics` returns `{by_risk_profile: {conservative: 72, aggressive: 226}}`
- **THEN** the Activity tab renders an SVG donut with two slices (olive-green for Conservative, amber for Aggressive) and a legend showing each label, count, and percentage

#### Scenario: Analytics endpoint unreachable
- **WHEN** `GET /api/analytics` fails
- **THEN** summary cards show skeleton/placeholder state and no JS error is thrown

### Requirement: Stats page renders action-type pie charts
The Decisions tab SHALL render a **single donut chart** with a **sector `<select>` dropdown** above it. The dropdown SHALL include "Overall" as the first option followed by every sector key from `action_breakdown` sorted alphabetically. When "Overall" is selected, the donut aggregates all sectors. When a specific sector is selected, the donut shows only that sector's signal distribution. The previous per-sector donut grid is REMOVED.

#### Scenario: Dropdown includes all sectors from action_breakdown
- **WHEN** `action_breakdown` contains keys `Technology`, `Semiconductors`, `Finance`, `Energy`, `Healthcare`
- **THEN** the dropdown has 6 options: "Overall", "Energy", "Finance", "Healthcare", "Semiconductors", "Technology" (alphabetical after Overall)

#### Scenario: Selecting a sector updates the donut
- **WHEN** the user selects "Semiconductors" from the dropdown
- **THEN** the donut re-renders with only Semiconductors signal counts and the legend updates accordingly

#### Scenario: "Overall" aggregates all sectors
- **WHEN** "Overall" is selected (the default)
- **THEN** the donut shows the sum of all action counts across all sectors

#### Scenario: No action data available
- **WHEN** `action_breakdown` is empty
- **THEN** the Decisions tab shows "No signal data yet." and no chart or dropdown is rendered

### Requirement: Stats page renders LONG-BUY track record table
The Performance table SHALL apply the following data rules before rendering:

**Deduplication**: rows with the same `ticker`, same UTC calendar date (derived from `recommended_at`), and same `trigger_price` SHALL be collapsed to one row, keeping the entry with the latest `recommended_at` timestamp.

**5-day exclusion**: entries whose `recommended_at` is within the last 5 calendar days (UTC) SHALL be excluded from both the table and KPI card computations.

**Version column**: the table SHALL include a `Version` column displaying the `prospectai_version` value for each row; null/missing values display as "—".

**Stop-loss disclaimer**: a note SHALL appear above the table: *"ROI figures assume the position was held to the current price. Stop-loss levels were not factored in — if the stop-loss price was hit, the actual outcome would differ."*

**Row count**: the section subtitle SHALL show the count of rows after deduplication and exclusion, e.g. "42 signals · entries within 5 days and duplicates excluded".

#### Scenario: Duplicate rows are collapsed
- **WHEN** the history contains 3 entries with ticker "MU", date "2026-05-18", trigger_price 724.66
- **THEN** the table shows exactly 1 row for that combination (the most recent `recommended_at`)

#### Scenario: Recent entries are excluded
- **WHEN** today is 2026-05-31 and an entry has `recommended_at: "2026-05-28T10:00:00Z"` (3 days ago)
- **THEN** that entry does not appear in the table and is not counted in KPI calculations

#### Scenario: Version column renders
- **WHEN** a row has `prospectai_version: "1.8.0"`
- **THEN** the Version cell displays "1.8.0"

#### Scenario: Version column shows dash for missing version
- **WHEN** a row has `prospectai_version: null`
- **THEN** the Version cell displays "—"

#### Scenario: Stop-loss disclaimer is always visible
- **WHEN** the Performance tab is active and history data has loaded
- **THEN** the disclaimer text is visible above the table regardless of how many rows are shown
