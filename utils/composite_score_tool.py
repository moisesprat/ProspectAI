"""
Composite Score Tool — deterministic score calculation only.

Computes the numeric composite_score and its three components for each stock.
Returns numbers. Does NOT map scores to actions — that is the LLM's reasoning job.

Formula (sentiment and fundamentals both available):
  sentiment_component  = ((average_sentiment + 1) / 2) × 30  [max 30 pts, linear -1→0, 0→15, +1→30]
  technical_component  = momentum_score × 4                  [max 40 pts]
  fundamental_component = quality_score + growth_score  [max 30 pts, min 6]
  composite_score = sum, rounded to 1 decimal

When average_sentiment is null (sentiment_available=false upstream -- both
Reddit and the Serper fallback failed), sentiment_component is dropped and
technical_component + fundamental_component are renormalized so the maximum
attainable score is still 100 (scaled by 100/70), instead of leaving the
composite silently capped at 70. This never happens implicitly: it only
triggers when average_sentiment is explicitly null, never for a 0.0 value
(0.0 is a real measured neutral sentiment, not a sentinel for "unavailable").

Score weights (labels are the schema Literals, QualityLabel / GrowthLabel in
schemas/agent_outputs.py; CORR-02, D-10):
  quality: High=20, Medium=10, Low=5, UNKNOWN=no points (component is null)
  growth:  High Growth=10, Moderate Growth=7, Stable=3, Declining=1, UNKNOWN=no points

Inputs are never defaulted (CORR-11, T-02-26): a missing quality/growth key is
UNKNOWN, a missing average_sentiment key is treated exactly like null, and a
missing or null momentum_score is an error naming the ticker. A label outside
the schema vocabulary is rejected with an error -- no case or whitespace
normalisation (D-11).
"""

import json
from crewai.tools import BaseTool
from utils.scoring_constants import _GROWTH_SCORE, _QUALITY_SCORE

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
            "quality":           <str>,     from FundamentalGraderTool, exactly one of:
                                 High | Medium | Low | UNKNOWN
            "growth":            <str>      from FundamentalGraderTool, exactly one of:
                                 High Growth | Moderate Growth | Stable | Declining | UNKNOWN
          },
          ...
        ]
        Labels are case-sensitive; any other value returns {"error": ...}. A missing
        quality/growth key counts as UNKNOWN; a missing average_sentiment key counts
        as null; momentum_score is required.

    Returns JSON with one entry per stock:
        ticker, sentiment_component (null when sentiment unavailable),
        technical_component, fundamental_component, sentiment_unavailable (bool),
        fundamental_unknown (bool), composite_score (0-100)

    The LLM then reasons about each composite_score alongside RSI, stochastic,
    MACD, and other signals to decide: LONG-BUY / WAIT-FOR-ENTRY / MONITOR / AVOID.
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
                # A missing average_sentiment key is the same as null: unavailable,
                # never a defaulted 0 (0.0 is a real measured neutral).
                raw_sentiment  = s.get("average_sentiment")
                sentiment_unavailable = raw_sentiment is None

                raw_momentum = s.get("momentum_score")
                if raw_momentum is None:
                    return json.dumps({"error": f"missing momentum_score for {ticker}"})
                momentum = float(raw_momentum)

                quality = s.get("quality", "UNKNOWN")
                growth  = s.get("growth", "UNKNOWN")
                if quality != "UNKNOWN" and quality not in _QUALITY_SCORE:
                    return json.dumps({"error": f"unknown quality label '{quality}' for {ticker}"})
                if growth != "UNKNOWN" and growth not in _GROWTH_SCORE:
                    return json.dumps({"error": f"unknown growth label '{growth}' for {ticker}"})

                tech_comp = round(momentum * 4, 1)

                # UNKNOWN means the data for this dimension was missing or the fetch failed.
                # Do NOT default to any score — exclude the fundamental component
                # entirely so the composite reflects only sentiment + technical.
                fund_unknown = quality == "UNKNOWN" or growth == "UNKNOWN"
                if fund_unknown:
                    fund_comp = None
                else:
                    fund_comp = _QUALITY_SCORE[quality] + _GROWTH_SCORE[growth]

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
