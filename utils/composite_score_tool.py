"""
Composite Score Tool — deterministic score calculation only.

Computes the numeric composite_score and its three components for each stock.
Returns numbers. Does NOT map scores to actions — that is the LLM's reasoning job.

Formula:
  sentiment_component  = ((average_sentiment + 1) / 2) × 30  [max 30 pts, linear -1→0, 0→15, +1→30]
  technical_component  = momentum_score × 4                  [max 40 pts]
  fundamental_component = financial_health_score + growth_score  [max 30 pts, min 6]
  composite_score = sum, rounded to 1 decimal

Score weights:
  financial_health: STRONG=20, ADEQUATE=10, WEAK=5
  growth_outlook:   HIGH=10, MODERATE=7, LOW=3, DECLINING=1
"""

import json
from crewai.tools import BaseTool

_FINANCIAL_HEALTH_SCORE = {"STRONG": 20, "ADEQUATE": 10, "WEAK": 5}
_GROWTH_OUTLOOK_SCORE   = {"HIGH": 10, "MODERATE": 7, "LOW": 3, "DECLINING": 1}


class CompositeScoreTool(BaseTool):
    name: str = "compute_composite_scores"
    description: str = """Compute composite investment scores for a list of stocks.

    Call this tool ONCE with all stocks combined. Returns numeric scores only —
    the LLM must reason about what each score means and decide the investment action.

    Args:
        stocks_json: JSON array, one object per stock:
        [
          {
            "ticker":            <str>,
            "average_sentiment": <float>,   from Market Analyst (−1.0 to 1.0)
            "momentum_score":    <float>,   from TechnicalInterpretationTool (0-10)
            "financial_health":  <str>,     from FundamentalGraderTool: STRONG/ADEQUATE/WEAK
            "growth_outlook":    <str>      from FundamentalGraderTool: HIGH/MODERATE/LOW/DECLINING
          },
          ...
        ]

    Returns JSON with one entry per stock:
        ticker, sentiment_component, technical_component, fundamental_component,
        composite_score (0-100)

    The LLM then reasons about each composite_score alongside RSI, stochastic,
    MACD, and other signals to decide: LONG-BUY / HOLD / WAIT-FOR-ENTRY / AVOID.
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

                sent_comp = round(((sentiment + 1) / 2) * 30, 1)
                tech_comp = round(momentum * 4, 1)

                # UNKNOWN means fetch_fundamental_data had no data for this ticker.
                # Do NOT default to any score — exclude the fundamental component
                # entirely so the composite reflects only sentiment + technical.
                fund_unknown = fh == "UNKNOWN" or growth == "UNKNOWN"
                if fund_unknown:
                    fund_comp = None
                    score     = round(sent_comp + tech_comp, 1)
                else:
                    fh_score  = _FINANCIAL_HEALTH_SCORE.get(fh, 5)
                    gr_score  = _GROWTH_OUTLOOK_SCORE.get(growth, 5)
                    fund_comp = fh_score + gr_score
                    score     = round(sent_comp + tech_comp + fund_comp, 1)

                results.append({
                    "ticker":                ticker,
                    "sentiment_component":   sent_comp,
                    "technical_component":   tech_comp,
                    "fundamental_component": fund_comp,
                    "fundamental_unknown":   fund_unknown,
                    "composite_score":       score,
                })

            return json.dumps({"scores": results})

        except Exception as e:
            return json.dumps({"error": f"Computation error: {e}"})
