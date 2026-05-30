# Capability: Analytics — Action Breakdown by Sector

## Purpose

Track and expose the distribution of recommendation action types (e.g., LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID) per sector across all pipeline runs, surfaced through the analytics API.

## Requirements

### Requirement: Record action type counts per sector on each run
After each successful pipeline run, `_persist_run_results` SHALL increment a counter in `analytics_store` for every position in the result, using the key `action:{sector}:{action_type}` where `action_type` is the uppercase action string (e.g., `LONG-BUY`, `WAIT-FOR-ENTRY`, `MONITOR`, `AVOID`).

#### Scenario: All action types are counted
- **WHEN** a pipeline run for sector "Technology" completes with positions [LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID]
- **THEN** `analytics_store["action:Technology:LONG-BUY"]` is incremented by 1, `analytics_store["action:Technology:WAIT-FOR-ENTRY"]` by 1, `analytics_store["action:Technology:MONITOR"]` by 1, and `analytics_store["action:Technology:AVOID"]` by 1

#### Scenario: Multiple positions of same action type
- **WHEN** a run for sector "Finance" completes with 3 MONITOR positions and 2 WAIT-FOR-ENTRY positions
- **THEN** `analytics_store["action:Finance:MONITOR"]` is incremented by 3 and `analytics_store["action:Finance:WAIT-FOR-ENTRY"]` by 2

#### Scenario: Counter write failure does not crash the run
- **WHEN** `analytics_store` raises an exception during action counter write
- **THEN** the exception is caught and the run result is still returned successfully

### Requirement: Analytics API exposes action breakdown by sector
`GET /api/analytics` SHALL include an `action_breakdown` field in its response. The field SHALL be a dict keyed by sector name, where each value contains:
- `counts`: dict mapping each action type to its total count across all runs for that sector
- `percentages`: dict mapping each action type to its percentage share (0–100, rounded to 1 decimal place) of all recommendations in that sector
- `total`: total number of individual recommendations tracked for that sector

#### Scenario: Breakdown present when action data exists
- **WHEN** the analytics store contains `action:Technology:LONG-BUY=10` and `action:Technology:MONITOR=30`
- **THEN** the response includes `action_breakdown.Technology.counts = {"LONG-BUY": 10, "MONITOR": 30}`, `action_breakdown.Technology.percentages = {"LONG-BUY": 25.0, "MONITOR": 75.0}`, and `action_breakdown.Technology.total = 40`

#### Scenario: Empty breakdown when no action data exists
- **WHEN** no action keys are present in the analytics store
- **THEN** `action_breakdown` is an empty dict `{}`

#### Scenario: Breakdown is additive — does not affect existing fields
- **WHEN** `GET /api/analytics` is called
- **THEN** the existing `total`, `by_sector`, `leading_sector`, and `by_risk_profile` fields are present and unchanged
