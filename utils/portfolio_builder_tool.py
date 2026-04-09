"""
Portfolio Builder Tool — deterministic composite scoring, action mapping,
portfolio allocation, and trade setup construction.

This tool is the single source of truth for ALL numeric outputs that appear in
the final InvestorStrategicOutput. The LLM's only job after calling this tool
is to write qualitative rationales and monitoring triggers.

Composite score formula (0-100):
  sentiment_component  = min(average_sentiment * 100, 30)   [max 30 pts]
  technical_component  = momentum_score * 4                  [max 40 pts]
  fundamental_component = financial_health_score + growth_score  [max 30 pts, min 0]
  composite_score = sum of above three, rounded to 1 decimal

Action mapping:
  >= 55 → LONG-BUY
  >= 40 → HOLD
  >= 25 → WAIT-FOR-ENTRY
  <  25 → AVOID

Trade setup (LONG-BUY only, invariant guaranteed):
  stop_loss   = entry_zone_low  × 0.97
  take_profit = entry_zone_high + (entry_zone_low − stop_loss) × 2
  Invariant:  stop_loss < entry_zone_low ≤ entry_zone_high < take_profit

Allocation:
  Proportional to composite_score among LONG-BUY stocks only.
  total_allocated_pct = sum of all allocation_pct.
  cash_reserve_pct    = 100 − total_allocated_pct.
"""

import json
from crewai.tools import BaseTool

_FINANCIAL_HEALTH_SCORE = {"STRONG": 20, "ADEQUATE": 10, "WEAK": 5}
_GROWTH_OUTLOOK_SCORE   = {"HIGH": 10, "MODERATE": 7, "LOW": 3, "DECLINING": 1}


def _composite_score(average_sentiment: float, momentum_score: float,
                     financial_health: str, growth_outlook: str) -> float:
    sentiment_component   = min(float(average_sentiment) * 100, 30)
    technical_component   = float(momentum_score) * 4
    fh_score              = _FINANCIAL_HEALTH_SCORE.get(str(financial_health).upper(), 5)
    growth_score          = _GROWTH_OUTLOOK_SCORE.get(str(growth_outlook).upper(), 5)
    fundamental_component = fh_score + growth_score
    return round(sentiment_component + technical_component + fundamental_component, 1)


def _action(score: float) -> str:
    if score >= 55:
        return "LONG-BUY"
    if score >= 40:
        return "HOLD"
    if score >= 25:
        return "WAIT-FOR-ENTRY"
    return "AVOID"


def _trade_setup(entry_zone_low: float, entry_zone_high: float) -> dict:
    stop_loss   = round(entry_zone_low  * 0.97, 2)
    take_profit = round(entry_zone_high + (entry_zone_low - stop_loss) * 2, 2)
    # Invariant is structurally guaranteed by the formula:
    # stop_loss = low * 0.97  < low  ≤  high  <  high + 2*(low-stop) = take_profit
    return {
        "direction":       "LONG-BUY",
        "entry_zone_low":  round(entry_zone_low,  2),
        "entry_zone_high": round(entry_zone_high, 2),
        "stop_loss":       stop_loss,
        "take_profit":     take_profit,
    }


class PortfolioBuilderTool(BaseTool):
    name: str = "build_portfolio"
    description: str = """Compute composite scores, actions, trade setups, and portfolio allocation.

    Call this tool ONCE with data for ALL stocks combined. Do NOT call it per ticker.
    Returns all numeric outputs for the final report — copy them into the JSON output verbatim.

    Args:
        stocks_json: JSON array, one object per stock:
        [
          {
            "ticker":            <str>,
            "average_sentiment": <float>,   from Market Analyst (−1.0 to 1.0)
            "momentum_score":    <float>,   from TechnicalInterpretationTool (0-10)
            "financial_health":  <str>,     from FundamentalGraderTool: STRONG/ADEQUATE/WEAK
            "growth_outlook":    <str>,     from FundamentalGraderTool: HIGH/MODERATE/LOW/DECLINING
            "entry_zone_low":    <float>,   from TechnicalInterpretationTool
            "entry_zone_high":   <float>    from TechnicalInterpretationTool
          },
          ...
        ]

    Returns JSON with:
        stocks: list of per-stock results (ticker, sentiment_component, technical_component,
                fundamental_component, composite_score, action, allocation_pct, trade_setup)
        total_allocated_pct, cash_reserve_pct
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
                ticker    = str(s.get("ticker", "UNKNOWN")).upper()
                sentiment = float(s.get("average_sentiment", 0))
                momentum  = float(s.get("momentum_score", 1))
                fh        = str(s.get("financial_health", "ADEQUATE")).upper()
                growth    = str(s.get("growth_outlook",   "MODERATE")).upper()
                ez_low    = float(s.get("entry_zone_low",  0))
                ez_high   = float(s.get("entry_zone_high", 0))

                sent_comp = round(min(sentiment * 100, 30), 1)
                tech_comp = round(momentum * 4, 1)
                fh_score  = _FINANCIAL_HEALTH_SCORE.get(fh, 5)
                gr_score  = _GROWTH_OUTLOOK_SCORE.get(growth, 5)
                fund_comp = fh_score + gr_score
                score     = round(sent_comp + tech_comp + fund_comp, 1)
                action    = _action(score)

                results.append({
                    "ticker":                ticker,
                    "sentiment_component":   sent_comp,
                    "technical_component":   tech_comp,
                    "fundamental_component": fund_comp,
                    "composite_score":       score,
                    "action":                action,
                    "entry_zone_low":        round(ez_low,  2),
                    "entry_zone_high":       round(ez_high, 2),
                })

            # ── Portfolio allocation (proportional among LONG-BUY only) ──────
            long_buys   = [r for r in results if r["action"] == "LONG-BUY"]
            score_total = sum(r["composite_score"] for r in long_buys)

            for r in results:
                if r["action"] == "LONG-BUY" and score_total > 0:
                    alloc = round(r["composite_score"] / score_total * 100, 1)
                    r["allocation_pct"] = alloc
                    r["trade_setup"]    = _trade_setup(r["entry_zone_low"], r["entry_zone_high"])
                else:
                    r["allocation_pct"] = 0.0
                    r["trade_setup"]    = None

            # Normalise rounding drift in allocation
            if long_buys:
                allocated = [r for r in results if r["allocation_pct"] > 0]
                diff      = round(100.0 - sum(r["allocation_pct"] for r in allocated), 1)
                if diff != 0 and allocated:
                    allocated[-1]["allocation_pct"] = round(
                        allocated[-1]["allocation_pct"] + diff, 1
                    )

            total_allocated = round(sum(r["allocation_pct"] for r in results), 1)
            cash_reserve    = round(100.0 - total_allocated, 1)

            # Remove working fields not needed in the output
            for r in results:
                del r["entry_zone_low"]
                del r["entry_zone_high"]

            return json.dumps({
                "stocks":             results,
                "total_allocated_pct": total_allocated,
                "cash_reserve_pct":   cash_reserve,
            })

        except Exception as e:
            return json.dumps({"error": f"Computation error: {e}"})
