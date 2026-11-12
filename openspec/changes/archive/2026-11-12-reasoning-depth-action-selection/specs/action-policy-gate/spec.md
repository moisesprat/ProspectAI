## MODIFIED Requirements

### Requirement: Action-policy table is evaluated as data, not left to LLM adherence
The Flow SHALL encode the `entry_zone_status × risk_profile → allowed actions` table
as a data structure evaluated in code, keyed on `entry_zone_status` (`CURRENT_ENTRY`,
`PULLBACK_ENTRY`, `BELOW_ZONE`) and `risk_profile` (`conservative`, `aggressive`).
`BELOW_ZONE` SHALL permit `LONG-BUY`, `MONITOR`, and `AVOID` for both risk profiles,
excluding only `WAIT-FOR-ENTRY` — since price is already below the actionable zone, there
is nothing left to "wait" for it to fall into, but there is no logical objection to buying
below a broken zone if the LLM's reasoning supports it. The permission is not a mandate:
the table only makes `LONG-BUY` reachable, and the LLM stays free to choose `MONITOR` or
`AVOID`. The `FUNDAMENTALS_UNKNOWN` row (only `MONITOR` or `AVOID`) is applied on top of
the matched zone row, and a missing current price caps the action at `MONITOR` or `AVOID`,
so the `BELOW_ZONE` permission holds only for a position with gradable fundamentals and a
usable price (see `reasoning-action-selection`, "The surviving hard invariants").

#### Scenario: Table resolves the allowed action set for a given status and profile
- **WHEN** `entry_zone_status=CURRENT_ENTRY` for either `risk_profile`
- **THEN** the resolved allowed-action set includes `LONG-BUY` and excludes `WAIT-FOR-ENTRY`

#### Scenario: BELOW_ZONE permits LONG-BUY for both profiles
- **WHEN** `entry_zone_status=BELOW_ZONE` for either `risk_profile`
- **THEN** the resolved allowed-action set includes `LONG-BUY`, `MONITOR`, and `AVOID`, and excludes `WAIT-FOR-ENTRY`

#### Scenario: BELOW_ZONE with fundamentals that could not be graded still excludes LONG-BUY
- **WHEN** `entry_zone_status=BELOW_ZONE` and `fundamentals_status=UNKNOWN` for either `risk_profile`
- **THEN** the resolved allowed-action set is `MONITOR` and `AVOID` only

## ADDED Requirements

### Requirement: PortfolioAllocatorTool anchors below-zone LONG-BUY trade setups to current price
When a position has `action=LONG-BUY` and `current_price < entry_zone_low` (price below
the actionable zone), `PortfolioAllocatorTool` SHALL anchor the trade setup (entry zone,
stop-loss, take-profit) to `current_price` using the same price-anchored formula already
used for above-zone LONG-BUY positions, rather than anchoring to `entry_zone_low`/`entry_zone_high`
— a zone the current price is not actually in. This prevents a below-zone LONG-BUY (now
reachable since `BELOW_ZONE` permits `LONG-BUY`) from producing a `TradeSetup` whose entry
zone/stop sit above the current price while the position asserts an immediate buy.

The requirement specifies the deterministic setup only. It does not say that the LLM
chooses `LONG-BUY` below the zone: that choice stays with the LLM and depends on the risk
profile and the evidence (live replay under the aggressive profile chose `LONG-BUY` and
produced a price-anchored, correctly ordered setup; under the conservative profile it chose
`MONITOR`).

#### Scenario: Below-zone LONG-BUY anchors to current price
- **WHEN** a position has `action=LONG-BUY`, `current_price=90`, `entry_zone_low=95`, `entry_zone_high=100`
- **THEN** `PortfolioAllocatorTool` computes the trade setup's entry zone, stop-loss, and take-profit relative to `current_price=90`, not relative to `entry_zone_low=95`/`entry_zone_high=100`

#### Scenario: Below-zone LONG-BUY trade setup still satisfies the TradeSetup invariant
- **WHEN** a below-zone LONG-BUY trade setup is computed
- **THEN** `stop_loss < entry_zone_low <= entry_zone_high < take_profit` holds, with `entry_zone_low`/`entry_zone_high` collapsed to `current_price`
