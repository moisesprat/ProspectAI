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

## 4. Verification (deferred — requires live API spend)

- [ ] 4.1 When API budget allows: re-run `python3 main.py --sector Energy
      --risk-profile aggressive` and `python3 main.py --sector Technology
      --risk-profile aggressive` (the two sectors that reproduced the bug),
      foreground, logged to `logs/critic-evidence-grounded-review/`.
- [ ] 4.2 Confirm LONG-BUY survives for positions at `entry_zone_status=CURRENT_ENTRY`
      in both re-runs (i.e. the Critic no longer inverts the rule).
- [ ] 4.3 If inversion still occurs after the prompt fix, do not attempt a further
      prompt patch reactively — escalate to the stronger structural option noted in
      design.md's Open Questions (a Critic self-check step) as a separate follow-up.
