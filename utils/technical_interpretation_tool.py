"""
Technical Interpretation Tool — deterministic signal computation.

Takes raw indicator values already fetched by TechnicalAnalysisTool and applies
all formula-based rules without any LLM involvement:
  - entry_zone_low / entry_zone_high  (SMA20-based)
  - momentum_score                    (point-count rule)
  - risk_level                        (ATR/price ratio)
  - overall_signal                    (MACD + MA status)

The LLM's job is to fetch data then call this tool — it must not recalculate.
"""

import json
from crewai.tools import BaseTool


class TechnicalInterpretationTool(BaseTool):
    name: str = "interpret_technical_indicators"
    description: str = """Compute derived technical signals from raw indicator values.

    Call this tool immediately after 'calculate_technical_indicators' for each ticker.
    Pass the raw indicator values as a JSON string. Returns entry zone, momentum score,
    risk level, and overall signal — all computed deterministically.

    Args:
        ticker: Stock ticker symbol (e.g. 'AAPL')
        raw_indicators_json: JSON string with these fields (use null for missing values):
            {
              "current_price": <float>,
              "sma_20":        <float>,
              "sma_50":        <float | null>,
              "sma_200":       <float | null>,
              "atr":           <float>,
              "rsi":           <float | null>,
              "macd_status":   <str>,   e.g. "Bullish", "Bearish", "Neutral"
              "ma_status":     <str>,   e.g. "Strong Uptrend", "Uptrend", "Downtrend"
              "bb_status":     <str>,   e.g. "Normal Range", "Overbought", "Oversold"
              "adx":           <float | null>
            }

    Returns JSON with:
        ticker, entry_zone_low, entry_zone_high, momentum_score (0-10),
        risk_level ("LOW"/"MEDIUM"/"HIGH"), overall_signal ("BULLISH"/"BEARISH"/"MIXED"/"NEUTRAL")
    """

    def _run(self, ticker: str, raw_indicators_json: str) -> str:
        try:
            ind = json.loads(raw_indicators_json)
        except (json.JSONDecodeError, TypeError) as e:
            return json.dumps({"ticker": ticker, "error": f"Invalid JSON: {e}"})

        try:
            current_price = float(ind.get("current_price") or 0)
            sma_20        = float(ind.get("sma_20") or 0)
            atr           = float(ind.get("atr") or 0)
            rsi           = ind.get("rsi")
            macd_status   = str(ind.get("macd_status") or "").lower()
            ma_status     = str(ind.get("ma_status")   or "").lower()
            bb_status     = str(ind.get("bb_status")   or "").lower()
            adx           = ind.get("adx")

            if sma_20 <= 0 or current_price <= 0:
                return json.dumps({
                    "ticker": ticker,
                    "error": "current_price and sma_20 must be positive numbers",
                })

            # ── Entry zone (2 % buffer below SMA20) ──────────────────────────
            entry_zone_high = round(sma_20, 2)
            entry_zone_low  = round(sma_20 * 0.98, 2)

            # ── Momentum score (0-10, +2 per true condition) ─────────────────
            score = 0
            if rsi is not None and 45 <= float(rsi) <= 65:
                score += 2
            if "bullish" in macd_status:
                score += 2
            if "strong uptrend" in ma_status or "uptrend" in ma_status:
                score += 2
            if adx is not None and float(adx) > 25:
                score += 2
            if "normal range" in bb_status:
                score += 2
            momentum_score = min(score, 10)

            # ── Risk level (ATR / current_price) ─────────────────────────────
            atr_ratio = atr / current_price if current_price > 0 else 0
            if atr_ratio > 0.03:
                risk_level = "HIGH"
            elif atr_ratio < 0.015:
                risk_level = "LOW"
            else:
                risk_level = "MEDIUM"

            # ── Overall signal ────────────────────────────────────────────────
            macd_bull = "bullish" in macd_status
            macd_bear = "bearish" in macd_status
            ma_up     = "uptrend" in ma_status
            ma_down   = "downtrend" in ma_status

            if macd_bull and ma_up:
                overall_signal = "BULLISH"
            elif macd_bear and ma_down:
                overall_signal = "BEARISH"
            elif macd_bull or ma_up:
                overall_signal = "MIXED"
            else:
                overall_signal = "NEUTRAL"

            return json.dumps({
                "ticker":           ticker.upper(),
                "entry_zone_low":   entry_zone_low,
                "entry_zone_high":  entry_zone_high,
                "momentum_score":   momentum_score,
                "risk_level":       risk_level,
                "overall_signal":   overall_signal,
            })

        except Exception as e:
            return json.dumps({"ticker": ticker, "error": f"Computation error: {e}"})
