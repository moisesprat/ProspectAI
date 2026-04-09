"""
Technical Interpretation Tool — deterministic numeric computation only.

Computes formula-based outputs from raw indicator values:
  - entry_zone_low / entry_zone_high  (SMA20 × 0.98 / SMA20)
  - momentum_score                    (point-count: +2 per favourable condition, cap 10)
  - risk_level                        (ATR / current_price thresholds)

What this tool does NOT do:
  - Signal interpretation (BULLISH / BEARISH) — that is the LLM's reasoning job.
  - Overbought / oversold judgment       — that is the LLM's reasoning job.
  - Buy / hold / sell recommendations    — that is the LLM's reasoning job.

The LLM reads the raw indicators alongside these computed numbers and applies
its own reasoning to decide overall_signal and investment action.
"""

import json
from crewai.tools import BaseTool


class TechnicalInterpretationTool(BaseTool):
    name: str = "interpret_technical_indicators"
    description: str = """Compute numeric technical outputs from raw indicator values.

    Call this tool immediately after 'calculate_technical_indicators' for each ticker.
    Returns only formula-based numbers — the LLM must reason about what they mean.

    Args:
        ticker: Stock ticker symbol (e.g. 'AAPL')
        raw_indicators_json: JSON string with these fields (use null for missing values):
            {
              "current_price": <float>,
              "sma_20":        <float>,
              "atr":           <float>,
              "rsi":           <float | null>,
              "macd_status":   <str>,   e.g. "Bullish", "Bearish", "Neutral"
              "ma_status":     <str>,   e.g. "Strong Uptrend", "Uptrend", "Downtrend"
              "bb_status":     <str>,   e.g. "Normal Range", "Overbought", "Oversold"
              "adx":           <float | null>
            }

    Returns JSON with computed numbers only:
        ticker, entry_zone_low, entry_zone_high, momentum_score (0-10),
        risk_level ("LOW"/"MEDIUM"/"HIGH")

    Note: overall_signal, overbought assessment, and investment action are NOT
    returned — the LLM determines those through reasoning.
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

            # ── Momentum score (0-10, +2 per favourable condition) ────────────
            score = 0
            if rsi is not None and 45 <= float(rsi) <= 65:
                score += 2
            if "bullish" in macd_status:
                score += 2
            if "uptrend" in ma_status:
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

            return json.dumps({
                "ticker":          ticker.upper(),
                "entry_zone_low":  entry_zone_low,
                "entry_zone_high": entry_zone_high,
                "momentum_score":  momentum_score,
                "risk_level":      risk_level,
            })

        except Exception as e:
            return json.dumps({"ticker": ticker, "error": f"Computation error: {e}"})
