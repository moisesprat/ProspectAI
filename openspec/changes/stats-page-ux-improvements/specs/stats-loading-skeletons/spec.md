## ADDED Requirements

### Requirement: Skeleton placeholders shown while API data is in-flight
Before the `/api/analytics` and `/api/long-buy-history` responses arrive, `stats.html` SHALL display animated skeleton placeholders in each data region (summary cards, charts area, KPI cards, and table body). Skeletons SHALL pulse with a CSS opacity animation. When data arrives, skeletons SHALL be replaced by the rendered content.

#### Scenario: Skeletons appear immediately on page load
- **WHEN** `stats.html` loads and API fetches are pending
- **THEN** the summary card values, chart areas, KPI card values, and table body each show a pulsing skeleton element instead of "—" or empty space

#### Scenario: Skeletons replaced when data arrives
- **WHEN** `/api/analytics` resolves successfully
- **THEN** the Activity tab cards and Decisions chart area render real data and no skeleton elements remain in those regions

#### Scenario: Skeletons replaced by error message on fetch failure
- **WHEN** `/api/long-buy-history` fails
- **THEN** the Performance tab shows the error message and no skeleton elements remain

#### Scenario: Skeleton animation is CSS-only
- **WHEN** the page is loading
- **THEN** the skeleton pulse is achieved via a CSS `@keyframes` animation with no JavaScript timers; removing the skeleton elements stops the animation
