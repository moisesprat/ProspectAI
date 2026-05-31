## MODIFIED Requirements

### Requirement: Stats page renders usage summary cards
`stats.html` SHALL display summary statistics on the **Activity** tab. The tab label SHALL read "Activity". The section title SHALL read "Coverage". The total-runs card label SHALL read "Total Runs" with sub-label "pipeline executions". The sector card label SHALL read "Sector Coverage". The risk-profile card label SHALL read "Risk Profile".

#### Scenario: Activity tab labels use correct vocabulary
- **WHEN** the Activity tab is active and `/api/analytics` returns data
- **THEN** the page shows a card labelled "Total Runs" (not "Total Analyses"), a card labelled "Sector Coverage", and a card labelled "Risk Profile"

#### Scenario: Analytics endpoint unreachable
- **WHEN** `GET /api/analytics` fails
- **THEN** summary cards show "—" placeholders and no error is thrown

### Requirement: Stats page renders action-type pie charts
`stats.html` SHALL display the donut charts on the **Decisions** tab. The tab label SHALL read "Decisions". The section title SHALL read "Signal Distribution". The section subtitle SHALL read "Signal mix across all runs and by sector."

#### Scenario: Decisions tab labels use correct vocabulary
- **WHEN** the Decisions tab is active and action_breakdown data is available
- **THEN** the section heading reads "Signal Distribution" (not "Recommendation Distribution")

#### Scenario: No action data available
- **WHEN** `action_breakdown` is empty
- **THEN** the Decisions tab shows a "No signal data yet" placeholder (not an empty/broken chart section)

### Requirement: Stats page renders LONG-BUY track record table
`stats.html` SHALL display the track record on the **Performance** tab. The tab label SHALL read "Performance". The section title SHALL read "Signal Performance". The section subtitle SHALL read "All LONG-BUY signals with live prices and return, ranked by ROI."

#### Scenario: Performance tab labels use correct vocabulary
- **WHEN** the Performance tab is active
- **THEN** the section heading reads "Signal Performance" (not "LONG-BUY Track Record")

#### Scenario: History endpoint unreachable
- **WHEN** `GET /api/long-buy-history` fails
- **THEN** the Performance tab shows "Could not load signal performance data" and KPI cards show "—"
