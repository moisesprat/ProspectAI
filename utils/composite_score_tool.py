"""
Composite Score Tool — deterministic score calculation only.

Computes the numeric composite_score and its three components for each stock.
Returns numbers. Does NOT map scores to actions — that is the LLM's reasoning job.

Formula (sentiment and fundamentals both available):
  sentiment_component  = ((average_sentiment + 1) / 2) × 30  [max 30 pts, linear -1→0, 0→15, +1→30]
  technical_component  = momentum_score × 4                  [max 40 pts]
  fundamental_component = financial_health_score + growth_score  [max 30 pts, min 6]
  composite_score = sum, rounded to 1 decimal

When average_sentiment is null (sentiment_available=false upstream -- both
Reddit and the Serper fallback failed), sentiment_component is dropped and
technical_component + fundamental_component are renormalized so the maximum
attainable score is still 100 (scaled by 100/70), instead of leaving the
composite silently capped at 70. This never happens implicitly: it only
triggers when average_sentiment is explicitly null, never for a 0.0 value
(0.0 is a real measured neutral sentiment, not a sentinel for "unavailable").

Score weights:
  financial_health: STRONG=20, ADEQUATE=10, WEAK=5
  growth_outlook:   HIGH=10, MODERATE=7, LOW=3, DECLINING=1
"""

import json
from crewai.tools import BaseTool
from utils.scoring_constants import _FINANCIAL_HEALTH_SCORE, _GROWTH_OUTLOOK_SCORE

_SENTIMENT_MAX = 30.0
_TECHNICAL_MAX = 40.0
_FUNDAMENTAL_MAX = 30.0
_NO_SENTIMENT_RENORM_FACTOR = round((_SENTIMENT_MAX + _TECHNICAL_MAX + _FUNDAMENTAL_MAX) / (_TECHNICAL_MAX + _FUNDAMENTAL_MAX), 6)


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
            "average_sentiment": <float|null>, from Market Analyst (−1.0 to 1.0),
                                 null when sentiment_available=false upstream
                                 (both Reddit and the Serper fallback failed) —
                                 never pass 0.0 to mean "unavailable".
            "momentum_score":    <float>,   from TechnicalInterpretationTool (0-10)
            "financial_health":  <str>,     from FundamentalGraderTool: STRONG/ADEQUATE/WEAK
            "growth_outlook":    <str>      from FundamentalGraderTool: HIGH/MODERATE/LOW/DECLINING
          },
          ...
        ]

    Returns JSON with one entry per stock:
        ticker, sentiment_component (null when sentiment unavailable),
        technical_component, fundamental_component, sentiment_unavailable (bool),
        fundamental_unknown (bool), composite_score (0-100)

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
                ticker         = str(s.get("ticker", "UNKNOWN")).upper()
                raw_sentiment  = s.get("average_sentiment", 0)
                sentiment_unavailable = raw_sentiment is None
                momentum       = float(s.get("momentum_score", 1))
                fh             = str(s.get("financial_health", "ADEQUATE")).upper()
                growth         = str(s.get("growth_outlook",   "MODERATE")).upper()

                tech_comp = round(momentum * 4, 1)

                # UNKNOWN means fetch_fundamental_data had no data for this ticker.
                # Do NOT default to any score — exclude the fundamental component
                # entirely so the composite reflects only sentiment + technical.
                fund_unknown = fh == "UNKNOWN" or growth == "UNKNOWN"
                if fund_unknown:
                    fund_comp = None
                else:
                    fh_score  = _FINANCIAL_HEALTH_SCORE.get(fh, 5)
                    gr_score  = _GROWTH_OUTLOOK_SCORE.get(growth, 5)
                    fund_comp = fh_score + gr_score

                if sentiment_unavailable:
                    sent_comp = None
                    if fund_unknown:
                        # Neither sentiment nor fundamentals available: renormalize
                        # over technical alone so the ceiling is still 100.
                        score = round(tech_comp * (100.0 / _TECHNICAL_MAX), 1)
                    else:
                        assert fund_comp is not None
                        score = round((tech_comp + fund_comp) * _NO_SENTIMENT_RENORM_FACTOR, 1)
                else:
                    sentiment = float(raw_sentiment)
                    sent_comp = round(((sentiment + 1) / 2) * 30, 1)
                    if fund_unknown:
                        # Legacy behaviour: composite capped at 70 (sentiment +
                        # technical only), not renormalized. Fundamentals-missing
                        # renormalization is out of scope for this change.
                        score = round(sent_comp + tech_comp, 1)
                    else:
                        assert fund_comp is not None
                        score = round(sent_comp + tech_comp + fund_comp, 1)

                results.append({
                    "ticker":                ticker,
                    "sentiment_component":   sent_comp,
                    "technical_component":   tech_comp,
                    "fundamental_component": fund_comp,
                    "sentiment_unavailable": sentiment_unavailable,
                    "fundamental_unknown":   fund_unknown,
                    "composite_score":       score,
                })

            return json.dumps({"scores": results})

        except Exception as e:
            return json.dumps({"error": f"Computation error: {e}"})
