## 1. Schema — Remove SCALED-ENTRY

- [x] 1.1 In `schemas/agent_outputs.py`, remove `"SCALED-ENTRY"` from the `action` Literal in `PositionRecommendation`
- [x] 1.2 In `schemas/agent_outputs.py`, remove or retire the `scaled_entry_setups` field from `PositionRecommendation` (set to `None`-only or delete)
- [x] 1.3 In `schemas/agent_outputs.py`, remove the SCALED-ENTRY auto-construction branch from `validate_setup_fields_by_action`

## 2. Allocator — Remove SCALED-ENTRY branch, add above-zone LONG-BUY path

- [x] 2.1 In `utils/portfolio_allocator_tool.py`, remove `SCALED-ENTRY` from `DEPLOYED_ACTIONS`
- [x] 2.2 In `utils/portfolio_allocator_tool.py`, remove the SCALED-ENTRY output branch (lines that produce `scaled_entry_setups`)
- [x] 2.3 In `utils/portfolio_allocator_tool.py`, remove the SCALED-ENTRY half/half bucket split from the capital breakdown section
- [x] 2.4 In `utils/portfolio_allocator_tool.py`, add an above-zone LONG-BUY detection: when `current_price > entry_zone_high`, use `_trade_setup_price_anchored(current_price, ...)` instead of `_trade_setup(entry_zone_low, entry_zone_high, ...)`; count full allocation as `deployed_pct`
- [x] 2.5 Update the allocator tool docstring to remove SCALED-ENTRY references and document the above-zone LONG-BUY path

## 3. tasks.yaml — Rewrite Draft Strategist STEP 3

- [x] 3.1 Replace the "price ABOVE zone" numeric-gate block with the qualitative reasoning framework: branch on `entry_zone_status`, describe conservative vs aggressive defaults for PULLBACK_ENTRY
- [x] 3.2 Remove the SCALED-ENTRY branch from the within-zone and above-zone rules; update "valid actions" list to `LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID`
- [x] 3.3 Update the aggressive profile qualitative guidance (lines 215-218) to be consistent with the new STEP 3 reasoning framework (mention gap, stochastic_status, and momentum_score as reasoning inputs, not thresholds)
- [x] 3.4 Remove SCALED-ENTRY references from STEP 4 and STEP 5 (allocate_portfolio call description, scaled_entry_setups copy instruction, monitoring_triggers guidance)

## 4. tasks.yaml — Update Critic failure modes

- [x] 4.1 Remove `OVERBOUGHT_IGNORED` from the Critic's failure-mode table
- [x] 4.2 Remove `ENTRY_ZONE_VIOLATED` from the Critic's failure-mode table
- [x] 4.3 Remove `MISSING_SCALED_SETUPS` and `IMMEDIATE_RR_BELOW_1_5` from the Critic's failure-mode table
- [x] 4.4 Add `ACTION_PROFILE_MISMATCH` — LONG-BUY on PULLBACK_ENTRY with overall_signal=BEARISH and no fundamental override thesis (MAJOR)
- [x] 4.5 Add `WAIT_IN_ZONE` — WAIT-FOR-ENTRY when entry_zone_status=CURRENT_ENTRY (CRITICAL)
- [x] 4.6 Add `UNCONVINCING_OVERRIDE` — aggressive LONG-BUY on PULLBACK_ENTRY with momentum_score < 4, financial_health=WEAK, no catalyst cited (MAJOR)
- [x] 4.7 Update the Critic's profile reference table to include PULLBACK_ENTRY entry-behavior thresholds for each profile

## 5. tasks.yaml — Update Final Strategist

- [x] 5.1 Remove SCALED-ENTRY references from STEP 2 CASE B (allocate_portfolio call) and STEP 4 output schema description in `final_strategy`
- [x] 5.2 Ensure the "valid actions" list in `final_strategy` RULES matches: `LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID`

## 6. Tests — Update for removed SCALED-ENTRY

- [x] 6.1 In `tests/test_tools_portfolio_allocator.py`, remove or update test cases that submit SCALED-ENTRY actions; add a test for above-zone LONG-BUY using current-price-anchored stop/TP
- [x] 6.2 In `tests/test_schemas.py`, add a test asserting `SCALED-ENTRY` is rejected by `PositionRecommendation` validation
- [x] 6.3 In `tests/test_schemas.py`, remove any test that constructs a `PositionRecommendation` with `action="SCALED-ENTRY"`

## 7. Validation

- [x] 7.1 Run `pytest tests/ -v` and confirm all tests pass (216 pass; 4 failures + 24 errors in test_crew.py are pre-existing chromadb import issues unrelated to this change)
- [x] 7.2 Run a full pipeline (`python3 main.py --sector Technology`) with `--risk-profile aggressive` and verify that PULLBACK_ENTRY stocks with BULLISH signals receive LONG-BUY actions (not WAIT-FOR-ENTRY)
- [x] 7.3 Verify the `/api/long-buy-wins` endpoint still functions after allocator change (no SCALED-ENTRY records expected)
