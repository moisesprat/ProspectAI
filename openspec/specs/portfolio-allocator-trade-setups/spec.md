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

### Requirement: Above-zone LONG-BUY uses current-price-anchored stop and take-profit
When the LLM assigns `LONG-BUY` to a stock with `current_price > entry_zone_high`
(i.e., the stock is above its entry zone), the allocator SHALL detect this condition
and compute stop and take-profit anchored to `current_price` rather than `entry_zone_low`,
using the same profile `stop_multiplier` and `rr_ratio`.

Formulas:
- `stop_loss = current_price × stop_multiplier`
- `take_profit = current_price + (current_price − stop_loss) × rr_ratio`

The `entry_zone_low` and `entry_zone_high` fields in the returned `trade_setup` SHALL
reflect the zone values from the technical tool (context for the user), but stop and
take-profit SHALL be anchored to `current_price` to ensure the R/R is valid at the
actual entry price.

The full allocation counts as `deployed_pct` (no split into reserved).

#### Scenario: Above-zone LONG-BUY aggressive uses current-price stop/TP
- **WHEN** a LONG-BUY stock has `current_price=220`, `entry_zone_low=207`, `entry_zone_high=213`, and `risk_profile=aggressive`
- **THEN** `stop_loss` equals 209.0 (220 × 0.95)
- **AND** `take_profit` equals 236.5 (220 + (220 − 209) × 1.5)
- **AND** full `allocation_pct` is counted in `deployed_pct`

#### Scenario: In-zone LONG-BUY continues to use zone-anchored stop/TP
- **WHEN** a LONG-BUY stock has `current_price=210`, `entry_zone_low=207`, `entry_zone_high=213`, and `risk_profile=aggressive`
- **THEN** `stop_loss` equals 196.65 (207 × 0.95)
- **AND** `take_profit` equals 221.45 (213 + (207 − 196.65) × 1.5)

#### Scenario: Above-zone LONG-BUY conservative uses current-price stop/TP
- **WHEN** a LONG-BUY stock has `current_price=220`, `entry_zone_low=207`, `entry_zone_high=213`, and `risk_profile=conservative`
- **THEN** `stop_loss` equals 213.4 (220 × 0.97)
- **AND** `take_profit` equals 230.4 (220 + (220 − 213.4) × 2.5)

#### Scenario: MONITOR and AVOID have null trade_setup

- **WHEN** stocks with action MONITOR or AVOID are submitted
- **THEN** trade_setup is null

