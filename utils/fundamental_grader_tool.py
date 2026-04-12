"""
Fundamental Grader Tool — deterministic financial health grading.

Takes raw fundamental metrics already fetched by FundamentalDataTool and
applies all threshold-based grading rules without any LLM involvement:
  - valuation_grade  (P/E or P/S thresholds)
  - financial_health (current_ratio, D/E, FCF)
  - growth_outlook   (revenue_growth_yoy)

Scores never go negative — a bad metric earns the lowest positive score,
not a penalty.
"""

import json
from crewai.tools import BaseTool


_FINANCIAL_HEALTH_SCORE = {"STRONG": 20, "ADEQUATE": 10, "WEAK": 5}
_GROWTH_OUTLOOK_SCORE   = {"HIGH": 10, "MODERATE": 7, "LOW": 3, "DECLINING": 1}


class FundamentalGraderTool(BaseTool):
    name: str = "grade_fundamental_data"
    description: str = """Compute deterministic fundamental grades from raw financial metrics.

    Call this tool immediately after 'fetch_fundamental_data' for each ticker.
    Pass the raw fundamental metrics as a JSON string. Returns grades and numeric
    scores — no LLM calculation required.

    Args:
        ticker: Stock ticker symbol (e.g. 'AAPL')
        raw_fundamentals_json: JSON string with these fields (use null for missing):
            {
              "pe_ratio":            <float | null>,
              "ps_ratio":            <float | null>,
              "current_ratio":       <float | null>,
              "debt_to_equity":      <float | null>,   normalized ratio (e.g. 1.5, not 150)
              "free_cash_flow":      <float | null>,   in USD
              "revenue_growth_yoy":  <float | null>    decimal (e.g. 0.12 = 12 %)
            }

    Returns JSON with:
        ticker, valuation_grade, financial_health, growth_outlook,
        financial_health_score, growth_score, fundamental_component
        (= financial_health_score + growth_score, always >= 0)
    """

    def _run(self, ticker: str, raw_fundamentals_json: str) -> str:
        try:
            raw = json.loads(raw_fundamentals_json)
        except (json.JSONDecodeError, TypeError) as e:
            return json.dumps({"ticker": ticker, "error": f"Invalid JSON: {e}"})

        # If fetch_fundamental_data returned an error, propagate UNKNOWN so
        # downstream agents never invent or default fundamental scores.
        if "error" in raw:
            return json.dumps({
                "ticker":                  ticker.upper(),
                "fundamental_unknown":     True,
                "valuation_grade":         "UNKNOWN",
                "financial_health":        "UNKNOWN",
                "growth_outlook":          "UNKNOWN",
                "financial_health_score":  None,
                "growth_score":            None,
                "fundamental_component":   None,
            })

        try:
            pe  = raw.get("pe_ratio")
            ps  = raw.get("ps_ratio")
            cr  = raw.get("current_ratio")
            de  = raw.get("debt_to_equity")
            fcf = raw.get("free_cash_flow")
            rev = raw.get("revenue_growth_yoy")

            # ── Valuation grade ───────────────────────────────────────────────
            if pe is not None:
                pe = float(pe)
                if pe < 15:
                    valuation_grade = "CHEAP"
                elif pe < 25:
                    valuation_grade = "FAIR"
                elif pe < 40:
                    valuation_grade = "EXPENSIVE"
                else:
                    valuation_grade = "VERY_EXPENSIVE"
            elif ps is not None:
                ps = float(ps)
                if ps < 3:
                    valuation_grade = "CHEAP"
                elif ps < 6:
                    valuation_grade = "FAIR"
                else:
                    valuation_grade = "EXPENSIVE"
            else:
                valuation_grade = "FAIR"  # default when no data

            # ── Financial health ──────────────────────────────────────────────
            cr_val  = float(cr)  if cr  is not None else None
            de_val  = float(de)  if de  is not None else None
            fcf_val = float(fcf) if fcf is not None else None

            strong = (
                (cr_val  is None or cr_val  > 1.5) and
                (de_val  is None or de_val  < 1.0) and
                (fcf_val is None or fcf_val > 0)
            )
            weak = (
                (cr_val  is not None and cr_val  < 1.0) or
                (de_val  is not None and de_val  > 3.0) or
                (fcf_val is not None and fcf_val < 0)
            )

            if strong:
                financial_health = "STRONG"
            elif weak:
                financial_health = "WEAK"
            else:
                financial_health = "ADEQUATE"

            # ── Growth outlook ────────────────────────────────────────────────
            if rev is None:
                growth_outlook = "MODERATE"
            else:
                rev = float(rev)
                if rev > 0.15:
                    growth_outlook = "HIGH"
                elif rev > 0.05:
                    growth_outlook = "MODERATE"
                elif rev >= 0:
                    growth_outlook = "LOW"
                else:
                    growth_outlook = "DECLINING"

            # ── Numeric scores (never negative) ──────────────────────────────
            fh_score     = _FINANCIAL_HEALTH_SCORE.get(financial_health, 5)
            growth_score = _GROWTH_OUTLOOK_SCORE.get(growth_outlook, 5)
            fundamental_component = fh_score + growth_score

            return json.dumps({
                "ticker":                ticker.upper(),
                "valuation_grade":       valuation_grade,
                "financial_health":      financial_health,
                "growth_outlook":        growth_outlook,
                "financial_health_score": fh_score,
                "growth_score":          growth_score,
                "fundamental_component": fundamental_component,
            })

        except Exception as e:
            return json.dumps({"ticker": ticker, "error": f"Computation error: {e}"})
