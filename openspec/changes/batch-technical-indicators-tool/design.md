## Context

`TechnicalAnalysisTool._run(ticker: str)` is called once per ticker in the technical analysis agentic loop. For a 5-ticker run, the LLM executes 5 sequential tool calls, and each result (a full indicator dict) is appended to the conversation context as an input message before the next LLM turn. This means the LLM reads 5 large tool results to accumulate data it then must aggregate itself.

`FundamentalDataTool._run(tickers_json: str)` already uses the batched pattern: it accepts a JSON array and returns `{"fundamentals": [one entry per ticker]}` in one call. The `tasks.yaml` `fundamental_analysis` description explicitly instructs the LLM to call once: "The tools loop internally over all tickers. Do NOT call them per ticker."

The `interpret_technical_indicators` tool (STEP 3) is called per-ticker because interpretation takes raw values for a single ticker and produces a structured interpretation object — batching that would require a more significant refactor of the interpretation tool as well. This change scopes to the raw data fetch only.

## Goals / Non-Goals

**Goals:**
- Change `TechnicalAnalysisTool._run()` to accept `tickers_json: str` (a JSON array) and return all results in one call under `{"technical_analysis": [...]}`
- Update `config/tasks.yaml` STEP 2 in `technical_analysis` to call the tool once with the full ticker array
- Reduce raw-data tool calls from 5 to 1 per run

**Non-Goals:**
- Batching `interpret_technical_indicators` (separate concern, separate change if needed)
- Changing indicator calculations or output structure per ticker
- Changing `TechnicalAnalysisOutput` schema

## Decisions

### D1: Return key is `"technical_analysis"` not `"results"`

Matches the naming convention of `FundamentalDataTool` which uses `"fundamentals"` as the outer key, and aligns with how `tasks.yaml` already refers to the per-ticker result set (`stock_analyses`). The LLM task description will reference this key explicitly.

### D2: Tool description string updated to reflect array input

The `description` field on the `TechnicalAnalysisTool` class (used by CrewAI to tell the LLM when/how to call the tool) must be updated to say "accepts a JSON array of ticker strings" and show an example call, otherwise the LLM will continue calling it per-ticker. This is the same pattern used in `FundamentalDataTool`.

### D3: Period parameter is a scalar applied to all tickers

All tickers in a single batch use the same `period` value (`"1y"` default). This matches current behavior — the task description never varies `period` per ticker.

### D4: Error handling — per-ticker errors do not abort the batch

If `yfinance` fails for one ticker, that ticker's entry in the result array contains `{"ticker": "...", "error": "..."}` rather than indicator fields. The outer call still returns the full array. This matches `FundamentalDataTool`'s error handling pattern.

**Alternatives considered:**
- Keep per-ticker calls, just pre-fetch in parallel: rejected — CrewAI's agentic loop controls tool invocation; the LLM decides when to call, so parallelism can't be injected without changing the loop structure
- Batch both raw and interpret tools: out of scope for this change

## Risks / Trade-offs

- **BREAKING change to tool signature**: Any code that calls `TechnicalAnalysisTool()._run(ticker="AAPL")` will break. The only caller is the LLM agent via the agentic loop — but the task description must be updated atomically with the tool to prevent the LLM from using the old per-ticker pattern.
- **tasks.yaml coupling**: If the task description is updated before the tool, or vice versa, the LLM will receive a malformed tool result. Mitigation: change both in the same commit.
- **LLM compliance**: The LLM must follow the new task description and call the tool once. Mitigation: the instruction pattern is identical to `fundamental_analysis` which already works correctly.

## Migration Plan

1. Update `TechnicalAnalysisTool._run()` and class `description`
2. Update `tasks.yaml` STEP 2 for `technical_analysis` atomically in the same commit
3. Run smoke test (`python main.py --sector Technology`) and verify token usage drops for the `technical_analysis` phase
