# Capability Spec: Parallel Analysis Flow

## Overview

This spec defines the requirements for the `ProspectAIFlow` orchestration class, which parallelizes the Technical Analysis and Fundamental Analysis pipeline phases to reduce total analysis time. It replaces `ProspectAICrew` as the primary entry point while keeping `ProspectAICrew` importable for backward compatibility.

---

## Requirements

### Requirement: Technical and Fundamental analysis phases execute concurrently
After Market Analysis completes, the Technical Analysis and Fundamental Analysis phases SHALL start simultaneously and run in parallel. Neither phase SHALL wait for the other to begin.

#### Scenario: Parallel start after Market Analysis
- **WHEN** the Market Analysis phase emits its output
- **THEN** Technical Analysis and Fundamental Analysis both start within the same scheduling tick, without one waiting for the other

#### Scenario: Draft Strategy waits for both parallel phases
- **WHEN** either Technical or Fundamental Analysis completes alone
- **THEN** the Draft Strategy phase SHALL NOT start
- **WHEN** both Technical and Fundamental Analysis have completed
- **THEN** the Draft Strategy phase SHALL start immediately

### Requirement: Pipeline preserves correct task_index in progress events
Each progress event emitted via `progress_callback` SHALL carry an explicit `task_index` field matching the agent's fixed position in the pipeline (Market=0, Technical=1, Fundamental=2, Draft=3, Critic=4, Final=5).

#### Scenario: Progress events during parallel phase
- **WHEN** Technical Analysis completes (regardless of whether Fundamental has completed)
- **THEN** a progress event with `task_index=1` and `agent="TechnicalAnalyst"` SHALL be emitted
- **WHEN** Fundamental Analysis completes (regardless of whether Technical has completed)
- **THEN** a progress event with `task_index=2` and `agent="FundamentalAnalyst"` SHALL be emitted

### Requirement: ProspectAIFlow is the pipeline entry point
A `ProspectAIFlow` class SHALL be the primary orchestration entry point, replacing `ProspectAICrew` as the object instantiated by `main.py` and `serve.py`.

#### Scenario: CLI invocation
- **WHEN** `main.py` runs with `--sector Technology`
- **THEN** `ProspectAIFlow().run_analysis({"sector": "Technology"})` is called and returns the same result dict shape as the previous `ProspectAICrew.run_analysis()`

#### Scenario: Backend SSE invocation
- **WHEN** `serve.py`'s `run()` thread calls `ProspectAIFlow(task_callback=..., step_callback=...).run_analysis({"sector": sector})`
- **THEN** `task_callback` and `step_callback` fire for each agent phase, and `progress_callback` events include `task_index`

### Requirement: ProspectAICrew is deprecated but not removed
`ProspectAICrew` SHALL remain importable and functional but SHALL emit a `DeprecationWarning` on instantiation and carry a `# DEPRECATED` docstring noting its planned removal.

#### Scenario: Importing the deprecated class
- **WHEN** code instantiates `ProspectAICrew()`
- **THEN** a `DeprecationWarning` is raised with the message "ProspectAICrew is deprecated; use ProspectAIFlow instead."
- **AND** the instance is still usable (no functionality removed)

### Requirement: Pipeline output schema and agent behaviour are unchanged
The structured output returned by `run_analysis()` SHALL be identical in shape to the existing `InvestorStrategicOutput` schema. No agent prompt, tool, or scoring formula SHALL change.

#### Scenario: Output schema compatibility
- **WHEN** `ProspectAIFlow.run_analysis()` completes successfully
- **THEN** the returned dict SHALL contain `pipeline_version`, `stock_recommendations`, and `portfolio_summary` keys, identical to the previous implementation
