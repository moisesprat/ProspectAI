## REMOVED Requirements

### Requirement: Critic profile reference table includes entry-behavior thresholds
**Reason**: This requirement mandated the exact profile-bounds table column (PULLBACK_ENTRY entry-behavior thresholds) that `reasoning-action-selection` eliminates. With `PULLBACK_ENTRY` open to LLM judgment for both profiles, there is no fixed "aggressive standard" vs. "conservative standard" for the Critic to apply — the Critic instead evaluates whether the rationale's own stated reasoning is coherent and evidence-grounded, per "Critic evaluates whether stated conviction is earned by the evidence" below.
**Migration**: See "Critic evaluates whether stated conviction is earned by the evidence."

### Requirement: Critic checks WAIT_ENTRY_ZERO_ALLOC against explicit reserved attribution
**Reason**: This check is redundant with `PortfolioBoundsValidator`, which already enforces allocation/reservation bounds deterministically after the Final Strategist phase, and the Final Strategist has no authority to fix a numeric field regardless of what the Critic finds — the Flow overwrites every numeric field unconditionally via `PortfolioAllocatorTool`. Keeping it in the Critic's checklist duplicated a check the Critic cannot act on.
**Migration**: None — deterministic enforcement continues unchanged via `PortfolioBoundsValidator`.

## MODIFIED Requirements

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

### Requirement: Critic checks UNCONVINCING_OVERRIDE for weak aggressive LONG-BUY
The Critic SHALL flag `UNCONVINCING_OVERRIDE` (MAJOR) when a position has
`risk_profile=aggressive`, `action=LONG-BUY`, weak momentum, and weak financial health,
AND the rationale cites no specific catalyst (earnings, product launch, macro event). The
qualifying condition SHALL be expressed qualitatively — "weak momentum" and "weak financial
health" as read from the provided `overall_signal`/`momentum_score`/`financial_health`
fields — not as a fixed numeric threshold embedded in the Critic's instructions; the Critic
uses its own judgment on what counts as weak in context, the same freedom the Draft
Strategist has.

#### Scenario: Critic flags aggressive LONG-BUY with weak momentum and weak health
- **WHEN** a position has `risk_profile=aggressive`, `action=LONG-BUY`, `momentum_score=3`, `financial_health=WEAK`, and the rationale contains no specific catalyst
- **THEN** Critic SHALL produce an `UNCONVINCING_OVERRIDE` finding with severity MAJOR

#### Scenario: Critic does not flag aggressive LONG-BUY with adequate momentum
- **WHEN** a position has `risk_profile=aggressive`, `action=LONG-BUY`, `momentum_score=6`, `financial_health=ADEQUATE`
- **THEN** Critic SHALL NOT produce `UNCONVINCING_OVERRIDE`

## ADDED Requirements

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
