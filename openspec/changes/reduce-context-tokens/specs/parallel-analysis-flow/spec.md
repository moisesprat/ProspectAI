## MODIFIED Requirements

### Requirement: Pipeline preserves correct task_index in progress events
Each progress event emitted via `progress_callback` SHALL carry an explicit `task_index` field matching the agent's fixed position in the pipeline (Market=0, Technical=1, Fundamental=2, Draft=3, Critic=4, Final=5).

#### Scenario: Progress events during parallel phase
- **WHEN** Technical Analysis completes (regardless of whether Fundamental has completed)
- **THEN** a progress event with `task_index=1` and `agent="TechnicalAnalyst"` SHALL be emitted
- **WHEN** Fundamental Analysis completes (regardless of whether Technical has completed)
- **THEN** a progress event with `task_index=2` and `agent="FundamentalAnalyst"` SHALL be emitted

### Requirement: Final Strategy receives minimal context sufficient for revision
The `final_strategy()` phase SHALL NOT receive the full Technical Analysis output, full Fundamental Analysis output, or full market narrative. It SHALL receive only what is required to apply the Critic's revision directives: critic findings, slim draft positions, and a minimal market signal.

#### Scenario: Final Strategy context is bounded
- **WHEN** `final_strategy()` assembles its context string
- **THEN** it SHALL call `_slim_for_final()` (or equivalent) rather than concatenating all 5 prior slim outputs
- **AND** the context SHALL contain critic findings (severity + field + directive), slim draft positions (ticker + action + allocation_pct + entry_zone + stop_loss), and market sector signal with top-3 tickers
- **AND** the context SHALL NOT contain Technical Analysis indicator tables, Fundamental Analysis ratio tables, or market narrative prose

#### Scenario: Final Strategy input token count is reduced
- **WHEN** a pipeline run completes
- **THEN** the `final_strategy` phase entry in `execution_metrics.phases` SHALL show input tokens below 50,000

## ADDED Requirements

### Requirement: `_slim_for_final()` helper encapsulates Final Strategy context
`ProspectAIFlow` SHALL expose a private `_slim_for_final()` method that assembles Final Strategy context from: `_slim_critique()` output, slim draft positions (ticker/action/allocation_pct/entry_zone/stop_loss only), and a minimal market signal (sector_signal + top-3 tickers with composite score).

#### Scenario: Helper returns well-formed context string
- **WHEN** `_slim_for_final()` is called after all prior phases have completed
- **THEN** it returns a non-empty string containing critic findings, draft position fields, and market sector signal
- **AND** it does NOT include `overall_strategy`, per-position `rationale`, Technical Analysis indicators, or Fundamental Analysis ratios

### Requirement: `_slim_draft()` drops `overall_strategy` and shortens `rationale`
The `_slim_draft()` helper SHALL omit the `overall_strategy` field from its output and SHALL truncate per-position `rationale` to 100 characters maximum.

#### Scenario: Slim draft output is compact
- **WHEN** `_slim_draft()` is called on a completed draft strategy output
- **THEN** the returned string SHALL NOT contain an `overall_strategy` key
- **AND** each position's `rationale` field SHALL be at most 100 characters

### Requirement: `_slim_critique()` truncates explanation prose
The `_slim_critique()` helper SHALL truncate each finding's `explanation` field to 80 characters maximum, retaining `severity`, `field`, and `directive` in full.

#### Scenario: Slim critique output retains directive fidelity
- **WHEN** `_slim_critique()` is called on a completed critic output
- **THEN** each finding's `directive` field SHALL be preserved in full (no truncation)
- **AND** each finding's `explanation` field SHALL be at most 80 characters
