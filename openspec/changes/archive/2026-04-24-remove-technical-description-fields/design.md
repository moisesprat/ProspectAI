## Context

`TechnicalAnalysisTool` returns a rich nested dict per ticker with four categories of indicators (momentum, trend, volatility, volume). Every leaf indicator dict includes a `"description"` string that was added to make tool output self-documenting for a human reader. However, the only consumer of this output is the LLM agent, which already has domain knowledge of all indicators by name. These strings add ~60-100 tokens per indicator × 15 indicators × 5 tickers ≈ 3,000-5,000 wasted input tokens per analysis run.

## Goals / Non-Goals

**Goals:**
- Remove all `"description"` keys from the tool output dicts in `_calculate_momentum_indicators`, `_calculate_trend_indicators`, `_calculate_volatility_indicators`, and `_calculate_volume_indicators`
- Reduce input token usage for the `technical_analysis` phase with no change to analytical quality

**Non-Goals:**
- Changing indicator values, status strings, or the nested dict structure
- Modifying the task description or agent prompts
- Changing any schema or downstream slim helper

## Decisions

### D1: Remove descriptions at the source, not in a slim helper

The `"description"` strings are removed from `_run()` output rather than stripped in `_slim_technical()`. Rationale: the tool result is injected into the LLM context directly during the agentic loop — the slim helper only runs afterwards to build context for the next phase. Removing at the source eliminates the waste before it hits the LLM.

### D2: No replacement — just deletion

No abbreviated alternative (e.g., a short label) is substituted. Indicator names (`"rsi"`, `"macd"`, `"stochastic"`) already identify the indicator uniquely; the LLM does not need a prose description alongside numeric values.

## Risks / Trade-offs

- **Readability of raw tool output**: Human inspection of tool results during debugging loses the self-documenting descriptions. Mitigation: indicator names are self-explanatory; this is a development ergonomics trade-off, not a correctness risk.
- **No LLM behavior change expected**: The descriptions did not add signal — they re-stated the indicator name in a sentence. Removing them should have no effect on LLM output quality. Mitigation: run a smoke test and compare Critic/Draft output before and after.

## Migration Plan

All changes are confined to `utils/technical_analysis_tool.py`. No migration needed — the change takes effect on the next run with no state to migrate.
