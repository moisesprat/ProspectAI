## Context

`ProspectAIFlow` runs the Critic between `draft_strategy` and `final_strategy`. The Critic reads a compact per-ticker reference table (`_critic_reference_table()`, per the `critic-compact-context` spec) and the draft, and emits `CriticOutput`: `per_ticker_critiques` (structured, severity-tagged `CritiqueItem`s) and `revision_directives` (free-text list). Both are actionable — the Final Strategist's prompt says "You MUST address every CRITICAL and MAJOR critique," referring to `per_ticker_critiques` by severity, independently of whatever `revision_directives` says.

`deterministic-enforcement-v1-9-1` added `utils/action_policy_gate.py`, encoding the `entry_zone_status × risk_profile → allowed actions` table the Draft Strategist already follows, and wired it to filter `revision_directives` before the Final Strategist sees them. It deliberately left `per_ticker_critiques` unfiltered and the Critic's prompt untouched, noting both as follow-up work.

Two live pipeline runs (Energy aggressive, Technology aggressive — see `logs/deterministic-enforcement-v1-9-1/run2_energy_aggressive.log`, `run4_technology_aggressive.log`) reproduced the exact scenario that motivated the gate in the first place: the Critic asserted, verbatim, "aggressive profile requires WAIT-FOR-ENTRY when price is at CURRENT_ENTRY" — the inverse of policy — for a draft position that was correctly `LONG-BUY`. The gate did not stop it, because the identical instruction also flows through `per_ticker_critiques`, which the gate never touched.

Root cause in the prompt: `config/tasks.yaml`'s `critique_review` task states the `PRICE_IN_ZONE_WAIT`/`WAIT_IN_ZONE` condition (flag when the draft has WAIT-FOR-ENTRY at CURRENT_ENTRY) but never states the corrective direction. The same task's STEP 2 says "You MUST find at least one issue per position," which — combined with an already-adversarial goal ("aggressively challenge... find every flaw") — gives the model a structural incentive to invent a violation on a position that has none, and the ambiguous checklist entry is the specific rule it reaches for.

## Goals

- Close the second gate-bypass channel (`per_ticker_critiques`) so the fix is complete, not partial.
- Remove the quota instruction that structurally incentivizes fabrication, without weakening genuine adversarial scrutiny.
- Make the CURRENT_ENTRY/WAIT-FOR-ENTRY checklist entries state their corrective direction so explicitly that inversion requires ignoring the text, not misreading it.
- Keep the fix testable: the gate extension is code, fully unit-testable; the prompt wording is not, so pair it with an explicit empirical re-validation step rather than treating merged code as "done."

## Non-Goals

- Rewriting the full adversarial checklist. Only `PRICE_IN_ZONE_WAIT`/`WAIT_IN_ZONE` and the quota instruction are touched — the other ~15 checklist items have no evidence of similar ambiguity.
- Changing the Critic's runtime model. The bug reproduced on Haiku (via `.env`'s `MODEL` override), not the yaml-configured Sonnet — left as a user decision, not silently changed.
- Constraining `CritiqueItem.issue_type` to an enum. It stays a free `str`; tightening it doesn't protect against this specific bug and adds unrelated risk.
- Re-opening any part of `deterministic-enforcement-v1-9-1`'s own scope (allocator re-invocation, bounds validator, sentiment sentinel, ETF filter, Serper retry).

## Decisions

### 1. Extend the existing gate rather than build a new mechanism

**Decision**: add `filter_critiques()` to `utils/action_policy_gate.py`, reusing `parse_directive()`, `resolve_allowed_actions()`, and `ACTION_POLICY_TABLE` unchanged. `CritiqueItem.instruction` uses the identical `"[TICKER]: [change] because [reason]"` format the prompt already specifies for `revision_directives` (STEP 4's format example applies to both), so the same regex-based parser applies without modification to the parsing logic itself.

**Alternative considered**: give `CritiqueItem` a structured `requested_action: Optional[Literal[...]]` field the Critic populates directly, instead of parsing free text. Rejected for this change — it's a schema change touching the Critic's output contract, larger blast radius than the bug requires, and doesn't fit `task-prompt-economy`'s preference for compact schemas; the existing free-text parsing approach is already proven (via `filter_directives()`) and this change's job is to close the second channel with the same mechanism, not redesign the mechanism.

**Consequence**: dropping is all-or-nothing per `CritiqueItem` — when an item's instruction is invalid, the whole item (finding + instruction) is removed, matching how `filter_directives()` already handles a rejected directive. A finding whose corrective instruction is wrong is not treated as separately salvageable informational content; keeping just the `finding` text without a valid instruction would leave the Final Strategist a CRITICAL-severity item with no actionable resolution, which is worse than removing it.

### 2. Fix `parse_directive()`'s action-extraction bug, discovered while writing the regression test

**Decision**: while building the fixture from the real NVDA log text, `parse_directive()` failed to extract the correct requested action. Two compounding bugs: (a) `re.search()` returns the *first* match, but directives are phrased "change action from LONG-BUY to WAIT-FOR-ENTRY," so the first match is the action being replaced; (b) a bare scan for any of the four action words also matches "monitor" used as an ordinary verb later in the same sentence ("...re-enter on pullback; monitor for price to exit zone"), which isn't the requested action either. Fixed by preferring the last `"to <ACTION>"` match (the phrasing the prompt's own STEP 4 example uses), falling back to the last bare action-word match only when no `"to <ACTION>"` pattern exists.

**Alternative considered**: leave `parse_directive()` alone and require the Critic to phrase instructions differently. Rejected — the prompt already produces the "to <ACTION>" phrasing correctly today; the parser was the thing not handling real output correctly, confirmed by testing against the actual log text rather than a synthetic example.

**Consequence**: this fix applies to `filter_directives()` too (both functions share `parse_directive()`), which is a correctness improvement for the already-shipped `revision_directives` filtering, not just the new `per_ticker_critiques` path — existing directive fixtures/tests continue to pass because they only ever contained one action word each, so the bug was latent until a real two-action-word directive was tested.

### 3. Remove the quota instruction instead of softening it

**Decision**: delete "You MUST find at least one issue per position" from STEP 2 entirely, rather than qualifying it (e.g. "...unless the position is genuinely clean"). The task's own RULES section already says the correct thing ("If a position is fully compliant, record it in approved_positions... Do not invent minor issues to fill a quota") — STEP 2's quota line contradicts RULES outright, so removing it resolves an internal inconsistency rather than introducing new guidance.

**Alternative considered**: keep a weaker version of the quota instruction to preserve thoroughness (e.g. "check every ticker against every checklist item"). Adopted in spirit, not as a quota: the replacement wording instructs checking every ticker against the full checklist, but frames a zero-finding result as a valid, complete outcome, matching the existing `approved_positions` field's purpose.

### 4. State the corrective direction inline plus one standalone guardrail sentence

**Decision**: reword the two checklist entries to name the fix direction explicitly, and add one short standalone sentence after the checklist (not per-entry) calling out this specific inversion by name, since it reproduced identically across two sectors — strong evidence it's a specific attractor for the model, not generic ambiguity worth handling as generic prose only.

**Alternative considered**: rely solely on the reworded checklist entries without the extra guardrail sentence, to stay minimal and respect `task-prompt-economy`'s token-cost discipline. Rejected — the checklist entries are two lines out of ~20 checklist lines in a token-optimized prompt already under pressure; a single reinforcing sentence is cheap relative to the cost of the bug recurring, and this is a targeted, evidence-driven exception, not a general loosening of the economy discipline.

## Risks / Trade-offs

- **[Risk]** Prompt wording changes cannot be unit-tested against a live LLM — a passing test suite does not prove the hallucination is fixed. **Mitigation**: explicit empirical re-validation step (re-run Energy aggressive and Technology aggressive, the exact two sectors that reproduced the bug) is called out as a required, separate verification step in the proposal and tasks, not assumed to follow automatically from code being merged. Deferred until the user confirms API budget is available (they are currently at their monthly spend limit).
- **[Risk]** Dropping a `CritiqueItem` entirely when its instruction is invalid discards the `finding` text too, even though the underlying observation (e.g. "NVDA is at CURRENT_ENTRY") was factually accurate — only the corrective instruction was inverted. **Mitigation**: accepted for this change, consistent with how `revision_directives` already work; if a future incident shows this loses valuable diagnostic information, that's a narrower follow-up (e.g., keep the finding, strip only the instruction) rather than a reason to block this fix.
- **[Risk]** The `parse_directive()` fix changes behavior for any directive containing multiple action words, which could affect directives already in flight in ways not covered by existing fixtures. **Mitigation**: full existing test suite re-run after the fix (all prior tests passed unchanged, since they only ever used single-action-word directives) plus new tests specifically targeting the two-action-word "from X to Y" phrasing pattern.

## Migration Plan

1. Land `filter_critiques()` and the `parse_directive()` fix in `utils/action_policy_gate.py` with unit tests, independently testable against the real NVDA fixture extracted from the production log.
2. Wire `filter_critiques()` into `ProspectAIFlow._gated_slim_critique()`; add the integration regression test reproducing the full incident end-to-end.
3. Reword `config/tasks.yaml`'s `critique_review` task (quota removal, corrective-direction wording, guardrail sentence).
4. Run the full test suite.
5. When API budget allows: re-run `python3 main.py --sector Energy --risk-profile aggressive` and `python3 main.py --sector Technology --risk-profile aggressive`, log to `logs/critic-evidence-grounded-review/`, and confirm LONG-BUY survives for CURRENT_ENTRY positions in both.
- **Rollback**: both the gate extension and the prompt wording are independently revertible; the gate extension is pure addition (new function, new call site) with no schema changes, so reverting either half doesn't require touching the other.

## Open Questions

- Should `filter_critiques()`'s rejections be surfaced anywhere beyond `logger.warning()` (e.g. `execution_metrics`) for operator visibility, matching the same open question already noted for `filter_directives()` in `deterministic-enforcement-v1-9-1`? Not required for this change to close.
- If empirical re-validation (step 5) still shows occasional inversion even after the prompt fix, the next escalation would be a stronger structural change (e.g., a Critic self-check step restating the ground-truth rule before asserting a violation) — not designed here, since it's speculative until the reworded prompt is actually tested against a live model.
