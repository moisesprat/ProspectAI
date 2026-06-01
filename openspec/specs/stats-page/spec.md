# Spec: Stats Page

## Purpose
`stats.html` is the analytics dashboard for ProspectAI. It presents usage summaries, signal distribution charts, and a LONG-BUY track record, organised across three tabs (Activity, Decisions, Performance).

## Requirements

### Requirement: Stats page is reachable from main page
The frontend SHALL render a clearly visible "ProspectAI Stats" button in `index.html`, positioned in the analytics bar row next to the runs count and leading-sector badge. Clicking it SHALL navigate to `stats.html`.

#### Scenario: Stats button present on load
- **WHEN** `index.html` finishes loading
- **THEN** a button or link with visible text "ProspectAI Stats" is present in the analytics bar area

#### Scenario: Stats button navigates to stats page
- **WHEN** the user clicks the "ProspectAI Stats" button
- **THEN** the browser navigates to `stats.html`

### Requirement: Stats page fires a Simple Analytics event on open
`stats.html` SHALL call `saEvent('stats_page_open')` once on page load, before any data fetch completes.

#### Scenario: Event fires on page load
- **WHEN** `stats.html` loads and `window.sa_event` is available
- **THEN** `sa_event('stats_page_open')` is called exactly once

#### Scenario: Event call does not block data fetch
- **WHEN** `stats.html` loads
- **THEN** the SA event fires and data fetches proceed in parallel; a failure in the SA call does not prevent stats from rendering

### Requirement: Stats page renders usage summary cards
`stats.html` SHALL display summary statistics on the **Activity** tab. The tab label SHALL read "Activity". The section title SHALL read "Coverage". The total-runs card label SHALL read "Total Runs" with sub-label "pipeline executions". The sector card label SHALL read "Sector Coverage". The risk-profile card label SHALL read "Risk Profile". Sector coverage SHALL be displayed as a **horizontal bar chart** (one row per sector, bar width proportional to run count relative to the maximum sector count). The risk profile SHALL be displayed as an **SVG donut chart** using the same `renderDonut()` helper as the Decisions tab, with Conservative mapped to `#4a7c59` and Aggressive to `#e0a040`, plus a mini legend. The plain list rendering for both is REMOVED.

#### Scenario: Activity tab labels use correct vocabulary
- **WHEN** the Activity tab is active and `/api/analytics` returns data
- **THEN** the page shows a card labelled "Total Runs" (not "Total Analyses"), a card labelled "Sector Coverage", and a card labelled "Risk Profile"

#### Scenario: Summary cards populate from analytics data
- **WHEN** `GET /api/analytics` returns `{ "total": 42, "by_sector": {"Technology": 18, "Finance": 14, "Energy": 10}, "by_risk_profile": {"conservative": 30, "aggressive": 12} }`
- **THEN** the page shows a "42" total-runs figure, a sector breakdown listing Technology (18), Finance (14), Energy (10), and a risk profile breakdown showing Conservative (30) and Aggressive (12)

#### Scenario: Risk profile keys are humanised
- **WHEN** `by_risk_profile` contains keys `"conservative"` and `"aggressive"`
- **THEN** these are displayed as "Conservative" and "Aggressive" respectively (sentence-case, not raw key strings)

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
`stats.html` SHALL display the donut charts on the **Decisions** tab. The tab label SHALL read "Decisions". The section title SHALL read "Signal Distribution". The section subtitle SHALL read "Signal mix across all runs and by sector." The Decisions tab SHALL render a **single donut chart** with a **sector `<select>` dropdown** above it. The dropdown SHALL include "Overall" as the first option followed by every sector key from `action_breakdown` sorted alphabetically. When "Overall" is selected, the donut aggregates all sectors. When a specific sector is selected, the donut shows only that sector's signal distribution. The previous per-sector donut grid is REMOVED.

#### Scenario: Decisions tab labels use correct vocabulary
- **WHEN** the Decisions tab is active and action_breakdown data is available
- **THEN** the section heading reads "Signal Distribution" (not "Recommendation Distribution")

#### Scenario: Dropdown includes all sectors from action_breakdown
- **WHEN** `action_breakdown` contains keys `Technology`, `Semiconductors`, `Finance`, `Energy`, `Healthcare`
- **THEN** the dropdown has 6 options: "Overall", "Energy", "Finance", "Healthcare", "Semiconductors", "Technology" (alphabetical after Overall)

#### Scenario: Selecting a sector updates the donut
- **WHEN** the user selects "Semiconductors" from the dropdown
- **THEN** the donut re-renders with only Semiconductors signal counts and the legend updates accordingly

#### Scenario: "Overall" aggregates all sectors
- **WHEN** "Overall" is selected (the default)
- **THEN** the donut shows the sum of all action counts across all sectors

#### Scenario: Action-type colour coding is consistent
- **WHEN** any chart renders
- **THEN** LONG-BUY slices are olive green (`#4a7c59`), WAIT-FOR-ENTRY is amber (`#e0a040`), MONITOR is grey (`#8c8c8c`), and AVOID is red (`#c0392b`); the same colour is used in chart slices and legend dots

#### Scenario: No action data available
- **WHEN** `action_breakdown` is empty
- **THEN** the Decisions tab shows "No signal data yet." and no chart or dropdown is rendered

### Requirement: Stats page renders LONG-BUY track record table
`stats.html` SHALL display the track record on the **Performance** tab. The tab label SHALL read "Performance". The section title SHALL read "Signal Performance". The section subtitle SHALL read "All LONG-BUY signals with live prices and return, ranked by ROI." The Performance table SHALL apply the following data rules before rendering:

**Deduplication**: rows with the same `ticker`, same UTC calendar date (derived from `recommended_at`), and same `trigger_price` SHALL be collapsed to one row, keeping the entry with the latest `recommended_at` timestamp.

**5-day exclusion**: entries whose `recommended_at` is within the last 5 calendar days (UTC) SHALL be excluded from both the table and KPI card computations.

**Version column**: the table SHALL include a `Version` column displaying the `prospectai_version` value for each row; null/missing values display as "—".

**Stop-loss disclaimer**: a note SHALL appear above the table: *"ROI figures assume the position was held to the current price. Stop-loss levels were not factored in — if the stop-loss price was hit, the actual outcome would differ."*

**Row count**: the section subtitle SHALL show the count of rows after deduplication and exclusion, e.g. "42 signals · entries within 5 days and duplicates excluded".

#### Scenario: Performance tab labels use correct vocabulary
- **WHEN** the Performance tab is active
- **THEN** the section heading reads "Signal Performance" (not "LONG-BUY Track Record")

#### Scenario: Table populates with all history entries
- **WHEN** `GET /api/long-buy-history` returns 12 entries with varying ROI values
- **THEN** the table shows 12 rows, sorted by `roi_pct` descending, each displaying ticker, sector, formatted date, entry price, current price, and ROI badge

#### Scenario: Positive ROI renders green with progress bar
- **WHEN** a row has `roi_pct: 22.5`
- **THEN** the ROI cell shows "+22.5%" in a green badge and a filled green bar whose width is proportional to ROI (capped at 50% ROI = full bar width)

#### Scenario: Negative ROI renders without progress bar
- **WHEN** a row has `roi_pct: -4.1`
- **THEN** the ROI cell shows "−4.1%" in a muted/red badge and no progress bar is rendered

#### Scenario: Missing trigger price renders gracefully
- **WHEN** a row has `trigger_price: null`
- **THEN** the Entry Price cell shows "—" and the ROI cell shows "—", with the row sorted below all rows that have a valid ROI

#### Scenario: Predicted date is formatted as dd-MMM-yy
- **WHEN** a row has `recommended_at: "2026-04-10T14:00:00Z"`
- **THEN** the Predicted Date column displays `10-Apr-26`

#### Scenario: History endpoint unreachable
- **WHEN** `GET /api/long-buy-history` fails
- **THEN** the Performance tab shows "Could not load signal performance data" and KPI cards show "—"

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

### Requirement: Stats page has navigation back to main page
`stats.html` SHALL include a back-link or button that navigates the user back to `index.html`.

#### Scenario: Back link is present and functional
- **WHEN** the user clicks the back link on `stats.html`
- **THEN** the browser navigates to `index.html` (or the root `/`)
