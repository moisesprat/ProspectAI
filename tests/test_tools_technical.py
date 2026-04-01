"""
Tests for TechnicalAnalysisTool.
yfinance calls are mocked — no network required.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


def _make_price_series(n=252, start=100.0, drift=0.001, seed=42):
    """Generate a realistic synthetic OHLCV DataFrame."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, 0.02, n)
    closes = start * np.cumprod(1 + returns)
    highs = closes * (1 + rng.uniform(0, 0.02, n))
    lows = closes * (1 - rng.uniform(0, 0.02, n))
    opens = closes * (1 + rng.uniform(-0.01, 0.01, n))
    volumes = rng.integers(1_000_000, 10_000_000, n).astype(float)

    idx = pd.date_range(end=datetime.today(), periods=n, freq="B")
    return pd.DataFrame({
        "Open": opens, "High": highs, "Low": lows,
        "Close": closes, "Volume": volumes,
    }, index=idx)


def _mock_ticker(hist_df):
    ticker = MagicMock()
    ticker.history.return_value = hist_df
    return ticker


# ── Tool structure ────────────────────────────────────────────────────────────

class TestTechnicalAnalysisToolStructure:

    def test_tool_name(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        assert TechnicalAnalysisTool().name == "calculate_technical_indicators"

    def test_description_is_not_empty(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        assert len(TechnicalAnalysisTool().description) > 20


# ── Successful analysis ───────────────────────────────────────────────────────

class TestTechnicalAnalysisSuccess:

    @pytest.fixture(autouse=True)
    def mock_yfinance(self):
        df = _make_price_series()
        with patch("yfinance.Ticker", return_value=_mock_ticker(df)):
            yield df

    def test_returns_expected_top_level_keys(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        result = TechnicalAnalysisTool()._run("NVDA")
        for key in ("ticker", "analysis_period", "analysis_date",
                    "stock_data", "technical_indicators"):
            assert key in result, f"Missing key: {key}"

    def test_ticker_is_echoed(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        result = TechnicalAnalysisTool()._run("AAPL")
        assert result["ticker"] == "AAPL"

    def test_stock_data_has_required_fields(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        sd = TechnicalAnalysisTool()._run("NVDA")["stock_data"]
        for field in ("current_price", "price_change", "high", "low", "volume"):
            assert field in sd

    def test_current_price_is_positive(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        sd = TechnicalAnalysisTool()._run("NVDA")["stock_data"]
        assert sd["current_price"] > 0

    def test_technical_indicators_four_categories(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        ti = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]
        for cat in ("momentum", "trend", "volatility", "volume"):
            assert cat in ti, f"Missing indicator category: {cat}"

    def test_momentum_has_rsi_and_macd(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        mom = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]["momentum"]
        assert "rsi" in mom
        assert "macd" in mom

    def test_rsi_value_is_in_valid_range(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        rsi = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]["momentum"]["rsi"]
        if rsi.get("current") is not None:
            assert 0 <= rsi["current"] <= 100

    def test_trend_has_moving_averages(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        trend = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]["trend"]
        assert "moving_averages" in trend
        ma = trend["moving_averages"]
        for key in ("sma_20", "sma_50", "sma_200"):
            assert key in ma

    def test_volatility_has_bollinger_and_atr(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        vol = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]["volatility"]
        assert "bollinger_bands" in vol
        assert "atr" in vol

    def test_volume_has_obv_and_vwap(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        vol = TechnicalAnalysisTool()._run("NVDA")["technical_indicators"]["volume"]
        assert "obv" in vol
        assert "vwap" in vol

    def test_analysis_date_is_today_format(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
        date_str = TechnicalAnalysisTool()._run("NVDA")["analysis_date"]
        # Should parse without error
        datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")


# ── Error handling ────────────────────────────────────────────────────────────

class TestTechnicalAnalysisErrors:

    def test_empty_history_returns_error(self):
        empty_df = pd.DataFrame()
        with patch("yfinance.Ticker", return_value=_mock_ticker(empty_df)):
            from utils.technical_analysis_tool import TechnicalAnalysisTool
            result = TechnicalAnalysisTool()._run("FAKE")
            assert "error" in result

    def test_exception_returns_error_dict(self):
        with patch("yfinance.Ticker", side_effect=Exception("network error")):
            from utils.technical_analysis_tool import TechnicalAnalysisTool
            result = TechnicalAnalysisTool()._run("NVDA")
            assert "error" in result


# ── Status interpretation methods ─────────────────────────────────────────────

class TestStatusMethods:

    @pytest.fixture(autouse=True)
    def tool(self):
        from utils.technical_analysis_tool import TechnicalAnalysisTool
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
