## ADDED Requirements

### Requirement: STEP 3 branches on entry_zone_status, not raw numeric thresholds
The Draft Strategist's STEP 3 SHALL use the pre-computed `entry_zone_status` field
(`CURRENT_ENTRY`, `PULLBACK_ENTRY`, `BELOW_ZONE`) as the primary action pivot.
The LLM MUST NOT recalculate RSI gaps, percentage distances, or price-to-zone arithmetic.
All numeric derivations are already encapsulated in the signals provided by the technical tool.

#### Scenario: LLM uses entry_zone_status as decision input
- **WHEN** the technical tool returns `entry_zone_status=PULLBACK_ENTRY` for a stock
- **THEN** the LLM reasons from that classification rather than computing `(current_price - entry_zone_high) / entry_zone_high`

#### Scenario: LLM does not re-derive overbought condition from raw RSI
- **WHEN** the technical tool returns `stochastic_status=Overbought` and `rsi=74`
- **THEN** the LLM uses `stochastic_status=Overbought` as its overbought signal, not a threshold comparison against the raw RSI value

### Requirement: CURRENT_ENTRY defaults to LONG-BUY for both profiles
When `entry_zone_status=CURRENT_ENTRY`, both conservative and aggressive profiles SHALL
default to LONG-BUY. The LLM MAY override to MONITOR or AVOID only when
`financial_health=WEAK` OR (`overall_signal=BEARISH` AND no cited fundamental catalyst).

#### Scenario: In-zone stock becomes LONG-BUY under aggressive profile
- **WHEN** `entry_zone_status=CURRENT_ENTRY`, `financial_health=ADEQUATE`, `overall_signal=BULLISH`, `risk_profile=aggressive`
- **THEN** action SHALL be `LONG-BUY`

#### Scenario: In-zone stock becomes LONG-BUY under conservative profile with good signals
- **WHEN** `entry_zone_status=CURRENT_ENTRY`, `financial_health=STRONG`, `overall_signal=BULLISH`, `risk_profile=conservative`
- **THEN** action SHALL be `LONG-BUY`

#### Scenario: In-zone stock overridden to MONITOR when financial_health=WEAK
- **WHEN** `entry_zone_status=CURRENT_ENTRY`, `financial_health=WEAK`
- **THEN** action SHALL be `MONITOR` or `AVOID` regardless of profile

### Requirement: PULLBACK_ENTRY action differs materially between conservative and aggressive
When `entry_zone_status=PULLBACK_ENTRY`, the risk profile SHALL produce meaningfully
different default actions. Conservative defaults to WAIT-FOR-ENTRY; aggressive defaults
to LONG-BUY when the overall signal context supports it.

#### Scenario: Conservative PULLBACK_ENTRY defaults to WAIT-FOR-ENTRY
- **WHEN** `entry_zone_status=PULLBACK_ENTRY`, `risk_profile=conservative`, `overall_signal=BULLISH`, `momentum_score=6`
- **THEN** action SHALL be `WAIT-FOR-ENTRY`

#### Scenario: Conservative PULLBACK_ENTRY may become LONG-BUY with converging strong signals
- **WHEN** `entry_zone_status=PULLBACK_ENTRY`, `risk_profile=conservative`, `overall_signal=BULLISH`, `momentum_score≥7`, `regime=TRENDING`, `financial_health=STRONG`
- **THEN** action MAY be `LONG-BUY` with rationale citing all four converging signals

#### Scenario: Aggressive PULLBACK_ENTRY defaults to LONG-BUY with positive overall signal
- **WHEN** `entry_zone_status=PULLBACK_ENTRY`, `risk_profile=aggressive`, `overall_signal=BULLISH`, `momentum_score=6`, `financial_health=ADEQUATE`
- **THEN** action SHALL be `LONG-BUY`

#### Scenario: Aggressive PULLBACK_ENTRY becomes WAIT-FOR-ENTRY when signals are clearly negative
- **WHEN** `entry_zone_status=PULLBACK_ENTRY`, `risk_profile=aggressive`, `overall_signal=BEARISH`
- **THEN** action SHALL be `WAIT-FOR-ENTRY` regardless of composite_score

#### Scenario: Aggressive PULLBACK_ENTRY becomes WAIT-FOR-ENTRY when momentum is very weak and stochastic overbought
- **WHEN** `entry_zone_status=PULLBACK_ENTRY`, `risk_profile=aggressive`, `stochastic_status=Overbought`, `momentum_score<5`, `overall_signal=MIXED`
- **THEN** action SHALL be `WAIT-FOR-ENTRY`

### Requirement: BELOW_ZONE treated as MONITOR or AVOID for both profiles
When `entry_zone_status=BELOW_ZONE`, neither profile SHALL assign LONG-BUY or WAIT-FOR-ENTRY.
The stock has broken below its actionable range; the LLM SHALL assign MONITOR (if
fundamentals remain intact) or AVOID (if `financial_health=WEAK` or `overall_signal=BEARISH`).

#### Scenario: Below-zone stock with intact fundamentals becomes MONITOR
- **WHEN** `entry_zone_status=BELOW_ZONE`, `financial_health=ADEQUATE`, `overall_signal=MIXED`
- **THEN** action SHALL be `MONITOR`

#### Scenario: Below-zone stock with weak fundamentals becomes AVOID
- **WHEN** `entry_zone_status=BELOW_ZONE`, `financial_health=WEAK`
- **THEN** action SHALL be `AVOID`

### Requirement: SCALED-ENTRY is not a valid action
The valid action set SHALL be exactly: `LONG-BUY`, `WAIT-FOR-ENTRY`, `MONITOR`, `AVOID`.
`SCALED-ENTRY` SHALL NOT be produced by the LLM and SHALL be rejected by schema validation.

#### Scenario: Schema rejects SCALED-ENTRY action
- **WHEN** the LLM output contains `"action": "SCALED-ENTRY"` in any position
- **THEN** Pydantic validation SHALL raise a validation error

### Requirement: Hard stops are preserved regardless of profile
The following conditions SHALL override profile reasoning and are not subject to
LLM judgment:
- `price_data_error` present → MONITOR or AVOID only
- `financial_health=WEAK` → MONITOR or AVOID only
- `overall_signal=BEARISH` with `entry_zone_status=PULLBACK_ENTRY` → WAIT-FOR-ENTRY for both profiles
- `composite_score < 55` with no cited catalyst → MONITOR

#### Scenario: Price data error prevents any trade action
- **WHEN** a stock has `price_data_error` set (current_price is null)
- **THEN** action SHALL be `MONITOR` or `AVOID` regardless of other signals or profile
