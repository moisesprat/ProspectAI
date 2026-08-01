## ADDED Requirements

### Requirement: Reserved bucket is explicitly attributed per ticker
`PortfolioAllocatorTool` SHALL emit `reserved_allocations: [{ticker, pct}]` alongside the
existing bucket fields. `reserved_pct` SHALL equal the sum of `pct` across
`reserved_allocations`. Every position with `action=WAIT-FOR-ENTRY` SHALL have a
corresponding entry in `reserved_allocations` with `pct > 0`.

#### Scenario: reserved_pct matches the sum of reserved_allocations
- **WHEN** two WAIT-FOR-ENTRY positions receive `allocation_pct` of 10.0 and 5.0
  respectively
- **THEN** `reserved_allocations` contains both tickers with those `pct` values, and
  `reserved_pct` equals 15.0

#### Scenario: A WAIT-FOR-ENTRY position with no attributed allocation is invalid output
- **WHEN** a position has `action=WAIT-FOR-ENTRY` but no corresponding entry exists in
  `reserved_allocations`, or its `pct` is 0
- **THEN** the tool's output is treated as failing the reserved-bucket attribution
  invariant (surfaced by `PortfolioBoundsValidator` — see `portfolio-bounds-enforcement`)
