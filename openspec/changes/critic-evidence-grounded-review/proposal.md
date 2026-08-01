## Why

Live validation of the `deterministic-enforcement-v1-9-1` change (8 real pipeline runs) surfaced a production bug, reproduced identically in two different sectors: the Critic invents a rule that is the exact inverse of documented policy ("aggressive profile requires WAIT-FOR-ENTRY when price is at CURRENT_ENTRY," when the real policy is the opposite — CURRENT_ENTRY defaults to LONG-BUY for both profiles), then orders a correct draft position downgraded. The Final Strategist obeys because the bad instruction is tagged `severity=CRITICAL`. Root-caused to an ambiguously-worded checklist entry in `config/tasks.yaml` combined with an explicit quota instruction ("You MUST find at least one issue per position") that structurally incentivizes fabrication, and to `ActionPolicyGate` (built in `deterministic-enforcement-v1-9-1`) filtering only `revision_directives` while leaving the identical bad instruction unfiltered inside `per_ticker_critiques`. `deterministic-enforcement-v1-9-1` explicitly deferred both the prompt wording and this gating gap, so this is its natural follow-up.

## What Changes

- Reword `config/tasks.yaml`'s `critique_review` task: remove the "must find at least one issue per position" quota instruction (it directly contradicts the task's own `approved_positions` mechanism and the agent's backstory); make the `PRICE_IN_ZONE_WAIT`/`WAIT_IN_ZONE` checklist entries state their corrective direction explicitly (fix is always → LONG-BUY at CURRENT_ENTRY, never the reverse); add a short standalone guardrail sentence naming this exact inversion, since it reproduced identically in two sectors.
- Extend `utils/action_policy_gate.py` with `filter_critiques()`, applying the same `entry_zone_status × risk_profile → allowed actions` table to `CriticOutput.per_ticker_critiques[].instruction`, not just `revision_directives`. A `CritiqueItem` whose instruction requests a disallowed action is dropped entirely.
- Fix a real parsing bug found while testing the extension: `parse_directive()` took the *first* action word in a directive, which misparses the common "change action from X to Y" phrasing (it returned X, the action being replaced, not Y, the one requested) and also risked false-matching an action word used as an ordinary verb elsewhere in the sentence (e.g. "monitor for price to exit zone"). Now prefers the last "to \<ACTION\>" match.
- Wire `filter_critiques()` into `ProspectAIFlow._gated_slim_critique()` so both channels are filtered before reaching the Final Strategist, with the same rejection logging as the existing directive filter.

Out of scope: rewriting the full adversarial checklist (only the two confirmed-buggy entries plus the quota instruction are touched); changing the Critic's model (it currently runs on Haiku via env override rather than the yaml-configured Sonnet — left as-is, a user decision, not a bug this change fixes); tightening `CritiqueItem.issue_type` to an enum (stays a free string); anything already covered by `deterministic-enforcement-v1-9-1` (allocator re-invocation, bounds validator, sentiment sentinel, ETF filter, Serper retry).

## Capabilities

### New Capabilities
(none — this change extends two existing capabilities)

### Modified Capabilities
- `action-policy-gate`: adds `filter_critiques()` covering `per_ticker_critiques`, and fixes `parse_directive()` to extract the requested (not replaced) action from "change action from X to Y" phrasing.
- `reasoning-critic-validation`: `WAIT_IN_ZONE`/`PRICE_IN_ZONE_WAIT` findings must state and enforce the correct corrective direction (→ LONG-BUY only); the Critic must not fabricate findings on a fully compliant position merely to satisfy a quota.

## Impact

- **Code**: `config/tasks.yaml` (`critique_review` task wording), `utils/action_policy_gate.py` (`filter_critiques()`, `parse_directive()` fix), `prospect_ai_flow.py` (`_gated_slim_critique()` wiring).
- **Tests**: unit tests for `filter_critiques()` and the `parse_directive()` fix in `tests/test_action_policy_gate.py`; an integration regression test in `tests/test_flow_action_policy_gate.py` reproducing the exact NVDA/CURRENT_ENTRY incident from `logs/deterministic-enforcement-v1-9-1/run4_technology_aggressive.log` through `ProspectAIFlow._gated_slim_critique()`, asserting the bad instruction is dropped from both `revision_directives` and `per_ticker_critiques`.
- **Verification**: prompt wording cannot be unit-tested against a live LLM. Empirical re-validation (re-running Energy aggressive and Technology aggressive, the two sectors that reproduced the bug, and confirming LONG-BUY survives at CURRENT_ENTRY) requires live API spend and is deferred until the user confirms budget is available — not run automatically as part of this change.
- **Versioning**: depends on `deterministic-enforcement-v1-9-1` landing first (this change extends code introduced there); no independent version bump implied by this change alone — coordinate with that change's release.
