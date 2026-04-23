## ADDED Requirements

### Requirement: Flow creates a fresh ExecutionTracker per run
`ProspectAIFlow.run_analysis()` SHALL instantiate a fresh `ExecutionTracker` at the start of each call and assign it to `self._tracker`. The tracker SHALL be active for the duration of the flow and set to `None` is not required — a new instance per call is sufficient to prevent cross-run accumulation.

#### Scenario: Tracker is fresh for each run
- **WHEN** `run_analysis()` is called
- **THEN** a new `ExecutionTracker` instance SHALL be created and stored on `self._tracker` before `self.kickoff()` is called

#### Scenario: Tracker finish called even on exception
- **WHEN** `self.kickoff()` raises an exception
- **THEN** `tracker.finish()` SHALL still be called (via `finally` block) so `pipeline_elapsed_sec` is recorded

### Requirement: Each phase method brackets its akickoff call with tracker hooks
Every phase method in `ProspectAIFlow` (`market_analysis`, `technical_analysis`, `fundamental_analysis`, `draft_strategy`, `critique_review`, `final_strategy`) SHALL call `tracker.start_phase(phase_name)` immediately before `await crew.akickoff()` and `tracker.finish_phase(phase_name, result.token_usage, model_id)` immediately after, where `model_id` is read from `task.agent.llm.model`.

#### Scenario: Phase timing recorded for market_analysis
- **WHEN** the `market_analysis` phase completes
- **THEN** the corresponding `PhaseMetrics` entry SHALL have `elapsed_sec` set to a positive float

#### Scenario: Parallel phases produce independent token counts
- **WHEN** `technical_analysis` and `fundamental_analysis` run in parallel
- **THEN** each phase's `finish_phase()` call receives only the `CrewOutput.token_usage` from its own mini-Crew
- **AND** tokens from `technical_analysis` SHALL NOT appear in the `fundamental_analysis` phase entry
