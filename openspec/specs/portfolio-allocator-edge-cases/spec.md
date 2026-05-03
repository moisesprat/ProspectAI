# portfolio-allocator-edge-cases Specification

## Purpose
TBD - created by archiving change portfolio-allocator-tests. Update Purpose after archive.
## Requirements
### Requirement: Invalid input returns a structured error

The allocator SHALL return a JSON object with an `"error"` key (not raise an exception)
for malformed or empty input.

#### Scenario: Invalid JSON string returns error

- **WHEN** the input is not valid JSON
- **THEN** the return value is a JSON object containing an "error" key

#### Scenario: Empty array returns error

- **WHEN** the input is an empty JSON array `[]`
- **THEN** the return value is a JSON object containing an "error" key

### Requirement: Entry zone falls back to current_price when omitted

The allocator SHALL substitute `current_price` for missing or zero `entry_zone_low` /
`entry_zone_high` so that a valid trade_setup is always returned for LONG-BUY and
WAIT-FOR-ENTRY positions.

#### Scenario: Missing entry zone uses current_price as fallback

- **WHEN** a LONG-BUY stock is submitted with entry_zone_low=0 and entry_zone_high=0 but current_price=120
- **THEN** trade_setup is not null
- **AND** trade_setup.entry_zone_low equals 120.0

### Requirement: All-MONITOR / all-AVOID input produces zero allocations

The allocator SHALL return valid output (not an error) when every stock has action
MONITOR or AVOID, with all allocations at 0% and cash_reserve_pct at 100%.

#### Scenario: All MONITOR positions produce zero deployment

- **WHEN** all submitted stocks have action MONITOR
- **THEN** every allocation_pct is 0.0
- **AND** cash_reserve_pct equals 100.0
- **AND** deployed_pct equals 0.0

