# portfolio-allocator-trade-setups Specification

## Purpose
TBD - created by archiving change portfolio-allocator-tests. Update Purpose after archive.
## Requirements
### Requirement: Zone-anchored trade setup for LONG-BUY and WAIT-FOR-ENTRY

For LONG-BUY and WAIT-FOR-ENTRY positions the allocator SHALL compute:
- `stop_loss = entry_zone_low × 0.97`
- `take_profit = entry_zone_high + (entry_zone_low − stop_loss) × 2`

The invariant `stop_loss < entry_zone_low ≤ entry_zone_high < take_profit` MUST hold.

#### Scenario: LONG-BUY trade setup uses zone-anchored formula

- **WHEN** a LONG-BUY stock with entry_zone_low=100 and entry_zone_high=105 is submitted
- **THEN** stop_loss equals 97.0 (100 × 0.97)
- **AND** take_profit equals 111.0 (105 + (100 − 97) × 2)

#### Scenario: WAIT-FOR-ENTRY trade setup uses the same zone-anchored formula

- **WHEN** a WAIT-FOR-ENTRY stock with entry_zone_low=200 and entry_zone_high=210 is submitted
- **THEN** stop_loss equals 194.0 (200 × 0.97)
- **AND** take_profit equals 222.0 (210 + (200 − 194) × 2)

#### Scenario: LONG-BUY trade_setup invariant holds

- **WHEN** any LONG-BUY trade setup is computed
- **THEN** stop_loss < entry_zone_low and take_profit > entry_zone_high

### Requirement: Current-price-anchored R/R 2:1 setup for SCALED-ENTRY immediate tranche

For SCALED-ENTRY the allocator SHALL produce two setups in `scaled_entry_setups`:
1. Immediate tranche: `stop_loss = current_price × 0.97`, `take_profit = current_price + (current_price − stop_loss) × 2` — R/R exactly 2.0.
2. Pullback tranche: zone-anchored formula (same as LONG-BUY).

`trade_setup` SHALL be null for SCALED-ENTRY.

#### Scenario: SCALED-ENTRY immediate tranche is anchored to current_price

- **WHEN** a SCALED-ENTRY stock with current_price=150 is submitted
- **THEN** immediate tranche stop_loss equals 145.5 (150 × 0.97)
- **AND** immediate tranche take_profit equals 159.0 (150 + (150 − 145.5) × 2)

#### Scenario: SCALED-ENTRY pullback tranche uses zone-anchored formula

- **WHEN** a SCALED-ENTRY stock with entry_zone_low=140 and entry_zone_high=145 is submitted
- **THEN** pullback tranche stop_loss equals 135.8 (140 × 0.97)
- **AND** pullback tranche take_profit equals 154.4 (145 + (140 − 135.8) × 2)

#### Scenario: SCALED-ENTRY trade_setup field is null

- **WHEN** a SCALED-ENTRY stock is submitted
- **THEN** trade_setup is null and scaled_entry_setups has exactly 2 entries

#### Scenario: MONITOR and AVOID have null trade_setup and null scaled_entry_setups

- **WHEN** stocks with action MONITOR or AVOID are submitted
- **THEN** both trade_setup and scaled_entry_setups are null

