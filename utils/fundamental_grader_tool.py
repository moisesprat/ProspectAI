"""
Fundamental Grader Tool — deterministic financial health grading for a batch of tickers.

Accepts the full JSON output from FundamentalDataTool and grades every entry in one call.
Extracts the needed fields from the nested structure returned by fetch_fundamental_data.

Grading rules:
  - valuation_grade  (P/E or P/S thresholds)
  - financial_health (current_ratio, D/E, FCF)
  - growth_outlook   (revenue_growth_yoy)

Scores never go negative — a bad metric earns the lowest positive score, not a penalty.
"""

import json
from crewai.tools import BaseTool
from utils.scoring_constants import _FINANCIAL_HEALTH_SCORE, _GROWTH_OUTLOOK_SCORE


class FundamentalGraderTool(BaseTool):
    name: str = "grade_fundamental_data"
    description: str = """Compute deterministic fundamental grades for a batch of tickers.

    Pass the complete JSON output from 'fetch_fundamental_data' directly to this tool.
    Call this tool ONCE — it grades all tickers in the batch and returns all results.

    Args:
        fundamentals_batch_json: The exact JSON string returned by fetch_fundamental_data,
            i.e. {"fundamentals": [...one entry per ticker...]}

    Returns JSON: {"grades": [one entry per ticker]} with fields:
        ticker, valuation_grade, financial_health, growth_outlook,
        financial_health_score, growth_score, fundamental_component
        (= financial_health_score + growth_score, always >= 0)
    On fetch error for a ticker: fundamental_unknown=true, all grades="UNKNOWN".
    """

    def _run(self, fundamentals_batch_json: str) -> str:
        try:
            batch = json.loads(fundamentals_batch_json)
        except (json.JSONDecodeError, TypeError) as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

        fundamentals = batch.get("fundamentals", []) if isinstance(batch, dict) else batch
        if not isinstance(fundamentals, list):
            return json.dumps({"error": "Expected {'fundamentals': [...]} from fetch_fundamental_data"})

        return json.dumps({"grades": [self._grade_one(entry) for entry in fundamentals]})

    def _grade_one(self, raw: dict) -> dict:
        ticker = str(raw.get("ticker", "UNKNOWN")).upper()

        # If fetch_fundamental_data returned an error, propagate UNKNOWN so
        # downstream agents never invent or default fundamental scores.
        if "error" in raw:
            return {
                "ticker":                ticker,
                "fundamental_unknown":   True,
                "valuation_grade":       "UNKNOWN",
                "financial_health":      "UNKNOWN",
                "growth_outlook":        "UNKNOWN",
                "financial_health_score": None,
                "growth_score":          None,
                "fundamental_component": None,
            }

        try:
            val = raw.get("valuation", {})
            bs  = raw.get("balance_sheet", {})
            gr  = raw.get("growth", {})

            pe  = val.get("pe_ratio")
            ps  = val.get("ps_ratio")
            cr  = bs.get("current_ratio")
            de  = bs.get("debt_to_equity")
            fcf = bs.get("free_cash_flow")
            rev = gr.get("revenue_growth_yoy")

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
                valuation_grade = "FAIR"

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

            return {
                "ticker":                ticker,
                "valuation_grade":       valuation_grade,
                "financial_health":      financial_health,
                "growth_outlook":        growth_outlook,
                "financial_health_score": fh_score,
                "growth_score":          growth_score,
                "fundamental_component": fh_score + growth_score,
            }

        except Exception as e:
            return {"ticker": ticker, "error": f"Computation error: {e}"}
