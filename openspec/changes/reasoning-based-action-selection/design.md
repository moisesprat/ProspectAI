## Context

ProspectAI is a 6-phase CrewAI pipeline. Phase 4 (Draft Strategist) receives pre-computed qualitative signals from Phases 1-3 and must decide one action per stock. Phase 5 (Critic) adversarially reviews that draft.

Currently, STEP 3 of the Draft Strategist task prompt gives the LLM explicit numeric gates: `if RSI > 70 → WAIT`, `if gap ≥ 5% → WAIT`, `if gap < 5% AND regime=TRENDING AND composite ≥ 75 → SCALED-ENTRY`. These are deterministic conditions the LLM evaluates identically regardless of context, profile, or signal convergence. The Critic then re-enforces those same thresholds as hard violations (`OVERBOUGHT_IGNORED`, `ENTRY_ZONE_VIOLATED`), so even if the LLM's full reasoning would support buying a stock 6% above its zone with exceptional fundamentals and BULLISH signal, the Critic overrides it.

The primary fix surface is `config/tasks.yaml`. Secondary surfaces are `utils/portfolio_allocator_tool.py` (remove SCALED-ENTRY branch) and `schemas/agent_outputs.py` (remove `SCALED-ENTRY` from action Literal).

## Goals / Non-Goals

**Goals:**
- STEP 3 instructs the LLM to reason from qualitative signals (`entry_zone_status`, `overall_signal`, `momentum_score`, `regime`, `financial_health`, `valuation_grade`, `composite_score`) rather than recalculate numeric thresholds
- Conservative and aggressive profiles produce materially different LONG-BUY vs WAIT-FOR-ENTRY outcomes for PULLBACK_ENTRY stocks
- The Critic validates reasoning coherence, not numeric compliance
- SCALED-ENTRY action is removed from the valid action space; above-zone eligible entries become standard LONG-BUY

**Non-Goals:**
- Changing how tools compute `entry_zone_status`, `momentum_score`, or `composite_score`
- Changing the allocator's stop/TP math or PROFILE_BOUNDS
- Changing flow orchestration, agent LLM selection, or parallel phase execution
- Making the system completely non-deterministic — hard stops (WEAK health, price_data_error, negative sentiment + no catalyst) are preserved

## Decisions

### Decision 1: Remove SCALED-ENTRY entirely rather than keep it profile-conditional

**Choice**: Remove SCALED-ENTRY from the action space. Above-zone stocks that warrant buying become LONG-BUY with a current-price-anchored stop/TP (the former immediate-tranche formula).

**Rationale**: SCALED-ENTRY was a mechanical compromise that split one position into two setups with different stop-losses, different take-profits, and split capital accounting. It required the LLM to pass `current_price` explicitly to the tool, introduced two Critic failure modes (`MISSING_SCALED_SETUPS`, `IMMEDIATE_RR_BELOW_1_5`), and confused users who expected a simple buy/wait answer. Folding it into LONG-BUY with current-price anchoring gives a coherent single-tranche position. The user explicitly requested this.

**Alternative considered**: Keep SCALED-ENTRY but restrict it to aggressive profile only. Rejected because it preserves the confusion and fragility without meaningful benefit — the above-zone LONG-BUY with current-price stop/TP is functionally equivalent to the immediate tranche and simpler.

### Decision 2: Use entry_zone_status as the primary action pivot, not raw price/zone arithmetic

**Choice**: STEP 3 branches on `entry_zone_status` (CURRENT_ENTRY / PULLBACK_ENTRY / BELOW_ZONE) — a qualitative label already computed by the technical interpretation tool — rather than instructing the LLM to compute `(current_price - entry_zone_high) / entry_zone_high`.

**Rationale**: `entry_zone_status` encodes the technical tool's judgment about whether the current price is actionable. The LLM does not need to re-derive this from raw numbers. Using the label means the LLM applies reasoning to a pre-classified situation, which is the correct separation of concerns (tool computes, LLM reasons).

**Alternative considered**: Keep numeric thresholds but make them profile-specific in STEP 3. Rejected because it still makes the LLM a threshold calculator with no room for signal convergence reasoning.

### Decision 3: Critic validates reasoning coherence, not numeric outcomes

**Choice**: Replace `OVERBOUGHT_IGNORED` (RSI > 70 with LONG-BUY) and `ENTRY_ZONE_VIOLATED` (gap ≥ 5% with LONG-BUY) with:
- `ACTION_PROFILE_MISMATCH`: LONG-BUY on PULLBACK_ENTRY with overall_signal=BEARISH and no compelling fundamental override cited in rationale
- `WAIT_IN_ZONE`: WAIT-FOR-ENTRY when entry_zone_status=CURRENT_ENTRY
- `UNCONVINCING_OVERRIDE`: aggressive LONG-BUY on PULLBACK_ENTRY with momentum_score < 4, financial_health=WEAK, and no specific catalyst cited

**Rationale**: The Critic's job is to catch bad reasoning, not to re-run the same numeric checks. If the LLM correctly identified PULLBACK_ENTRY + BULLISH + momentum=8 + STRONG health and chose LONG-BUY (aggressive), the Critic should validate that reasoning — not override it because RSI was 72 when the decision was made.

### Decision 4: Preserve hard stops as non-negotiable overrides

The following remain as hard stops regardless of profile:
- `price_data_error` → MONITOR or AVOID only
- `financial_health=WEAK` → MONITOR or AVOID
- `overall_signal=BEARISH` with PULLBACK_ENTRY → WAIT-FOR-ENTRY for both profiles (no override)
- `sentiment < 0` with no cited catalyst → cannot be LONG-BUY

These are correctness guardrails, not conservatism. Removing them would enable the LLM to buy into broken or deteriorating positions.

## Risks / Trade-offs

**LLM may default to conservative even under aggressive profile** → Mitigation: The profile-specific reasoning framework in STEP 3 explicitly states what "aggressive default" and "aggressive override" mean with concrete signal thresholds. The Critic's `ACTION_PROFILE_MISMATCH` check will flag under-aggressive behavior.

**Removing numeric Critic checks makes behavior harder to predict** → Mitigation: The new Critic checks (`WAIT_IN_ZONE`, `UNCONVINCING_OVERRIDE`) still have enough specificity to catch systematic errors. Behavior can be validated by running the same sector/profile combination before and after and comparing action distributions.

**SCALED-ENTRY removal changes output schema** → Mitigation: The `action` Literal in `PositionRecommendation` loses `SCALED-ENTRY`; `scaled_entry_setups` field becomes unused. Any downstream consumer (backend, frontend) reading `action` must handle the reduced set. The backend `app.py` does not currently inspect `action` values — only the `positions` array and `deployed_pct`/`reserved_pct`.

## Migration Plan

1. Update `config/tasks.yaml` (STEP 3 of `draft_strategy`, STEP 2 of `critique_review`, profile reference table in `critique_review`, monitoring_triggers in `final_strategy`)
2. Update `utils/portfolio_allocator_tool.py` (remove SCALED-ENTRY branch, add current-price-anchored LONG-BUY path)
3. Update `schemas/agent_outputs.py` (remove `SCALED-ENTRY` from Literal, remove `scaled_entry_setups`)
4. Update tests that reference SCALED-ENTRY
5. No data migration needed — historical records in Modal Dict are unaffected

Rollback: revert `tasks.yaml` only. The tool and schema changes are backward-compatible for existing deployed runs (no SCALED-ENTRY records exist in production).

## Open Questions

- Should BELOW_ZONE stocks always be MONITOR (watch for recovery) or can they be AVOID? Current proposal: both profiles treat it as MONITOR unless fundamentals are also WEAK, in which case AVOID is appropriate.
- The aggressive profile's PULLBACK_ENTRY LONG-BUY path requires `momentum_score ≥ 5`. Should this threshold also be made qualitative ("momentum is not clearly weak") rather than numeric? Decision deferred — momentum_score is a tool-computed number, so referencing it is not the same as asking the LLM to re-derive it.
