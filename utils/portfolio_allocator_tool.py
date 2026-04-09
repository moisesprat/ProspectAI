"""
Portfolio Allocator Tool — deterministic allocation and trade setup calculation.

Takes the LLM's investment decisions (action per stock) as input and computes:
  - allocation_pct  proportional to composite_score among LONG-BUY stocks
  - trade_setup     stop_loss and take_profit for LONG-BUY positions
  - total_allocated_pct and cash_reserve_pct

Trade setup formula (LONG-BUY only, invariant guaranteed by construction):
  stop_loss   = entry_zone_low × 0.97
  take_profit = entry_zone_high + (entry_zone_low − stop_loss) × 2
  Invariant:  stop_loss < entry_zone_low ≤ entry_zone_high < take_profit

The LLM decided the actions. This tool only does the math from those decisions.
"""

import json
from crewai.tools import BaseTool


def _trade_setup(entry_zone_low: float, entry_zone_high: float) -> dict:
    stop_loss   = round(entry_zone_low * 0.97, 2)
    take_profit = round(entry_zone_high + (entry_zone_low - stop_loss) * 2, 2)
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
    Allocates capital proportionally among LONG-BUY positions and computes
    stop_loss / take_profit for each. Returns only math — no decisions.

    Args:
        stocks_json: JSON array, one object per stock:
        [
          {
            "ticker":          <str>,
            "action":          <str>,   LLM-decided: LONG-BUY / HOLD / WAIT-FOR-ENTRY / AVOID
            "composite_score": <float>, from compute_composite_scores
            "entry_zone_low":  <float>, from interpret_technical_indicators (required for LONG-BUY)
            "entry_zone_high": <float>  from interpret_technical_indicators (required for LONG-BUY)
          },
          ...
        ]

    Returns JSON with:
        stocks: list of {ticker, action, allocation_pct, trade_setup}
        total_allocated_pct, cash_reserve_pct

    trade_setup is null for any action other than LONG-BUY.
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
                    "action":          str(s.get("action", "HOLD")),
                    "composite_score": float(s.get("composite_score", 0)),
                    "entry_zone_low":  float(s.get("entry_zone_low",  0)),
                    "entry_zone_high": float(s.get("entry_zone_high", 0)),
                })

            # ── Proportional allocation among LONG-BUY positions ─────────────
            long_buys   = [r for r in results if r["action"] == "LONG-BUY"]
            score_total = sum(r["composite_score"] for r in long_buys)

            output = []
            for r in results:
                if r["action"] == "LONG-BUY" and score_total > 0:
                    alloc = round(r["composite_score"] / score_total * 100, 1)
                    setup = _trade_setup(r["entry_zone_low"], r["entry_zone_high"])
                else:
                    alloc = 0.0
                    setup = None

                output.append({
                    "ticker":        r["ticker"],
                    "action":        r["action"],
                    "allocation_pct": alloc,
                    "trade_setup":   setup,
                })

            # Correct rounding drift so allocations sum to exactly 100 %
            allocated = [o for o in output if o["allocation_pct"] > 0]
            if allocated:
                drift = round(100.0 - sum(o["allocation_pct"] for o in allocated), 1)
                if drift != 0:
                    allocated[-1]["allocation_pct"] = round(
                        allocated[-1]["allocation_pct"] + drift, 1
                    )

            total_allocated = round(sum(o["allocation_pct"] for o in output), 1)
            cash_reserve    = round(100.0 - total_allocated, 1)

            return json.dumps({
                "stocks":              output,
                "total_allocated_pct": total_allocated,
                "cash_reserve_pct":    cash_reserve,
            })

        except Exception as e:
            return json.dumps({"error": f"Computation error: {e}"})
