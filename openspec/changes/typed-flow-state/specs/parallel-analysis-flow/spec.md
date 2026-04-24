## MODIFIED Requirements

### Requirement: Pipeline output schema and agent behaviour are unchanged
The structured output returned by `run_analysis()` SHALL be identical in shape to the existing `InvestorStrategicOutput` schema. No agent prompt, tool, or scoring formula SHALL change. The internal flow state representation (typed models vs strings) is an implementation detail and SHALL NOT affect the public return value.

#### Scenario: Output schema compatibility
- **WHEN** `ProspectAIFlow.run_analysis()` completes successfully
- **THEN** the returned dict SHALL contain `status`, `result`, `summary`, `execution_metrics`, and `validation_warnings` keys with the same structure as before this change
