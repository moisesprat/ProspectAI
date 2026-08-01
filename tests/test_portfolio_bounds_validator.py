"""
Tests for PortfolioBoundsValidator.
No network or mocking required — pure deterministic math.
"""

import json
import random

import pytest

from utils.portfolio_allocator_tool import PortfolioAllocatorTool, PROFILE_BOUNDS
from utils.portfolio_bounds_validator import BoundsViolationError, validate, validate_or_raise
from tests.fixtures_deterministic_enforcement import PUBLISHED_ENERGY_OUTPUT_BOUNDS_VIOLATION


def _position(ticker="AAPL", action="LONG-BUY", alloc=10.0, low=100.0, high=105.0,
              stop=97.0, tp=112.5, price=102.0):
    return {
        "ticker": ticker,
        "action": action,
        "allocation_pct": alloc,
        "current_price": price,
        "trade_setup": {
            "direction": "LONG-BUY",
            "entry_zone_low": low,
            "entry_zone_high": high,
            "stop_loss": stop,
            "take_profit": tp,
        },
    }


def _output(positions, deployed=10.0, reserved=0.0, cash=90.0, reserved_allocations=None):
    out = {
        "positions": positions,
        "deployed_pct": deployed,
        "reserved_pct": reserved,
        "cash_reserve_pct": cash,
    }
    if reserved_allocations is not None:
        out["reserved_allocations"] = reserved_allocations
    return out


# ── Compliant baseline ───────────────────────────────────────────────────────

def test_compliant_conservative_output_has_no_violations():
    # 100 * 0.97 = 97.0 stop (3%), tp = 105 + (100-97)*2.5 = 112.5 (R/R 2.5)
    out = _output([_position(alloc=15.0, low=100.0, high=105.0, stop=97.0, tp=112.5)])
    assert validate(out, "conservative") == []


def test_compliant_aggressive_output_has_no_violations():
    # 100 * 0.95 = 95.0 stop (5%), tp = 105 + (100-95)*1.5 = 112.5 (R/R 1.5)
    out = _output([_position(alloc=30.0, low=100.0, high=105.0, stop=95.0, tp=112.5)], deployed=30.0, cash=70.0)
    assert validate(out, "aggressive") == []


# ── Per-position violations ──────────────────────────────────────────────────

def test_allocation_over_conservative_cap_is_flagged():
    out = _output([_position(alloc=25.0, low=100.0, high=105.0, stop=97.0, tp=112.5)], deployed=25.0, cash=75.0)
    violations = validate(out, "conservative")
    assert any(v["rule"] == "allocation_cap" and v["ticker"] == "AAPL" for v in violations)


def test_stop_distance_over_conservative_cap_is_flagged():
    # stop is 5.16% below entry_zone_low, conservative cap is 3%
    out = _output([_position(low=155.0, high=158.0, stop=147.0, tp=180.0)])
    violations = validate(out, "conservative")
    assert any(v["rule"] == "stop_distance_cap" for v in violations)


def test_rr_below_conservative_minimum_is_flagged():
    # risk = 100-98 = 2, reward = 103-105 -> would be negative; use a low-R/R but valid setup
    out = _output([_position(low=100.0, high=105.0, stop=97.0, tp=106.0)])  # reward=1, risk=3 -> RR=0.33
    violations = validate(out, "conservative")
    assert any(v["rule"] == "min_rr_ratio" for v in violations)


def test_trade_setup_invariant_violation_is_flagged():
    out = _output([_position(low=100.0, high=95.0, stop=97.0, tp=112.5)])  # low > high
    violations = validate(out, "conservative")
    assert any(v["rule"] == "trade_setup_invariant" for v in violations)


def test_zero_width_zone_is_flagged_when_not_price_anchored():
    out = _output([_position(low=100.0, high=100.0, stop=97.0, tp=112.5, price=150.0)])
    violations = validate(out, "conservative")
    assert any(v["rule"] == "min_entry_zone_width" for v in violations)


def test_zero_width_zone_is_not_flagged_when_price_anchored():
    # entry_zone_low == entry_zone_high == current_price: the deliberate
    # above-zone LONG-BUY case (PortfolioAllocatorTool._trade_setup_price_anchored).
    out = _output([_position(low=150.0, high=150.0, stop=142.5, tp=161.25, price=150.0)])
    violations = validate(out, "conservative")
    assert not any(v["rule"] == "min_entry_zone_width" for v in violations)


# ── Portfolio-level violations ───────────────────────────────────────────────

def test_bucket_sum_not_100_is_flagged():
    out = _output([_position(alloc=15.0)], deployed=15.0, reserved=10.0, cash=70.0)  # sums to 95
    violations = validate(out, "conservative")
    assert any(v["rule"] == "bucket_sum" for v in violations)


def test_reserved_allocations_sum_mismatch_is_flagged():
    pos = _position(ticker="AMZN", action="WAIT-FOR-ENTRY", alloc=12.0)
    out = _output([pos], deployed=0.0, reserved=12.0, cash=88.0,
                   reserved_allocations=[{"ticker": "AMZN", "pct": 8.0}])
    violations = validate(out, "conservative")
    assert any(v["rule"] == "reserved_allocation_sum_mismatch" for v in violations)


def test_wait_for_entry_without_reserved_allocation_entry_is_flagged():
    pos = _position(ticker="AMZN", action="WAIT-FOR-ENTRY", alloc=12.0)
    out = _output([pos], deployed=0.0, reserved=12.0, cash=88.0, reserved_allocations=[])
    violations = validate(out, "conservative")
    assert any(v["rule"] == "wait_entry_unattributed" and v["ticker"] == "AMZN" for v in violations)


# ── Regression: replay the published Energy-sector output ───────────────────

def test_published_energy_output_raises_bounds_violation_error():
    with pytest.raises(BoundsViolationError) as exc_info:
        validate_or_raise(PUBLISHED_ENERGY_OUTPUT_BOUNDS_VIOLATION, "conservative")
    rules = {v["rule"] for v in exc_info.value.violations}
    assert "allocation_cap" in rules
    assert "stop_distance_cap" in rules


def test_unknown_risk_profile_raises_value_error():
    with pytest.raises(ValueError):
        validate(_output([_position()]), "moderate")


# ── Property test: allocate_portfolio output always passes the validator ────

@pytest.mark.parametrize("risk_profile", ["conservative", "aggressive"])
def test_allocator_output_always_passes_bounds_validator(risk_profile):
    rng = random.Random(42)
    tool = PortfolioAllocatorTool()
    actions = ["LONG-BUY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID"]

    for _ in range(200):
        n = rng.randint(1, 5)
        stocks = []
        for i in range(n):
            low = round(rng.uniform(10.0, 500.0), 2)
            width_pct = rng.uniform(0.005, 0.05)
            high = round(low * (1 + width_pct), 2)
            price = round(rng.uniform(low * 0.98, high * 1.05), 2)
            stocks.append({
                "ticker": f"T{i}",
                "action": rng.choice(actions),
                "composite_score": round(rng.uniform(0.0, 100.0), 1),
                "entry_zone_low": low,
                "entry_zone_high": high,
                "current_price": price,
            })

        payload = {"risk_profile": risk_profile, "stocks": stocks}
        result = json.loads(tool._run(json.dumps(payload)))
        assert "error" not in result, result

        # Reshape allocator output into the InvestorStrategicOutput-like shape
        # the validator expects (positions carry current_price + trade_setup).
        by_ticker_price = {s["ticker"]: s["current_price"] for s in stocks}
        positions = []
        for o in result["stocks"]:
            positions.append({
                "ticker": o["ticker"],
                "action": o["action"],
                "allocation_pct": o["allocation_pct"],
                "current_price": by_ticker_price[o["ticker"]],
                "trade_setup": o["trade_setup"],
            })
        final_output = {
            "positions": positions,
            "deployed_pct": result["deployed_pct"],
            "reserved_pct": result["reserved_pct"],
            "cash_reserve_pct": 100.0 - result["deployed_pct"] - result["reserved_pct"],
        }
        if "reserved_allocations" in result:
            final_output["reserved_allocations"] = result["reserved_allocations"]

        violations = validate(final_output, risk_profile)
        assert violations == [], (payload, result, violations)
