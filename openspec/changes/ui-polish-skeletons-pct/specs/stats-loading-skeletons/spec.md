## MODIFIED Requirements

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
