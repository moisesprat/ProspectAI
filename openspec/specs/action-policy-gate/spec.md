# action-policy-gate Specification

## Purpose
Deterministically enforces the `entry_zone_status × risk_profile → allowed actions`
policy table as code, rather than relying on LLM adherence. Filters Critic
`revision_directives` between the critique-review and final-strategy phases so that any
directive ordering an action outside the policy table for a position's
`entry_zone_status`/`risk_profile` never reaches the Final Strategist.

## Requirements

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

### Requirement: per_ticker_critiques is filtered against the action policy table
The Flow SHALL apply the `entry_zone_status × risk_profile → allowed actions` table to
`CriticOutput.per_ticker_critiques[].instruction`, using the same evaluation as
`revision_directives`. A `CritiqueItem` whose instruction requests an action outside the
allowed set for its ticker's `entry_zone_status`/`risk_profile` SHALL be removed entirely
from what reaches the Final Strategist, and the removal SHALL be logged with the ticker,
rejected action, and reason — matching the existing logging for rejected
`revision_directives`.

#### Scenario: per_ticker_critiques instruction ordering a disallowed action is dropped
- **WHEN** a `CritiqueItem` for a ticker with `entry_zone_status=CURRENT_ENTRY` has an
  `instruction` requesting `WAIT-FOR-ENTRY`
- **THEN** the Flow removes that `CritiqueItem` from the `per_ticker_critiques` passed to
  the Final Strategist and logs the rejection

#### Scenario: per_ticker_critiques instruction requesting a permitted action passes through
- **WHEN** a `CritiqueItem` for a ticker with `entry_zone_status=PULLBACK_ENTRY`,
  `risk_profile=aggressive` has an `instruction` requesting `LONG-BUY`
- **THEN** the `CritiqueItem` passes through unchanged

#### Scenario: Both channels carrying the same bad instruction are both filtered
- **WHEN** a Critic output contains the same disallowed action for the same ticker in both
  `revision_directives` and `per_ticker_critiques`
- **THEN** the Flow removes it from both before building the Final Strategist's context

### Requirement: Requested-action extraction prefers the target of "from X to Y" phrasing
When parsing a ticker/action pair from free text (`revision_directives` entries or
`per_ticker_critiques[].instruction`), the parser SHALL prefer the action following the
word "to" over any earlier action word in the same string, since directives are routinely
phrased "change action from \<old\> to \<new\>" — the first action word is the one being
replaced, not the one requested. When no "to \<ACTION\>" phrasing is present, the parser
SHALL fall back to the last bare action-word match rather than the first, to avoid an
action word used elsewhere in the string (e.g. as an ordinary verb) being mistaken for an
earlier, unintended requested action.

#### Scenario: "Change action from X to Y" extracts Y, not X
- **WHEN** parsing the text `"NVDA: Change action from LONG-BUY to WAIT-FOR-ENTRY because entry_zone_status=CURRENT_ENTRY..."`
- **THEN** the extracted requested action is `WAIT-FOR-ENTRY`, not `LONG-BUY`

#### Scenario: A trailing verb use of an action word is not mistaken for the requested action
- **WHEN** parsing text containing `"...change action from LONG-BUY to WAIT-FOR-ENTRY because...monitor for price to exit zone and re-enter on pullback."`
- **THEN** the extracted requested action is `WAIT-FOR-ENTRY`, not `MONITOR`
