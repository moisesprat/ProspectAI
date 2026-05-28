## ADDED Requirements

### Requirement: Pipeline accepts a risk_profile input parameter
The system SHALL accept `risk_profile` as a top-level key in the `run_analysis()` input dict alongside `sector`. Valid values are `"conservative"` and `"aggressive"`. Any other value SHALL raise a `ValueError` before the pipeline starts.

#### Scenario: Conservative profile accepted
- **WHEN** `run_analysis({"sector": "Technology", "risk_profile": "conservative"})` is called
- **THEN** the pipeline runs with conservative bounds and the result's `risk_profile` field equals `"conservative"`

#### Scenario: Aggressive profile accepted
- **WHEN** `run_analysis({"sector": "Technology", "risk_profile": "aggressive"})` is called
- **THEN** the pipeline runs with aggressive bounds and the result's `risk_profile` field equals `"aggressive"`

#### Scenario: Invalid profile is rejected before pipeline starts
- **WHEN** `run_analysis({"sector": "Technology", "risk_profile": "moderate"})` is called
- **THEN** a `ValueError` is raised and no LLM calls are made

### Requirement: risk_profile is stored in flow state and available to all strategic phases
`ProspectAIFlowState` SHALL store `risk_profile` and the task rendering layer SHALL inject it as `$risk_profile` into the Draft Strategist, Critic, and Final Strategist task prompts.

#### Scenario: risk_profile reaches Draft Strategist task prompt
- **WHEN** the pipeline runs with `risk_profile="aggressive"`
- **THEN** the Draft Strategist task prompt contains the string `"aggressive"`

#### Scenario: risk_profile reaches Critic task prompt
- **WHEN** the pipeline runs with `risk_profile="conservative"`
- **THEN** the Critic task prompt contains the string `"conservative"` and the profile-specific bounds table

#### Scenario: risk_profile reaches Final Strategist task prompt
- **WHEN** the pipeline runs with `risk_profile="aggressive"`
- **THEN** the Final Strategist task prompt contains the string `"aggressive"` and the instruction to stay within aggressive bounds

### Requirement: InvestorStrategicOutput carries risk_profile
`InvestorStrategicOutput` SHALL include a `risk_profile: Literal["conservative", "aggressive"]` field. The Final Strategist output SHALL echo back the profile that was active during the run.

#### Scenario: risk_profile is present in the final output
- **WHEN** the pipeline completes with `risk_profile="conservative"`
- **THEN** `result["risk_profile"]` equals `"conservative"` in the `run_analysis()` return value

### Requirement: Backend /api/analyze endpoint accepts risk_profile query parameter
The `/api/analyze` endpoint SHALL accept an optional `risk_profile` query parameter (`"conservative"` | `"aggressive"`). When absent it SHALL default to `"conservative"`. The value SHALL be forwarded to `run_analysis()`.

#### Scenario: risk_profile defaults to conservative when omitted
- **WHEN** `/api/analyze?sector=Technology` is called without `risk_profile`
- **THEN** the pipeline runs with `risk_profile="conservative"`

#### Scenario: risk_profile=aggressive is forwarded
- **WHEN** `/api/analyze?sector=Technology&risk_profile=aggressive` is called
- **THEN** the pipeline runs with `risk_profile="aggressive"`

### Requirement: Analytics tracks risk_profile usage
On each successful pipeline run the backend SHALL increment `analytics_store[f"risk_profile:{risk_profile}"]`. The `/api/analytics` response SHALL include a `by_risk_profile` field with counts per profile.

#### Scenario: Conservative run is counted
- **WHEN** a pipeline run completes with `risk_profile="conservative"`
- **THEN** `analytics_store["risk_profile:conservative"]` is incremented by 1

#### Scenario: Analytics response includes by_risk_profile
- **WHEN** `/api/analytics` is called after runs with both profiles
- **THEN** the response JSON contains `"by_risk_profile": {"conservative": <n>, "aggressive": <m>}`

### Requirement: Web UI exposes a Conservative / Aggressive toggle
The web UI SHALL display a 2-button selector (Conservative / Aggressive) before the pipeline trigger. The selected value SHALL be sent as the `risk_profile` query parameter when the pipeline is triggered. Conservative SHALL be the default selection.

#### Scenario: Conservative is selected by default
- **WHEN** the page loads
- **THEN** the Conservative button is active and Aggressive is inactive

#### Scenario: Selecting Aggressive sends risk_profile=aggressive
- **WHEN** the user clicks Aggressive and triggers the pipeline
- **THEN** the SSE request URL contains `risk_profile=aggressive`
