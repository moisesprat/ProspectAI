## ADDED Requirements

### Requirement: Action-policy table is evaluated as data, not left to LLM adherence
The Flow SHALL encode the `entry_zone_status × risk_profile → allowed actions` table
(as documented for the Draft Strategist in `config/tasks.yaml`) as a data structure
evaluated in code, keyed on `entry_zone_status` (`CURRENT_ENTRY`, `PULLBACK_ENTRY`,
`BELOW_ZONE`) and `risk_profile` (`conservative`, `aggressive`).

#### Scenario: Table resolves the allowed action set for a given status and profile
- **WHEN** `entry_zone_status=CURRENT_ENTRY` for either `risk_profile`
- **THEN** the resolved allowed-action set includes `LONG-BUY` and excludes `WAIT-FOR-ENTRY`

### Requirement: Critic revision directives outside the policy table are dropped before reaching the Final Strategist
Between `critique_review` and `final_strategy`, the Flow SHALL resolve each entry in
`revision_directives` to the position it targets and that position's current
`entry_zone_status` and `risk_profile`. If the directive's requested action is not in the
allowed set for that combination, the Flow SHALL exclude the directive from the context
passed to `final_strategy` and SHALL log the ticker, the rejected action, and the reason.

#### Scenario: Critic orders an action the policy table forbids
- **WHEN** a `revision_directives` entry instructs `WAIT-FOR-ENTRY` for a position whose
  `entry_zone_status=CURRENT_ENTRY`
- **THEN** the Flow drops that directive, logs the rejection, and the Final Strategist does
  not receive it as context

#### Scenario: Critic orders an action the policy table permits
- **WHEN** a `revision_directives` entry instructs `LONG-BUY` for a position whose
  `entry_zone_status=PULLBACK_ENTRY`, `overall_signal=BULLISH`, `momentum_score=6`, and
  `risk_profile=aggressive`
- **THEN** the Flow passes the directive through to the Final Strategist unchanged

#### Scenario: Directive does not target a specific position's action
- **WHEN** a `revision_directives` entry addresses rationale quality or a non-action concern
  rather than requesting a specific action change
- **THEN** the Flow passes it through unfiltered — the gate only evaluates directives that
  request a specific action for a specific position
