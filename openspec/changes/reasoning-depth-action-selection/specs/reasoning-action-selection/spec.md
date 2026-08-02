## REMOVED Requirements

### Requirement: STEP 3 branches on entry_zone_status, not raw numeric thresholds
**Reason**: This requirement encoded the premise that STEP 3 is a rule-following procedure at all. It is superseded by "Draft Strategist synthesizes conflicting signals into a conviction-based action" below, which still forbids re-deriving raw numeric arithmetic (that constraint moves into the new requirement) but no longer frames `entry_zone_status` as a decision-table pivot.
**Migration**: See "Draft Strategist synthesizes conflicting signals into a conviction-based action" and "The two surviving hard invariants."

### Requirement: CURRENT_ENTRY defaults to LONG-BUY for both profiles
**Reason**: `financial_health=WEAK` no longer overrides the action pre-reasoning; it is now a factor the LLM weighs and must acknowledge in the rationale, not a hard override. Only the `WAIT-FOR-ENTRY` exclusion at `CURRENT_ENTRY` survives as a hard rule (semantic contradiction, not risk policy).
**Migration**: See "The two surviving hard invariants." LONG-BUY vs MONITOR vs AVOID at `CURRENT_ENTRY` is now open LLM judgment.

### Requirement: PULLBACK_ENTRY action differs materially between conservative and aggressive
**Reason**: The numeric thresholds (`momentum_score≥7`, `momentum_score<5`, etc.) and the profile-specific default actions encoded exactly the decision table being eliminated. `PULLBACK_ENTRY` already permitted all 4 actions in `ActionPolicyGate` for both profiles — the over-prescription lived entirely in this prompt requirement, not in code.
**Migration**: See "Draft Strategist synthesizes conflicting signals into a conviction-based action." Risk profile is now a general disposition (conservative weighs capital preservation and requires broader signal alignment; aggressive weighs opportunity capture and may act on strong single-dimension conviction if named and defended), not a set of branch conditions.

### Requirement: BELOW_ZONE treated as MONITOR or AVOID for both profiles
**Reason**: Excluding `LONG-BUY` at `BELOW_ZONE` was identified as a risk-policy preference dressed up as a rule ("don't buy into a potential breakdown" is a defensible but debatable stance, not a logical necessity — a real analyst might buy below support if fundamentals justify it). `WAIT-FOR-ENTRY` stays excluded at `BELOW_ZONE` because its "wait for price to fall into the zone" semantics don't apply below the zone; that part is a genuine invariant, not risk policy, and survives.
**Migration**: See `action-policy-gate`'s modified `BELOW_ZONE` row (permits `LONG-BUY`, `MONITOR`, `AVOID`; still excludes `WAIT-FOR-ENTRY`) and `PortfolioAllocatorTool`'s new below-zone price-anchored trade-setup branch.

### Requirement: Hard stops are preserved regardless of profile
**Reason**: Of the four listed hard stops, only `price_data_error` is a genuine mechanical invariant (no `current_price` means no valid `TradeSetup` can be constructed). The other three (`financial_health=WEAK`, bearish-signal-forces-WAIT at `PULLBACK_ENTRY`, `composite_score<55`-forces-MONITOR) are risk-policy preferences the user explicitly wants opened to LLM judgment — this is the literal example the user gave when requesting this change (strong technicals + weak fundamentals should be the LLM's call, not a pre-set block).
**Migration**: See "The two surviving hard invariants" (`price_data_error` retained) and "Draft Strategist synthesizes conflicting signals into a conviction-based action" (the other three become weighed factors).

## ADDED Requirements

### Requirement: Draft Strategist synthesizes conflicting signals into a conviction-based action
The Draft Strategist's STEP 3 SHALL present technical (`entry_zone_status`, `overall_signal`, `momentum_score`, `regime`), fundamental (`financial_health`, `growth_outlook`, `valuation_grade`), sentiment (`average_sentiment` or explicit unavailability), and `composite_score` as inputs to weigh holistically, not as branches of a decision table. When these inputs conflict (e.g. bullish technicals with weak fundamentals), the task description SHALL state that there is no pre-set resolution — the LLM SHALL reach a defensible conclusion through its own reasoning, in the way a market analyst would, rather than defaulting to a fixed rule. The LLM MUST NOT recalculate raw numeric arithmetic already encapsulated in the provided signals (e.g. RSI-to-price-gap percentages).

#### Scenario: Conflicting technical and fundamental signals require explicit reasoning, not a table lookup
- **WHEN** a stock has `overall_signal=BULLISH`, `momentum_score=7`, and `financial_health=WEAK`
- **THEN** the task description does not specify a fixed resulting action for this combination — the LLM determines the action and is required to name the conflict explicitly in the rationale

#### Scenario: LLM uses entry_zone_status as one input among several, not a table pivot
- **WHEN** the technical tool returns `entry_zone_status=PULLBACK_ENTRY` for a stock
- **THEN** the LLM treats it as one of several signals to weigh, not as a switch that alone determines a profile-specific default action

### Requirement: Rationale names tensions between conflicting signals explicitly
When technical, fundamental, and sentiment signals point in different directions for a position, the LLM's rationale SHALL explicitly name the tension (which signals conflict) and explain why the chosen action is justified despite it. A rationale that omits an evident conflict is incomplete.

#### Scenario: Rationale names an omitted conflict as insufficient
- **WHEN** a position has `overall_signal=BULLISH` and `financial_health=WEAK`, and the LLM assigns `LONG-BUY`
- **THEN** the rationale explicitly addresses the weak-fundamentals factor and states why the technical conviction outweighs it, rather than citing only the bullish technicals

### Requirement: The two surviving hard invariants
Exactly two conditions SHALL remain outside LLM judgment, because they are logical/mechanical facts rather than risk-policy preferences:
- `entry_zone_status=CURRENT_ENTRY` SHALL NOT be paired with `action=WAIT-FOR-ENTRY` — the phrase "wait for entry" is self-contradictory once price is already in the actionable zone.
- `price_data_error` present (no `current_price`) SHALL cap the action at `MONITOR` or `AVOID` — a `TradeSetup` cannot be mechanically constructed without a current price (`entry_zone_low/high`, `stop_loss`, `take_profit` are all required positive fields).

Every other condition previously treated as a hard stop is now a factor the LLM weighs, per "Draft Strategist synthesizes conflicting signals into a conviction-based action."

#### Scenario: CURRENT_ENTRY excludes WAIT-FOR-ENTRY regardless of any other factor
- **WHEN** `entry_zone_status=CURRENT_ENTRY` for a position, regardless of `financial_health`, `overall_signal`, or `risk_profile`
- **THEN** the LLM SHALL NOT assign `action=WAIT-FOR-ENTRY`, and `ActionPolicyGate` enforces this as a backstop if it does

#### Scenario: Price data error caps the action regardless of other signals
- **WHEN** a stock has `price_data_error` set (current_price is null)
- **THEN** action SHALL be `MONITOR` or `AVOID` regardless of other signals or profile

### Requirement: SCALED-ENTRY is not a valid action
The valid action set SHALL be exactly: `LONG-BUY`, `WAIT-FOR-ENTRY`, `MONITOR`, `AVOID`.
`SCALED-ENTRY` SHALL NOT be produced by the LLM and SHALL be rejected by schema validation. This requirement is unaffected by the reasoning-depth changes in this capability — the closed action set is enforced independently of how the action is chosen.

#### Scenario: Schema rejects SCALED-ENTRY action
- **WHEN** the LLM output contains `"action": "SCALED-ENTRY"` in any position
- **THEN** Pydantic validation SHALL raise a validation error
