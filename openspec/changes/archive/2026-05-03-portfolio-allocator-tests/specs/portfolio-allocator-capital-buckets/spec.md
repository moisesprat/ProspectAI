## ADDED Requirements

### Requirement: Three-bucket capital breakdown is computed correctly

The allocator SHALL compute three capital buckets from the final allocations:
- `deployed_pct`: sum of LONG-BUY allocations + half of each SCALED-ENTRY allocation
- `reserved_pct`: sum of WAIT-FOR-ENTRY allocations + half of each SCALED-ENTRY allocation
- `cash_reserve_pct`: 100 − deployed_pct − reserved_pct

`deployed_pct + reserved_pct + cash_reserve_pct` SHALL equal 100.0.

#### Scenario: LONG-BUY position contributes fully to deployed_pct

- **WHEN** a single LONG-BUY stock with allocation_pct=30 is submitted
- **THEN** deployed_pct equals 30.0 and reserved_pct equals 0.0
- **AND** cash_reserve_pct equals 70.0

#### Scenario: SCALED-ENTRY splits allocation evenly between deployed and reserved

- **WHEN** a single SCALED-ENTRY stock with allocation_pct=20 is submitted
- **THEN** deployed_pct equals 10.0 and reserved_pct equals 10.0
- **AND** cash_reserve_pct equals 80.0

#### Scenario: WAIT-FOR-ENTRY position contributes fully to reserved_pct

- **WHEN** a single WAIT-FOR-ENTRY stock with allocation_pct=15 is submitted
- **THEN** reserved_pct equals 15.0 and deployed_pct equals 0.0
- **AND** cash_reserve_pct equals 85.0

#### Scenario: Mixed action types produce correct bucket totals

- **WHEN** a LONG-BUY (alloc=30), a SCALED-ENTRY (alloc=20), and a WAIT-FOR-ENTRY (alloc=15) are submitted
- **THEN** deployed_pct equals 40.0 (30 + 10)
- **AND** reserved_pct equals 25.0 (15 + 10)
- **AND** cash_reserve_pct equals 35.0

#### Scenario: Buckets sum to 100

- **WHEN** any valid input is submitted
- **THEN** deployed_pct + reserved_pct + cash_reserve_pct equals 100.0
