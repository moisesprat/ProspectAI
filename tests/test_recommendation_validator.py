"""Tests for the degenerate entry-zone check in recommendation_validator (deferred item D-04-06-1).

A price-anchored LONG-BUY / WAIT-FOR-ENTRY (entry_zone_low == entry_zone_high == current_price) is
produced on purpose by the allocator and accepted by PortfolioBoundsValidator._is_price_anchored.
validate_portfolio must share that predicate instead of reporting it as a critical issue.
"""
import pytest

from utils.recommendation_validator import validate_portfolio, validate_position


def position(action="LONG-BUY", low=168.89, high=168.89, price=168.89, stop=163.82, target=181.56):
    return {
        "ticker": "TEST",
        "action": action,
        "current_price": price,
        "allocation_pct": 15.0,
        "trade_setup": {
            "entry_zone_low": low, "entry_zone_high": high,
            "stop_loss": stop, "take_profit": target,
        },
        "monitoring_triggers": [],
    }


def degenerate(issues):
    return [i for i in issues if i.severity == "critical" and "degenerate" in i.message]


@pytest.mark.parametrize("action", ["LONG-BUY", "WAIT-FOR-ENTRY"])
def test_price_anchored_zero_width_zone_is_not_degenerate(action):
    assert degenerate(validate_position(position(action=action))) == []


def test_price_anchored_zone_has_no_critical_issue_through_validate_portfolio():
    portfolio = {
        "positions": [position()],
        "deployed_pct": 15.0, "reserved_pct": 0.0, "cash_reserve_pct": 85.0,
    }
    assert [i for i in validate_portfolio(portfolio) if i.severity == "critical"] == []


def test_zero_width_zone_away_from_price_is_still_degenerate():
    # Not anchored: the zone is collapsed but sits away from current_price.
    issues = validate_position(position(low=170.0, high=170.0, price=168.89))
    assert len(degenerate(issues)) == 1


def test_near_zero_width_zone_is_still_degenerate():
    issues = validate_position(position(low=170.0, high=170.1, price=170.0))
    assert len(degenerate(issues)) == 1


def test_zero_width_zone_without_a_price_is_still_degenerate():
    issues = validate_position(position(price=None))
    assert len(degenerate(issues)) == 1


def test_zero_width_zone_on_a_non_deployed_action_is_still_degenerate():
    issues = validate_position(position(action="MONITOR"))
    assert len(degenerate(issues)) == 1
