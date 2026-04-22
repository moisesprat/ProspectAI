## Why

Technical Analysis (Task 2) and Fundamental Analysis (Task 3) both depend only on Task 1's output (the 5-ticker list) and are fully independent of each other, yet they run sequentially today — one waits for the other with no reason to. Refactoring the pipeline into a CrewAI Flow lets those two phases run in true parallel, cutting wall-clock time for that portion roughly in half. The Flow architecture also aligns the codebase with the direction CrewAI has been pushing since v1.7 and gives access to checkpoint/state management (v1.14) for free.

## What Changes

- Introduce a `ProspectAIFlow` class (subclass of `crewai.flow.Flow`) that replaces the monolithic single-Crew pipeline.
- Phase 1 (`market_analysis`) runs as a single-task Crew, exactly as today.
- Phase 2 (`technical_analysis` and `fundamental_analysis`) are two separate single-task Crews decorated with `@listen(market_analysis)` — they fire in parallel when Phase 1 completes.
- Phase 3 (`draft_strategy`) is decorated with `@listen(and_(technical_analysis, fundamental_analysis))` — it waits for both Phase 2 crews to finish before running.
- Phase 4 (`critique_review`) and Phase 5 (`final_strategy`) follow sequentially as `@listen` steps.
- `ProspectAICrew` is retained as a thin compatibility shim or removed; `main.py` calls `ProspectAIFlow.kickoff()` instead.
- Task definitions in `config/tasks.yaml`, agent configs in `config/agents.yaml`, and all tool implementations are **unchanged**.
- Output schema and `_parse_result` logic are **unchanged**.

## Capabilities

### New Capabilities

- `parallel-analysis-flow`: A CrewAI Flow orchestrates the six-agent pipeline so Technical and Fundamental analysis execute concurrently, with explicit `and_` synchronisation before the strategy phase.

### Modified Capabilities

<!-- No spec-level requirement changes — agent behaviour, schemas, and tools are untouched. -->

## Impact

- **New file**: `prospect_ai_flow.py` — `ProspectAIFlow` class with the Flow wiring.
- **Modified**: `main.py` — swap `ProspectAICrew` instantiation for `ProspectAIFlow`.
- **Modified**: `prospect_ai_crew.py` — keep or slim down to a helper; no longer the entry point.
- **Dependency**: requires `crewai>=1.7.0` (already satisfied by installed v1.12.2); no new packages needed.
- **Estimated wall-clock saving**: ~20–35% of total run time (the two analysis phases are the heaviest tool-calling steps and currently run back-to-back).
- **No breaking changes** to CLI interface, output schema, or downstream consumers.
