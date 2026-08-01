## 1. Gate extension (code, fully testable)

- [x] 1.1 Add `filter_critiques()` to `utils/action_policy_gate.py`, reusing
      `parse_directive()`, `resolve_allowed_actions()`, and `ACTION_POLICY_TABLE`
      unchanged; drop the entire `CritiqueItem`-shaped dict when its `instruction`
      requests a disallowed action.
- [x] 1.2 Fix `parse_directive()` to prefer the last `"to <ACTION>"` match over the
      first bare action-word match, so "change action from X to Y" phrasing extracts
      Y (the requested action), not X (the one being replaced), and so a later verb
      use of an action word (e.g. "monitor for price...") isn't mistaken for the
      requested action.
- [x] 1.3 Wire `filter_critiques()` into `ProspectAIFlow._gated_slim_critique()`,
      filtering `co.per_ticker_critiques` the same way `co.revision_directives` is
      already filtered, with matching `logger.warning()` rejection logging.

## 2. Tests

- [x] 2.1 Unit tests in `tests/test_action_policy_gate.py` for `filter_critiques()`:
      the real NVDA `PRICE_IN_ZONE_WAIT` instruction from
      `logs/deterministic-enforcement-v1-9-1/run4_technology_aggressive.log` is
      dropped at `entry_zone_status=CURRENT_ENTRY`; a permitted-action critique
      passes through; a non-action critique passes through; a critique for an
      unknown ticker passes through; kept-item ordering is preserved.
- [x] 2.2 Unit tests for the `parse_directive()` fix: "change action from LONG-BUY to
      WAIT-FOR-ENTRY" extracts `WAIT-FOR-ENTRY`; a trailing "monitor for..." verb
      phrase doesn't get mistaken for the requested action.
- [x] 2.3 Integration regression test in `tests/test_flow_action_policy_gate.py`
      reproducing the full NVDA/CURRENT_ENTRY incident (both `revision_directives`
      and `per_ticker_critiques` carrying the same bad instruction) through
      `ProspectAIFlow._gated_slim_critique()`, asserting both channels are empty
      after filtering.
- [x] 2.4 Add the real NVDA finding/instruction text as a fixture in
      `tests/fixtures_deterministic_enforcement.py` (`CRITIC_OUTPUT_INVERTED_CURRENT_ENTRY_BUG`).
- [x] 2.5 Run the full test suite and confirm no regressions.

## 3. Prompt rewording

- [x] 3.1 Remove "You MUST find at least one issue per position" from
      `config/tasks.yaml`'s `critique_review` STEP 2; replace with wording that
      keeps full-checklist coverage without a quota, consistent with the task's
      existing `approved_positions` mechanism and RULES section.
- [x] 3.2 Reword `PRICE_IN_ZONE_WAIT`/`WAIT_IN_ZONE` checklist entries to state the
      corrective direction explicitly (fix is always → LONG-BUY at CURRENT_ENTRY).
- [x] 3.3 Add one standalone guardrail sentence after the checklist naming this
      specific inversion, since it reproduced identically in two sectors.
- [x] 3.4 Reword `draft_assessment`'s output-field description so it doesn't presume
      weaknesses always exist ("if the draft has no grounded weaknesses, say so
      plainly instead of inventing one").
- [x] 3.5 Confirm no changes made to `config/agents.yaml`'s critic backstory (per
      `reduce-prompt-verbosity`, checklist content must not move back there).

## 4. Verification

- [x] 4.1 Re-ran live: 6 parallel runs, 3 sectors x 2 risk profiles (Energy,
      Technology, Healthcare — the two that reproduced the bug plus one control),
      foreground, logged to `logs/critic-evidence-grounded-review/run{1-6}_*.log`.
      All 6 completed successfully, no exceptions, no `BoundsViolationError`.
- [x] 4.2 Confirmed LONG-BUY survives for positions at `entry_zone_status=CURRENT_ENTRY`
      in all 6 runs. Aggressive now produces more LONG-BUY than conservative in
      every sector (Energy 3 vs 1, Technology 3 vs 2, Healthcare 5 vs 3) —
      previously 0 LONG-BUY in every aggressive run. Grepped all 6 logs for the
      original inverted phrasing ("CURRENT_ENTRY requires/mandates WAIT-FOR-ENTRY"):
      zero matches. Where `ActionPolicyGate` still rejected a critique, manual
      inspection of the raw text confirmed these are legitimate conditional
      critiques (rationale-quality issue with an "or downgrade" fallback clause),
      not the original hallucination — the gate's binary keep/drop behavior on
      such conditional instructions is a known minor side effect (see Open
      Questions), not a recurrence of the bug.
- [x] 4.3 Inversion did not recur after the prompt fix — the escalation path
      (Critic self-check step) is not needed. Noted instead, as a smaller
      follow-up: `filter_critiques()`/`filter_directives()` could be refined to
      strip only the disallowed branch of a conditional "or change action to Y"
      instruction rather than dropping the whole item, to stop discarding valid
      rationale-quality feedback as a side effect. Not required for this change.
