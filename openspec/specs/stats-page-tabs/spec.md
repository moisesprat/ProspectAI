# Spec: Stats Page Tabs

## Purpose
`stats.html` is divided into three tabs — Activity, Decisions, and Performance — so users can navigate between usage summary, signal distribution, and track-record views without leaving the page.

## Requirements

### Requirement: Stats page renders a three-tab navigation
`stats.html` SHALL render a horizontal tab bar with exactly three tabs: **Activity**, **Decisions**, and **Performance**. Only one tab panel SHALL be visible at a time.

#### Scenario: Default tab on load with no hash
- **WHEN** the user navigates to `stats.html` with no URL hash
- **THEN** the Activity tab is active and its panel is visible; Decisions and Performance panels are hidden

#### Scenario: Direct link to a specific tab via hash
- **WHEN** the user navigates to `stats.html#decisions`
- **THEN** the Decisions tab is active and its panel is visible on load

#### Scenario: Tab click switches the visible panel
- **WHEN** the user clicks the "Performance" tab
- **THEN** the Performance panel becomes visible, Activity and Decisions panels are hidden, and the URL hash updates to `#performance`

#### Scenario: Browser back/forward navigates between tabs
- **WHEN** the user clicks Activity then Decisions then presses the browser back button
- **THEN** the Activity tab becomes active again

### Requirement: Tab bar uses correct accessibility attributes
Each tab button SHALL have `role="tab"` and `aria-selected="true"` when active, `aria-selected="false"` when inactive. The active tab SHALL have a visible amber bottom border and amber text colour.

#### Scenario: Active tab styling
- **WHEN** the Decisions tab is active
- **THEN** the Decisions button has `aria-selected="true"` and renders with an amber underline; the other two buttons have `aria-selected="false"` and muted text
