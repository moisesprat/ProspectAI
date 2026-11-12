## Context

`draft_strategy`'s STEP 3 (`config/tasks.yaml`) is currently a near-complete decision table: branch on `entry_zone_status`, apply fixed numeric thresholds on `momentum_score`/`financial_health` per `risk_profile`, and a "HARD STOPS" section that blocks the decision before any reasoning starts. This was the root cause of a real bug diagnosed earlier this session (the Critic inverted the `CURRENT_ENTRY` rule) and is philosophically at odds with the pipeline's own premise: an agentic Strategist should reason like a market analyst synthesizing conflicting signals, not execute a lookup table that code would run more reliably and cheaply.

Constraint from the user: this must NOT become "loosen everything," it must become "keep the true invariants, open everything else to judgment" — and it must not create a path for the LLM to invent an action outside the existing 4-value set.

## Goals / Non-Goals

**Goals:**
- Draft and Final Strategist reason holistically over technical/fundamental/sentiment signals and reach an action as the conclusion of an explicit, evidence-cited thesis.
- Reduce deterministic constraints to only the two that are genuine logical/mechanical invariants: `CURRENT_ENTRY` excludes `WAIT-FOR-ENTRY` (semantic contradiction), and `price_data_error` caps at MONITOR/AVOID (a `TradeSetup` cannot be constructed without `current_price`).
- Critic reviews reasoning coherence only; deterministically-enforced items (bounds, bucket sums, allocation caps) are removed from its checklist since it has no authority to fix them and the check is redundant with `PortfolioBoundsValidator`.
- Preserve, unmodified: the closed 4-value action set (schema-enforced), the numeric/pricing layer, `PortfolioBoundsValidator`, the sentiment sentinel, the ETF filter, Serper retry logic.

**Non-Goals:**
- Not changing `investor_strategic`'s temperature (stays 0.1 — variability comes from the prompt, not sampling, per explicit user decision).
- Not making `WAIT-FOR-ENTRY` valid at `BELOW_ZONE` (its "wait for price to fall into the zone" semantics are inherently about waiting from above; that asymmetry is preserved).
- Not touching how allocation percentages, stop-loss, or take-profit values are computed, beyond the one scoped addition below.

## Decisions

**1. Narrow `ActionPolicyGate`'s `BELOW_ZONE` row instead of removing it.**
Alternative considered: delete the `BELOW_ZONE` restriction entirely (permit all 4 actions). Rejected — `WAIT-FOR-ENTRY` at `BELOW_ZONE` has no coherent meaning under the current prompt semantics ("wait for price to fall into the zone" doesn't apply when price is already below it), so keeping it excluded is still a genuine invariant, not risk policy. Only `LONG-BUY` moves from excluded to permitted.

**2. Add a below-zone price-anchored trade-setup branch to `PortfolioAllocatorTool` as a scoped, in-plan addition to the numeric layer — not a "Non-Goal" exception.**
Verified directly against the code: the allocator only anchors to `current_price` when `current_price > entry_zone_high` (above-zone case). If `BELOW_ZONE` now permits `LONG-BUY` without a symmetric branch for `current_price < entry_zone_low`, the code falls through to the plain zone-anchored formula — placing the entry zone/stop *above* the current price while the position asserts "buy now." This is economically incoherent even though the `TradeSetup` Pydantic invariant (`stop_loss < entry_zone_low <= entry_zone_high < take_profit`) would still technically hold. This must ship in the same change as the gate narrowing, or the gate change enables a broken output.

**3. Relax `CriticOutput.per_ticker_critiques`/`revision_directives` from `min_length=1` to `min_length=0` (allow empty lists).**
Alternative considered: keep `min_length=1` and require the Critic to always produce at least a trivial note. Rejected — this is precisely the mechanism that produced the earlier fabrication bug (`critic-evidence-grounded-review`): a schema pressure to non-emptiness conflicts directly with "the Critic must not invent findings on a fully compliant draft." With the trimmed checklist, a genuinely clean draft is a legitimate, expected outcome.

**4. Reframe rather than remove `final_strategy` STEP 1's requirement to address every CRITICAL/MAJOR item.**
Alternative considered: let the Final Strategist freely accept-or-ignore Critic directives as "just another opinion," matching the new "weigh, don't execute" framing everywhere. Rejected — without an explicit obligation to respond to every CRITICAL/MAJOR item (accept with the change, or rebut citing specific data), "weighing" degrades into silent disregard, reopening the exact failure mode (unaddressed structural error propagating to the final output) that motivated the Critic fix earlier this session. The reframing changes *how* directives are evaluated (as a counter-argument to weigh, not a command to execute) without removing the *obligation to respond*.

**5. Guardrails against action hallucination are enforced entirely below the prompt layer, not added to the prompt.**
The valid-action closure already exists at three independent points: `PositionRecommendation.action: Literal[...]` in the schema (`_extract_pydantic()` rejects anything else), `ActionPolicyGate`'s closed-vocabulary regex parser (unrecognized action words parse to `None`, not a fabricated action), and STEP 7's existing "valid actions" reminder line (left untouched). No new guardrail code is needed — this change only widens what's *reachable* within the same 4 values, never what's *expressible*.

**6. Word budget (~250-350 words) for the new STEP 3 reasoning block, replacing the "table ≤20 lines" prompt-economy rule.**
Chosen (over an unbounded rewrite) per explicit user preference during planning, to keep prompt cost roughly comparable to the removed table while giving enough room to state the reasoning framework, the two surviving invariants, and the rationale-must-name-tensions requirement.

## Risks / Trade-offs

- **[Risk] More run-to-run variance in recommended actions for the same input data.** → Explicitly accepted by the user as the intended trade-off, not a defect. No mitigation attempted (e.g. no self-consistency voting) — that would reintroduce the "matrix the code should run" pattern this change is undoing.
- **[Risk] The LLM under-weighs the removed "HARD STOPS" (e.g. `financial_health=WEAK`) and produces a LONG-BUY that a stricter table would have blocked.** → Mitigated at two levels: (a) the reasoning framework requires the rationale to explicitly name the tension when signals conflict, giving the Critic and any downstream reviewer a concrete claim to check against the data; (b) the Critic's `UNCONVINCING_OVERRIDE`/`FABRICATED_SIGNAL` checks remain in place specifically to catch a conviction that isn't earned by the evidence.
- **[Risk] Below-zone `LONG-BUY` becomes reachable at the same moment the allocator gains a new untested code path.** → Mitigated by shipping the allocator branch in the same change (Decision 2) and adding direct unit tests for it (price-anchored stop/TP, `TradeSetup` invariant) before the gate narrowing is testable end-to-end.
- **[Risk] Reasoning-quality/depth changes are not verifiable by unit tests.** → Accepted; empirical validation (real API calls against conflict cases) is explicitly deferred pending user-confirmed budget, consistent with how the earlier Critic prompt fix was validated in this same session.

## Migration Plan

No data migration or backward-compatibility shim needed — this is a prompt/config/gate-table change with no persisted state format change. Deploy path: merge → run full `pytest tests/ -v` → (optional, budget-gated) live validation runs → standard `/deploy` version bump when ready to ship, same as prior changes this session. Rollback is a plain revert of the changed files (`tasks.yaml`, `agents.yaml`, `action_policy_gate.py`, `portfolio_allocator_tool.py`, `agent_outputs.py`) — no schema/data cleanup required since the schema relaxation (`min_length=0`) is backward-compatible with existing non-empty payloads.
