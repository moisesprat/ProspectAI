# reasoning-critic-validation Specification

## Purpose
Defines the Critic agent's validation checks for reasoning-based action selection. Replaces numeric threshold checks (OVERBOUGHT_IGNORED, ENTRY_ZONE_VIOLATED) with reasoning-coherence checks that evaluate whether the LLM's action choice is consistent with the signals and risk profile.

## Requirements

### Requirement: Critic checks ACTION_PROFILE_MISMATCH instead of ENTRY_ZONE_VIOLATED
The Critic SHALL flag `ACTION_PROFILE_MISMATCH` (MAJOR) when a LONG-BUY position has
`overall_signal=BEARISH` and the rationale cites no compelling fundamental thesis (e.g.
exceptional earnings growth, fundamental re-rating) to explain why the action outweighs the
bearish signal. This is a reasoning-coherence check, not a numeric-threshold check: it does
not depend on a fixed `entry_zone_status` branch or a profile-specific default action —
`PULLBACK_ENTRY` and `BELOW_ZONE` no longer have a single "expected" action per profile, so
the Critic instead asks whether the stated conviction is earned by the cited evidence,
regardless of `entry_zone_status`.

The Critic SHALL NOT flag LONG-BUY as a violation solely because `overall_signal` is
BULLISH or MIXED and `entry_zone_status` is not `CURRENT_ENTRY` — that is valid reasoning
under this change's open judgment for `PULLBACK_ENTRY`/`BELOW_ZONE`.

#### Scenario: Critic flags LONG-BUY on bearish signal without override thesis
- **WHEN** a position has `action=LONG-BUY`, `overall_signal=BEARISH`, and the rationale does not cite a specific fundamental catalyst
- **THEN** Critic SHALL produce an `ACTION_PROFILE_MISMATCH` finding with severity MAJOR

#### Scenario: Critic does not flag LONG-BUY on bullish PULLBACK_ENTRY under aggressive profile
- **WHEN** a position has `action=LONG-BUY`, `entry_zone_status=PULLBACK_ENTRY`, `overall_signal=BULLISH`, `risk_profile=aggressive`
- **THEN** Critic SHALL NOT produce `ACTION_PROFILE_MISMATCH` solely on the basis of `entry_zone_status`

#### Scenario: Critic does not flag LONG-BUY on mixed PULLBACK_ENTRY under aggressive profile
- **WHEN** a position has `action=LONG-BUY`, `entry_zone_status=PULLBACK_ENTRY`, `overall_signal=MIXED`, `risk_profile=aggressive`
- **THEN** Critic SHALL NOT produce `ACTION_PROFILE_MISMATCH` solely on the basis of `entry_zone_status`

### Requirement: Critic checks WAIT_IN_ZONE for misplaced WAIT-FOR-ENTRY
The Critic SHALL flag `WAIT_IN_ZONE` (CRITICAL) when a position has
`action=WAIT-FOR-ENTRY` AND `entry_zone_status=CURRENT_ENTRY`. Price is already in the
actionable zone — waiting is contradictory regardless of profile.

#### Scenario: Critic flags WAIT-FOR-ENTRY when price is in zone
- **WHEN** a position has `action=WAIT-FOR-ENTRY` and `entry_zone_status=CURRENT_ENTRY`
- **THEN** Critic SHALL produce a `WAIT_IN_ZONE` finding with severity CRITICAL

### Requirement: Critic checks UNCONVINCING_OVERRIDE for weak aggressive LONG-BUY
The Critic SHALL flag `UNCONVINCING_OVERRIDE` (MAJOR) when a position has
`risk_profile=aggressive`, `action=LONG-BUY`, weak momentum, and weak financial health,
AND the rationale cites no specific catalyst (earnings, product launch, macro event). The
qualifying condition SHALL be expressed qualitatively — "weak momentum" and "weak financial
health" as read from the provided `overall_signal`/`momentum_score`/`fundamental_rating.quality`
fields — not as a fixed numeric threshold embedded in the Critic's instructions; the Critic
uses its own judgment on what counts as weak in context, the same freedom the Draft
Strategist has.

#### Scenario: Critic flags aggressive LONG-BUY with weak momentum and weak health
- **WHEN** a position has `risk_profile=aggressive`, `action=LONG-BUY`, `momentum_score=3`, `fundamental_rating.quality=Low`, and the rationale contains no specific catalyst
- **THEN** Critic SHALL produce an `UNCONVINCING_OVERRIDE` finding with severity MAJOR

#### Scenario: Critic does not flag aggressive LONG-BUY with adequate momentum
- **WHEN** a position has `risk_profile=aggressive`, `action=LONG-BUY`, `momentum_score=6`, `fundamental_rating.quality=Medium`
- **THEN** Critic SHALL NOT produce `UNCONVINCING_OVERRIDE`

### Requirement: Critic removes OVERBOUGHT_IGNORED and ENTRY_ZONE_VIOLATED checks
The Critic SHALL NOT check `OVERBOUGHT_IGNORED` (RSI > 70 with LONG-BUY) or
`ENTRY_ZONE_VIOLATED` (gap ≥ 5% with LONG-BUY). These numeric checks are replaced by
the reasoning-coherence checks above. Elevated RSI or above-zone price alone are NOT
Critic violations — they are inputs to the LLM's reasoning.

#### Scenario: Critic does not flag LONG-BUY on elevated RSI alone
- **WHEN** a position has `action=LONG-BUY` and `rsi=74` with no other disqualifying signals
- **THEN** Critic SHALL NOT produce `OVERBOUGHT_IGNORED` or any RSI-threshold violation

### Requirement: Critic sentiment-based findings are out of scope when sentiment is unavailable
The Critic SHALL NOT raise a finding whose basis is a candidate's sentiment score or
sentiment trend when that candidate's `sentiment_available=False`.

#### Scenario: Critic skips sentiment-based critique for an unavailable-sentiment candidate
- **WHEN** a position's `sentiment_available=False`
- **THEN** the Critic's review of that position SHALL NOT cite `average_sentiment` or a
  sentiment trend as grounds for any finding

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

### Requirement: An empty per_ticker_critiques and revision_directives is a valid outcome
`CriticOutput.per_ticker_critiques` and `CriticOutput.revision_directives` SHALL allow
empty lists (`min_length=0`). A genuinely clean draft under the trimmed reasoning-coherence
checklist can legitimately produce zero findings. Schema validation SHALL NOT force a
minimum of one entry, since doing so previously created pressure toward fabricated findings
on fully compliant drafts — directly conflicting with "Critic does not fabricate findings
on a fully compliant position."

#### Scenario: Fully compliant draft produces empty critique lists without validation failure
- **WHEN** the Critic determines every position in the draft is reasoning-coherent and cites no violations
- **THEN** `CriticOutput` with `per_ticker_critiques=[]` and `revision_directives=[]` SHALL pass Pydantic validation
