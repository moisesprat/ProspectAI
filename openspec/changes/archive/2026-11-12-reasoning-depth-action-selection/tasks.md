## 1. Deterministic layer: gate and allocator

- [x] 1.1 Narrow `ActionPolicyGate.ACTION_POLICY_TABLE`'s `BELOW_ZONE` rows to permit `LONG-BUY`/`MONITOR`/`AVOID`, excluding only `WAIT-FOR-ENTRY`, for both risk profiles
- [x] 1.2 Update `action_policy_gate.py` module docstring to reflect the narrowed table
- [x] 1.3 Add a below-zone price-anchored trade-setup branch to `PortfolioAllocatorTool` (`current_price < entry_zone_low`), reusing `_trade_setup_price_anchored()`
- [x] 1.4 Update `PortfolioAllocatorTool`'s module and class docstrings to document the below-zone branch alongside the existing above-zone one

## 2. Schema

- [x] 2.1 Relax `CriticOutput.per_ticker_critiques` and `.revision_directives` from `min_length=1` to `default_factory=list` (min_length=0), with a comment explaining why forcing non-emptiness conflicted with "Critic does not fabricate findings"

## 3. Prompts (config/tasks.yaml)

- [x] 3.1 Rewrite `draft_strategy`'s `RISK PROFILE` block to qualitative disposition language (no numeric thresholds)
- [x] 3.2 Replace `draft_strategy` STEP 3's decision table with the ~250-350 word reasoning-framework block; verify word count against budget
- [x] 3.3 Update `draft_strategy` STEP 4's LONG-BUY comment to cover above- and below-zone cases
- [x] 3.4 Rewrite `critique_review`'s intro to remove the profile-bounds numeric table, replaced with a short note that `PortfolioBoundsValidator` already enforces bounds deterministically
- [x] 3.5 Remove deterministically-redundant checklist items from `critique_review` STEP 2: `CONCENTRATION_BREACH`, `BUCKET_SUM_ERROR`, `MONITOR_WITH_SETUP`, `AVOID_WITH_SETUP`, `INVALID_ACTION`, `COMPOSITE_SCORE_MISMATCH`, `WAIT_ENTRY_ZERO_ALLOC`, `ALLOCATION_MISMATCH`
- [x] 3.6 Reword remaining checklist items (`ACTION_PROFILE_MISMATCH`, `UNCONVINCING_OVERRIDE`, `FABRICATED_SIGNAL`, etc.) to qualitative language; keep `PRICE_IN_ZONE_WAIT`/`WAIT_IN_ZONE` unchanged
- [x] 3.7 Trim `critique_review` STEP 3 (portfolio-level review) to reasoning-consistency bullets only
- [x] 3.8 Update `critique_review` STEP 5 output spec and RULES section: annotate list fields "(may be empty)", state empty lists are valid, clarify only `PRICE_IN_ZONE_WAIT`/`WAIT_IN_ZONE` reach CRITICAL
- [x] 3.9 Reframe `final_strategy` STEP 1 to "weigh the Critic's counter-argument," keeping the requirement that every CRITICAL/MAJOR item is addressed
- [x] 3.10 Update `final_strategy`'s `RISK PROFILE` block and RULES to remove numeric restatement/orphaned cap line
- [x] 3.11 Validate `config/tasks.yaml` parses as valid YAML after all edits

## 4. Agent backstories (config/agents.yaml)

- [x] 4.1 Add "reason like an analyst, not a rule-executor" principle line to `investor_strategic` backstory; remove stale `SCALED-ENTRY` references
- [x] 4.2 Add "break the draft's reasoning, not re-derive numbers a tool already computed" clause to `critic` backstory
- [x] 4.3 Confirm `investor_strategic.temperature` stays at `0.1` (no change)
- [x] 4.4 Validate `config/agents.yaml` parses as valid YAML

## 5. Tests

- [x] 5.1 Update `test_action_policy_gate.py`: invert `BELOW_ZONE` expectation for `LONG-BUY` (now allowed), keep `WAIT-FOR-ENTRY` excluded
- [x] 5.2 Add below-zone LONG-BUY tests to `test_tools_portfolio_allocator.py`: aggressive/conservative price-anchored stop/TP, `TradeSetup` invariant
- [x] 5.3 Update `test_flow_sentiment_availability.py`'s Critic-checklist test to assert removed items are absent from `critique_review`
- [x] 5.4 Run full `pytest tests/ -v` and confirm no unexpected regressions

## 6. OpenSpec artifacts

- [x] 6.1 `proposal.md`
- [x] 6.2 `design.md`
- [x] 6.3 Spec deltas: `reasoning-action-selection`, `task-prompt-economy`, `action-policy-gate`, `reasoning-critic-validation`
- [x] 6.4 `tasks.md` (this file)
- [x] 6.5 `openspec validate reasoning-depth-action-selection --strict`
- [x] 6.6 Correct the deltas before archive: drop the duplicate closed-action-set requirement, name the three surviving hard invariants, use the current fundamental field names (phase 4)

## 7. Deferred (not part of this change's completion criteria)

- [x] 7.1 Empirical live validation: technical/fundamental-conflict case (bullish technicals + weak fundamentals) — confirm the LLM reasons through it rather than defaulting, and names the tension in the rationale. Requires user-confirmed API budget before running. — validated 2026-11-12: replayed through the live draft, critic and final phases (claude-sonnet-5-5) on synthetic records (seeded from report cc3581b8, ticker META), 1 completed pass (replay pass 5; passes 1 to 4 failed on connection or authentication before reaching a model): draft and final MONITOR, and the final rationale names the tension between the bullish technicals (momentum 8.0, MACD bullish, price above SMA50 and SMA200) and the weak fundamentals (valuation VERY_EXPENSIVE, quality Low, growth Declining) and justifies MONITOR under a conservative profile; scope: a single completed sample, the Critic raised no critique, MONITOR is also the default-safe choice; operator approved on 2026-11-12 (phase 4, D-08 to D-10)
- [x] 7.2 Empirical live validation: below-zone LONG-BUY case — confirm the new allocator branch produces a valid, coherent `TradeSetup` end-to-end. Requires user-confirmed API budget before running. — validated 2026-11-12 under the aggressive profile only: replayed through the live draft, critic and final phases (claude-sonnet-5-5) on synthetic records (ticker NVDA, price 168.89 below the entry zone), 2 of 2 aggressive passes chose LONG-BUY and published a price-anchored valid setup (entry 168.89 zero-width, stop 160.45 < price < take-profit 181.55, no bounds violation, no critical issue); not shown for the conservative profile, which chose MONITOR in 10 of 10 below-zone passes (the choice is the model's, no clamp fired); operator approved on 2026-11-12 (phase 4, D-08 to D-10)
