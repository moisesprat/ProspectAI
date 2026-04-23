## Context

`ProspectAIFlow` passes prior phase outputs to each downstream phase via slim helper methods (`_slim_market_for_analysis()`, `_slim_market_for_strategy()`, `_slim_technical()`, `_slim_fundamental()`, `_slim_draft()`, `_slim_critique()`). These were introduced to avoid passing raw CrewAI output strings, but `final_strategy()` still concatenates all 5 prior outputs, yielding ~117k input tokens per run.

Measured token profile (representative run):
| Phase | Input | Total |
|---|---|---|
| Market Analysis | 13k | 15k |
| Technical Analysis | 30k | 35k |
| Fundamental Analysis | 27k | 33k |
| Draft Strategy | 46k | 49k |
| Critic Review | 12k | 19k |
| Final Strategy | **117k** | **124k** |
| **Pipeline total** | **245k** | **275k** |

Final Strategy dominates because it receives all 5 prior context blobs.

## Goals / Non-Goals

**Goals:**
- Reduce Final Strategy input tokens from ~117k to ~30–40k
- Reduce pipeline total from ~275k to ~180–200k input tokens
- Zero changes to agent prompts, tools, output schema, or observable report quality

**Non-Goals:**
- Reducing tokens for Technical, Fundamental, or Critic phases (already reasonable)
- Changing the LLM model or temperature settings
- Modifying output schemas or downstream data consumers

## Decisions

### Decision: Add `_slim_for_final()` instead of modifying existing helpers

**Chosen**: New dedicated `_slim_for_final()` method for Final Strategy context.

**Why**: Each existing slim helper is reused by multiple phases. Tightening `_slim_draft()` in place would also affect Critic's input (which uses it). A dedicated helper gives Final Strategy its own budget without coupling to other phases.

**Alternative considered**: Tighten all existing helpers uniformly. Rejected because Critic actually benefits from the fuller draft context to generate accurate revision directives.

### Decision: Final Strategy receives critic + slim positions + market signal only

**Chosen**: `_slim_for_final()` returns:
1. **Critic directives only** — `findings` list with `severity`, `field`, `directive` (no `explanation` prose > 80 chars)
2. **Slim draft positions** — per ticker: `ticker`, `action`, `allocation_pct`, `entry_zone`, `stop_loss` (no `rationale`)
3. **Minimal market signal** — `sector_signal` + top-3 tickers by composite score (ticker + score only)

Market narrative, technical indicators, and fundamental ratios are **dropped** from Final Strategy context. The Final Strategist's task prompt already instructs it to "address CRITICAL and MAJOR critique findings" — it does not need to re-read raw indicator values.

**Alternative considered**: Keep technical and fundamental summaries as 1-sentence per ticker. Rejected because the Critic already references those in its findings; passing them again is redundant.

### Decision: Tighten `_slim_critique()` in place

**Chosen**: Trim `explanation` fields to 80 chars (from current ~unlimited) since `_slim_critique()` is only used by Final Strategy today.

**Why**: If a future phase also consumes critique output, it can get a fuller version via a dedicated helper.

### Decision: Drop `overall_strategy` from `_slim_draft()`

**Chosen**: Remove `overall_strategy` field from `_slim_draft()` output.

**Why**: Critic receives draft slim — it doesn't use `overall_strategy` to produce findings. Final Strategy gets `_slim_for_final()` which doesn't include it anyway. Safe to drop.

## Risks / Trade-offs

- **Risk**: Final Strategy misses context it implicitly relied on → output quality degrades.  
  **Mitigation**: The Critic's findings already encode the key problems with the draft referencing specific indicator values. Final Strategist only needs to apply the corrections, not re-derive them.

- **Risk**: Cached tokens (Anthropic prompt cache) become less effective with shorter contexts.  
  **Mitigation**: Acceptable trade-off — absolute token cost drops even if cache hit rate slightly decreases.

- **Trade-off**: Critic's `_slim_critique()` tightening reduces explanation verbosity. Directives themselves are kept in full; only explanation prose is truncated.

## Migration Plan

1. Update `_slim_draft()` — drop `overall_strategy`, shorten `rationale` to 100 chars
2. Update `_slim_critique()` — truncate `explanation` to 80 chars
3. Add `_slim_market_for_final()` — `sector_signal` + top-3 tickers (ticker + score only)
4. Add `_slim_for_final()` — assembles critic + slim draft positions + market signal
5. Update `final_strategy()` — replace 5-context join with `_slim_for_final()` output
6. Manual smoke test: run one sector, verify report quality and token counts in execution metrics

Rollback: revert `prospect_ai_flow.py` — no schema or config changes needed.

## Open Questions

- None — approach is well-bounded to a single file.
