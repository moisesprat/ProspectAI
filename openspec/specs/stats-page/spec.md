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
`stats.html` SHALL display summary statistics on the **Activity** tab. The tab label SHALL read "Activity". The section title SHALL read "Coverage". The total-runs card label SHALL read "Total Runs" with sub-label "pipeline executions". The sector card label SHALL read "Sector Coverage". The risk-profile card label SHALL read "Risk Profile".

#### Scenario: Activity tab labels use correct vocabulary
- **WHEN** the Activity tab is active and `/api/analytics` returns data
- **THEN** the page shows a card labelled "Total Runs" (not "Total Analyses"), a card labelled "Sector Coverage", and a card labelled "Risk Profile"

#### Scenario: Summary cards populate from analytics data
- **WHEN** `GET /api/analytics` returns `{ "total": 42, "by_sector": {"Technology": 18, "Finance": 14, "Energy": 10}, "by_risk_profile": {"conservative": 30, "aggressive": 12} }`
- **THEN** the page shows a "42" total-runs figure, a sector breakdown listing Technology (18), Finance (14), Energy (10), and a risk profile breakdown showing Conservative (30) and Aggressive (12)

#### Scenario: Risk profile keys are humanised
- **WHEN** `by_risk_profile` contains keys `"conservative"` and `"aggressive"`
- **THEN** these are displayed as "Conservative" and "Aggressive" respectively (sentence-case, not raw key strings)

#### Scenario: Analytics endpoint unreachable
- **WHEN** `GET /api/analytics` fails
- **THEN** summary cards show "—" placeholders and no error is thrown

### Requirement: Stats page renders action-type pie charts
`stats.html` SHALL display the donut charts on the **Decisions** tab. The tab label SHALL read "Decisions". The section title SHALL read "Signal Distribution". The section subtitle SHALL read "Signal mix across all runs and by sector."

#### Scenario: Decisions tab labels use correct vocabulary
- **WHEN** the Decisions tab is active and action_breakdown data is available
- **THEN** the section heading reads "Signal Distribution" (not "Recommendation Distribution")

#### Scenario: Overall donut chart shows aggregated counts
- **WHEN** `action_breakdown` contains data for Technology and Finance sectors
- **THEN** an "Overall" donut chart appears whose slices sum all action counts across both sectors, with a legend showing each action type, its total count, and its percentage

#### Scenario: Per-sector donuts appear for each sector with data
- **WHEN** `action_breakdown` has entries for three sectors
- **THEN** three per-sector donut charts appear below the overall chart, each labelled with its sector name

#### Scenario: Action-type colour coding is consistent
- **WHEN** any chart renders
- **THEN** LONG-BUY slices are olive green (`#4a7c59`), WAIT-FOR-ENTRY is amber (`#e0a040`), MONITOR is grey (`#8c8c8c`), and AVOID is red (`#c0392b`); the same colour is used in chart slices and legend dots

#### Scenario: No action data available
- **WHEN** `action_breakdown` is empty
- **THEN** the Decisions tab shows a "No signal data yet" placeholder (not an empty/broken chart section)

### Requirement: Stats page renders LONG-BUY track record table
`stats.html` SHALL display the track record on the **Performance** tab. The tab label SHALL read "Performance". The section title SHALL read "Signal Performance". The section subtitle SHALL read "All LONG-BUY signals with live prices and return, ranked by ROI."

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

### Requirement: Stats page has navigation back to main page
`stats.html` SHALL include a back-link or button that navigates the user back to `index.html`.

#### Scenario: Back link is present and functional
- **WHEN** the user clicks the back link on `stats.html`
- **THEN** the browser navigates to `index.html` (or the root `/`)
