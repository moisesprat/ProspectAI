## ADDED Requirements

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
`stats.html` SHALL display summary statistics fetched from `GET /api/analytics`: total analyses run, breakdown by sector (count per sector), and breakdown by risk profile (Conservative vs Aggressive counts).

#### Scenario: Summary cards populate from analytics data
- **WHEN** `GET /api/analytics` returns `{ "total": 42, "by_sector": {"Technology": 18, "Finance": 14, "Energy": 10}, "by_risk_profile": {"conservative": 30, "aggressive": 12} }`
- **THEN** the page shows a "42 Analyses" headline card, a sector breakdown listing Technology (18), Finance (14), Energy (10), and a risk profile breakdown showing Conservative (30) and Aggressive (12)

#### Scenario: Risk profile keys are humanised
- **WHEN** `by_risk_profile` contains keys `"conservative"` and `"aggressive"`
- **THEN** these are displayed as "Conservative" and "Aggressive" respectively (sentence-case, not raw key strings)

#### Scenario: Analytics endpoint unreachable
- **WHEN** `GET /api/analytics` fails with a network error or non-200 response
- **THEN** summary cards show "—" placeholders and no error is thrown to the user

### Requirement: Stats page renders action-type pie charts
`stats.html` SHALL render SVG donut charts showing the distribution of recommendation action types (LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID) using the `action_breakdown` field from `GET /api/analytics`. One "Overall" chart SHALL aggregate all sectors; one smaller chart SHALL be rendered per sector that has data.

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
- **WHEN** `action_breakdown` is an empty dict `{}`
- **THEN** the chart section is hidden and no empty chart is rendered

### Requirement: Stats page renders LONG-BUY track record table
`stats.html` SHALL fetch `GET /api/long-buy-history` and display a table with one row per LONG-BUY prediction. Columns SHALL be: `#` (rank), Ticker, Sector, Predicted Date, Entry Price, Current Price, ROI. The table SHALL be sorted by ROI descending on load, with `null`-ROI rows at the bottom. Positive ROI cells SHALL display a green badge and a proportional mini progress bar. Negative ROI cells SHALL display a grey/red badge with no bar.

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
- **THEN** the table section shows a "Could not load track record" message and the rest of the page renders normally

### Requirement: Stats page has navigation back to main page
`stats.html` SHALL include a back-link or button that navigates the user back to `index.html`.

#### Scenario: Back link is present and functional
- **WHEN** the user clicks the back link on `stats.html`
- **THEN** the browser navigates to `index.html` (or the root `/`)
