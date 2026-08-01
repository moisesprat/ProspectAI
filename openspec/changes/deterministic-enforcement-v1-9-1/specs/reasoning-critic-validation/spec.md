## ADDED Requirements

### Requirement: Critic checks WAIT_ENTRY_ZERO_ALLOC against explicit reserved attribution
The Critic SHALL flag `WAIT_ENTRY_ZERO_ALLOC` (CRITICAL) when a position has
`action=WAIT-FOR-ENTRY` and either no corresponding entry exists for it in
`reserved_allocations` or its attributed `pct` is 0 — not merely when the aggregate
`reserved_pct` for the whole portfolio happens to be positive. An aggregate `reserved_pct`
greater than zero SHALL NOT be treated as proof that a specific WAIT-FOR-ENTRY position was
actually funded.

#### Scenario: Critic flags an unattributed WAIT-FOR-ENTRY despite positive aggregate reserved_pct
- **WHEN** the portfolio's `reserved_pct` is 12.0, but a specific `WAIT-FOR-ENTRY` position
  has no entry in `reserved_allocations`
- **THEN** the Critic SHALL produce a `WAIT_ENTRY_ZERO_ALLOC` finding with severity CRITICAL
  for that position, even though the aggregate bucket is non-zero

#### Scenario: Critic does not flag a properly attributed WAIT-FOR-ENTRY
- **WHEN** a `WAIT-FOR-ENTRY` position has a `reserved_allocations` entry with `pct=8.0`
- **THEN** the Critic SHALL NOT produce `WAIT_ENTRY_ZERO_ALLOC` for that position

### Requirement: Critic sentiment-based findings are out of scope when sentiment is unavailable
The Critic SHALL NOT raise a finding whose basis is a candidate's sentiment score or
sentiment trend when that candidate's `sentiment_available=False`.

#### Scenario: Critic skips sentiment-based critique for an unavailable-sentiment candidate
- **WHEN** a position's `sentiment_available=False`
- **THEN** the Critic's review of that position SHALL NOT cite `average_sentiment` or a
  sentiment trend as grounds for any finding
