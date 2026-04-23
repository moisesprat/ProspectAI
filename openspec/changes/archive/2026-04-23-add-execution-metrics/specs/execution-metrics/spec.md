## ADDED Requirements

### Requirement: Pipeline emits execution_metrics in result dict
Every successful call to `ProspectAIFlow.run_analysis()` SHALL include an `execution_metrics` key in the returned dict. The value SHALL be a JSON-serializable dict with the following top-level fields: `run_at` (ISO-8601 UTC timestamp), `sector`, `pipeline_elapsed_sec` (float), `phases` (list), `totals` (dict), and `by_model` (dict).

#### Scenario: Successful run populates metrics
- **WHEN** `run_analysis()` completes without error
- **THEN** the returned dict SHALL contain `execution_metrics` with non-null `run_at`, `sector`, and `pipeline_elapsed_sec` fields

#### Scenario: Metrics present even with validation warnings
- **WHEN** `run_analysis()` completes and `validation_warnings` is non-empty
- **THEN** `execution_metrics` SHALL still be present and complete in the result

### Requirement: Phase-level timing is captured for all six pipeline phases
The `phases` list inside `execution_metrics` SHALL contain one entry per pipeline phase, in execution order: `market_analysis`, `technical_analysis`, `fundamental_analysis`, `draft_strategy`, `critique_review`, `final_strategy`. Each entry SHALL include: `name` (string), `elapsed_sec` (float, wall-clock duration of the phase), `input_tokens` (int), `output_tokens` (int), `cached_tokens` (int), `total_tokens` (int). Token values are read from `CrewOutput.token_usage` (`prompt_tokens` → `input_tokens`, `completion_tokens` → `output_tokens`, `cached_prompt_tokens` → `cached_tokens`).

#### Scenario: All phases reported after normal run
- **WHEN** `run_analysis()` completes successfully
- **THEN** `execution_metrics.phases` SHALL contain exactly 6 entries, one per phase name listed above
- **AND** each entry's `elapsed_sec` SHALL be greater than 0.0

#### Scenario: Parallel phases each have independent timing
- **WHEN** `technical_analysis` and `fundamental_analysis` execute concurrently
- **THEN** their respective `elapsed_sec` values SHALL reflect only their own wall-clock duration
- **AND** the sum of `technical_analysis.elapsed_sec` + `fundamental_analysis.elapsed_sec` MAY exceed the total parallel window elapsed time (i.e. they overlap)

### Requirement: Token counts are aggregated in totals and by_model
`execution_metrics.totals` SHALL contain: `input_tokens` (int), `output_tokens` (int), `cached_tokens` (int), `total_tokens` (int) — summed across all phases. `execution_metrics.by_model` SHALL be a dict keyed by the model identifier string read from `task.agent.llm.model`, each value containing `input_tokens`, `output_tokens`, `cached_tokens`, `total_tokens` for that model across all phases.

#### Scenario: Totals match sum of phases
- **WHEN** `run_analysis()` completes
- **THEN** `totals.total_tokens` SHALL equal the sum of `total_tokens` across all phase entries

#### Scenario: by_model keys reflect actual models used
- **WHEN** the pipeline uses model `anthropic/claude-sonnet-4-6`
- **THEN** `by_model` SHALL contain an entry keyed `"anthropic/claude-sonnet-4-6"` with non-zero `total_tokens`

#### Scenario: Token fields are zero when CrewOutput.token_usage is None
- **WHEN** the LLM backend does not populate `CrewOutput.token_usage` (e.g., some Ollama models)
- **THEN** the affected phase's token fields SHALL be 0 rather than raising an error

### Requirement: CLI prints execution_metrics JSON after the analysis summary
When `main.py` runs to completion, it SHALL print the `execution_metrics` dict as formatted JSON to stdout, after the analysis summary output.

#### Scenario: CLI output ends with metrics block
- **WHEN** `python main.py --sector Technology` completes successfully
- **THEN** stdout SHALL contain a line `=== Execution Metrics ===` followed by the JSON-formatted `execution_metrics` dict

### Requirement: Web UI receives execution_metrics via progress_callback
When `run_analysis()` is called with a `progress_callback`, the callback SHALL be invoked once at pipeline completion with an event dict containing `event: "execution_complete"` and `metrics: <execution_metrics dict>`.

#### Scenario: progress_callback receives final metrics event
- **WHEN** `run_analysis(market_criteria, progress_callback=cb)` completes
- **THEN** `cb` SHALL have been called with a dict where `event == "execution_complete"` and `metrics` equals the same `execution_metrics` dict returned in the result
