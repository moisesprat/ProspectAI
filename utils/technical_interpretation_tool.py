"""
Technical Interpretation Tool — deterministic numeric computation only.

Computes formula-based outputs from raw indicator values:
  - entry_zone_low / entry_zone_high  (SMA20 × 0.98 / SMA20)
  - momentum_score                    (weighted 0-10 across RSI, MACD, MA, Stochastic, ADX)
  - risk_level                        (ATR / current_price thresholds)

Scoring breakdown (max 10 pts):
  RSI       2.5 pts — full if 45-65, partial if trending, 0 if extreme
  MACD      2.0 pts — Bullish=2.0, Mixed=1.0, Bearish/other=0
  MA align  2.5 pts — SMA20>SMA50>SMA200=2.5, SMA20>SMA50=1.5, else 0.5
  Stoch     1.5 pts — Neutral=1.5, Oversold=1.0, Overbought=0.3
  ADX       1.5 pts — >25=1.5, >20=1.0, else 0.3

What this tool does NOT do:
  - Signal interpretation (BULLISH / BEARISH) — that is the LLM's reasoning job.
  - Buy / hold / sell recommendations          — that is the LLM's reasoning job.

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
              "current_price":    <float>,
              "sma_20":           <float>,
              "sma_50":           <float | null>,
              "sma_200":          <float | null>,
              "atr":              <float>,
              "rsi":              <float | null>,
              "macd_status":      <str>,   e.g. "Bullish", "Bearish", "Mixed"
              "ma_status":        <str>,   e.g. "Strong Uptrend", "Uptrend", "Downtrend"
              "bb_status":        <str>,   e.g. "Normal Range", "Overbought", "Oversold"
              "stochastic_status":<str | null>,  e.g. "Neutral", "Overbought", "Oversold"
              "adx":              <float | null>
            }

    Returns JSON with computed numbers only:
        ticker, entry_zone_low, entry_zone_high,
        momentum_score (0-10, float), risk_level ("LOW"/"MEDIUM"/"HIGH")

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
            sma_50        = ind.get("sma_50")
            sma_200       = ind.get("sma_200")
            atr           = float(ind.get("atr") or 0)
            rsi           = ind.get("rsi")
            macd_status   = str(ind.get("macd_status")      or "").lower()
            stoch_status  = str(ind.get("stochastic_status") or "").lower()
            adx           = ind.get("adx")

            if sma_20 <= 0 or current_price <= 0:
                return json.dumps({
                    "ticker": ticker,
                    "error": "current_price and sma_20 must be positive numbers",
                })

            # ── Momentum score (0-10, weighted) ──────────────────────────────
            score = 0.0

            # RSI — 2.5 pts
            if rsi is not None:
                rsi_f = float(rsi)
                if 45 <= rsi_f <= 65:
                    score += 2.5
                elif 65 < rsi_f <= 70:
                    score += 1.5
                elif rsi_f > 70:
                    score += 0.5          # overbought — still some momentum, but reduced
                elif rsi_f < 30:
                    score += 1.0          # oversold — potential reversal
                else:
                    score += 1.5          # 30-45 neutral-low

            # MACD — 2.0 pts
            if "bullish" in macd_status:
                score += 2.0
            elif "mixed" in macd_status:
                score += 1.0
            # Bearish or unknown → 0 pts

            # MA alignment — 2.5 pts
            # Prefer explicit sma values; fall back to ma_status string
            sma_50_f  = float(sma_50)  if sma_50  is not None else None
            sma_200_f = float(sma_200) if sma_200 is not None else None
            if sma_50_f is not None and sma_200_f is not None:
                if sma_20 > sma_50_f > sma_200_f:
                    score += 2.5
                elif sma_20 > sma_50_f:
                    score += 1.5
                else:
                    score += 0.5
            else:
                # Fall back to ma_status string
                ma_status = str(ind.get("ma_status") or "").lower()
                if "strong uptrend" in ma_status:
                    score += 2.5
                elif "uptrend" in ma_status:
                    score += 1.5
                elif "sideways" in ma_status or "neutral" in ma_status:
                    score += 1.0
                else:
                    score += 0.5

            # Stochastic — 1.5 pts
            if "neutral" in stoch_status:
                score += 1.5
            elif "oversold" in stoch_status:
                score += 1.0              # potential reversal
            elif "overbought" in stoch_status:
                score += 0.3              # caution signal
            else:
                score += 1.0              # unknown → neutral default

            # ADX trend strength — 1.5 pts
            if adx is not None:
                adx_f = float(adx)
                if adx_f > 25:
                    score += 1.5
                elif adx_f > 20:
                    score += 1.0
                else:
                    score += 0.3

            momentum_score = round(min(score, 10.0), 2)

            # ── Regime detection ─────────────────────────────────────────────────────
            adx_f = float(adx) if adx is not None else 0.0

            strong_uptrend = (
                adx_f > 25 and
                sma_50_f is not None and
                sma_200_f is not None and
                sma_20 > sma_50_f > sma_200_f
            )

            downtrend = (
                sma_50_f is not None and
                sma_20 < sma_50_f
            )

            # ── Entry zone by regime ──────────────────────────────────────────────────
            if strong_uptrend:
                # TRENDING regime: anchor to current price, not SMA20.
                # Price may stay above SMA20 for weeks in a bull run — using SMA20
                # as the ceiling produces 100% cash portfolios in bull markets.
                if atr > 0:
                    entry_zone_high = round(current_price * 0.990, 2)   # 1% below price
                    entry_zone_low  = round(current_price - atr * 1.5, 2)
                else:
                    entry_zone_high = round(current_price * 0.990, 2)
                    entry_zone_low  = round(current_price * 0.975, 2)
                # Clamp: zone cannot drop below SMA50
                if sma_50_f is not None:
                    entry_zone_low = max(entry_zone_low, round(sma_50_f * 1.001, 2))
                regime = "TRENDING"

            elif downtrend:
                # REVERTING or BEARISH regime: anchor conservatively to SMA20.
                # Price in a downtrend should not be chased — wait for SMA20 support.
                entry_zone_high = round(sma_20 * 0.995, 2)
                entry_zone_low  = round(sma_20 * 0.980, 2)
                regime = "REVERTING"

            else:
                # NEUTRAL regime: split between current price and SMA20.
                mid = (current_price + sma_20) / 2.0
                if atr > 0:
                    entry_zone_high = round(mid * 0.995, 2)
                    entry_zone_low  = round(mid - atr, 2)
                else:
                    entry_zone_high = round(mid * 0.995, 2)
                    entry_zone_low  = round(mid * 0.980, 2)
                regime = "NEUTRAL"

            # ── Universal clamps ──────────────────────────────────────────────────────
            # 1. entry_zone_high must always be strictly below sma_20 by at least 0.4%
            #    in REVERTING/NEUTRAL to prevent SMA20 = entry zone top bug.
            if regime != "TRENDING":
                entry_zone_high = min(entry_zone_high, round(sma_20 * 0.995, 2))

            # 2. entry_zone_low must not fall more than 5% below entry_zone_high.
            entry_zone_low = max(entry_zone_low, round(entry_zone_high * 0.950, 2))

            # 3. Ensure low < high (rounding safety).
            if entry_zone_low >= entry_zone_high:
                entry_zone_low = round(entry_zone_high * 0.985, 2)

            entry_zone_high = round(entry_zone_high, 2)
            entry_zone_low  = round(entry_zone_low,  2)

            # ── Entry zone status ─────────────────────────────────────────────────────
            if current_price > entry_zone_high * 1.01:
                gap_pct = round((current_price - entry_zone_high) / entry_zone_high * 100, 1)
                entry_zone_status = "PULLBACK_ENTRY"
                entry_zone_label = (
                    f"PULLBACK ENTRY — not actionable at current price "
                    f"({current_price:.2f} is {gap_pct}% above zone top {entry_zone_high:.2f}). "
                    f"Wait for retracement to {entry_zone_low:.2f}–{entry_zone_high:.2f}."
                )
            elif current_price >= entry_zone_low:
                entry_zone_status = "CURRENT_ENTRY"
                entry_zone_label = (
                    f"Actionable now — current price {current_price:.2f} is within "
                    f"entry zone {entry_zone_low:.2f}–{entry_zone_high:.2f}."
                )
            else:
                entry_zone_status = "BELOW_ZONE"
                entry_zone_label = (
                    f"Price {current_price:.2f} is below entry zone — potential "
                    f"breakdown. Verify support before entering."
                )

            # ── Risk level (ATR / current_price) ─────────────────────────────
            atr_ratio = atr / current_price if current_price > 0 else 0
            if atr_ratio > 0.03:
                risk_level = "HIGH"
            elif atr_ratio < 0.015:
                risk_level = "LOW"
            else:
                risk_level = "MEDIUM"

            return json.dumps({
                "ticker":             ticker.upper(),
                "entry_zone_low":     entry_zone_low,
                "entry_zone_high":    entry_zone_high,
                "entry_zone_status":  entry_zone_status,
                "entry_zone_label":   entry_zone_label,
                "regime":             regime,
                "momentum_score":     momentum_score,
                "risk_level":         risk_level,
            })

        except Exception as e:
            return json.dumps({"ticker": ticker, "error": f"Computation error: {e}"})
