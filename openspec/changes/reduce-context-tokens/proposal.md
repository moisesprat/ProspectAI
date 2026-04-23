## Why

The pipeline consumes ~275k input tokens per run, with Final Strategy alone at 117,733 input tokens because it receives all 5 prior phase outputs concatenated. Reducing context passed to each agent — especially Final Strategy — will cut costs and latency substantially without affecting output quality.

## What Changes

- Introduce a dedicated `_slim_for_final()` helper that replaces the current 5-context concatenation for Final Strategy, retaining only: critic directives (full), draft positions (ticker + action + allocation only), and a minimal market signal (sector signal + top 3 tickers). Market, technical, and fundamental narrative prose is dropped.
- Tighten `_slim_draft()` to further shorten per-position rationale (100 chars max, down from 150) and drop `overall_strategy` entirely — the Final Strategist gets this from the critic output.
- Tighten `_slim_critique()` to retain only the `findings` list (severity + field + directive) and drop verbose `explanation` fields exceeding 200 chars.
- Tighten `_slim_market_for_strategy()` to drop `rationale` fields and keep only `ticker`, `signal`, and `composite_score` per stock.
- No changes to Technical or Fundamental context passed to Draft Strategy (those phases are already well-sized at ~35k and ~33k).

## Capabilities

### New Capabilities

- None

### Modified Capabilities

- `parallel-analysis-flow`: Context scope rules for each phase are changing — specifically what fields each downstream phase receives from prior phases. The spec requirement for "Final Strategy receives all prior phase outputs" changes to "Final Strategy receives critic directives, slim draft positions, and minimal market signal only."

## Impact

- `prospect_ai_flow.py`: update `_slim_draft()`, `_slim_critique()`, `_slim_market_for_strategy()`; add `_slim_for_final()`; update `final_strategy()` to use new helper
- Expected token reduction for Final Strategy: ~117k → ~30–40k input tokens (critic ~7k + slim draft ~8k + minimal market ~2k)
- Expected pipeline total: ~275k → ~180–200k input tokens
- No changes to agent configs, tools, or output schemas
