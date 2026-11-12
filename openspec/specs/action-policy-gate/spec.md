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
as a data structure evaluated in code, keyed on `entry_zone_status` (`CURRENT_ENTRY`,
`PULLBACK_ENTRY`, `BELOW_ZONE`) and `risk_profile` (`conservative`, `aggressive`).
`BELOW_ZONE` SHALL permit `LONG-BUY`, `MONITOR`, and `AVOID` for both risk profiles,
excluding only `WAIT-FOR-ENTRY` — since price is already below the actionable zone, there
is nothing left to "wait" for it to fall into, but there is no logical objection to buying
below a broken zone if the LLM's reasoning supports it. The permission is not a mandate:
the table only makes `LONG-BUY` reachable, and the LLM stays free to choose `MONITOR` or
`AVOID`. The `FUNDAMENTALS_UNKNOWN` row (only `MONITOR` or `AVOID`) is applied on top of
the matched zone row, and a missing current price caps the action at `MONITOR` or `AVOID`,
so the `BELOW_ZONE` permission holds only for a position with gradable fundamentals and a
usable price (see `reasoning-action-selection`, "The surviving hard invariants").

#### Scenario: Table resolves the allowed action set for a given status and profile
- **WHEN** `entry_zone_status=CURRENT_ENTRY` for either `risk_profile`
- **THEN** the resolved allowed-action set includes `LONG-BUY` and excludes `WAIT-FOR-ENTRY`

#### Scenario: BELOW_ZONE permits LONG-BUY for both profiles
- **WHEN** `entry_zone_status=BELOW_ZONE` for either `risk_profile`
- **THEN** the resolved allowed-action set includes `LONG-BUY`, `MONITOR`, and `AVOID`, and excludes `WAIT-FOR-ENTRY`

#### Scenario: BELOW_ZONE with fundamentals that could not be graded still excludes LONG-BUY
- **WHEN** `entry_zone_status=BELOW_ZONE` and `fundamentals_status=UNKNOWN` for either `risk_profile`
- **THEN** the resolved allowed-action set is `MONITOR` and `AVOID` only

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

### Requirement: PortfolioAllocatorTool anchors below-zone LONG-BUY trade setups to current price
When a position has `action=LONG-BUY` and `current_price < entry_zone_low` (price below
the actionable zone), `PortfolioAllocatorTool` SHALL anchor the trade setup (entry zone,
stop-loss, take-profit) to `current_price` using the same price-anchored formula already
used for above-zone LONG-BUY positions, rather than anchoring to `entry_zone_low`/`entry_zone_high`
— a zone the current price is not actually in. This prevents a below-zone LONG-BUY (now
reachable since `BELOW_ZONE` permits `LONG-BUY`) from producing a `TradeSetup` whose entry
zone/stop sit above the current price while the position asserts an immediate buy.

The requirement specifies the deterministic setup only. It does not say that the LLM
chooses `LONG-BUY` below the zone: that choice stays with the LLM and depends on the risk
profile and the evidence (live replay under the aggressive profile chose `LONG-BUY` and
produced a price-anchored, correctly ordered setup; under the conservative profile it chose
`MONITOR`).

#### Scenario: Below-zone LONG-BUY anchors to current price
- **WHEN** a position has `action=LONG-BUY`, `current_price=90`, `entry_zone_low=95`, `entry_zone_high=100`
- **THEN** `PortfolioAllocatorTool` computes the trade setup's entry zone, stop-loss, and take-profit relative to `current_price=90`, not relative to `entry_zone_low=95`/`entry_zone_high=100`

#### Scenario: Below-zone LONG-BUY trade setup still satisfies the TradeSetup invariant
- **WHEN** a below-zone LONG-BUY trade setup is computed
- **THEN** `stop_loss < entry_zone_low <= entry_zone_high < take_profit` holds, with `entry_zone_low`/`entry_zone_high` collapsed to `current_price`
