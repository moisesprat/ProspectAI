"""
Portfolio Allocator Tool — deterministic allocation and trade setup calculation.

Takes the LLM's investment decisions (action per stock) as input and computes:
  - allocation_pct  proportional to composite_score, capped per risk profile
  - trade_setup     for LONG-BUY and WAIT-FOR-ENTRY positions
  - deployed_pct / reserved_pct / cash_reserve_pct  three-bucket capital breakdown

Profile bounds (from PROFILE_BOUNDS table):
  conservative: max 15% per position, stop 3% (0.97), R/R 2.5
  aggressive:   max 30% per position, stop 5% (0.95), R/R 1.5

All positions (LONG-BUY, WAIT-FOR-ENTRY) share the same per-profile cap.
MONITOR / AVOID always receive 0% allocation.

Three-bucket capital breakdown:
  deployed_pct   = LONG-BUY allocations (active capital)
  reserved_pct   = WAIT-FOR-ENTRY allocations (earmarked)
  cash_reserve   = 100 - deployed - reserved (unallocated free buffer)

Trade setup formulas (stop_multiplier and rr_ratio from PROFILE_BOUNDS):
  LONG-BUY in-zone (current_price ≤ entry_zone_high):
    stop_loss   = entry_zone_low × stop_multiplier
    take_profit = entry_zone_high + (entry_zone_low − stop_loss) × rr_ratio
    Invariant:  stop_loss < entry_zone_low ≤ entry_zone_high < take_profit

  LONG-BUY above-zone (current_price > entry_zone_high):
    stop_loss   = current_price × stop_multiplier
    take_profit = current_price + (current_price − stop_loss) × rr_ratio
    The zone values are preserved in entry_zone_low/high for context, but
    stop/TP are anchored to current_price so R/R is valid at actual entry.

  WAIT-FOR-ENTRY: same zone-anchored formula as in-zone LONG-BUY.

The LLM decided the actions. This tool only does the math from those decisions.
"""

import json
from crewai.tools import BaseTool

PROFILE_BOUNDS = {
    "conservative": {
        "max_alloc_pct":   15.0,
        "stop_multiplier": 0.97,
        "rr_ratio":        2.5,
    },
    "aggressive": {
        "max_alloc_pct":   30.0,
        "stop_multiplier": 0.95,
        "rr_ratio":        1.5,
    },
}


def _trade_setup(entry_zone_low: float, entry_zone_high: float, stop_multiplier: float, rr_ratio: float) -> dict:
    """Zone-anchored setup for LONG-BUY and WAIT-FOR-ENTRY positions."""
    stop_loss   = round(entry_zone_low * stop_multiplier, 2)
    take_profit = round(entry_zone_high + (entry_zone_low - stop_loss) * rr_ratio, 2)
    return {
        "direction":       "LONG-BUY",
        "entry_zone_low":  round(entry_zone_low,  2),
        "entry_zone_high": round(entry_zone_high, 2),
        "stop_loss":       stop_loss,
        "take_profit":     take_profit,
    }


def _trade_setup_price_anchored(current_price: float, entry_zone_low: float, entry_zone_high: float,
                                stop_multiplier: float, rr_ratio: float) -> dict:
    """Above-zone LONG-BUY: stop/TP anchored to current_price (valid R/R at actual entry).
    Zone values are preserved for user context but do not drive the math.
    """
    stop_loss   = round(current_price * stop_multiplier, 2)
    take_profit = round(current_price + (current_price - stop_loss) * rr_ratio, 2)
    return {
        "direction":       "LONG-BUY",
        "entry_zone_low":  round(entry_zone_low,  2),
        "entry_zone_high": round(entry_zone_high, 2),
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
        stocks_json: JSON object with a top-level "risk_profile" key and a "stocks" array:
        {
          "risk_profile": "conservative" | "aggressive",
          "stocks": [
            {
              "ticker":          <str>,
              "action":          <str>,   LLM-decided: LONG-BUY / WAIT-FOR-ENTRY / MONITOR / AVOID
              "composite_score": <float>, from compute_composite_scores
              "entry_zone_low":  <float>, from interpret_technical_indicators
              "entry_zone_high": <float>, from interpret_technical_indicators
              "current_price":   <float>  current market price
            },
            ...
          ]
        }

    Profile bounds applied by this tool (deterministic, not overridable by LLM):
      conservative: max 15% per position, stop 3% from zone/price, R/R 2.5
      aggressive:   max 30% per position, stop 5% from zone/price, R/R 1.5

    Returns JSON with:
        stocks: list of {ticker, action, allocation_pct, trade_setup}
        deployed_pct:        LONG-BUY allocations (active capital)
        reserved_pct:        WAIT-FOR-ENTRY allocations (earmarked)
        cash_reserve_pct:    100 - deployed - reserved (free unallocated buffer)
        total_allocated_pct: deployed + reserved

    trade_setup:
        LONG-BUY in-zone:    zone-anchored stop/TP (stop = entry_zone_low × stop_multiplier)
        LONG-BUY above-zone: price-anchored stop/TP (stop = current_price × stop_multiplier)
                             detected automatically when current_price > entry_zone_high
        WAIT-FOR-ENTRY:      zone-anchored formula; allocation_pct is earmarked
        MONITOR/AVOID:       null
    """

    def _run(self, stocks_json: str) -> str:
        try:
            payload = json.loads(stocks_json)
        except (json.JSONDecodeError, TypeError) as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

        # Support {"risk_profile": ..., "stocks": [...]} and legacy plain array
        if isinstance(payload, list):
            stocks_raw = payload
            risk_profile = "conservative"
        elif isinstance(payload, dict):
            raw_profile = payload.get("risk_profile", "conservative")
            if raw_profile not in PROFILE_BOUNDS:
                return json.dumps({"error": f"Unknown risk_profile {raw_profile!r}. Valid values: conservative, aggressive"})
            risk_profile = raw_profile
            stocks_raw = payload.get("stocks", [])
        else:
            return json.dumps({"error": "stocks_json must be a JSON array or object"})

        if not isinstance(stocks_raw, list) or len(stocks_raw) == 0:
            return json.dumps({"error": "stocks_json must be a non-empty JSON array"})

        bounds = PROFILE_BOUNDS[risk_profile]
        max_alloc_pct   = bounds["max_alloc_pct"]
        stop_multiplier = bounds["stop_multiplier"]
        rr_ratio        = bounds["rr_ratio"]

        try:
            results = []
            for s in stocks_raw:
                results.append({
                    "ticker":          str(s.get("ticker", "UNKNOWN")).upper(),
                    "action":          str(s.get("action", "MONITOR")),
                    "composite_score": float(s.get("composite_score", 0)),
                    "entry_zone_low":  float(s.get("entry_zone_low",  0)),
                    "entry_zone_high": float(s.get("entry_zone_high", 0)),
                    "current_price":   float(s.get("current_price",   0)),
                })

            DEPLOYED_ACTIONS = ("LONG-BUY", "WAIT-FOR-ENTRY")

            # Single profile-based cap for all deployed action types
            ticker_cap = {
                r["ticker"]: max_alloc_pct
                for r in results if r["action"] in DEPLOYED_ACTIONS
            }

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
                largest = max(final_allocs, key=lambda t: final_allocs.get(t, 0.0))
                drift = round(total_deployed_round - sum(final_allocs.values()), 1)
                if drift != 0:
                    final_allocs[largest] = round(final_allocs[largest] + drift, 1)

            # ── Resolve effective entry zones (fall back to current_price) ────
            for r in results:
                if r["action"] in ("LONG-BUY", "WAIT-FOR-ENTRY"):
                    if r["entry_zone_low"] <= 0:
                        r["entry_zone_low"] = r["current_price"]
                    if r["entry_zone_high"] <= 0:
                        r["entry_zone_high"] = r["current_price"]

            # ── Build per-position output ────────────────────────────────────
            output = []
            for r in results:
                if r["action"] == "LONG-BUY" and r["ticker"] in final_allocs:
                    alloc = final_allocs[r["ticker"]]
                    # Above-zone LONG-BUY: anchor stop/TP to current_price for valid R/R
                    if r["current_price"] > r["entry_zone_high"] > 0:
                        setup = _trade_setup_price_anchored(
                            r["current_price"], r["entry_zone_low"], r["entry_zone_high"],
                            stop_multiplier, rr_ratio,
                        )
                    else:
                        setup = _trade_setup(r["entry_zone_low"], r["entry_zone_high"], stop_multiplier, rr_ratio)
                elif r["action"] == "WAIT-FOR-ENTRY" and r["ticker"] in final_allocs:
                    alloc = final_allocs[r["ticker"]]
                    setup = _trade_setup(r["entry_zone_low"], r["entry_zone_high"], stop_multiplier, rr_ratio)
                else:  # MONITOR, AVOID
                    alloc = 0.0
                    setup = None

                output.append({
                    "ticker":         r["ticker"],
                    "action":         r["action"],
                    "allocation_pct": alloc,
                    "trade_setup":    setup,
                })

            # ── Three-bucket capital breakdown ───────────────────────────────
            deployed_total = 0.0
            reserved_total = 0.0
            for o in output:
                act = next(r["action"] for r in results if r["ticker"] == o["ticker"])
                if act == "LONG-BUY":
                    deployed_total += o["allocation_pct"]
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
