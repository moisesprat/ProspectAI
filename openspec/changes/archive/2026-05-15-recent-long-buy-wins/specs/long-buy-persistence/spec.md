## ADDED Requirements

### Requirement: LONG-BUY positions are persisted on pipeline completion
The backend SHALL persist every position with `action == "LONG-BUY"` from the pipeline result into the `long-buy-history` Modal Dict immediately after a successful pipeline run completes.

#### Scenario: Pipeline produces two LONG-BUY positions
- **WHEN** a pipeline run completes with positions `[{ticker: "AAPL", action: "LONG-BUY", ...}, {ticker: "GOOG", action: "MONITOR", ...}, {ticker: "NVDA", action: "LONG-BUY", ...}]`
- **THEN** two records are written to `long-buy-history` with keys `{run_id}:AAPL` and `{run_id}:NVDA`

#### Scenario: Pipeline produces no LONG-BUY positions
- **WHEN** a pipeline run completes with all positions having action "MONITOR" or "AVOID"
- **THEN** no records are written to `long-buy-history`

#### Scenario: Persistence failure does not break SSE stream
- **WHEN** writing to the Modal Dict fails (e.g., transient infrastructure error)
- **THEN** the `pipeline_done` SSE event is still sent to the client and the stream closes normally

### Requirement: Record schema includes trigger_price
Each persisted record SHALL contain the fields: `ticker`, `sector`, `recommended_at` (ISO 8601 timestamp of the run), `entry_zone_low`, `entry_zone_high`, `entry_zone_mid` (computed as average of low and high), `run_id`, and `trigger_price` (the `current_price` from the pipeline position output, or `null` if not available).

#### Scenario: Record with trigger_price
- **WHEN** a LONG-BUY position has `current_price: 185.50`, `trade_setup.entry_zone_low: 180.00`, `trade_setup.entry_zone_high: 188.00`
- **THEN** the stored record has `trigger_price: 185.50`, `entry_zone_low: 180.00`, `entry_zone_high: 188.00`, `entry_zone_mid: 184.00`

#### Scenario: Record without current_price
- **WHEN** a LONG-BUY position has `current_price: null`
- **THEN** the stored record has `trigger_price: null`

### Requirement: Deduplication by run_id and ticker
Records SHALL be keyed as `{run_id}:{ticker}` to ensure the same pipeline run never creates duplicate entries for the same ticker, even if the persistence code runs more than once.

#### Scenario: Idempotent write
- **WHEN** persistence runs twice for the same pipeline result (e.g., due to a retry)
- **THEN** only one record per ticker per run exists in the dict (second write overwrites with identical data)
