## MODIFIED Requirements

### Requirement: Allocation is proportional to composite score, capped per risk profile

The allocator SHALL distribute capital proportionally to each stock's `composite_score`
among deployed positions (LONG-BUY, SCALED-ENTRY, WAIT-FOR-ENTRY), subject to a
per-position cap determined by `risk_profile`:

| Profile | Max allocation per position |
|---|---|
| `conservative` | 15% |
| `aggressive` | 30% |

MONITOR and AVOID positions SHALL receive 0% allocation regardless of profile.

The `risk_profile` value SHALL be read from the top-level `risk_profile` key in the JSON
payload passed to `PortfolioAllocatorTool`. If absent or invalid it SHALL default to
`"conservative"` and log a warning.

#### Scenario: Single LONG-BUY under conservative gets full share up to 15% cap

- **WHEN** one stock with action LONG-BUY and composite_score 75 is submitted with `risk_profile="conservative"`
- **THEN** allocation_pct is 15.0 (sole position, capped at conservative limit)

#### Scenario: Single LONG-BUY under aggressive gets full share up to 30% cap

- **WHEN** one stock with action LONG-BUY and composite_score 75 is submitted with `risk_profile="aggressive"`
- **THEN** allocation_pct is 30.0 (sole position, capped at aggressive limit)

#### Scenario: Conservative profile caps all positions at 15%

- **WHEN** one stock has a much higher composite_score than all others under `risk_profile="conservative"`
- **THEN** its allocation_pct does not exceed 15.0

#### Scenario: Aggressive profile caps all positions at 30%

- **WHEN** one stock has a much higher composite_score than all others under `risk_profile="aggressive"`
- **THEN** its allocation_pct does not exceed 30.0

#### Scenario: Two equal-score LONG-BUY positions split evenly under both profiles

- **WHEN** two stocks with action LONG-BUY and equal composite_scores are submitted
- **THEN** each receives an equal allocation_pct regardless of profile

#### Scenario: MONITOR and AVOID receive zero allocation under both profiles

- **WHEN** stocks with action MONITOR or AVOID are submitted alongside deployed positions
- **THEN** their allocation_pct is 0.0 regardless of risk_profile
