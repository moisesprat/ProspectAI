## Context

ProspectAI currently uses a single `CrewAI Crew` with `Process.sequential` (default) that runs six tasks one after another: Market → Technical → Fundamental → Draft → Critic → Final. Task 3 (Fundamental) lists Task 2 (Technical) in its `context=` even though it does not consume Technical output — it independently fetches financials via `FundamentalDataTool`. As a result, Fundamental always waits for Technical to finish before starting, adding the full wall-clock cost of Technical Analysis to every run with no benefit.

CrewAI v1.7+ ships a `Flow` abstraction with `@start`, `@listen`, and `and_` that enables event-driven parallel execution with an explicit synchronisation barrier. The installed version (1.12.2) fully supports this; the latest stable (1.14.x) adds checkpointing on top but is not required.

## Goals / Non-Goals

**Goals:**
- Technical Analysis and Fundamental Analysis execute concurrently, each starting as soon as Market Analysis finishes.
- Draft Strategy starts only after **both** parallel phases are complete (`and_` gate).
- CLI interface (`main.py`), output schema, agent configs, task prompts, and tools are unchanged.
- `progress_callback` and `task_callback` / `step_callback` hooks continue to work.
- Existing `ProspectAICrew` tests remain valid (or are migrated with minimal changes).

**Non-Goals:**
- Upgrading CrewAI beyond the currently installed version.
- Parallelising any other phase of the pipeline (Market, Draft, Critic, Final each have true sequential dependencies).
- Changing agent prompts, schemas, or scoring formulas.
- Adding checkpointing or Flow state persistence (can be layered on later).

## Decisions

### D1 — Use CrewAI Flow over `async_execution=True`

`async_execution=True` on individual tasks within a single Crew is simpler but has a documented constraint: async tasks may not appear in the `context` of other async tasks, and the last task in the crew must be synchronous. This creates subtle ordering rules that are easy to break later. Flow with `@listen` + `and_` expresses the dependency graph explicitly and is the officially recommended pattern for parallel phases.

**Alternative rejected**: Python `asyncio.gather()` over separate `Crew.kickoff_async()` calls. This works but requires manual state threading and bypasses CrewAI's built-in event system, making future observability (telemetry, HITL) harder to add.

### D2 — One mini-Crew per pipeline phase

Each `@listen`-decorated Flow method wraps a single-task `Crew`. This keeps the existing `Task` + `Agent` + `Tool` wiring completely intact — the only new code is the Flow class that composes them.

**Alternative rejected**: One multi-task Crew with `async_execution`. See D1.

### D3 — `ProspectAICrew` becomes a factory, not the orchestrator

`ProspectAICrew` is retained and refactored into a factory that creates and returns individual tasks and agents. `ProspectAIFlow` owns the orchestration. `main.py` swaps `ProspectAICrew().run_analysis()` for `ProspectAIFlow().run_analysis()`. This keeps the diff minimal and preserves the existing test surface.

**Alternative rejected**: Delete `ProspectAICrew` entirely. Too disruptive; tests and any external callers would break.

### D4 — Flow state holds Pydantic outputs

`ProspectAIFlow` subclasses `Flow[ProspectAIFlowState]` where `ProspectAIFlowState` is a Pydantic `BaseModel` holding the typed outputs of each phase (MarketAnalysisOutput, TechnicalAnalysisOutput, etc.). This replaces CrewAI's implicit `context=` passing with explicit state fields — clearer and easier to test.

### D5 — `progress_callback` fires from Flow methods, not task callbacks

The current `_on_task_done` callback fires inside the Crew. In the Flow design, each `@listen` method knows which phase just completed and calls `progress_callback` directly with the correct `task_index`. The `task_callback` / `step_callback` hooks on individual Crews still fire for finer-grained events.

## Risks / Trade-offs

- **CrewAI Flow API surface** → The Flow `@listen` / `and_` API is stable since v1.7 but is less documented than the Crew API. Mitigation: pin `crewai>=1.7.0,<2.0` in requirements.txt and write a smoke test that imports `Flow`, `listen`, `and_`.
- **Parallel tool calls to yfinance** → Technical and Fundamental both call `yfinance` concurrently. The existing `yfinance_cache` module uses an in-process dict; concurrent reads are safe but concurrent writes could race. Mitigation: the cache is cleared once before the Flow starts (as today) and each phase writes different ticker keys, so there is no write conflict in practice.
- **Error propagation** → If one parallel phase fails, `and_` will never fire, leaving the Flow hanging. Mitigation: wrap each mini-Crew kickoff in a try/except inside the `@listen` method and set an `error` field on the Flow state; the `and_` listener checks for errors before proceeding.
- **Test surface**: existing tests call `ProspectAICrew.run_analysis()` directly. After the refactor, tests should call `ProspectAIFlow.run_analysis()` or use the factory methods on `ProspectAICrew` to construct individual tasks for unit testing.

## Migration Plan

1. Add `prospect_ai_flow.py` with `ProspectAIFlowState` and `ProspectAIFlow`.
2. Refactor `ProspectAICrew.create_tasks()` to also expose per-phase task builders (`build_market_task()`, `build_technical_task()`, `build_fundamental_task()`, etc.) for use by the Flow.
3. Update `main.py` to import and instantiate `ProspectAIFlow` instead of `ProspectAICrew`.
4. Update tests to use `ProspectAIFlow` or the per-phase task builders.
5. Run the full pipeline end-to-end once to confirm parallel execution and correct output.
6. Rollback: revert `main.py` import to `ProspectAICrew` — the old class is unchanged.

## Open Questions

~~Should `ProspectAIFlow.run_analysis()` be async or synchronous?~~
**Resolved — synchronous.** `flow.kickoff()` is sync-callable; CrewAI handles its internal asyncio loop. The CLI stays free of `asyncio.run()`. The Modal backend (`../prospectai-backend/serve.py`) already runs `run_analysis()` inside a `threading.Thread`, so a blocking call is fine — the FastAPI event loop is never blocked. Modal also scales horizontally, so concurrent web requests each get their own container.

~~Should `prospect_ai_crew.py` be kept long-term?~~
**Resolved — mark deprecated.** `ProspectAICrew` will be refactored into a task/agent factory but will not be the orchestration entry point. A `# DEPRECATED` docstring and `DeprecationWarning` in `__init__` will signal removal in a future release.

### Remaining consideration — `serve.py` progress stream counter

`serve.py` has two separate counters with different concerns:

- **`analytics_store[sector]`** — counts complete end-to-end pipeline runs. Incremented once on `pipeline_done`. **No change needed.**
- **`agent_counter`** — drives the SSE progress stream within a single run (0→5). Maps completion index to `_DONE_MESSAGES[idx]` and `AGENT_NAMES[idx]`. With parallel execution, Technical and Fundamental complete in non-deterministic order, so `agent_counter` could assign the wrong message to whichever finishes second.

**Fix (in prospectai-backend):** `ProspectAIFlow.run_analysis()` passes an explicit `task_index` field in every `progress_callback` event (Market=0, Technical=1, Fundamental=2, Draft=3, Critic=4, Final=5). `serve.py` uses that index directly instead of auto-incrementing `agent_counter`. This ensures the correct message is emitted regardless of which parallel phase completes first. Migration step tracked below.
