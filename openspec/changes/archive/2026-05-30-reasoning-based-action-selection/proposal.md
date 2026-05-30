## Why

STEP 3 of the Draft Strategist task currently instructs the LLM to evaluate deterministic numeric gates (`if RSI > 70 → WAIT`, `if gap ≥ 5% → WAIT`) that any rule-engine could execute, eliminating the value of LLM reasoning entirely. The Critic then re-enforces those same numeric thresholds as hard violations, overriding any judgment the LLM might apply. This produces a system that is structurally over-conservative — especially on the aggressive profile — because the same fixed thresholds apply regardless of the overall signal quality, fundamental strength, or regime context.

## What Changes

- **STEP 3 of `draft_strategy` rewritten**: Replace numeric threshold gates with reasoning guidance. The LLM receives pre-computed qualitative signals (`entry_zone_status`, `overall_signal`, `momentum_score`, `regime`, `financial_health`, `valuation_grade`, `composite_score`) and is instructed to reason about action through the lens of the risk profile — not to recalculate gaps or RSI levels.
- **Profile guidance made operative**: Conservative and aggressive profiles get distinct reasoning frameworks for PULLBACK_ENTRY situations, so the profile selection actually changes which stocks become LONG-BUY vs WAIT-FOR-ENTRY.
- **Critic failure modes updated**: `OVERBOUGHT_IGNORED` and `ENTRY_ZONE_VIOLATED` (numeric checks) are replaced by reasoning-consistency checks: `ACTION_PROFILE_MISMATCH`, `WAIT_IN_ZONE`, and `UNCONVINCING_OVERRIDE`. The Critic validates coherent reasoning, not numeric compliance.
- **SCALED-ENTRY removed as an action**: The SCALED-ENTRY branch in STEP 3 is eliminated. Above-zone stocks that qualify for entry become LONG-BUY with a current-price-anchored setup (the same math the immediate SCALED-ENTRY tranche used), simplifying the action space to four values: LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID.
- **Critic reference table extended**: Profile-specific entry-behavior expectations added alongside existing stop/R/R/allocation bounds.

## Capabilities

### New Capabilities
- `reasoning-action-selection`: Qualitative, profile-aware action selection in the Draft Strategist — LLM reasons from `entry_zone_status` + signal context rather than evaluating numeric thresholds.
- `reasoning-critic-validation`: Critic validates reasoning coherence (action consistent with signals and profile) rather than enforcing deterministic numeric rules.

### Modified Capabilities
- `portfolio-allocator-trade-setups`: SCALED-ENTRY action removed; above-zone LONG-BUY uses current-price-anchored stop/TP (the former immediate-tranche formula). All capital for that position counted as `deployed_pct`.

## Impact

- `config/tasks.yaml` — primary change surface: STEP 3 of `draft_strategy`, STEP 2 failure-mode table of `critique_review`, profile reference table in `critique_review`, STEP 1 of `final_strategy`.
- `utils/portfolio_allocator_tool.py` — remove SCALED-ENTRY branch; add current-price-anchored LONG-BUY path for above-zone entries.
- `schemas/agent_outputs.py` — remove `SCALED-ENTRY` from the `action` Literal; remove `scaled_entry_setups` field (or make permanently `null`-only) from `PositionRecommendation`.
- No changes to tool implementations, agent YAML, or flow orchestration.
