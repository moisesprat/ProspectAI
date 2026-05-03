"""
Tests for PortfolioAllocatorTool.
No network or mocking required — pure deterministic math.
"""

import json
import pytest

from utils.portfolio_allocator_tool import PortfolioAllocatorTool


@pytest.fixture
def tool():
    return PortfolioAllocatorTool()


def _run(tool, stocks: list) -> dict:
    """Call _run() with a stock list and return the parsed result dict."""
    return json.loads(tool._run(json.dumps(stocks)))


def _stock(ticker, action, score=50, low=100.0, high=105.0, price=102.0):
    return {
        "ticker": ticker,
        "action": action,
        "composite_score": score,
        "entry_zone_low": low,
        "entry_zone_high": high,
        "current_price": price,
    }


def _find(result, ticker):
    return next(s for s in result["stocks"] if s["ticker"] == ticker)


# ── Allocation tests ───────────────────────────────────────────────────────────

def test_single_long_buy_gets_max_allocation(tool):
    result = _run(tool, [_stock("AAPL", "LONG-BUY", score=75)])
    assert _find(result, "AAPL")["allocation_pct"] == pytest.approx(40.0, abs=0.1)


def test_two_equal_long_buy_split_evenly(tool):
    result = _run(tool, [
        _stock("AAPL", "LONG-BUY", score=50),
        _stock("MSFT", "LONG-BUY", score=50),
    ])
    aapl = _find(result, "AAPL")["allocation_pct"]
    msft = _find(result, "MSFT")["allocation_pct"]
    assert aapl == pytest.approx(msft, abs=0.1)


def test_long_buy_allocation_capped_at_40(tool):
    result = _run(tool, [
        _stock("AAPL", "LONG-BUY", score=90),
        _stock("MSFT", "LONG-BUY", score=10),
    ])
    assert _find(result, "AAPL")["allocation_pct"] <= 40.0


def test_scaled_entry_allocation_capped_at_20(tool):
    result = _run(tool, [_stock("TSLA", "SCALED-ENTRY", score=80, price=150.0)])
    assert _find(result, "TSLA")["allocation_pct"] == pytest.approx(20.0, abs=0.1)


def test_wait_for_entry_allocation_capped_at_15(tool):
    result = _run(tool, [_stock("AMZN", "WAIT-FOR-ENTRY", score=70)])
    assert _find(result, "AMZN")["allocation_pct"] == pytest.approx(15.0, abs=0.1)


def test_monitor_and_avoid_get_zero_allocation(tool):
    result = _run(tool, [
        _stock("IBM",  "MONITOR", score=60),
        _stock("GE",   "AVOID",   score=40),
        _stock("AAPL", "LONG-BUY", score=75),
    ])
    assert _find(result, "IBM")["allocation_pct"] == 0.0
    assert _find(result, "GE")["allocation_pct"]  == 0.0


# ── Trade setup formula tests ──────────────────────────────────────────────────

def test_long_buy_zone_anchored_stop_and_tp(tool):
    result = _run(tool, [_stock("AAPL", "LONG-BUY", low=100.0, high=105.0, price=102.0)])
    setup = _find(result, "AAPL")["trade_setup"]
    assert setup["stop_loss"]   == pytest.approx(97.0,  abs=0.01)
    assert setup["take_profit"] == pytest.approx(111.0, abs=0.01)


def test_wait_for_entry_zone_anchored_formula(tool):
    result = _run(tool, [_stock("AMZN", "WAIT-FOR-ENTRY", low=200.0, high=210.0, price=205.0)])
    setup = _find(result, "AMZN")["trade_setup"]
    assert setup["stop_loss"]   == pytest.approx(194.0, abs=0.01)
    assert setup["take_profit"] == pytest.approx(222.0, abs=0.01)


def test_long_buy_trade_setup_invariant(tool):
    result = _run(tool, [_stock("AAPL", "LONG-BUY", low=100.0, high=105.0, price=102.0)])
    setup = _find(result, "AAPL")["trade_setup"]
    assert setup["stop_loss"] < setup["entry_zone_low"]
    assert setup["entry_zone_low"] <= setup["entry_zone_high"]
    assert setup["take_profit"] > setup["entry_zone_high"]


def test_scaled_entry_immediate_tranche_anchored_to_current_price(tool):
    result = _run(tool, [_stock("TSLA", "SCALED-ENTRY", low=140.0, high=145.0, price=150.0)])
    immediate = _find(result, "TSLA")["scaled_entry_setups"][0]
    assert immediate["stop_loss"]   == pytest.approx(145.5, abs=0.01)
    assert immediate["take_profit"] == pytest.approx(159.0, abs=0.01)


def test_scaled_entry_pullback_tranche_zone_anchored(tool):
    result = _run(tool, [_stock("TSLA", "SCALED-ENTRY", low=140.0, high=145.0, price=150.0)])
    pullback = _find(result, "TSLA")["scaled_entry_setups"][1]
    assert pullback["stop_loss"]   == pytest.approx(135.8, abs=0.01)
    assert pullback["take_profit"] == pytest.approx(153.4, abs=0.01)


def test_scaled_entry_trade_setup_is_null_and_has_two_setups(tool):
    result = _run(tool, [_stock("TSLA", "SCALED-ENTRY", low=140.0, high=145.0, price=150.0)])
    stock = _find(result, "TSLA")
    assert stock["trade_setup"] is None
    assert len(stock["scaled_entry_setups"]) == 2


def test_monitor_avoid_trade_setup_and_scaled_are_null(tool):
    result = _run(tool, [
        _stock("IBM", "MONITOR"),
        _stock("GE",  "AVOID"),
    ])
    for ticker in ("IBM", "GE"):
        s = _find(result, ticker)
        assert s["trade_setup"] is None
        assert s["scaled_entry_setups"] is None


# ── Capital bucket tests ───────────────────────────────────────────────────────

def test_long_buy_contributes_fully_to_deployed(tool):
    result = _run(tool, [_stock("AAPL", "LONG-BUY", score=75)])
    assert result["deployed_pct"]     == pytest.approx(40.0, abs=0.1)
    assert result["reserved_pct"]     == pytest.approx(0.0,  abs=0.1)
    assert result["cash_reserve_pct"] == pytest.approx(60.0, abs=0.1)


def test_scaled_entry_splits_evenly_between_deployed_and_reserved(tool):
    result = _run(tool, [_stock("TSLA", "SCALED-ENTRY", score=80, price=150.0)])
    assert result["deployed_pct"]     == pytest.approx(10.0, abs=0.1)
    assert result["reserved_pct"]     == pytest.approx(10.0, abs=0.1)
    assert result["cash_reserve_pct"] == pytest.approx(80.0, abs=0.1)


def test_wait_for_entry_contributes_fully_to_reserved(tool):
    result = _run(tool, [_stock("AMZN", "WAIT-FOR-ENTRY", score=70)])
    assert result["deployed_pct"]     == pytest.approx(0.0,  abs=0.1)
    assert result["reserved_pct"]     == pytest.approx(15.0, abs=0.1)
    assert result["cash_reserve_pct"] == pytest.approx(85.0, abs=0.1)


def test_mixed_actions_produce_correct_bucket_totals(tool):
    # With dominant scores all three positions hit their caps:
    # LONG-BUY→40, SCALED-ENTRY→20, WAIT-FOR-ENTRY→15
    # deployed = 40 + 20/2 = 50, reserved = 15 + 20/2 = 25, cash = 25
    result = _run(tool, [
        _stock("AAPL", "LONG-BUY",       score=60, low=100.0, high=105.0, price=102.0),
        _stock("TSLA", "SCALED-ENTRY",   score=40, low=140.0, high=145.0, price=150.0),
        _stock("AMZN", "WAIT-FOR-ENTRY", score=30, low=200.0, high=210.0, price=205.0),
    ])
    assert result["deployed_pct"]     == pytest.approx(50.0, abs=0.1)
    assert result["reserved_pct"]     == pytest.approx(25.0, abs=0.1)
    assert result["cash_reserve_pct"] == pytest.approx(25.0, abs=0.1)


def test_buckets_always_sum_to_100(tool):
    result = _run(tool, [
        _stock("AAPL", "LONG-BUY",     score=60, low=100.0, high=105.0, price=102.0),
        _stock("TSLA", "SCALED-ENTRY", score=40, low=140.0, high=145.0, price=150.0),
        _stock("IBM",  "MONITOR",      score=30),
    ])
    total = result["deployed_pct"] + result["reserved_pct"] + result["cash_reserve_pct"]
    assert total == pytest.approx(100.0, abs=0.1)


# ── Edge case tests ────────────────────────────────────────────────────────────

def test_invalid_json_returns_error(tool):
    result = json.loads(tool._run("not valid json {"))
    assert "error" in result


def test_empty_array_returns_error(tool):
    result = json.loads(tool._run("[]"))
    assert "error" in result


def test_missing_entry_zone_falls_back_to_current_price(tool):
    result = _run(tool, [{
        "ticker": "AAPL",
        "action": "LONG-BUY",
        "composite_score": 75,
        "entry_zone_low": 0,
        "entry_zone_high": 0,
        "current_price": 120.0,
    }])
    setup = _find(result, "AAPL")["trade_setup"]
    assert setup is not None
    assert setup["entry_zone_low"] == pytest.approx(120.0, abs=0.01)


def test_all_monitor_returns_zero_allocations_and_full_cash(tool):
    result = _run(tool, [
        _stock("AAPL", "MONITOR", score=80),
        _stock("MSFT", "MONITOR", score=60),
    ])
    for s in result["stocks"]:
        assert s["allocation_pct"] == 0.0
    assert result["deployed_pct"]     == 0.0
    assert result["cash_reserve_pct"] == pytest.approx(100.0, abs=0.1)
