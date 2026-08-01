## ADDED Requirements

### Requirement: Final output is re-priced by the allocator, not trusted from the LLM
Before `run_analysis()` returns a result, the Flow SHALL invoke `allocate_portfolio`
against the Final Strategist's decided actions and SHALL overwrite `allocation_pct`,
`trade_setup`, `scaled_entry_setups`, `deployed_pct`, `reserved_pct`, `cash_reserve_pct`,
and `total_allocated_pct` on the final output with the tool's result. This SHALL happen
unconditionally — including when no position's action differs from the draft — and SHALL
NOT depend on the LLM choosing to invoke the tool itself.

#### Scenario: Final Strategist changes an action without calling the allocator
- **WHEN** the Final Strategist output changes a position's action from `WAIT-FOR-ENTRY` to `LONG-BUY` relative to the draft, and the Final Strategist's raw output contains hand-written `allocation_pct` and `trade_setup` values rather than a tool-computed result
- **THEN** the Flow overwrites those fields with the result of its own `allocate_portfolio` call before returning the result

#### Scenario: No actions changed between draft and final
- **WHEN** every position's action in the Final Strategist output is identical to the draft
- **THEN** the Flow still invokes `allocate_portfolio` and the returned numeric fields are the tool's output, not values copied from the draft or final LLM text

### Requirement: Final output is validated against deterministic bounds before publication
The Flow SHALL run `PortfolioBoundsValidator` against the final output before returning it
from `run_analysis()`. The validator SHALL check, per `risk_profile`:
- Each position's `allocation_pct` does not exceed `PROFILE_BOUNDS[risk_profile].max_alloc_pct`.
- For LONG-BUY and WAIT-FOR-ENTRY positions, the stop distance from `entry_zone_low` is
  within the profile's `stop_multiplier` tolerance and R/R is at least the profile's
  `rr_ratio`.
- The invariant `stop_loss < entry_zone_low ≤ entry_zone_high < take_profit` holds for
  every LONG-BUY and WAIT-FOR-ENTRY `trade_setup`.
- `entry_zone_high − entry_zone_low` is at least the minimum entry-zone width.
- `deployed_pct + reserved_pct + cash_reserve_pct` equals `100 ± 0.5`.

#### Scenario: Position exceeds the per-profile allocation cap
- **WHEN** `risk_profile=conservative` and a position has `allocation_pct=25.0`
- **THEN** `PortfolioBoundsValidator` reports a violation for that position (cap 15.0 exceeded)

#### Scenario: Stop distance exceeds the profile's cap
- **WHEN** `risk_profile=conservative` and a LONG-BUY position's `stop_loss` is 5.4% below `entry_zone_low`
- **THEN** `PortfolioBoundsValidator` reports a violation (conservative cap is 3%)

#### Scenario: Trade setup invariant is violated
- **WHEN** a LONG-BUY position's `trade_setup` has `entry_zone_low == entry_zone_high` (zero-width zone)
- **THEN** `PortfolioBoundsValidator` reports a violation for minimum entry-zone width

#### Scenario: Bucket sum does not equal 100
- **WHEN** `deployed_pct + reserved_pct + cash_reserve_pct` sums to 97.0
- **THEN** `PortfolioBoundsValidator` reports a bucket-sum violation

### Requirement: One repair attempt, then hard fail-closed
On the first bounds-validation failure, the Flow SHALL re-invoke `allocate_portfolio` once
more against the same decided actions and re-validate the result. If the second validation
also fails, the Flow SHALL raise a structured `BoundsViolationError` containing the list of
violations, and `run_analysis()` SHALL NOT return a result to the caller.

#### Scenario: Violation is resolved by re-invoking the allocator
- **WHEN** the first bounds check fails because the Final Strategist's hand-written numbers
  violated the cap, and a fresh `allocate_portfolio` call for the same actions produces
  compliant numbers
- **THEN** the Flow returns the result of the second, compliant `allocate_portfolio` call

#### Scenario: Violation persists after re-invocation
- **WHEN** re-invoking `allocate_portfolio` still produces a result that fails
  `PortfolioBoundsValidator`
- **THEN** the Flow raises `BoundsViolationError` with the violation list and does not
  return a result

#### Scenario: Replaying a previously published bad output through the validator
- **WHEN** the previously published Energy-sector output (25% conservative position,
  5.0–5.4% stops) is passed directly to `PortfolioBoundsValidator`
- **THEN** it raises `BoundsViolationError` listing the allocation-cap and stop-distance
  violations
