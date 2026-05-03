# portfolio-allocator-allocation Specification

## Purpose
TBD - created by archiving change portfolio-allocator-tests. Update Purpose after archive.
## Requirements
### Requirement: Allocation is proportional to composite score, capped per action type

The allocator SHALL distribute capital proportionally to each stock's `composite_score`
among deployed positions (LONG-BUY, SCALED-ENTRY, WAIT-FOR-ENTRY), subject to per-action
caps: LONG-BUY ≤ 40%, SCALED-ENTRY ≤ 20%, WAIT-FOR-ENTRY ≤ 15%. MONITOR and AVOID
positions SHALL receive 0% allocation.

#### Scenario: Single LONG-BUY gets full proportional share up to cap

- **WHEN** one stock with action LONG-BUY and composite_score 75 is submitted
- **THEN** allocation_pct is 100.0 (sole position, uncapped at 40% cap)

#### Scenario: Two equal-score LONG-BUY positions split evenly

- **WHEN** two stocks with action LONG-BUY and equal composite_scores are submitted
- **THEN** each receives allocation_pct of 50.0

#### Scenario: LONG-BUY allocation is capped at 40%

- **WHEN** one LONG-BUY stock has a much higher composite_score than other deployed positions
- **THEN** its allocation_pct does not exceed 40.0

#### Scenario: SCALED-ENTRY allocation is capped at 20%

- **WHEN** a SCALED-ENTRY stock would otherwise exceed 20% proportionally
- **THEN** its allocation_pct does not exceed 20.0

#### Scenario: WAIT-FOR-ENTRY allocation is capped at 15%

- **WHEN** a WAIT-FOR-ENTRY stock would otherwise exceed 15% proportionally
- **THEN** its allocation_pct does not exceed 15.0

#### Scenario: MONITOR and AVOID receive zero allocation

- **WHEN** stocks with action MONITOR or AVOID are submitted alongside deployed positions
- **THEN** their allocation_pct is 0.0

