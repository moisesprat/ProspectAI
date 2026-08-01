## Why

Deterministic bounds already exist in `PortfolioAllocatorTool` and in the action-policy
guidance given to the LLM, but nothing in the pipeline *enforces* that the published
output actually respects them. Two production runs show the gap concretely:

- The Final Strategist changed actions without re-invoking `allocate_portfolio`, hand-writing
  allocation/bucket numbers and a fabricated entry zone.
- The Critic issued a revision directive that contradicted the action-policy table
  (WAIT-FOR-ENTRY at `entry_zone_status=CURRENT_ENTRY`), and the Final Strategist obeyed it.
- The published Energy-sector output violated profile bounds outright: a 25% position under
  a 15% conservative cap, stops of 5.0–5.4% against a 3% cap, and round-number setups that
  were clearly typed rather than computed.
- With Reddit down and Serper returning 400s (retried 3× before giving up), `average_sentiment`
  was left at `0.0` and treated downstream as a real neutral signal instead of "no data."
- `reserved_pct` has been unattributed to any WAIT-FOR-ENTRY position, or has contradicted
  the prose, in different runs.
- A sector benchmark ETF (XLE) was recommended as an investable position.
- The v1.9.0 TRENDING-regime anchoring produced a zero-width entry zone.

None of these are reasoning failures the LLM should be trusted to self-correct — they are
exactly the class of bound that a deterministic tool already computes correctly. The fix is
to stop asking the LLM to preserve tool output faithfully and instead make the Flow itself
the enforcement point, with a hard fail-closed validator before anything is published.

## What Changes

- **BREAKING**: `ProspectAIFlow` calls `allocate_portfolio` programmatically after the Final
  Strategist phase whenever any position's action differs from the draft, overwriting all
  numeric allocation/trade-setup fields on the final output. The Final Strategist prompt's
  "CASE B" (LLM decides whether to re-invoke the allocator) is removed — the LLM no longer
  makes that call.
- Add `PortfolioBoundsValidator`, run by the Flow against the final JSON before it is
  returned: per-position allocation cap, stop-distance cap, minimum R/R, bucket sum
  (100 ± 0.5), the LONG-BUY invariant `stop < entry_low ≤ entry_high < take_profit`, and a
  minimum entry-zone width. On violation the Flow re-invokes the allocator once; if the
  result still fails, the Flow raises a structured `BoundsViolationError` — non-compliant
  output is never published.
- Add `ActionPolicyGate`: the existing entry_zone_status × risk_profile → allowed-actions
  table (already documented informally in `config/tasks.yaml`) becomes data the Flow
  evaluates deterministically. Critic `revision_directives` that target an action outside
  the allowed set for a position are dropped and logged before reaching the Final
  Strategist. The Critic's own prompt is unchanged — only the Flow's handling of its output
  changes.
- Add a sentiment-availability sentinel: `MarketAnalysisOutput.sentiment_available: bool`.
  When every sentiment source fails, `average_sentiment` is set to `null` (never `0.0`).
  `CompositeScoreTool` renormalizes its weights over the technical + fundamental components
  when sentiment is unavailable. The Critic is instructed that sentiment-based findings are
  out of scope when `sentiment_available=false`. The report surfaces "sentiment: no data"
  instead of a fabricated neutral score.
- Serper tool: 4xx responses fail fast (no retry, response body logged); only 429/5xx are
  retried (max 2 attempts, backoff). The current 400 is root-caused as part of this work.
- `allocate_portfolio` emits `reserved_allocations: [{ticker, pct}]` alongside the existing
  fields, with new invariants: `reserved_pct` equals the sum of `reserved_allocations`,
  every WAIT-FOR-ENTRY position has a corresponding entry with `pct > 0`, and `deployed_pct`
  equals the sum of LONG-BUY `allocation_pct`. The Critic's `WAIT_ENTRY_ZERO_ALLOC` checklist
  item is reworded to match this explicit-attribution semantics.
- The candidate universe excludes ETFs and the active sector's benchmark ticker, including
  in the Reddit/Serper failure-fallback list.

Out of scope for this change: prose-vs-schema numeric consistency checking (planned for
v1.9.2), aggressive-profile conviction recalibration (to be re-measured only after this
lands), `UniverseScreenerTool` (v1.10.0), and model routing configuration.

## Capabilities

### New Capabilities
- `portfolio-bounds-enforcement`: Flow-level deterministic validation of the final published
  output against per-profile allocation, stop-distance, R/R, bucket-sum, and entry-zone
  invariants, with re-invocation and hard fail-closed behavior on violation.
- `action-policy-gate`: deterministic filtering of Critic revision directives against the
  entry_zone_status × risk_profile allowed-actions table before they reach the Final
  Strategist.
- `sentiment-availability-sentinel`: explicit `sentiment_available` signal replacing the
  implicit "0.0 = neutral" convention, propagated through composite scoring, critique, and
  reporting.

### Modified Capabilities
- `portfolio-allocator-allocation`: the Flow — not the LLM — decides when `allocate_portfolio`
  is invoked for the final output; its result is authoritative and overwrites any LLM-written
  numeric fields.
- `portfolio-allocator-capital-buckets`: adds `reserved_allocations` and the explicit
  per-ticker attribution invariants for `reserved_pct` / `deployed_pct`.
- `reasoning-critic-validation`: the `WAIT_ENTRY_ZERO_ALLOC` checklist item is reworded to
  match the new explicit-attribution bucket semantics; Critic sentiment-based findings are
  scoped out when `sentiment_available=false`.

## Impact

- **Code**: `prospect_ai_flow.py` (final-phase orchestration, new validator + gate
  invocation), `utils/portfolio_allocator_tool.py` (`reserved_allocations` output), new
  `utils/portfolio_bounds_validator.py`, new `utils/action_policy_gate.py`,
  `utils/composite_score_tool.py` (sentiment renormalization), `schemas/agent_outputs.py`
  (`sentiment_available` field), `config/tasks.yaml` (remove Final Strategist CASE B, reword
  `WAIT_ENTRY_ZERO_ALLOC`), Serper/Reddit fallback candidate filtering, Serper retry logic.
- **Tests**: new regression fixtures built from the two failing runs described above; a
  property test asserting `allocate_portfolio` output always passes
  `PortfolioBoundsValidator`; a fixture replaying the published Energy-sector output through
  the validator to confirm it raises `BoundsViolationError`.
- **Versioning**: patch release `v1.9.1` of the `prospectai` package only — no changes to
  `prospectai-backend` or `prospectai-web`, and no coordinated redeploy is required by this
  change itself (a future PyPI publish + Modal redeploy is still needed to ship it, per the
  standard release process).
