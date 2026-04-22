"""
Portfolio Allocator Tool — deterministic allocation and trade setup calculation.

Takes the LLM's investment decisions (action per stock) as input and computes:
  - allocation_pct  proportional to composite_score, capped per action type
  - trade_setup     for LONG-BUY and WAIT-FOR-ENTRY positions
  - scaled_entry_setups  for SCALED-ENTRY positions (2 setups)
  - deployed_pct / reserved_pct / cash_reserve_pct  three-bucket capital breakdown

Allocation caps:
  LONG-BUY        40%  — deployed now
  SCALED-ENTRY    20%  — half deployed now, half reserved (pullback tranche)
  WAIT-FOR-ENTRY  15%  — earmarked (reserved until entry trigger fires)
  MONITOR / AVOID  0%  — no capital

Three-bucket capital breakdown:
  deployed_pct   = LONG-BUY allocations + half of each SCALED-ENTRY allocation
  reserved_pct   = WAIT-FOR-ENTRY allocations + half of each SCALED-ENTRY allocation
  cash_reserve   = 100 - deployed - reserved (unallocated free buffer)

Trade setup formulas:
  LONG-BUY / WAIT-FOR-ENTRY (zone-anchored):
    stop_loss   = entry_zone_low × 0.97
    take_profit = entry_zone_high + (entry_zone_low − stop_loss) × 2
    Invariant:  stop_loss < entry_zone_low ≤ entry_zone_high < take_profit

  SCALED-ENTRY immediate tranche (current_price-anchored, R/R = 2.0):
    stop_loss   = current_price × 0.97   (3% below — stop anchored to current price)
    take_profit = current_price + (current_price − stop_loss) × 2  (6% above)
    R/R = 2.0 ≥ 1.5 invariant guaranteed by construction.
    CRITICAL: stop is NOT copied from the zone — entering above the zone with a
    zone-based stop produces an invalid R/R at the actual entry price.

  SCALED-ENTRY pullback tranche: same as LONG-BUY zone-anchored formula.

The LLM decided the actions. This tool only does the math from those decisions.
"""

import json
from crewai.tools import BaseTool


def _trade_setup(entry_zone_low: float, entry_zone_high: float) -> dict:
    """Zone-anchored setup for LONG-BUY and WAIT-FOR-ENTRY positions."""
    stop_loss   = round(entry_zone_low * 0.97, 2)
    take_profit = round(entry_zone_high + (entry_zone_low - stop_loss) * 2, 2)
    return {
        "direction":       "LONG-BUY",
        "entry_zone_low":  round(entry_zone_low,  2),
        "entry_zone_high": round(entry_zone_high, 2),
        "stop_loss":       stop_loss,
        "take_profit":     take_profit,
    }


def _trade_setup_immediate(current_price: float) -> dict:
    """Immediate tranche for SCALED-ENTRY: entered at current_price above the zone.
    Stop/TP anchored to current_price — never copied from the entry zone.
    R/R = 2.0 from current_price (stop 3% below, TP 6% above).
    """
    stop_loss   = round(current_price * 0.97, 2)
    take_profit = round(current_price + (current_price - stop_loss) * 2, 2)
    return {
        "direction":       "LONG-BUY",
        "entry_zone_low":  round(current_price, 2),
        "entry_zone_high": round(current_price, 2),
        "stop_loss":       stop_loss,
        "take_profit":     take_profit,
    }


class PortfolioAllocatorTool(BaseTool):
    name: str = "allocate_portfolio"
    description: str = """Compute portfolio allocations and trade setups from LLM-decided actions.

    Call this tool ONCE after the LLM has decided the action for every stock.
    Allocates capital proportionally among deployed/reserved positions and computes
    trade setups. Returns only math — no decisions.

    Args:
        stocks_json: JSON array, one object per stock:
        [
          {
            "ticker":          <str>,
            "action":          <str>,   LLM-decided: LONG-BUY / SCALED-ENTRY / WAIT-FOR-ENTRY / MONITOR / AVOID
            "composite_score": <float>, from compute_composite_scores
            "entry_zone_low":  <float>, from interpret_technical_indicators
            "entry_zone_high": <float>, from interpret_technical_indicators
            "current_price":   <float>  current market price (required for SCALED-ENTRY)
          },
          ...
        ]

    Returns JSON with:
        stocks: list of {ticker, action, allocation_pct, trade_setup, scaled_entry_setups}
        deployed_pct:        LONG-BUY + SCALED-ENTRY immediate tranches (active capital)
        reserved_pct:        WAIT-FOR-ENTRY + SCALED-ENTRY pullback tranches (earmarked)
        cash_reserve_pct:    100 - deployed - reserved (free unallocated buffer)
        total_allocated_pct: deployed + reserved (backward-compat sum)

    trade_setup:
        LONG-BUY:       zone-anchored stop/TP (stop = entry_zone_low × 0.97)
        WAIT-FOR-ENTRY: same zone-anchored formula; allocation_pct is earmarked (≤ 15%)
        SCALED-ENTRY:   null — execution details go in scaled_entry_setups
        MONITOR/AVOID:  null

    scaled_entry_setups: null for all actions except SCALED-ENTRY.
        SCALED-ENTRY: [immediate_tranche, pullback_tranche]
          immediate_tranche: R/R 2:1 anchored to current_price (stop 3%, TP 6%)
          pullback_tranche:  zone-anchored (same formula as LONG-BUY)

    Allocation caps: LONG-BUY 40% / SCALED-ENTRY 20% / WAIT-FOR-ENTRY 15%
    """

    def _run(self, stocks_json: str) -> str:
        try:
            stocks = json.loads(stocks_json)
        except (json.JSONDecodeError, TypeError) as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

        if not isinstance(stocks, list) or len(stocks) == 0:
            return json.dumps({"error": "stocks_json must be a non-empty JSON array"})

        try:
            results = []
            for s in stocks:
                results.append({
                    "ticker":          str(s.get("ticker", "UNKNOWN")).upper(),
                    "action":          str(s.get("action", "MONITOR")),
                    "composite_score": float(s.get("composite_score", 0)),
                    "entry_zone_low":  float(s.get("entry_zone_low",  0)),
                    "entry_zone_high": float(s.get("entry_zone_high", 0)),
                    "current_price":   float(s.get("current_price",   0)),
                })

            # ── Per-action allocation caps ───────────────────────────────────
            MAX_LONG_BUY_ALLOC       = 40.0
            MAX_SCALED_ENTRY_ALLOC   = 20.0
            MAX_WAIT_FOR_ENTRY_ALLOC = 15.0

            DEPLOYED_ACTIONS = ("LONG-BUY", "SCALED-ENTRY", "WAIT-FOR-ENTRY")

            # Build per-ticker cap lookup
            ticker_cap = {}
            for r in results:
                if r["action"] == "LONG-BUY":
                    ticker_cap[r["ticker"]] = MAX_LONG_BUY_ALLOC
                elif r["action"] == "SCALED-ENTRY":
                    ticker_cap[r["ticker"]] = MAX_SCALED_ENTRY_ALLOC
                elif r["action"] == "WAIT-FOR-ENTRY":
                    ticker_cap[r["ticker"]] = MAX_WAIT_FOR_ENTRY_ALLOC

            deployed    = [r for r in results if r["action"] in DEPLOYED_ACTIONS]
            score_total = sum(r["composite_score"] for r in deployed)

            # ── Proportional allocation with per-ticker cap (iterative) ──────
            raw_allocs = {}
            if score_total > 0:
                for r in deployed:
                    raw_allocs[r["ticker"]] = r["composite_score"] / score_total * 100.0

            capped = dict(raw_allocs)
            for _ in range(10):
                capped   = {t: min(v, ticker_cap[t]) for t, v in raw_allocs.items()}
                overflow = sum(v - ticker_cap[t] for t, v in raw_allocs.items()
                               if v > ticker_cap[t])
                if overflow < 0.01:
                    break
                under_cap = {t: v for t, v in capped.items() if v < ticker_cap[t]}
                if not under_cap:
                    break
                total_under = sum(under_cap.values())
                for t in under_cap:
                    capped[t] += overflow * (under_cap[t] / total_under)
                    capped[t]  = min(capped[t], ticker_cap[t])
                raw_allocs = capped

            # Round and fix rounding drift
            final_allocs = {t: round(v, 1) for t, v in capped.items()}
            total_deployed_round = round(sum(final_allocs.values()), 1)
            if final_allocs:
                largest = max(final_allocs, key=final_allocs.get)
                drift = round(total_deployed_round - sum(final_allocs.values()), 1)
                if drift != 0:
                    final_allocs[largest] = round(final_allocs[largest] + drift, 1)

            # ── Validate zone fields before computing setups ─────────────────
            for r in results:
                if r["action"] in ("LONG-BUY", "WAIT-FOR-ENTRY"):
                    if r["entry_zone_low"] <= 0 or r["entry_zone_high"] <= 0:
                        return json.dumps({
                            "error": (
                                f"{r['action']} for {r['ticker']} requires entry_zone_low > 0 "
                                f"and entry_zone_high > 0 to compute stop_loss and take_profit. "
                                f"Got entry_zone_low={r['entry_zone_low']}, "
                                f"entry_zone_high={r['entry_zone_high']}. "
                                f"Pass the values from interpret_technical_indicators for this ticker."
                            )
                        })
                if r["action"] == "SCALED-ENTRY" and r["current_price"] <= 0:
                    return json.dumps({
                        "error": (
                            f"SCALED-ENTRY for {r['ticker']} requires current_price > 0 "
                            f"to anchor the immediate tranche stop/TP. "
                            f"Pass current_price from the Technical Analysis output."
                        )
                    })

            # ── Build per-position output ────────────────────────────────────
            output = []
            for r in results:
                if r["action"] == "LONG-BUY" and r["ticker"] in final_allocs:
                    alloc  = final_allocs[r["ticker"]]
                    setup  = _trade_setup(r["entry_zone_low"], r["entry_zone_high"])
                    scaled = None
                elif r["action"] == "SCALED-ENTRY" and r["ticker"] in final_allocs:
                    alloc  = final_allocs[r["ticker"]]
                    setup  = None
                    scaled = [
                        _trade_setup_immediate(r["current_price"]),
                        _trade_setup(r["entry_zone_low"], r["entry_zone_high"]),
                    ]
                elif r["action"] == "WAIT-FOR-ENTRY" and r["ticker"] in final_allocs:
                    alloc  = final_allocs[r["ticker"]]   # earmarked, capped at 15%
                    setup  = _trade_setup(r["entry_zone_low"], r["entry_zone_high"])
                    scaled = None
                else:  # MONITOR, AVOID
                    alloc  = 0.0
                    setup  = None
                    scaled = None

                output.append({
                    "ticker":              r["ticker"],
                    "action":              r["action"],
                    "allocation_pct":      alloc,
                    "trade_setup":         setup,
                    "scaled_entry_setups": scaled,
                })

            # ── Three-bucket capital breakdown ───────────────────────────────
            deployed_total = 0.0
            reserved_total = 0.0
            for o in output:
                act = next(r["action"] for r in results if r["ticker"] == o["ticker"])
                if act == "LONG-BUY":
                    deployed_total += o["allocation_pct"]
                elif act == "SCALED-ENTRY":
                    half = round(o["allocation_pct"] / 2, 1)
                    deployed_total += half
                    reserved_total += half
                elif act == "WAIT-FOR-ENTRY":
                    reserved_total += o["allocation_pct"]

            deployed_total = round(deployed_total, 1)
            reserved_total = round(reserved_total, 1)
            cash_reserve   = round(100.0 - deployed_total - reserved_total, 1)

            return json.dumps({
                "stocks":              output,
                "deployed_pct":        deployed_total,
                "reserved_pct":        reserved_total,
                "cash_reserve_pct":    cash_reserve,
                "total_allocated_pct": round(deployed_total + reserved_total, 1),
            })

        except Exception as e:
            return json.dumps({"error": f"Computation error: {e}"})
