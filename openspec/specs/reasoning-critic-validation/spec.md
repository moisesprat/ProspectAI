# reasoning-critic-validation Specification

## Purpose
Defines the Critic agent's validation checks for reasoning-based action selection. Replaces numeric threshold checks (OVERBOUGHT_IGNORED, ENTRY_ZONE_VIOLATED) with reasoning-coherence checks that evaluate whether the LLM's action choice is consistent with the signals and risk profile.

## Requirements

### Requirement: Critic checks ACTION_PROFILE_MISMATCH instead of ENTRY_ZONE_VIOLATED
The Critic SHALL flag `ACTION_PROFILE_MISMATCH` (MAJOR) when a LONG-BUY position has
`entry_zone_status=PULLBACK_ENTRY` AND `overall_signal=BEARISH` AND the rationale cites
no compelling fundamental thesis (e.g. exceptional earnings growth, fundamental re-rating)
to override the bearish signal. This replaces the removed `ENTRY_ZONE_VIOLATED` check.

The Critic SHALL NOT flag LONG-BUY on PULLBACK_ENTRY as a violation when
`overall_signal` is BULLISH or MIXED — that is valid reasoning under the aggressive profile.

#### Scenario: Critic flags LONG-BUY on bearish PULLBACK_ENTRY without override thesis
- **WHEN** a position has `action=LONG-BUY`, `entry_zone_status=PULLBACK_ENTRY`, `overall_signal=BEARISH`, and the rationale does not cite a specific fundamental catalyst
- **THEN** Critic SHALL produce an `ACTION_PROFILE_MISMATCH` finding with severity MAJOR

#### Scenario: Critic does not flag LONG-BUY on bullish PULLBACK_ENTRY under aggressive profile
- **WHEN** a position has `action=LONG-BUY`, `entry_zone_status=PULLBACK_ENTRY`, `overall_signal=BULLISH`, `risk_profile=aggressive`
- **THEN** Critic SHALL NOT produce `ACTION_PROFILE_MISMATCH` or any entry-zone violation finding

#### Scenario: Critic does not flag LONG-BUY on mixed PULLBACK_ENTRY under aggressive profile
- **WHEN** a position has `action=LONG-BUY`, `entry_zone_status=PULLBACK_ENTRY`, `overall_signal=MIXED`, `risk_profile=aggressive`, `momentum_score≥5`
- **THEN** Critic SHALL NOT produce any entry-zone violation finding

### Requirement: Critic checks WAIT_IN_ZONE for misplaced WAIT-FOR-ENTRY
The Critic SHALL flag `WAIT_IN_ZONE` (CRITICAL) when a position has
`action=WAIT-FOR-ENTRY` AND `entry_zone_status=CURRENT_ENTRY`. Price is already in the
actionable zone — waiting is contradictory regardless of profile.

#### Scenario: Critic flags WAIT-FOR-ENTRY when price is in zone
- **WHEN** a position has `action=WAIT-FOR-ENTRY` and `entry_zone_status=CURRENT_ENTRY`
- **THEN** Critic SHALL produce a `WAIT_IN_ZONE` finding with severity CRITICAL

### Requirement: Critic checks UNCONVINCING_OVERRIDE for weak aggressive LONG-BUY
The Critic SHALL flag `UNCONVINCING_OVERRIDE` (MAJOR) when all of the following hold:
- `risk_profile=aggressive`, `action=LONG-BUY`, `entry_zone_status=PULLBACK_ENTRY`
- `momentum_score < 4`
- `financial_health=WEAK`
- The rationale cites no specific catalyst (earnings, product launch, macro event)

#### Scenario: Critic flags aggressive LONG-BUY with weak momentum and weak health
- **WHEN** a position has `risk_profile=aggressive`, `action=LONG-BUY`, `entry_zone_status=PULLBACK_ENTRY`, `momentum_score=3`, `financial_health=WEAK`, and the rationale contains no specific catalyst
- **THEN** Critic SHALL produce an `UNCONVINCING_OVERRIDE` finding with severity MAJOR

#### Scenario: Critic does not flag aggressive LONG-BUY with adequate momentum
- **WHEN** a position has `risk_profile=aggressive`, `action=LONG-BUY`, `entry_zone_status=PULLBACK_ENTRY`, `momentum_score=6`, `financial_health=ADEQUATE`
- **THEN** Critic SHALL NOT produce `UNCONVINCING_OVERRIDE`

### Requirement: Critic removes OVERBOUGHT_IGNORED and ENTRY_ZONE_VIOLATED checks
The Critic SHALL NOT check `OVERBOUGHT_IGNORED` (RSI > 70 with LONG-BUY) or
`ENTRY_ZONE_VIOLATED` (gap ≥ 5% with LONG-BUY). These numeric checks are replaced by
the reasoning-coherence checks above. Elevated RSI or above-zone price alone are NOT
Critic violations — they are inputs to the LLM's reasoning.

#### Scenario: Critic does not flag LONG-BUY on elevated RSI alone
- **WHEN** a position has `action=LONG-BUY` and `rsi=74` with no other disqualifying signals
- **THEN** Critic SHALL NOT produce `OVERBOUGHT_IGNORED` or any RSI-threshold violation

### Requirement: Critic profile reference table includes entry-behavior thresholds
The Critic's profile reference table (used in STEP 1 to validate each position) SHALL
include the entry-behavior thresholds for PULLBACK_ENTRY in addition to the existing
stop/R/R/allocation bounds.

#### Scenario: Critic applies aggressive PULLBACK_ENTRY standards when profile is aggressive
- **WHEN** `risk_profile=aggressive` and a position has `entry_zone_status=PULLBACK_ENTRY` with `overall_signal=BULLISH`
- **THEN** the Critic evaluates the position against aggressive entry standards (LONG-BUY permissible) rather than conservative standards (WAIT-FOR-ENTRY expected)
