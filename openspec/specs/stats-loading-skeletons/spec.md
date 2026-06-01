# Spec: Stats Loading Skeletons

## Purpose
`stats.html` SHALL display animated skeleton placeholders while API data is in-flight, giving users immediate visual feedback that content is loading rather than showing empty or dash-filled regions.

## Requirements

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

### Requirement: Skeleton placeholders shown on the main page while data is in-flight
The main `index.html` page SHALL display animated skeleton placeholders for the version tag and the runs count while the backend API calls are pending. The recent wins section SHALL show a ghost placeholder strip while `/api/long-buy-wins` is fetching.

#### Scenario: Version tag shows skeleton on load
- **WHEN** `index.html` loads and the `/api/version` call is in-flight
- **THEN** the version tag area shows a pulsing skeleton element instead of the static `v—` text

#### Scenario: Version tag skeleton replaced when version resolves
- **WHEN** `/api/version` responds successfully
- **THEN** the skeleton is removed and the version tag displays the version string (e.g., `v1.9.0`)

#### Scenario: Runs count shows skeleton on load
- **WHEN** `index.html` loads and the `/api/analytics` call is in-flight
- **THEN** the runs count area in the analytics bar shows a pulsing skeleton element instead of `—`

#### Scenario: Runs count skeleton replaced when analytics resolves
- **WHEN** `/api/analytics` responds successfully
- **THEN** the skeleton is removed and the count displays the actual number of runs

#### Scenario: Recent wins shows ghost placeholder while fetching
- **WHEN** `index.html` loads and `/api/long-buy-wins` is in-flight
- **THEN** a placeholder strip with ghost card shapes appears in the wins banner area

#### Scenario: Recent wins placeholder removed after fetch completes
- **WHEN** `/api/long-buy-wins` responds (successfully or not)
- **THEN** the ghost placeholder is removed and either the real marquee renders (if wins exist) or the area is empty
