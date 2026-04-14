"""
Tests for TechnicalAnalysisTool and CompositeScoreTool.
yfinance is mocked via patch on the tool's internal method — avoids
the double yf.Ticker call in _get_stock_data + _calculate_all_indicators.
"""

import json
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime

from utils.technical_analysis_tool import TechnicalAnalysisTool
from utils.composite_score_tool import CompositeScoreTool


# ── Synthetic price data ───────────────────────────────────────────────────────

def _make_price_df(n=252, start=100.0, drift=0.001, seed=42) -> pd.DataFrame:
    """Realistic synthetic OHLCV DataFrame with enough history for all indicators."""
    # Generate index first; pd.date_range with freq="B" may return fewer than n items
    # when today is a weekend (end snaps to last business day). Use normalize() to
    # avoid the time-component causing off-by-one on weekends.
    idx = pd.date_range(
        end=pd.Timestamp.today().normalize() - pd.offsets.BDay(0),
        periods=n,
        freq="B",
    )
    n = len(idx)  # actual count (may be less than requested when today is non-business)
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, 0.02, n)
    closes = start * np.cumprod(1 + returns)
    highs   = closes * (1 + rng.uniform(0, 0.02, n))
    lows    = closes * (1 - rng.uniform(0, 0.02, n))
    opens   = closes * (1 + rng.uniform(-0.01, 0.01, n))
    volumes = rng.integers(1_000_000, 10_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=idx,
    )


def _mock_ticker(hist_df: pd.DataFrame) -> MagicMock:
    ticker = MagicMock()
    ticker.history.return_value = hist_df
    return ticker


# ── Tool structure ────────────────────────────────────────────────────────────

def test_tool_name():
    assert TechnicalAnalysisTool().name == "calculate_technical_indicators"

def test_description_is_not_empty():
    assert len(TechnicalAnalysisTool().description) > 20


# ── Successful analysis ───────────────────────────────────────────────────────

class TestTechnicalAnalysisSuccess:

    @pytest.fixture(autouse=True)
    def mock_yf(self):
        df = _make_price_df()
        with patch("yfinance.Ticker", return_value=_mock_ticker(df)):
            yield df

    def test_returns_expected_top_level_keys(self):
        result = TechnicalAnalysisTool()._run("NVDA")
        for key in ("ticker", "analysis_period", "analysis_date",
                    "stock_data", "technical_indicators"):
            assert key in result, f"Missing key: {key}"

    def test_ticker_is_echoed(self):
        assert TechnicalAnalysisTool()._run("AAPL")["ticker"] == "AAPL"

    def test_stock_data_has_required_fields(self):
        sd = TechnicalAnalysisTool()._run("NVDA")["stock_data"]
        for field in ("current_price", "price_change", "high", "low", "volume"):
            assert field in sd

    def test_current_price_is_positive(self):
        sd = TechnicalAnalysisTool()._run("NVDA")["stock_data"]
        assert sd["current_price"] > 0

    def test_technical_indicators_four_categories(self):
        ti = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]
        for cat in ("momentum", "trend", "volatility", "volume"):
            assert cat in ti, f"Missing indicator category: {cat}"

    def test_momentum_has_rsi_and_macd(self):
        mom = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]["momentum"]
        assert "rsi" in mom
        assert "macd" in mom

    def test_rsi_in_valid_range(self):
        rsi = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]["momentum"]["rsi"]
        current = rsi.get("current")
        if current is not None:
            assert 0 <= current <= 100

    def test_trend_has_moving_averages(self):
        trend = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]["trend"]
        assert "moving_averages" in trend
        for key in ("sma_20", "sma_50", "sma_200"):
            assert key in trend["moving_averages"]

    def test_volatility_has_bollinger_and_atr(self):
        vol = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]["volatility"]
        assert "bollinger_bands" in vol
        assert "atr" in vol

    def test_volume_has_obv_and_vwap(self):
        vol = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]["volume"]
        assert "obv" in vol
        assert "vwap" in vol

    def test_analysis_date_is_parseable(self):
        date_str = TechnicalAnalysisTool()._run("NVDA")["analysis_date"]
        datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")


# ── Error handling ────────────────────────────────────────────────────────────

class TestTechnicalAnalysisErrors:

    def test_empty_history_returns_error(self):
        with patch("yfinance.Ticker", return_value=_mock_ticker(pd.DataFrame())):
            result = TechnicalAnalysisTool()._run("FAKE")
        assert "error" in result

    def test_exception_returns_error_dict(self):
        with patch("yfinance.Ticker", side_effect=Exception("network error")):
            result = TechnicalAnalysisTool()._run("NVDA")
        assert "error" in result


# ── Status helper methods ─────────────────────────────────────────────────────

class TestStatusMethods:

    @pytest.fixture(autouse=True)
    def tool(self):
        self.t = TechnicalAnalysisTool()

    def test_rsi_overbought(self):
        assert self.t._get_rsi_status(75) == "Overbought"

    def test_rsi_oversold(self):
        assert self.t._get_rsi_status(25) == "Oversold"

    def test_rsi_neutral(self):
        assert self.t._get_rsi_status(50) == "Neutral"

    def test_macd_bullish(self):
        assert self.t._get_macd_status(1.0, 0.5, 0.5) == "Bullish"

    def test_macd_bearish(self):
        assert self.t._get_macd_status(-1.0, -0.5, -0.5) == "Bearish"

    def test_ma_strong_uptrend(self):
        assert self.t._get_ma_status(300, 200, 100) == "Strong Uptrend"

    def test_ma_strong_downtrend(self):
        assert self.t._get_ma_status(100, 200, 300) == "Strong Downtrend"

    def test_bollinger_overbought(self):
        assert self.t._get_bollinger_status(110, 100, 80) == "Overbought"

    def test_bollinger_oversold(self):
        assert self.t._get_bollinger_status(75, 100, 80) == "Oversold"

    def test_bollinger_normal(self):
        assert self.t._get_bollinger_status(90, 100, 80) == "Normal Range"

    def test_adx_strong_trend(self):
        assert self.t._get_adx_status(30) == "Strong Trend"

    def test_adx_weak_trend(self):
        assert self.t._get_adx_status(15) == "Weak Trend"

    def test_williams_r_oversold(self):
        assert self.t._get_williams_r_status(-85) == "Oversold"

    def test_williams_r_overbought(self):
        assert self.t._get_williams_r_status(-10) == "Overbought"

    def test_cci_overbought(self):
        assert self.t._get_cci_status(150) == "Overbought"

    def test_cci_oversold(self):
        assert self.t._get_cci_status(-150) == "Oversold"


# ── CompositeScoreTool ────────────────────────────────────────────────────────

def test_composite_tool_name():
    assert CompositeScoreTool().name == "compute_composite_scores"


def _compute(*stocks) -> list:
    payload = json.dumps(list(stocks))
    result = json.loads(CompositeScoreTool()._run(payload))
    return result["scores"]


class TestCompositeScoreFormula:

    def test_sentiment_max_at_positive_one(self):
        scores = _compute({"ticker": "A", "average_sentiment": 1.0,
                           "momentum_score": 0, "financial_health": "WEAK",
                           "growth_outlook": "DECLINING"})
        assert scores[0]["sentiment_component"] == 30.0

    def test_sentiment_neutral_gives_15(self):
        scores = _compute({"ticker": "A", "average_sentiment": 0.0,
                           "momentum_score": 0, "financial_health": "WEAK",
                           "growth_outlook": "DECLINING"})
        assert scores[0]["sentiment_component"] == pytest.approx(15.0)

    def test_sentiment_negative_one_gives_zero(self):
        scores = _compute({"ticker": "A", "average_sentiment": -1.0,
                           "momentum_score": 0, "financial_health": "WEAK",
                           "growth_outlook": "DECLINING"})
        assert scores[0]["sentiment_component"] == pytest.approx(0.0)

    def test_sentiment_scales_linearly(self):
        scores = _compute({"ticker": "A", "average_sentiment": 0.2,
                           "momentum_score": 0, "financial_health": "WEAK",
                           "growth_outlook": "DECLINING"})
        # ((0.2 + 1) / 2) * 30 = 18.0
        assert scores[0]["sentiment_component"] == pytest.approx(18.0)

    def test_technical_component_max_40(self):
        scores = _compute({"ticker": "A", "average_sentiment": 0.0,
                           "momentum_score": 10, "financial_health": "WEAK",
                           "growth_outlook": "DECLINING"})
        assert scores[0]["technical_component"] == 40.0

    @pytest.mark.parametrize("health,growth,expected", [
        ("STRONG",   "HIGH",      30),
        ("STRONG",   "MODERATE",  27),
        ("ADEQUATE", "HIGH",      20),
        ("ADEQUATE", "LOW",       13),
        ("WEAK",     "MODERATE",  12),
        ("WEAK",     "DECLINING",  6),  # minimum: 5 + 1
    ])
    def test_fundamental_component(self, health, growth, expected):
        scores = _compute({"ticker": "A", "average_sentiment": 0.0,
                           "momentum_score": 0,
                           "financial_health": health,
                           "growth_outlook": growth})
        assert scores[0]["fundamental_component"] == expected

    def test_composite_max_is_100(self):
        scores = _compute({"ticker": "A", "average_sentiment": 1.0,
                           "momentum_score": 10, "financial_health": "STRONG",
                           "growth_outlook": "HIGH"})
        assert scores[0]["composite_score"] == pytest.approx(100.0)

    def test_composite_min_above_zero(self):
        scores = _compute({"ticker": "A", "average_sentiment": 0.0,
                           "momentum_score": 0, "financial_health": "WEAK",
                           "growth_outlook": "DECLINING"})
        assert scores[0]["composite_score"] >= 6  # WEAK(5) + DECLINING(1)

    def test_distinct_inputs_produce_distinct_scores(self):
        scores = _compute(
            {"ticker": "A", "average_sentiment": 0.8, "momentum_score": 8,
             "financial_health": "STRONG", "growth_outlook": "HIGH"},
            {"ticker": "B", "average_sentiment": 0.3, "momentum_score": 5,
             "financial_health": "ADEQUATE", "growth_outlook": "MODERATE"},
        )
        assert scores[0]["composite_score"] != scores[1]["composite_score"]

    def test_all_component_fields_present(self):
        scores = _compute({"ticker": "NVDA", "average_sentiment": 0.7,
                           "momentum_score": 7.5, "financial_health": "STRONG",
                           "growth_outlook": "HIGH"})
        for field in ("ticker", "sentiment_component", "technical_component",
                      "fundamental_component", "composite_score"):
            assert field in scores[0]

    def test_invalid_json_returns_error(self):
        result = json.loads(CompositeScoreTool()._run("not json"))
        assert "error" in result
