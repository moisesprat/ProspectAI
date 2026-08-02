"""
Portfolio Bounds Validator — deterministic, fail-closed check of the final
published output against the same per-profile bounds `PortfolioAllocatorTool`
already enforces when it computes allocations. This exists because the tool
being correct does not guarantee its output survives untouched through the
Final Strategist LLM phase (see change deterministic-enforcement-v1-9-1).

Nothing here recomputes allocations — it only asserts that whatever numbers
are about to be published satisfy the invariants:
  - per-position allocation <= risk_profile's max_alloc_pct
  - stop distance from entry_zone_low <= risk_profile's stop tolerance
  - reward/risk >= risk_profile's rr_ratio
  - stop_loss < entry_zone_low <= entry_zone_high < take_profit
  - entry-zone width is non-degenerate (except for intentional price-anchored
    above-zone setups, where entry_zone_low == entry_zone_high == current_price
    by design)
  - deployed_pct + reserved_pct + cash_reserve_pct == 100 (± tolerance)
  - if reserved_allocations is present: it sums to reserved_pct, and every
    WAIT-FOR-ENTRY position has an attributed entry with pct > 0
  - no position with entry_zone_status=CURRENT_ENTRY is published as
    WAIT-FOR-ENTRY (the one logical/mechanical invariant that survives
    reasoning-depth-action-selection's loosened action-selection freedom --
    "wait for entry" is a contradiction once price is already in the zone).
    `ActionPolicyGate` only filters Critic directives on their way to the
    Final Strategist; it does not constrain what the Final Strategist
    decides on its own, so this check is the last line of defense against
    that specific invariant reaching publication.
"""

from typing import Any, Dict, List, Optional

from utils.portfolio_allocator_tool import PROFILE_BOUNDS

DEPLOYED_ACTIONS = ("LONG-BUY", "WAIT-FOR-ENTRY")
MIN_ENTRY_ZONE_WIDTH_FRACTION = 0.005  # matches technical_interpretation_tool's min_width
BUCKET_SUM_TOLERANCE = 0.5
_EPS = 1e-6
# Stop-distance and R/R are derived from stop_loss/take_profit values that the
# allocator rounds to 2 decimal places; for narrow entry zones that rounding
# can shift the resulting ratio by up to ~1 percentage point / 0.01 R/R units.
# This tolerance absorbs that rounding noise without masking a real bounds
# violation (a genuine violation from a hand-written/fabricated number, per the
# regression fixtures, is off by several percentage points, not fractions of one).
_RATIO_ROUNDING_TOLERANCE = 0.01


class BoundsViolationError(Exception):
    """Raised when a final portfolio output fails deterministic bounds validation.

    `violations` is a list of dicts: {"ticker", "rule", "expected", "actual"}.
    `ticker` is None for portfolio-level (non-per-position) violations.
    """

    def __init__(self, violations: List[Dict[str, Any]]):
        self.violations = violations
        summary = "; ".join(
            f"{v['ticker'] or 'portfolio'}/{v['rule']}: expected {v['expected']}, got {v['actual']}"
            for v in violations
        )
        super().__init__(f"{len(violations)} portfolio bounds violation(s): {summary}")


def _is_price_anchored(entry_zone_low: float, entry_zone_high: float, current_price: Optional[float]) -> bool:
    """True for the deliberate above-zone LONG-BUY case where the allocator
    collapses entry_zone_low/high to current_price (see
    PortfolioAllocatorTool._trade_setup_price_anchored). A zero-width zone is
    correct there, not a violation.
    """
    if current_price is None or current_price <= 0:
        return False
    return abs(entry_zone_low - entry_zone_high) < _EPS and abs(entry_zone_low - current_price) < 0.01


def validate(
    final_output: Dict[str, Any],
    risk_profile: str,
    entry_zone_status_by_ticker: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Return a list of violation dicts. Empty list means the output is compliant.

    `entry_zone_status_by_ticker` (ticker -> entry_zone_status, from the
    deterministic Phase-2 technical output) is optional but should always be
    passed by callers that have it -- without it, the CURRENT_ENTRY/
    WAIT-FOR-ENTRY invariant below cannot be checked.
    """
    if risk_profile not in PROFILE_BOUNDS:
        raise ValueError(f"Unknown risk_profile {risk_profile!r}. Valid values: {sorted(PROFILE_BOUNDS)}")

    bounds = PROFILE_BOUNDS[risk_profile]
    max_alloc_pct = bounds["max_alloc_pct"]
    max_stop_pct = round(1.0 - bounds["stop_multiplier"], 4)
    min_rr_ratio = bounds["rr_ratio"]
    zone_status = entry_zone_status_by_ticker or {}

    violations: List[Dict[str, Any]] = []
    positions = final_output.get("positions", [])

    for pos in positions:
        ticker = pos.get("ticker", "UNKNOWN")
        action = pos.get("action")
        alloc = float(pos.get("allocation_pct", 0.0) or 0.0)

        if action == "WAIT-FOR-ENTRY" and zone_status.get(str(ticker).upper()) == "CURRENT_ENTRY":
            violations.append({
                "ticker": ticker, "rule": "wait_for_entry_at_current_entry",
                "expected": "action != WAIT-FOR-ENTRY when entry_zone_status=CURRENT_ENTRY",
                "actual": "WAIT-FOR-ENTRY",
            })

        if action in DEPLOYED_ACTIONS and alloc > max_alloc_pct + _EPS:
            violations.append({
                "ticker": ticker, "rule": "allocation_cap",
                "expected": f"<= {max_alloc_pct}", "actual": alloc,
            })

        setup = pos.get("trade_setup")
        if action in DEPLOYED_ACTIONS and setup:
            low   = float(setup.get("entry_zone_low", 0.0) or 0.0)
            high  = float(setup.get("entry_zone_high", 0.0) or 0.0)
            stop  = float(setup.get("stop_loss", 0.0) or 0.0)
            tp    = float(setup.get("take_profit", 0.0) or 0.0)
            price = pos.get("current_price")

            if not (stop < low <= high < tp):
                violations.append({
                    "ticker": ticker, "rule": "trade_setup_invariant",
                    "expected": "stop_loss < entry_zone_low <= entry_zone_high < take_profit",
                    "actual": {"stop_loss": stop, "entry_zone_low": low, "entry_zone_high": high, "take_profit": tp},
                })
                continue  # further checks assume the invariant holds

            if low > 0:
                stop_distance_pct = round((low - stop) / low, 4)
                if stop_distance_pct > max_stop_pct + _RATIO_ROUNDING_TOLERANCE:
                    violations.append({
                        "ticker": ticker, "rule": "stop_distance_cap",
                        "expected": f"<= {max_stop_pct * 100:.1f}%",
                        "actual": f"{stop_distance_pct * 100:.2f}%",
                    })

            risk = low - stop
            reward = tp - high
            if risk > 0:
                rr = round(reward / risk, 4)
                if rr < min_rr_ratio - _RATIO_ROUNDING_TOLERANCE:
                    violations.append({
                        "ticker": ticker, "rule": "min_rr_ratio",
                        "expected": f">= {min_rr_ratio}", "actual": rr,
                    })

            if not _is_price_anchored(low, high, price):
                min_width = round(high * MIN_ENTRY_ZONE_WIDTH_FRACTION, 2) if high > 0 else 0.0
                if high - low < min_width - _EPS:
                    violations.append({
                        "ticker": ticker, "rule": "min_entry_zone_width",
                        "expected": f">= {min_width}", "actual": round(high - low, 4),
                    })

    deployed = float(final_output.get("deployed_pct", 0.0) or 0.0)
    reserved = float(final_output.get("reserved_pct", 0.0) or 0.0)
    cash     = float(final_output.get("cash_reserve_pct", 0.0) or 0.0)
    total    = round(deployed + reserved + cash, 4)
    if abs(total - 100.0) > BUCKET_SUM_TOLERANCE:
        violations.append({
            "ticker": None, "rule": "bucket_sum",
            "expected": "100 ± 0.5", "actual": total,
        })

    reserved_allocations = final_output.get("reserved_allocations")
    if reserved_allocations is not None:
        summed = round(sum(float(r.get("pct", 0.0) or 0.0) for r in reserved_allocations), 2)
        if abs(summed - reserved) > BUCKET_SUM_TOLERANCE:
            violations.append({
                "ticker": None, "rule": "reserved_allocation_sum_mismatch",
                "expected": reserved, "actual": summed,
            })
        attributed = {
            r.get("ticker") for r in reserved_allocations
            if float(r.get("pct", 0.0) or 0.0) > 0
        }
        for pos in positions:
            if pos.get("action") == "WAIT-FOR-ENTRY" and pos.get("ticker") not in attributed:
                violations.append({
                    "ticker": pos.get("ticker"), "rule": "wait_entry_unattributed",
                    "expected": "entry in reserved_allocations with pct > 0", "actual": "missing",
                })

    return violations


def validate_or_raise(
    final_output: Dict[str, Any],
    risk_profile: str,
    entry_zone_status_by_ticker: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Convenience wrapper: raises BoundsViolationError if non-compliant, else returns input unchanged."""
    violations = validate(final_output, risk_profile, entry_zone_status_by_ticker)
    if violations:
        raise BoundsViolationError(violations)
    return final_output
