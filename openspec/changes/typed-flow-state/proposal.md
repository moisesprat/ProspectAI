## Why

When `ProspectAICrew` was refactored into `ProspectAIFlow`, the typed Pydantic outputs that each mini-Crew produces are discarded — the flow stores `result.raw` (a raw string) instead of `result.tasks_output[0].pydantic` (the validated model). This forces the `_slim_*` helpers to re-parse JSON defensively with silent fallbacks, losing the validation guarantees that `output_pydantic=` was designed to provide.

## What Changes

- `ProspectAIFlowState` fields `market_output`, `technical_output`, `fundamental_output`, `draft_output`, and `critique_output` change from `str` to the corresponding `Optional[<TypedModel>]`.
- Each flow method extracts `result.tasks_output[0].pydantic` instead of `result.raw` after a mini-Crew finishes.
- All `_slim_*` helpers are rewritten to access typed model attributes directly, eliminating `json.loads()` and the raw-string fallback paths.
- `_fmt_ctx` continues to serialize the slimmed dict to a JSON string for task-description injection (unavoidable across independent mini-Crews in a Flow).
- `final_strategy` continues to use `result.raw` as the source for `_parse_result`, since the final output is consumed as a dict by the caller — no change there.

## Capabilities

### New Capabilities

- `typed-flow-state`: Inter-agent data in `ProspectAIFlow` is stored and accessed as validated Pydantic models; context slimming is driven by typed attribute access rather than JSON string parsing.

### Modified Capabilities

- `parallel-analysis-flow`: The flow state schema changes — outputs are now typed models, not strings. No behavioral change to the parallelism or sequencing logic.

## Impact

- `prospect_ai_flow.py` — all changes are contained here.
- No changes to `schemas/agent_outputs.py`, `prospect_ai_crew.py`, or any agent/tool file.
- No changes to the public API of `ProspectAIFlow.run_analysis()`.
- Tests that inspect `flow.state.*_output` fields will see typed models instead of strings.
