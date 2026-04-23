## Context

ProspectAI runs 6 agent phases (market → technical ‖ fundamental → draft → critic → final) via `ProspectAIFlow`. Each phase spins up a single-task `Crew` whose LLM calls go through LiteLLM. Today the pipeline returns a results dict with no record of how long it took or how many tokens it consumed. Operators and developers have no visibility into cost, latency hotspots, or per-agent efficiency.

The parallel phases (technical + fundamental) run as concurrent asyncio tasks on the same event loop, which makes naive thread-local phase attribution wrong — the solution must be async-safe.

## Goals / Non-Goals

**Goals:**
- Capture wall-clock elapsed time for the full pipeline and for each named phase
- Capture LLM input/output token counts per phase and aggregated by model identifier
- Produce a structured `execution_metrics` JSON block appended to `run_analysis()` result
- Print the metrics JSON block to stdout in the CLI after the analysis report
- Deliver metrics to the web UI via `progress_callback` so no new API surface is needed

**Non-Goals:**
- Cost estimation in dollars (no authoritative per-model pricing table in the codebase; can be layered later)
- Persistent storage or aggregation across multiple runs
- Streaming per-step token counts (per-phase aggregate is sufficient)
- Changing any agent prompt, tool, or output schema

## Decisions

### 1. Read `CrewOutput.token_usage` directly for token capture

After each `await crew.akickoff()`, the returned `CrewOutput` already contains a fully populated `UsageMetrics` object at `result.token_usage` (`prompt_tokens`, `completion_tokens`, `cached_prompt_tokens`, `total_tokens`). CrewAI populates this via `calculate_usage_metrics()` which reads from each agent's `_token_process` or `llm.get_token_usage_summary()`. The flow calls `tracker.finish_phase(name, result.token_usage, model_id)` immediately after each `akickoff()` returns.

**Why not LiteLLM `CustomLogger` callbacks:** LiteLLM callbacks do not fire for token tracking in practice — CrewAI uses its own `TokenProcess`/`TokenCalcHandler` path that accumulates tokens internally and surfaces them on `CrewOutput.token_usage`. A LiteLLM callback approach always produces zero token counts.

**Why not CrewAI task/step callbacks:** `task_callback` fires with task text output, not token counts.

### 2. Model identifier read from `task.agent.llm.model`

Since each mini-Crew wraps a single agent, `task.agent.llm.model` gives the exact model string (e.g. `"anthropic/claude-sonnet-4-6"`) used for that phase. This is passed to `finish_phase()` as the `model_id` for `by_model` bucketing.

### 3. Fresh `ExecutionTracker` instance per `run_analysis()` call

`ExecutionTracker` is a plain Python class (no LiteLLM inheritance) instantiated fresh at the start of each `run_analysis()` call. This prevents cross-run accumulation and is safe for concurrent test runs without any global state.

**Why not a global singleton:** Tests run multiple analyses in the same process; a persistent singleton would accumulate tokens across unrelated runs.

### 4. Minimal invasiveness — two hooks per phase method

Each of the 6 phase methods in `prospect_ai_flow.py` calls:
```
tracker.start_phase(PHASE_NAME)
result = await crew.akickoff()
tracker.finish_phase(PHASE_NAME, result.token_usage, model_id)
```

`start_phase` records the wall-clock start. `finish_phase` records the stop and reads token counts directly from the `CrewOutput`. No `ContextVar`, no global callbacks, no async coordination needed.

No changes to agent code, task config, or output schemas are required.

## Risks / Trade-offs

- **Ollama / local models may not populate `token_usage`** → `finish_phase` treats `None` token_usage as zero counts rather than raising; metrics are still emitted with zeros.
- **CrewAI changes `CrewOutput.token_usage` field name** → would surface immediately as a test failure (zero tokens in assertions); easy to detect and fix.
- **Parallel phase token counts** → each asyncio task's `akickoff()` returns its own `CrewOutput` with usage only for that mini-Crew, so parallel phases are inherently isolated with no attribution logic needed.

## Migration Plan

1. Add `utils/execution_tracker.py` (new file, no existing code changes).
2. Modify `prospect_ai_flow.py`: import tracker, add `start_phase`/`end_phase` calls, attach metrics to result dict.
3. Modify `main.py`: print `execution_metrics` JSON after the summary.
4. No changes to agents, tools, schemas, or config.
5. Rollback: revert steps 2–3; `execution_tracker.py` is inert if not imported.

## Open Questions

- Should `execution_metrics` also be emitted as a `progress_callback` event mid-run (e.g., after each phase) so the web UI can show live per-phase timing? Or only at the end? → Initial implementation: end-of-run only; streaming can be added in a follow-up.
- When `serve.py` / web UI is built, how should metrics be surfaced? → `run_analysis()` already returns `execution_metrics` in the result dict; the web layer reads it from there. No additional changes needed in this change.
