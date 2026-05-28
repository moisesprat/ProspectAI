# portfolio-allocator-trade-setups Specification

## Purpose
TBD - created by archiving change portfolio-allocator-tests. Update Purpose after archive.
## Requirements
### Requirement: Zone-anchored trade setup for LONG-BUY and WAIT-FOR-ENTRY

For LONG-BUY and WAIT-FOR-ENTRY positions the allocator SHALL compute stop_loss and
take_profit using profile-specific constants:

| Constant | Conservative | Aggressive |
|---|---|---|
| `stop_multiplier` | 0.97 (3% below entry_zone_low) | 0.95 (5% below entry_zone_low) |
| `rr_ratio` | 2.5 | 1.5 |

Formulas:
- `stop_loss = entry_zone_low × stop_multiplier`
- `take_profit = entry_zone_high + (entry_zone_low − stop_loss) × rr_ratio`

The invariant `stop_loss < entry_zone_low ≤ entry_zone_high < take_profit` MUST hold
for both profiles.

#### Scenario: LONG-BUY conservative trade setup uses 3% stop and R/R 2.5

- **WHEN** a LONG-BUY stock with entry_zone_low=100 and entry_zone_high=105 is submitted with `risk_profile="conservative"`
- **THEN** stop_loss equals 97.0 (100 × 0.97)
- **AND** take_profit equals 112.5 (105 + (100 − 97) × 2.5)

#### Scenario: LONG-BUY aggressive trade setup uses 5% stop and R/R 1.5

- **WHEN** a LONG-BUY stock with entry_zone_low=100 and entry_zone_high=105 is submitted with `risk_profile="aggressive"`
- **THEN** stop_loss equals 95.0 (100 × 0.95)
- **AND** take_profit equals 112.5 (105 + (100 − 95) × 1.5)

#### Scenario: WAIT-FOR-ENTRY conservative uses same conservative formula

- **WHEN** a WAIT-FOR-ENTRY stock with entry_zone_low=200 and entry_zone_high=210 is submitted with `risk_profile="conservative"`
- **THEN** stop_loss equals 194.0 (200 × 0.97)
- **AND** take_profit equals 229.0 (210 + (200 − 194) × 2.5)

#### Scenario: Trade setup invariant holds for both profiles

- **WHEN** any LONG-BUY or WAIT-FOR-ENTRY trade setup is computed
- **THEN** stop_loss < entry_zone_low and take_profit > entry_zone_high

### Requirement: Current-price-anchored R/R setup for SCALED-ENTRY immediate tranche

For SCALED-ENTRY the allocator SHALL produce two setups in `scaled_entry_setups` using
profile-specific constants:

1. Immediate tranche: `stop_loss = current_price × stop_multiplier`, `take_profit = current_price + (current_price − stop_loss) × rr_ratio`
2. Pullback tranche: zone-anchored formula (same as LONG-BUY), using the same profile constants.

`trade_setup` SHALL be null for SCALED-ENTRY.

| Constant | Conservative | Aggressive |
|---|---|---|
| `stop_multiplier` | 0.97 | 0.95 |
| `rr_ratio` | 2.5 | 1.5 |

#### Scenario: SCALED-ENTRY conservative immediate tranche uses 3% stop and R/R 2.5

- **WHEN** a SCALED-ENTRY stock with current_price=150 is submitted with `risk_profile="conservative"`
- **THEN** immediate tranche stop_loss equals 145.5 (150 × 0.97)
- **AND** immediate tranche take_profit equals 156.0 (150 + (150 − 145.5) × 2.5)

#### Scenario: SCALED-ENTRY aggressive immediate tranche uses 5% stop and R/R 1.5

- **WHEN** a SCALED-ENTRY stock with current_price=150 is submitted with `risk_profile="aggressive"`
- **THEN** immediate tranche stop_loss equals 142.5 (150 × 0.95)
- **AND** immediate tranche take_profit equals 161.25 (150 + (150 − 142.5) × 1.5)

#### Scenario: SCALED-ENTRY pullback tranche uses profile zone-anchored formula

- **WHEN** a SCALED-ENTRY stock with entry_zone_low=140 and entry_zone_high=145 is submitted with `risk_profile="conservative"`
- **THEN** pullback tranche stop_loss equals 135.8 (140 × 0.97)
- **AND** pullback tranche take_profit equals 159.5 (145 + (140 − 135.8) × 2.5)

#### Scenario: SCALED-ENTRY trade_setup field is null

- **WHEN** a SCALED-ENTRY stock is submitted
- **THEN** trade_setup is null and scaled_entry_setups has exactly 2 entries

#### Scenario: MONITOR and AVOID have null trade_setup and null scaled_entry_setups

- **WHEN** stocks with action MONITOR or AVOID are submitted
- **THEN** both trade_setup and scaled_entry_setups are null

