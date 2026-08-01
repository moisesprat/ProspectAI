## ADDED Requirements

### Requirement: WAIT_IN_ZONE / PRICE_IN_ZONE_WAIT corrective direction is fixed and enforced
The Critic's `WAIT_IN_ZONE`/`PRICE_IN_ZONE_WAIT` findings SHALL only ever request changing
an action TO `LONG-BUY` at `entry_zone_status=CURRENT_ENTRY`, never FROM `LONG-BUY` TO
`WAIT-FOR-ENTRY`. A finding or instruction that requests `WAIT-FOR-ENTRY` for a position
whose `entry_zone_status=CURRENT_ENTRY` is invalid regardless of severity or risk_profile,
and SHALL be removed before it reaches the Final Strategist by the deterministic action
policy gate (see `action-policy-gate`) — this requirement does not rely on the Critic's own
prompt compliance alone.

#### Scenario: Critic instruction ordering WAIT-FOR-ENTRY at CURRENT_ENTRY is invalid
- **WHEN** a `CritiqueItem` with `issue_type=PRICE_IN_ZONE_WAIT` or `issue_type=WAIT_IN_ZONE` has an `instruction` requesting a change to `WAIT-FOR-ENTRY` for a position with `entry_zone_status=CURRENT_ENTRY`
- **THEN** the instruction is invalid per this requirement and SHALL be removed from what reaches the Final Strategist, regardless of which output channel (`revision_directives` or `per_ticker_critiques`) carries it

#### Scenario: Critic instruction ordering LONG-BUY at CURRENT_ENTRY remains valid
- **WHEN** a `CritiqueItem` with `issue_type=WAIT_IN_ZONE` has an `instruction` requesting a change TO `LONG-BUY` for a position with `entry_zone_status=CURRENT_ENTRY` and the draft's actual action was `WAIT-FOR-ENTRY`
- **THEN** the instruction is valid and SHALL pass through unfiltered

### Requirement: Critic does not fabricate findings on a fully compliant position
The Critic SHALL NOT be instructed to produce a minimum number of findings per position.
A ticker with zero findings grounded in the reference_table and Draft data SHALL be
recorded in `approved_positions` rather than assigned an invented `per_ticker_critiques`
entry. This is a requirement on the Critic's task instructions, not independently testable
against a live LLM in this repository's test suite — verified instead by the absence of a
quota instruction in the `critique_review` task description and by empirical re-validation
against previously-failing runs.

#### Scenario: Task description contains no quota instruction
- **WHEN** `config/tasks.yaml`'s `critique_review` task description is read
- **THEN** it does not instruct the Critic to find a minimum number of issues per position
