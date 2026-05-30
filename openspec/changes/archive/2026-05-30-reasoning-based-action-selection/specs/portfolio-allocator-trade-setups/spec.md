## REMOVED Requirements

### Requirement: Current-price-anchored R/R setup for SCALED-ENTRY immediate tranche
**Reason**: SCALED-ENTRY action is removed from the valid action space. The split-tranche model (half deployed now at current price, half reserved for pullback) introduced two different stop-losses and take-profits for the same position, confusing users and adding pipeline fragility. Above-zone stocks eligible for entry now use LONG-BUY with a current-price-anchored setup instead.
**Migration**: Any code path that produced `SCALED-ENTRY` or read `scaled_entry_setups` should be updated to use `LONG-BUY` with a current-price-anchored trade_setup. The `PortfolioAllocatorTool` SCALED-ENTRY branch should be removed.

## ADDED Requirements

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
