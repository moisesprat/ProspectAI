## MODIFIED Requirements

### Requirement: Each phase method brackets its akickoff call with tracker hooks
Every phase method in `ProspectAIFlow` (`market_analysis`, `technical_analysis`, `fundamental_analysis`, `draft_strategy`, `critique_review`, `final_strategy`) SHALL call `tracker.start_phase(phase_name)` immediately before `await crew.akickoff()` and `tracker.finish_phase(phase_name, result.token_usage, model_id)` immediately after, where `model_id` is read from `task.agent.llm.model`.

The `critique_review` phase SHALL build its context using `_slim_draft()` and `_critic_reference_table()` only — it SHALL NOT pass `_slim_market_for_strategy()`, `_slim_technical()`, or `_slim_fundamental()` to the Critic's task description.

#### Scenario: Phase timing recorded for market_analysis
- **WHEN** the `market_analysis` phase completes
- **THEN** the corresponding `PhaseMetrics` entry SHALL have `elapsed_sec` set to a positive float

#### Scenario: Parallel phases produce independent token counts
- **WHEN** `technical_analysis` and `fundamental_analysis` run in parallel
- **THEN** each phase's `finish_phase()` call receives only the `CrewOutput.token_usage` from its own mini-Crew
- **AND** tokens from `technical_analysis` SHALL NOT appear in the `fundamental_analysis` phase entry

#### Scenario: critique_review context excludes upstream slim outputs
- **WHEN** `critique_review()` assembles the Critic's task description
- **THEN** the context SHALL include the draft output (from `_slim_draft()`) and the reference table (from `_critic_reference_table()`)
- **AND** the context SHALL NOT include sections built from `_slim_market_for_strategy()`, `_slim_technical()`, or `_slim_fundamental()`
