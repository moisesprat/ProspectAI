## Why

ProspectAI runs multi-agent pipelines that can take several minutes, but currently produces no structured record of how that time was spent or what LLM resources were consumed. Adding an execution metrics artifact gives operators and developers visibility into cost, latency, and per-agent efficiency — making it easier to optimize the pipeline and budget API spend.

## What Changes

- A new `ExecutionTracker` component captures wall-clock elapsed time for the full pipeline and for each agent individually.
- Token usage (input + output) is collected per agent and per model, then aggregated to a pipeline total.
- At pipeline completion a `metrics.json` object is produced containing all timing and token data plus derived fields (e.g. cost estimate, tokens/sec).
- The CLI prints the metrics JSON to stdout after the analysis report.
- The web UI surfaces the metrics in a collapsible summary panel after results are shown.

## Capabilities

### New Capabilities

- `execution-metrics`: Captures, aggregates, and surfaces execution timing, token usage (input/output totals split by agent and by model), and derived stats (duration, cost estimate) as a structured JSON artifact emitted at the end of every pipeline run.

### Modified Capabilities

- `parallel-analysis-flow`: The existing parallel flow orchestration must emit per-agent timing hooks so the tracker can attribute wall-clock time to each agent correctly.

## Impact

- **`prospect_ai_crew.py` / flow orchestrator** — wrap agent execution with start/stop timing hooks and capture token callbacks from CrewAI/LiteLLM.
- **`main.py`** — print metrics JSON to stdout after report output.
- **Web UI** `../prospectai-web` — receive and display metrics panel.
- **New file**: `utils/execution_tracker.py`.
- **Dependencies**: no new packages required; uses CrewAI's existing callback/event system and Python `time` module.
