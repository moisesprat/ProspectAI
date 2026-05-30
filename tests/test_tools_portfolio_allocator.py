"""
Tests for PortfolioAllocatorTool.
No network or mocking required — pure deterministic math.
"""

import json
import pytest

from utils.portfolio_allocator_tool import PortfolioAllocatorTool, PROFILE_BOUNDS


@pytest.fixture
def tool():
    return PortfolioAllocatorTool()


def _run(tool, stocks: list, risk_profile: str = "conservative") -> dict:
    """Call _run() with a stock list and explicit risk_profile."""
    payload = {"risk_profile": risk_profile, "stocks": stocks}
    return json.loads(tool._run(json.dumps(payload)))


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


# ── Profile bounds constants ───────────────────────────────────────────────────

def test_profile_bounds_table_has_both_profiles():
    assert "conservative" in PROFILE_BOUNDS
    assert "aggressive" in PROFILE_BOUNDS


def test_conservative_bounds():
    b = PROFILE_BOUNDS["conservative"]
    assert b["max_alloc_pct"] == 15.0
    assert b["stop_multiplier"] == pytest.approx(0.97)
    assert b["rr_ratio"] == pytest.approx(2.5)


def test_aggressive_bounds():
    b = PROFILE_BOUNDS["aggressive"]
    assert b["max_alloc_pct"] == 30.0
    assert b["stop_multiplier"] == pytest.approx(0.95)
    assert b["rr_ratio"] == pytest.approx(1.5)


# ── Allocation tests — conservative ───────────────────────────────────────────

def test_conservative_single_long_buy_capped_at_15(tool):
    result = _run(tool, [_stock("AAPL", "LONG-BUY", score=75)], "conservative")
    assert _find(result, "AAPL")["allocation_pct"] == pytest.approx(15.0, abs=0.1)




def test_conservative_single_wait_for_entry_capped_at_15(tool):
    result = _run(tool, [_stock("AMZN", "WAIT-FOR-ENTRY", score=70)], "conservative")
    assert _find(result, "AMZN")["allocation_pct"] == pytest.approx(15.0, abs=0.1)


# ── Allocation tests — aggressive ─────────────────────────────────────────────

def test_aggressive_single_long_buy_capped_at_30(tool):
    result = _run(tool, [_stock("AAPL", "LONG-BUY", score=75)], "aggressive")
    assert _find(result, "AAPL")["allocation_pct"] == pytest.approx(30.0, abs=0.1)


def test_aggressive_dominant_long_buy_capped_at_30(tool):
    result = _run(tool, [
        _stock("AAPL", "LONG-BUY", score=90),
        _stock("MSFT", "LONG-BUY", score=10),
    ], "aggressive")
    assert _find(result, "AAPL")["allocation_pct"] <= 30.0


# ── Allocation tests — shared behaviour ───────────────────────────────────────

def test_two_equal_long_buy_split_evenly(tool):
    for profile in ("conservative", "aggressive"):
        result = _run(tool, [
            _stock("AAPL", "LONG-BUY", score=50),
            _stock("MSFT", "LONG-BUY", score=50),
        ], profile)
        aapl = _find(result, "AAPL")["allocation_pct"]
        msft = _find(result, "MSFT")["allocation_pct"]
        assert aapl == pytest.approx(msft, abs=0.1)


def test_monitor_and_avoid_get_zero_allocation(tool):
    for profile in ("conservative", "aggressive"):
        result = _run(tool, [
            _stock("IBM",  "MONITOR",  score=60),
            _stock("GE",   "AVOID",    score=40),
            _stock("AAPL", "LONG-BUY", score=75),
        ], profile)
        assert _find(result, "IBM")["allocation_pct"] == 0.0
        assert _find(result, "GE")["allocation_pct"]  == 0.0


# ── Trade setup formula tests — conservative ──────────────────────────────────

def test_conservative_long_buy_stop_and_tp(tool):
    # stop = 100 × 0.97 = 97.0, tp = 105 + (100 - 97) × 2.5 = 112.5
    result = _run(tool, [_stock("AAPL", "LONG-BUY", low=100.0, high=105.0, price=102.0)], "conservative")
    setup = _find(result, "AAPL")["trade_setup"]
    assert setup["stop_loss"]   == pytest.approx(97.0,  abs=0.01)
    assert setup["take_profit"] == pytest.approx(112.5, abs=0.01)


def test_conservative_wait_for_entry_stop_and_tp(tool):
    # stop = 200 × 0.97 = 194.0, tp = 210 + (200 - 194) × 2.5 = 225.0
    result = _run(tool, [_stock("AMZN", "WAIT-FOR-ENTRY", low=200.0, high=210.0, price=205.0)], "conservative")
    setup = _find(result, "AMZN")["trade_setup"]
    assert setup["stop_loss"]   == pytest.approx(194.0, abs=0.01)
    assert setup["take_profit"] == pytest.approx(225.0, abs=0.01)


# ── Trade setup formula tests — aggressive ────────────────────────────────────

def test_aggressive_long_buy_stop_and_tp(tool):
    # stop = 100 × 0.95 = 95.0, tp = 105 + (100 - 95) × 1.5 = 112.5
    result = _run(tool, [_stock("AAPL", "LONG-BUY", low=100.0, high=105.0, price=102.0)], "aggressive")
    setup = _find(result, "AAPL")["trade_setup"]
    assert setup["stop_loss"]   == pytest.approx(95.0,  abs=0.01)
    assert setup["take_profit"] == pytest.approx(112.5, abs=0.01)


# ── Above-zone LONG-BUY: current-price-anchored stop/TP ──────────────────────

def test_above_zone_long_buy_aggressive_uses_price_anchored_stop_tp(tool):
    # current_price=220 > entry_zone_high=213; aggressive: stop = 220 × 0.95 = 209.0
    # tp = 220 + (220 - 209) × 1.5 = 236.5
    result = _run(tool, [_stock("NVDA", "LONG-BUY", low=207.0, high=213.0, price=220.0)], "aggressive")
    setup = _find(result, "NVDA")["trade_setup"]
    assert setup["stop_loss"]   == pytest.approx(209.0, abs=0.01)
    assert setup["take_profit"] == pytest.approx(236.5, abs=0.01)


def test_above_zone_long_buy_conservative_uses_price_anchored_stop_tp(tool):
    # current_price=220 > entry_zone_high=213; conservative: stop = 220 × 0.97 = 213.4
    # tp = 220 + (220 - 213.4) × 2.5 = 236.5
    result = _run(tool, [_stock("NVDA", "LONG-BUY", low=207.0, high=213.0, price=220.0)], "conservative")
    setup = _find(result, "NVDA")["trade_setup"]
    assert setup["stop_loss"]   == pytest.approx(213.4, abs=0.01)
    assert setup["take_profit"] == pytest.approx(236.5, abs=0.01)


def test_above_zone_long_buy_full_allocation_in_deployed(tool):
    # above-zone LONG-BUY: full allocation in deployed, nothing in reserved
    result = _run(tool, [_stock("NVDA", "LONG-BUY", low=207.0, high=213.0, price=220.0)], "aggressive")
    assert result["deployed_pct"] == pytest.approx(30.0, abs=0.1)
    assert result["reserved_pct"] == pytest.approx(0.0,  abs=0.1)


def test_in_zone_long_buy_still_uses_zone_anchored_stop_tp(tool):
    # current_price=102 inside zone 100-105; conservative: stop = 100 × 0.97 = 97.0
    result = _run(tool, [_stock("AAPL", "LONG-BUY", low=100.0, high=105.0, price=102.0)], "conservative")
    setup = _find(result, "AAPL")["trade_setup"]
    assert setup["stop_loss"]   == pytest.approx(97.0,  abs=0.01)
    assert setup["take_profit"] == pytest.approx(112.5, abs=0.01)


# ── Trade setup invariants ─────────────────────────────────────────────────────

def test_trade_setup_invariant_holds_for_both_profiles(tool):
    for profile in ("conservative", "aggressive"):
        result = _run(tool, [_stock("AAPL", "LONG-BUY", low=100.0, high=105.0, price=102.0)], profile)
        setup = _find(result, "AAPL")["trade_setup"]
        assert setup["stop_loss"] < setup["entry_zone_low"]
        assert setup["entry_zone_low"] <= setup["entry_zone_high"]
        assert setup["take_profit"] > setup["entry_zone_high"]


def test_monitor_avoid_trade_setup_is_null(tool):
    result = _run(tool, [_stock("IBM", "MONITOR"), _stock("GE", "AVOID")])
    for ticker in ("IBM", "GE"):
        s = _find(result, ticker)
        assert s["trade_setup"] is None


# ── Capital bucket tests ───────────────────────────────────────────────────────

def test_conservative_long_buy_bucket_breakdown(tool):
    # single LONG-BUY capped at 15%: deployed=15, reserved=0, cash=85
    result = _run(tool, [_stock("AAPL", "LONG-BUY", score=75)], "conservative")
    assert result["deployed_pct"]     == pytest.approx(15.0, abs=0.1)
    assert result["reserved_pct"]     == pytest.approx(0.0,  abs=0.1)
    assert result["cash_reserve_pct"] == pytest.approx(85.0, abs=0.1)


def test_wait_for_entry_contributes_fully_to_reserved(tool):
    result = _run(tool, [_stock("AMZN", "WAIT-FOR-ENTRY", score=70)], "conservative")
    assert result["deployed_pct"]     == pytest.approx(0.0,  abs=0.1)
    assert result["reserved_pct"]     == pytest.approx(15.0, abs=0.1)
    assert result["cash_reserve_pct"] == pytest.approx(85.0, abs=0.1)


def test_conservative_mixed_actions_correct_buckets(tool):
    # LONG-BUY capped at 15% (deployed), WAIT-FOR-ENTRY capped at 15% (reserved), cash=70
    result = _run(tool, [
        _stock("AAPL", "LONG-BUY",       score=60, low=100.0, high=105.0, price=102.0),
        _stock("AMZN", "WAIT-FOR-ENTRY", score=30, low=200.0, high=210.0, price=205.0),
    ], "conservative")
    assert result["deployed_pct"]     == pytest.approx(15.0, abs=0.2)
    assert result["reserved_pct"]     == pytest.approx(15.0, abs=0.2)
    assert result["cash_reserve_pct"] == pytest.approx(70.0, abs=0.2)


def test_buckets_always_sum_to_100(tool):
    for profile in ("conservative", "aggressive"):
        result = _run(tool, [
            _stock("AAPL", "LONG-BUY",       score=60, low=100.0, high=105.0, price=102.0),
            _stock("AMZN", "WAIT-FOR-ENTRY", score=40, low=200.0, high=210.0, price=205.0),
            _stock("IBM",  "MONITOR",        score=30),
        ], profile)
        total = result["deployed_pct"] + result["reserved_pct"] + result["cash_reserve_pct"]
        assert total == pytest.approx(100.0, abs=0.1)


# ── Error / validation tests ───────────────────────────────────────────────────

def test_invalid_json_returns_error(tool):
    result = json.loads(tool._run("not valid json {"))
    assert "error" in result


def test_empty_array_returns_error(tool):
    result = json.loads(tool._run('{"risk_profile": "conservative", "stocks": []}'))
    assert "error" in result


def test_legacy_plain_array_defaults_to_conservative(tool):
    # Backward compat: plain array → conservative profile (15% cap)
    result = json.loads(tool._run(json.dumps([_stock("AAPL", "LONG-BUY", score=75)])))
    assert _find(result, "AAPL")["allocation_pct"] == pytest.approx(15.0, abs=0.1)


def test_unknown_risk_profile_returns_error(tool):
    payload = {"risk_profile": "moderate", "stocks": [_stock("AAPL", "LONG-BUY")]}
    result = json.loads(tool._run(json.dumps(payload)))
    assert "error" in result
    assert "moderate" in result["error"]


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


# ── Schema validation tests ────────────────────────────────────────────────────

def test_investor_strategic_output_accepts_risk_profile():
    from schemas.agent_outputs import InvestorStrategicOutput
    base_position = {
        "ticker": "AAPL",
        "action": "MONITOR",
        "composite_score": 60.0,
        "allocation_pct": 0.0,
        "rationale": "x" * 50,
        "monitoring_triggers": ["RSI drops below 55"],
        "review_frequency": "WEEKLY",
    }
    for profile in ("conservative", "aggressive"):
        output = InvestorStrategicOutput(
            sector="Technology",
            risk_profile=profile,
            positions=[base_position],  # type: ignore[arg-type]
            deployed_pct=0.0,
            reserved_pct=0.0,
            total_allocated_pct=0.0,
            cash_reserve_pct=100.0,
            overall_strategy="x" * 100,
            risk_level="Low",
        )
        assert output.risk_profile == profile


def test_investor_strategic_output_defaults_to_conservative():
    from schemas.agent_outputs import InvestorStrategicOutput
    output = InvestorStrategicOutput(
        sector="Technology",
        positions=[{  # type: ignore[arg-type]
            "ticker": "AAPL",
            "action": "MONITOR",
            "composite_score": 60.0,
            "allocation_pct": 0.0,
            "rationale": "x" * 50,
            "monitoring_triggers": ["RSI drops below 55"],
            "review_frequency": "WEEKLY",
        }],
        deployed_pct=0.0,
        reserved_pct=0.0,
        total_allocated_pct=0.0,
        cash_reserve_pct=100.0,
        overall_strategy="x" * 100,
        risk_level="Low",
    )
    assert output.risk_profile == "conservative"


def test_critic_output_accepts_risk_profile():
    from schemas.agent_outputs import CriticOutput, CritiqueItem
    critique = CritiqueItem(
        ticker="AAPL",
        severity="MINOR",
        issue_type="VAGUE_RATIONALE",
        finding="rationale does not cite specific RSI value",
        instruction="add RSI=67 and momentum_score to rationale text",
    )
    for profile in ("conservative", "aggressive"):
        output = CriticOutput(
            sector="Technology",
            risk_profile=profile,
            draft_assessment="x" * 50,
            per_ticker_critiques=[critique],
            portfolio_level_issues=[],
            revision_directives=["AAPL: add RSI to rationale"],
            approved_positions=[],
        )
        assert output.risk_profile == profile
