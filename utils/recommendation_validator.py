"""
Recommendation Validator — post-generation sanity checks on pipeline output.

Runs after the Investor Strategist output is parsed and before it reaches the
frontend. Detects contradictions, bad R/R ratios, and trigger proximity issues.
Exposes findings as ValidationIssue list; caller decides how to surface them.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class ValidationIssue:
    severity: str        # "critical" | "warning"
    ticker: str
    field: str
    message: str


def validate_position(position: Dict[str, Any]) -> List[ValidationIssue]:
    """Validate a single position dict from InvestorStrategicOutput.positions."""
    issues: List[ValidationIssue] = []
    ticker  = position.get("ticker", "UNKNOWN")
    action  = (position.get("action") or "").upper()
    setup   = position.get("trade_setup") or {}
    triggers = position.get("monitoring_triggers") or []

    entry_low   = setup.get("entry_zone_low")
    entry_high  = setup.get("entry_zone_high")
    stop_loss   = setup.get("stop_loss")
    take_profit = setup.get("take_profit")

    # ── TradeSetup invariant (should be caught by Pydantic, but belt-and-suspenders) ──
    if stop_loss is not None and entry_low is not None:
        if stop_loss >= entry_low:
            issues.append(ValidationIssue(
                severity="critical",
                ticker=ticker,
                field="trade_setup.stop_loss",
                message=(
                    f"stop_loss ({stop_loss}) >= entry_zone_low ({entry_low}) — "
                    "stop will trigger immediately on entry."
                ),
            ))

    if entry_high is not None and take_profit is not None:
        if take_profit <= entry_high:
            issues.append(ValidationIssue(
                severity="critical",
                ticker=ticker,
                field="trade_setup.take_profit",
                message=(
                    f"take_profit ({take_profit}) <= entry_zone_high ({entry_high}) — "
                    "no upside above entry zone."
                ),
            ))

    # ── Risk / Reward ratio ───────────────────────────────────────────────────
    if entry_low and take_profit and stop_loss and entry_low > stop_loss:
        upside   = take_profit - entry_low
        downside = entry_low - stop_loss
        rr = upside / downside if downside > 0 else 0
        if rr < 1.5:
            issues.append(ValidationIssue(
                severity="warning",
                ticker=ticker,
                field="trade_setup",
                message=(
                    f"R/R ratio is {rr:.1f}:1 — below 1.5:1 minimum "
                    f"(upside {upside:.2f} vs downside {downside:.2f})."
                ),
            ))

    # ── RSI trigger contradiction ─────────────────────────────────────────────
    # If action is LONG-BUY and a trigger fires at RSI=70, it will fire during
    # normal bullish execution when RSI is already > 60.
    for t in triggers:
        t_lower = t.lower()
        if "rsi" in t_lower and action in ("LONG-BUY", "HOLD"):
            m = re.search(r"rsi[^0-9]*(\d+)", t_lower)
            if m:
                trigger_rsi = int(m.group(1))
                if trigger_rsi <= 72:
                    issues.append(ValidationIssue(
                        severity="warning",
                        ticker=ticker,
                        field="monitoring_triggers",
                        message=(
                            f"RSI trigger fires at {trigger_rsi} but action is "
                            f"{action} — this will trigger during normal upward "
                            "momentum. Consider a higher threshold (≥75)."
                        ),
                    ))

    # ── Dividend yield trigger proximity ─────────────────────────────────────
    for t in triggers:
        if "dividend" in t.lower():
            m = re.search(r"(\d+\.\d+)\s*%", t)
            if m:
                trigger_yield = float(m.group(1))
                # We don't have the current yield in the position dict, but flag
                # very low trigger thresholds in a bullish position.
                if action == "LONG-BUY" and trigger_yield < 2.0:
                    issues.append(ValidationIssue(
                        severity="warning",
                        ticker=ticker,
                        field="monitoring_triggers",
                        message=(
                            f"Dividend trigger at {trigger_yield}% is very low "
                            "for a LONG-BUY position — may fire from normal price "
                            "appreciation compressing the yield."
                        ),
                    ))

    return issues


def validate_portfolio(portfolio: Dict[str, Any]) -> List[ValidationIssue]:
    """
    Validate a full InvestorStrategicOutput dict.
    Returns all issues found across all positions.
    """
    issues: List[ValidationIssue] = []

    positions = portfolio.get("positions") or []
    if not positions:
        return issues

    # ── Per-position checks ───────────────────────────────────────────────────
    for pos in positions:
        issues.extend(validate_position(pos))

    # ── Composite-score differentiation check ────────────────────────────────
    # If every active position has the same allocation, the LLM likely defaulted.
    long_buys = [p for p in positions if (p.get("action") or "").upper() == "LONG-BUY"]
    if len(long_buys) >= 3:
        allocs = [p.get("allocation_pct", 0) for p in long_buys]
        if len(set(allocs)) == 1:
            issues.append(ValidationIssue(
                severity="warning",
                ticker="PORTFOLIO",
                field="allocation_pct",
                message=(
                    "All LONG-BUY positions have identical allocation_pct "
                    f"({allocs[0]}%). Composite scores likely collapsed to the "
                    "same value — check that upstream sentiment/momentum inputs "
                    "are distinct per ticker."
                ),
            ))

    # ── Total allocation sanity ───────────────────────────────────────────────
    total = portfolio.get("total_allocated_pct", 0)
    cash  = portfolio.get("cash_reserve_pct", 0)
    if abs(total + cash - 100.0) > 1.0:
        issues.append(ValidationIssue(
            severity="critical",
            ticker="PORTFOLIO",
            field="total_allocated_pct",
            message=(
                f"total_allocated_pct ({total}) + cash_reserve_pct ({cash}) "
                f"= {total + cash:.1f}, expected ~100."
            ),
        ))

    return issues
