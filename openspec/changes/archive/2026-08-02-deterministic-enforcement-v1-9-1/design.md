## Context

`ProspectAIFlow` (`prospect_ai_flow.py`) runs six phases as `crewai.Flow` steps chained
with `@listen`. Every phase output is validated against a Pydantic schema
(`schemas/agent_outputs.py`) via `_extract_pydantic()`, but schema validation only checks
*shape* (types, enum membership, required fields) — it has no notion of the numeric
invariants that `PortfolioAllocatorTool` already enforces internally (per-position cap,
stop-distance, R/R, bucket sums). Those invariants exist only inside the tool; nothing
forces the Final Strategist (`final_strategy`, line ~492) to actually call the tool, or to
copy its output verbatim rather than paraphrasing numbers.

Today the contract with the LLM is entirely prompt-based: `config/tasks.yaml`'s
`final_strategy` task tells the model "CASE A: if actions are unchanged, keep the draft's
numbers; CASE B: if you changed an action, re-call `allocate_portfolio`." Two production
runs show this contract silently breaks — the model can (and did) skip CASE B and hand-write
numbers instead. Similarly, `critique_review`'s `revision_directives: List[str]` (free text,
`schemas/agent_outputs.py:307`) is consumed by the Final Strategist with no check that a
directive's requested action is even legal for that position's `entry_zone_status` /
`risk_profile` combination — the action-policy table in `tasks.yaml:265-291` is documentation
for the LLM's own reasoning, not something any code evaluates.

The other failure modes (sentiment `0.0` after upstream failure, ETF-as-position,
zero-width entry zone) share the same root pattern: a deterministic fact is known
somewhere in the pipeline, but it is never asserted against the artifact that actually
gets published.

## Goals / Non-Goals

**Goals:**
- Make `allocate_portfolio` invocation for the final output a Flow-level decision, not an
  LLM-followed instruction — remove the class of bug where the model skips or
  mis-transcribes the tool call.
- Add one authoritative, fail-closed gate (`PortfolioBoundsValidator`) between "LLM/tool
  produced a candidate final output" and "this is what `run_analysis()` returns," so no
  future prompt regression can leak a bounds-violating result to users.
- Make the entry_zone_status × risk_profile action-policy table an enforceable data
  structure (`ActionPolicyGate`), not prose duplicated across three task prompts.
- Distinguish "sentiment measured as neutral" from "sentiment could not be measured" at the
  schema level, and propagate that distinction through scoring, critique, and the report.
- Fail Serper fast on non-retryable errors so failures surface as `sentiment_available=false`
  quickly instead of burning 3 retries on a 400.

**Non-Goals:**
- Re-tuning the aggressive-profile action thresholds (`composite_score<55`,
  `momentum_score≥5`) — that recalibration only makes sense after this change proves the
  numeric layer is trustworthy, and is tracked separately.
- General prose-vs-schema consistency checking (rationale text asserting a number that
  disagrees with the schema field) — narrower and deferred to v1.9.2.
- Building `UniverseScreenerTool` or any general-purpose ticker-eligibility service — ETF /
  benchmark exclusion here is a narrow filter on the existing candidate list, not a new
  screening subsystem.
- Any change to `prospectai-backend` or `prospectai-web` — this is a `prospectai` patch
  release; `run_analysis()`'s return shape is unchanged (see Migration Plan).

## Decisions

### 1. The Flow re-invokes `allocate_portfolio`, not the LLM

**Decision**: After `final_strategy` produces its `InvestorStrategicOutput`, the Flow diffs
`final_output.positions[].action` against `draft_output.positions[].action`. If any action
differs, the Flow itself builds the `allocate_portfolio` payload (ticker, action,
composite_score, entry_zone_low/high, current_price — the same fields the tool already
requires) and calls the tool directly, overwriting `allocation_pct`, `trade_setup`,
`scaled_entry_setups`, `deployed_pct`, `reserved_pct`, `cash_reserve_pct`,
`total_allocated_pct` on the final output. If no action changed, the Flow still re-invokes
the allocator (see Decision 2's fail-closed rationale) rather than trusting the LLM's
verbatim-copy of the draft numbers.

**Alternative considered**: Keep CASE A/CASE B in the prompt but add a post-hoc check that
flags when the model should have called the tool and didn't, asking the Critic to catch it.
Rejected — this is exactly the pattern that already failed twice; a probabilistic reviewer
is not a substitute for a deterministic recomputation when the computation is cheap and
the tool is idempotent given the same actions.

**Consequence**: the Final Strategist prompt's CASE B branch is deleted from
`config/tasks.yaml`. The model's job in `final_strategy` narrows to: decide whether to
accept, revise, or defend against each critic directive, and produce the resulting
`action` and `rationale` per position. It no longer touches allocation math at all — even
in the "nothing changed" case, since the Flow always recomputes.

### 2. `PortfolioBoundsValidator` is fail-closed with exactly one repair attempt

**Decision**: `PortfolioBoundsValidator.validate(final_output, risk_profile)` checks, per
position: allocation ≤ `PROFILE_BOUNDS[risk_profile].max_alloc_pct`; for LONG-BUY/
WAIT-FOR-ENTRY, stop distance from `entry_zone_low` within the profile's `stop_multiplier`
tolerance and R/R ≥ the profile's `rr_ratio`; the trade-setup invariant
`stop_loss < entry_zone_low ≤ entry_zone_high < take_profit`; and a minimum entry-zone
width (reuse the existing `min_width` concept from `technical_interpretation_tool.py`, applied
here as a floor rather than recomputed). Across the whole output: bucket sum
`deployed_pct + reserved_pct + cash_reserve_pct == 100 ± 0.5`.

On the first failure, the Flow performs exactly one more `allocate_portfolio` invocation
(this handles the case where the violation came from stale/hand-written numbers that a
correct tool call would fix) and re-validates. If it still fails, the Flow raises
`BoundsViolationError(violations: list[dict])` and `run_analysis()` surfaces it as a
failed run rather than returning a result — see Migration Plan for exactly how this
propagates to `main.py` / the backend's SSE stream.

**Alternative considered**: clamp violating values to the nearest legal bound and publish
anyway (auto-correct rather than fail-closed). Rejected per the explicit instruction that
non-compliant output must never be published — a silently clamped number is still a number
the user didn't get an honest account of (e.g., a fabricated entry zone would clamp into
*some* valid-looking zone, which is worse than a visible failure).

**Alternative considered**: retry the entire `final_strategy` LLM phase on violation
instead of only re-invoking the deterministic allocator. Rejected for this change — the
violations found so far are traceable to the allocator not being (correctly) called, not
to the LLM's action decisions being wrong; re-running the expensive LLM phase for a
tool-invocation gap is unnecessary cost. If future evidence shows action-level violations
survive an allocator re-invocation, that would justify revisiting this.

### 3. `ActionPolicyGate` filters directives before they reach the Final Strategist, not after

**Decision**: encode the `entry_zone_status × risk_profile → allowed actions` table from
`config/tasks.yaml:265-291` as a plain Python data structure
(`utils/action_policy_gate.py`). Between `critique_review` and `final_strategy`, the Flow
resolves each `revision_directives` entry to the position it targets (matching on ticker,
same approach as `_critic_reference_table()` already uses for context slimming) and its
current `entry_zone_status`/`risk_profile`. If the directive's requested action is not in
the allowed set, the Flow drops it from the context passed to `final_strategy` and logs it
(ticker, requested action, why it was rejected) — the Final Strategist never sees it.

**Alternative considered**: leave directive validation to the Critic's own prompt (i.e.,
instruct the Critic more strongly not to violate the policy table). Rejected — this is the
exact failure that already happened once; a second free-text instruction on top of the
first one that failed is not a fix. The policy table is finite and already exists as
structured knowledge (`tasks.yaml`'s table); evaluating it in code is strictly more
reliable than asking the model to re-derive it correctly every run.

**Consequence**: the Critic's own prompt is explicitly left unchanged per the proposal
scope — the gate is a Flow-side filter on the Critic's output, not a rewrite of how the
Critic reasons.

### 4. Sentiment unavailability is a first-class schema value, not an implicit convention

**Decision**: add `MarketAnalysisOutput.sentiment_available: bool = True`. When
`RedditSentimentTool` and the Serper fallback both fail, the Market Analyst sets
`sentiment_available=False` and `average_sentiment=null` for affected candidates (schema
change: `average_sentiment: float | None`). `CompositeScoreTool` checks this flag per stock;
when unavailable, it renormalizes the composite formula over technical + fundamental only
(scaling `technical_component` and `fundamental_component` weights so the max possible score
is still 100, rather than silently capping at 70). The Critic prompt gets one added
instruction: sentiment-based findings are out of scope when `sentiment_available=false`.
The final report renders "sentiment: no data" for those tickers instead of a
sentiment-derived phrase.

**Alternative considered**: keep `average_sentiment: float` and use a sentinel value like
`-2.0` (outside the valid `[-1,1]` range) to signal unavailability. Rejected — a sentinel
smuggled through a field whose schema says `ge=-1.0, le=1.0` is exactly the kind of implicit
convention that caused the original bug (`0.0` silently meaning "neutral" instead of "no
data"); an explicit boolean is self-documenting and fails loudly if a consumer forgets to
check it (a `None` value is much harder to silently misuse arithmetically than `0.0` is).

### 5. Serper error handling: fail fast on 4xx, retry only 429/5xx

**Decision**: the Serper client distinguishes 4xx (client error — bad request, auth,
quota) from 429 (rate limit) and 5xx (server error). 4xx fails immediately, logs the
response body, and marks the source unavailable. 429/5xx retry up to 2 times with backoff.
This is standard HTTP retry semantics; the current 400 will be root-caused as part of
implementation (likely a malformed query parameter given Serper's API contract) rather than
papered over by more retries.

**Alternative considered**: keep uniform retry-on-any-failure but reduce the count.
Rejected — retrying a 400 can never succeed (the request itself is malformed), so any
retry budget spent there is pure latency with zero chance of success; distinguishing by
status code is both faster and more correct.

### 6. `reserved_allocations` makes bucket attribution explicit and checkable

**Decision**: `PortfolioAllocatorTool` output gains
`reserved_allocations: [{ticker, pct}]` — the same per-ticker breakdown that already exists
internally as `final_allocs` filtered to WAIT-FOR-ENTRY, just surfaced. Two invariants become
mechanically checkable (both by `PortfolioBoundsValidator` and by tests): `reserved_pct ==
sum(p.pct for p in reserved_allocations)`, and every position with `action=WAIT-FOR-ENTRY`
has a corresponding entry with `pct > 0`. The Critic's `WAIT_ENTRY_ZERO_ALLOC` checklist item
is reworded to check against `reserved_allocations` rather than inferring zero-allocation
from the aggregate `reserved_pct` alone (which is what allowed the previous
under-attribution to go unnoticed by the Critic).

**Alternative considered**: leave `reserved_pct` as the only bucket signal and add a
Critic-only cross-check. Rejected for the same reason as Decision 2/3 — the Critic is a
probabilistic reviewer; the fix belongs in the deterministic tool's output contract, with
the Critic check as a secondary line of defense, not the only one.

### 7. ETF/benchmark exclusion at the candidate-universe boundary

**Decision**: candidates are filtered against a small denylist mechanism (sector benchmark
ticker per `SECTOR_TICKERS`-style mapping already used by `RedditSentimentTool`, plus a
generic ETF check) at the single point where candidates enter the pipeline — this applies
identically to the Reddit-derived list and to the Serper/manual fallback list, so the
exclusion cannot be bypassed by whichever source happens to be active that run (this is
precisely how XLE reached a live run: it was in a fallback list that didn't share the
primary list's filtering).

## Risks / Trade-offs

- **[Risk]** A hard fail-closed validator means some runs that previously "succeeded" with
  a bad number now fail outright, which looks like a regression in success rate.
  **Mitigation**: this is the intended behavior change per the proposal ("never publish
  non-compliant output"); the regression fixtures from the two failing runs become
  acceptance tests that the Flow now fails loudly instead of publishing silently, and
  `execution_metrics`/logs should surface `BoundsViolationError` clearly enough for
  triage (see Open Questions on caller-facing shape).
- **[Risk]** Removing the Final Strategist's discretion over allocator invocation could
  strand a case where the model legitimately wants to change *only* the rationale/
  monitoring_triggers without touching actions — the Flow's always-recompute policy
  (Decision 1) is harmless there since identical actions in, identical numbers out, but it
  does spend one extra tool call every run. **Mitigation**: `allocate_portfolio` is a cheap,
  synchronous, deterministic call (no LLM/network involved) — the cost is negligible
  against a multi-minute LLM pipeline.
- **[Risk]** `ActionPolicyGate` dropping a directive silently changes what the Final
  Strategist sees versus what the Critic wrote, which could be confusing when debugging a
  run. **Mitigation**: dropped directives are logged with ticker + rejected action + reason,
  and should be surfaced in `execution_metrics` or run logs (see Open Questions) so this is
  visible in postmortems, not silent.
- **[Risk]** `sentiment_available=False` reduces the composite score's discriminating power
  for affected tickers (only two components instead of three), which could shift which
  stocks clear the `composite_score<55` hard-stop threshold purely due to sentiment being
  down, not due to underlying quality. **Mitigation**: this is strictly more honest than the
  status quo (a fabricated `0.0` doing the same distortion invisibly); the renormalization
  in Decision 4 is designed to keep the 0–100 scale meaningful rather than just dropping 30
  points.
- **[Risk]** `BoundsViolationError` propagating out of `run_analysis()` is a shape change
  callers must handle. **Mitigation**: scoped as in-process only for this patch (see
  Migration Plan) — no `prospectai-backend` change is in scope, so the backend's existing
  exception handling around `ProspectAIFlow().run_analysis()` (`app.py:509,943`) will need
  to catch this specific exception in a *future*, separately-versioned backend change; until
  then a `BoundsViolationError` surfaces as a generic run failure, which is acceptable
  because it is strictly rarer and more actionable than a silently bad result.

## Migration Plan

1. Land the new modules (`utils/portfolio_bounds_validator.py`,
   `utils/action_policy_gate.py`) and schema changes independently, with unit tests, before
   wiring them into `ProspectAIFlow` — each is independently testable against
   hand-constructed fixtures.
2. Wire `PortfolioAllocatorTool` re-invocation and `PortfolioBoundsValidator` into
   `final_strategy`/`run_analysis()` in `prospect_ai_flow.py`. Add the two regression
   fixtures (the two failing runs described in the proposal) as integration tests at this
   point — both must pass (first fixture: allocator now runs even though the LLM skipped
   it; second fixture: the previously-published bounds-violating output is replayed
   directly through `PortfolioBoundsValidator` and asserted to raise
   `BoundsViolationError`).
3. Wire `ActionPolicyGate` between `critique_review` and `final_strategy`.
4. Land the sentiment sentinel end-to-end (schema → `CompositeScoreTool` →
   `MarketAnalystAgent` fallback path → report rendering) and the Serper retry-classification
   fix together, since they touch the same failure path.
5. Land `reserved_allocations` and the reworded `WAIT_ENTRY_ZERO_ALLOC` checklist item.
6. Land ETF/benchmark exclusion on both the primary and fallback candidate paths.
7. Bump `pyproject.toml`/`VERSION.md` to `1.9.1` per the standard `/deploy` flow described in
   `CLAUDE.md`; publish to PyPI. No Modal backend redeploy is required by this change alone
   (return shape of a *successful* `run_analysis()` is unchanged), but the backend should be
   made aware that failures can now surface as `BoundsViolationError` for its own future
   handling.
- **Rollback**: each of the four mechanisms (allocator re-invocation, bounds validator,
  policy gate, sentiment sentinel) is independently revertible — none change the on-disk
  schema in a way that breaks older data (`sentiment_available` defaults to `True`,
  preserving old-record semantics for anything read after the fact).

## Open Questions

- Where should `BoundsViolationError` details (which invariant failed, for which ticker,
  with what numbers) surface for operator triage — `execution_metrics`, a dedicated log
  line, or both? This change assumes "both" but the exact shape is an implementation
  decision, not a spec-level one.
- Should `ActionPolicyGate` rejections and Serper fail-fast events be counted anywhere in
  `ExecutionTracker`/analytics, given `/prospectai-analytics` already tracks run-level
  breakdowns? Proposed as a nice-to-have, not required for this change to close.
- The Serper 400 root cause is unknown until diagnosed during implementation; if it turns
  out to be a persistent account/quota issue rather than a malformed request, the "fail
  fast" behavior is still correct, but the sentiment-unavailability rate in production could
  be materially higher than today (silently masked by retries) — worth flagging to the user
  once real numbers are available, not a design blocker.
