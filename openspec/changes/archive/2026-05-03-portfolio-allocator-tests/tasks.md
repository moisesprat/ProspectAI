## 1. Test file scaffolding

- [x] 1.1 Create `tests/test_tools_portfolio_allocator.py` with imports, a `PortfolioAllocatorTool` fixture, and a `_run` helper that parses the JSON response

## 2. Allocation tests

- [x] 2.1 Add test: single LONG-BUY receives 100% of allocated share (uncapped)
- [x] 2.2 Add test: two equal-score LONG-BUY positions split 50/50
- [x] 2.3 Add test: LONG-BUY allocation is capped at 40%
- [x] 2.4 Add test: SCALED-ENTRY allocation is capped at 20%
- [x] 2.5 Add test: WAIT-FOR-ENTRY allocation is capped at 15%
- [x] 2.6 Add test: MONITOR and AVOID positions receive 0% allocation

## 3. Trade setup formula tests

- [x] 3.1 Add test: LONG-BUY zone-anchored stop_loss and take_profit (entry_zone_low=100, high=105)
- [x] 3.2 Add test: WAIT-FOR-ENTRY uses same zone-anchored formula (entry_zone_low=200, high=210)
- [x] 3.3 Add test: LONG-BUY trade_setup invariant — stop < low ≤ high < take_profit
- [x] 3.4 Add test: SCALED-ENTRY immediate tranche anchored to current_price=150
- [x] 3.5 Add test: SCALED-ENTRY pullback tranche uses zone-anchored formula
- [x] 3.6 Add test: SCALED-ENTRY trade_setup is null, scaled_entry_setups has 2 entries
- [x] 3.7 Add test: MONITOR/AVOID have null trade_setup and null scaled_entry_setups

## 4. Capital bucket tests

- [x] 4.1 Add test: LONG-BUY contributes fully to deployed_pct
- [x] 4.2 Add test: SCALED-ENTRY splits evenly between deployed and reserved
- [x] 4.3 Add test: WAIT-FOR-ENTRY contributes fully to reserved_pct
- [x] 4.4 Add test: mixed LONG-BUY + SCALED-ENTRY + WAIT-FOR-ENTRY produces correct bucket totals
- [x] 4.5 Add test: deployed + reserved + cash_reserve always sums to 100

## 5. Edge case tests

- [x] 5.1 Add test: invalid JSON returns error dict
- [x] 5.2 Add test: empty array returns error dict
- [x] 5.3 Add test: missing entry zone falls back to current_price for LONG-BUY
- [x] 5.4 Add test: all-MONITOR input returns zero allocations and cash_reserve_pct=100

## 6. Verify

- [x] 6.1 Run `pytest tests/test_tools_portfolio_allocator.py -v` and confirm all tests pass
- [x] 6.2 Run `/test --coverage` and confirm portfolio_allocator_tool.py coverage is ≥ 90%
