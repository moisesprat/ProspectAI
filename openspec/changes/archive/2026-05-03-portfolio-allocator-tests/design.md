## Context

`PortfolioAllocatorTool._run()` is pure deterministic math — it takes a JSON string,
parses it, and returns a JSON string. No yfinance calls, no LLM calls, no network I/O.
This makes it straightforward to test: pass JSON in, assert JSON out, no mocking needed.

## Goals / Non-Goals

**Goals:**
- Cover all five action types: LONG-BUY, SCALED-ENTRY, WAIT-FOR-ENTRY, MONITOR, AVOID
- Verify allocation cap enforcement for each action type
- Verify trade setup formulas against known numeric inputs
- Verify three-bucket capital breakdown arithmetic
- Verify error handling and entry-zone fallback behavior

**Non-Goals:**
- Testing the LLM's action decisions (those are made upstream)
- Testing `CompositeScoreTool` or `TechnicalAnalysisTool` integration
- Testing the iterative cap redistribution in exhaustive detail (one representative case is enough)

## Decisions

### Decision: Call `_run()` directly, not through CrewAI tool machinery

`PortfolioAllocatorTool._run()` is the pure computation method. Instantiating the tool
and calling `_run(json_str)` directly avoids CrewAI framework overhead and keeps tests
fast and deterministic. No need to mock BaseTool internals.

### Decision: Use `json.loads()` to assert output, not string matching

The tool returns a JSON string. Parse it with `json.loads()` and assert on dict values.
This is more robust than string comparison and tolerant of key ordering.

### Decision: Pin numeric inputs to round-number prices for readable assertions

Use simple prices like 100/105, 200/210, 150 so expected stop/TP values are
easy to hand-verify. Avoids floating-point surprise in test assertions (use `pytest.approx`).

## Risks / Trade-offs

- Floating-point rounding: the tool uses `round(..., 1)` and `round(..., 2)`. Use
  `pytest.approx(abs=0.01)` for price assertions to avoid brittle exact float comparisons.
