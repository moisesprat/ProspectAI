## 1. ExecutionTracker utility

- [x] 1.1 Create `utils/execution_tracker.py` with `PhaseMetrics` dataclass (name, start_time, end_time, input_tokens, output_tokens, cached_tokens, model_token_map) and `elapsed_sec` / `total_tokens` properties
- [x] 1.2 Implement `ExecutionTracker` class with `start()` / `finish()` for pipeline-level timing, `start_phase(name)` / `finish_phase(name, token_usage, model_id)` for phase-level timing; reads token counts directly from `CrewOutput.token_usage` (`prompt_tokens` → input, `completion_tokens` → output, `cached_prompt_tokens` → cached); treats `None` token_usage as zeros
- [x] 1.3 Implement `to_dict()` on `ExecutionTracker` that produces the `execution_metrics` JSON shape: `run_at` (ISO-8601 UTC), `sector`, `pipeline_elapsed_sec`, `phases` list (all 6 phases always present), `totals` (sum across phases), `by_model` (dict keyed by model identifier string)
- [x] 1.4 Write unit tests in `tests/test_execution_tracker.py` covering: phase timing, token aggregation per phase and by model, totals match sum of phases, zero-token graceful fallback (None token_usage), cached_tokens field, run_at ISO format

## 2. Flow integration

- [x] 2.1 Import `ExecutionTracker` in `prospect_ai_flow.py`; add `self._tracker: Optional[ExecutionTracker] = None` on the class; add `_model_id(task)` static helper that reads `task.agent.llm.model` with try/except fallback to `"unknown"`
- [x] 2.2 In `run_analysis()`, instantiate a fresh `ExecutionTracker`, call `tracker.set_sector(sector)` and `tracker.start()`, store on `self._tracker`, wrap `self.kickoff()` in try/finally so `tracker.finish()` is always called
- [x] 2.3 In each of the 6 phase methods (`market_analysis`, `technical_analysis`, `fundamental_analysis`, `draft_strategy`, `critique_review`, `final_strategy`), bracket `await crew.akickoff()` with `tracker.start_phase(PHASE_NAME)` before and `tracker.finish_phase(PHASE_NAME, result.token_usage, self._model_id(task))` after
- [x] 2.4 Add `execution_metrics: tracker.to_dict()` to the result dict returned by `run_analysis()`
- [x] 2.5 Emit a `progress_callback` event `{"event": "execution_complete", "metrics": tracker.to_dict()}` at the end of `run_analysis()` when a callback is set

## 3. CLI output

- [x] 3.1 In `main.py`, after printing `result["summary"]`, check for `result.get("execution_metrics")` and print `=== Execution Metrics ===` followed by `json.dumps(execution_metrics, indent=2)` to stdout

## 4. Web UI

- [x] 4.1 In `../prospectai-backend/serve.py`, add `"metrics": result.get("execution_metrics")` to the `pipeline_done` queue event so the SSE stream forwards execution metrics to the frontend
- [x] 4.2 In `../prospectai-web/ui/pipeline.js`, update the `pipeline_done` case to pass `event.metrics ?? null` as the 5th argument to `report.show()`
- [x] 4.3 Add `renderMetrics(metrics)` export to `../prospectai-web/ui/reportRenderer.js`: renders a 4-box summary row (pipeline time, total/input/cached tokens) and two tables (per-phase and by-model breakdown) using the existing `.metric-box`, `.subsection-label` and new `.metrics-table` classes
- [x] 4.4 In `../prospectai-web/ui/report.js`, import `renderMetrics`, update `show()` signature to accept `metrics` param, and append `renderMetrics(metrics)` to `reportBodyEl` when metrics is present
- [x] 4.5 Add `.metrics-table-wrap`, `.metrics-table`, `.mt-name`, `.mt-num`, `.mt-total` styles to `../prospectai-web/styles/style.css`

## 5. Verification

- [ ] 5.1 Run `python main.py --sector Technology` end-to-end and confirm `=== Execution Metrics ===` block appears in stdout with correct phase names and non-zero elapsed times
- [ ] 5.2 Confirm `by_model` keys in the output match the model identifier strings used in the run (e.g. `"anthropic/claude-sonnet-4-6"`)
- [ ] 5.3 Confirm `totals.total_tokens` equals the sum of all phase `total_tokens` values
- [x] 5.4 Run existing tests (`python tests/test_skeleton.py`) to confirm no regressions
