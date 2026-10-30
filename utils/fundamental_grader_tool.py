"""
Fundamental Grader Tool — deterministic fundamental grading for a batch of tickers.

Accepts the full JSON output from FundamentalDataTool and grades every entry in one call.
Extracts the needed fields from the nested structure returned by fetch_fundamental_data.

Output keys and label values are the schema's vocabulary
(schemas/agent_outputs.py ValuationLabel / QualityLabel / GrowthLabel / DataStatus;
CORR-02, D-10):
  - valuation  CHEAP / FAIR / EXPENSIVE / VERY_EXPENSIVE / UNKNOWN  (P/E, else P/S)
  - quality    High / Medium / Low / UNKNOWN   (current_ratio, D/E, FCF)
  - growth     High Growth / Moderate Growth / Stable / Declining / UNKNOWN  (revenue_growth_yoy)
  - data_status ok / partial / failed

No credit for missing data (CORR-11, D-07): a dimension with no inputs is UNKNOWN
with a null score. High quality needs all three balance-sheet metrics present;
any present weak metric makes quality Low; otherwise Medium. fundamental_component
is the sum of the two scores only when both quality and growth are known.

Scores never go negative — a bad metric earns the lowest positive score, not a penalty.
"""

import json
from crewai.tools import BaseTool
from utils.scoring_constants import _QUALITY_SCORE, _GROWTH_SCORE


def fundamentals_status(quality: str, growth: str) -> str:
    """AVAILABLE when both quality and growth are graded, else UNKNOWN."""
    return "UNKNOWN" if "UNKNOWN" in (quality, growth) else "AVAILABLE"


def _failed(ticker: str) -> dict:
    """Failed fetch / computation: UNKNOWN labels, null scores, never a default grade."""
    return {
        "ticker":                ticker,
        "valuation":             "UNKNOWN",
        "quality":               "UNKNOWN",
        "growth":                "UNKNOWN",
        "data_status":           "failed",
        "quality_score":         None,
        "growth_score":          None,
        "fundamental_component": None,
        "fundamental_unknown":   True,
    }


class FundamentalGraderTool(BaseTool):
    name: str = "grade_fundamental_data"
    description: str = """Compute deterministic fundamental grades for a batch of tickers.

    Pass the complete JSON output from 'fetch_fundamental_data' directly to this tool.
    Call this tool ONCE — it grades all tickers in the batch and returns all results.

    Args:
        fundamentals_batch_json: The exact JSON string returned by fetch_fundamental_data,
            i.e. {"fundamentals": [...one entry per ticker...]}

    Returns JSON: {"grades": [one entry per ticker]} with fields:
        ticker,
        valuation (CHEAP|FAIR|EXPENSIVE|VERY_EXPENSIVE|UNKNOWN),
        quality (High|Medium|Low|UNKNOWN),
        growth (High Growth|Moderate Growth|Stable|Declining|UNKNOWN),
        data_status (ok|partial|failed),
        quality_score, growth_score (null when that dimension is UNKNOWN),
        fundamental_component (= quality_score + growth_score; null unless both are known),
        fundamental_unknown (true when quality or growth is UNKNOWN)
    Missing data is never graded (CORR-11): a dimension with no inputs is "UNKNOWN" with a
    null score. On fetch error for a ticker: data_status="failed", all labels "UNKNOWN",
    all scores null, fundamental_unknown=true. Copy "UNKNOWN" and data_status verbatim.
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
            return _failed(ticker)

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

            # ── Valuation ─────────────────────────────────────────────────────
            if pe is not None:
                pe = float(pe)
                if pe < 15:
                    valuation = "CHEAP"
                elif pe < 25:
                    valuation = "FAIR"
                elif pe < 40:
                    valuation = "EXPENSIVE"
                else:
                    valuation = "VERY_EXPENSIVE"
            elif ps is not None:
                ps = float(ps)
                if ps < 3:
                    valuation = "CHEAP"
                elif ps < 6:
                    valuation = "FAIR"
                else:
                    valuation = "EXPENSIVE"
            else:
                valuation = "UNKNOWN"

            # ── Quality ───────────────────────────────────────────────────────
            cr_val  = float(cr)  if cr  is not None else None
            de_val  = float(de)  if de  is not None else None
            fcf_val = float(fcf) if fcf is not None else None

            all_present = None not in (cr_val, de_val, fcf_val)
            none_present = cr_val is None and de_val is None and fcf_val is None
            weak = (
                (cr_val is not None and cr_val < 1.0) or
                (de_val is not None and de_val > 3.0) or
                (fcf_val is not None and fcf_val < 0)
            )

            if none_present:
                quality = "UNKNOWN"
            elif weak:
                quality = "Low"
            elif all_present and cr_val > 1.5 and de_val < 1.0 and fcf_val > 0:
                quality = "High"
            else:
                quality = "Medium"

            # ── Growth ────────────────────────────────────────────────────────
            if rev is None:
                growth = "UNKNOWN"
            else:
                rev = float(rev)
                if rev > 0.15:
                    growth = "High Growth"
                elif rev > 0.05:
                    growth = "Moderate Growth"
                elif rev >= 0:
                    growth = "Stable"
                else:
                    growth = "Declining"

            # ── Numeric scores (never negative; null when UNKNOWN) ────────────
            quality_score = _QUALITY_SCORE[quality] if quality != "UNKNOWN" else None
            growth_score  = _GROWTH_SCORE[growth] if growth != "UNKNOWN" else None
            known = quality_score is not None and growth_score is not None

            has_valuation_input = pe is not None or ps is not None
            complete = has_valuation_input and all_present and rev is not None

            return {
                "ticker":                ticker,
                "valuation":             valuation,
                "quality":               quality,
                "growth":                growth,
                "data_status":           "ok" if complete else "partial",
                "quality_score":         quality_score,
                "growth_score":          growth_score,
                "fundamental_component": quality_score + growth_score if known else None,
                "fundamental_unknown":   not known,
            }

        except Exception:
            # A malformed value is a failed grade, never a defaulted one.
            return _failed(ticker)
