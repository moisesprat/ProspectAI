## Context

`ProspectAIFlow` runs six pipeline phases as independent mini-Crews. Each mini-Crew has `output_pydantic=<Schema>` set on its single task, meaning CrewAI validates the LLM output and populates `result.tasks_output[0].pydantic` with a typed model. However, the flow ignores this and stores `result.raw` (a string) in `ProspectAIFlowState`. The `_slim_*` helpers then re-parse that string with `json.loads()` and silent fallbacks — undoing validation that already happened.

The schemas in `schemas/agent_outputs.py` are well-designed and already used correctly by `build_task()`. The only gap is the flow state and the extraction step.

## Goals / Non-Goals

**Goals:**
- Store each phase's output as its validated Pydantic model in `ProspectAIFlowState`.
- Extract `result.tasks_output[0].pydantic` (not `result.raw`) after each mini-Crew.
- Rewrite `_slim_*` helpers to access model attributes directly — no `json.loads()`, no fallback string paths.
- Keep the slimming logic (field selection) intact; only the access mechanism changes.

**Non-Goals:**
- Changing the public API of `run_analysis()` or its return shape.
- Changing `prospect_ai_crew.py` or any agent/tool file.
- Changing the parallelism or sequencing logic of the flow.
- Eliminating the JSON-string injection into task descriptions (unavoidable across independent mini-Crews).

## Decisions

### D1: State field types — `Optional[Model]` not `str`

`ProspectAIFlowState` fields become:
```python
market_output:      Optional[MarketAnalysisOutput]     = None
technical_output:   Optional[TechnicalAnalysisOutput]  = None
fundamental_output: Optional[FundamentalAnalysisOutput] = None
draft_output:       Optional[InvestorStrategicOutput]  = None
critique_output:    Optional[CriticOutput]             = None
```

**Alternatives considered:**
- Keep as `str`, parse on access (current state — rejected, loses validation).
- Store both raw and typed (adds redundancy with no benefit).

`None` as default is intentional: a flow method that hasn't run yet yields `None`, and helpers can guard on it clearly rather than checking for empty string.

### D2: Extraction — `result.tasks_output[0].pydantic`

After `await self._make_crew(task).akickoff()`, the validated model lives at `result.tasks_output[0].pydantic`. Each flow method assigns this directly to the state field:

```python
self.state.market_output = result.tasks_output[0].pydantic
```

`final_strategy` is exempt — its result is consumed by `_parse_result()` which already handles `tasks_output[-1].pydantic`. No change needed there.

**Risk**: If `output_pydantic` validation fails, CrewAI may raise or set `.pydantic` to `None`. The existing retry/error handling in CrewAI covers retries; if it ultimately returns `None`, the `_check_error()` pattern should catch it or the helper guard handles it.

### D3: Slim helpers — attribute access replaces JSON parsing

Each `_slim_*` method receives a typed model. Example:

```python
def _slim_market_for_analysis(self) -> str:
    mo = self.state.market_output
    if mo is None:
        return ""
    return json.dumps({
        "sector": mo.sector,
        "candidate_stocks": [
            {"ticker": s.ticker, "average_sentiment": s.average_sentiment, "relevance_score": s.relevance_score}
            for s in mo.candidate_stocks
        ],
    })
```

The `except Exception: return self.state.market_output` fallback paths are removed — if the model is `None` the guard returns `""`, and model attribute access cannot produce silent wrong data the way JSON parsing can.

### D4: `_fmt_ctx` and task-description injection unchanged

The final step (serializing a slimmed dict to a JSON string and appending it to the task description) stays the same. This is the only viable cross-mini-Crew context mechanism in CrewAI Flow. The improvement is that the data driving that serialization is now typed, not re-parsed.

### D5: Extend `TechnicalAnalysisOutput` schema to capture all downstream-referenced fields

During implementation, a gap was found: `TechnicalAnalysisOutput` (and `MomentumAnalysis`) did not capture `raw_indicators` (rsi, stochastic_status, macd_status, ma_status, adx), `overall_signal`, `entry_zone_status`, or `regime` — all referenced by name in the draft strategy and critic task descriptions. Storing `result.tasks_output[0].pydantic` and relying only on the schema would have silently omitted these fields from the context.

**Resolution**: Extend the schemas to capture the full tasks.yaml output format:
- Add `RawIndicators` model with optional fields for the five raw indicators.
- Add `raw_indicators: Optional[RawIndicators]` to `StockTechnicalAnalysis`.
- Add `overall_signal`, `entry_zone_status`, `regime` as `Optional[str]` to `MomentumAnalysis`.

All fields are `Optional` to preserve validation tolerance for partial outputs (e.g., price-error tickers).

**Alternatives considered**: Store the raw dict alongside the Pydantic model (rejected — adds redundancy and defeats the purpose of typed state).

## Risks / Trade-offs

- **CrewAI pydantic field availability**: `result.tasks_output[0].pydantic` is the documented path for `output_pydantic` tasks. If a future CrewAI version moves this, the extraction line breaks. Mitigation: pin CrewAI version in `requirements.txt`; add a guard that raises clearly if `.pydantic` is `None`.
- **Flow state serialization**: CrewAI Flow may serialize/deserialize state between steps. Nested Pydantic models in state are supported by CrewAI (state is a `BaseModel`), but complex nested types should be tested. Mitigation: run the full pipeline integration test after the change.
- **`_slim_*` None guards**: If a helper is called before its phase has run (e.g., programming error in flow wiring), it now returns `""` silently. The old behavior returned an empty/unparseable string. The behavior is equivalent — but explicit `None` guards make it readable.

## Migration Plan

Changes are confined to `prospect_ai_flow.py` and `schemas/agent_outputs.py`. No data format changes to the public `run_analysis()` API. Existing tests verify correctness; full pipeline integration test recommended before shipping.
