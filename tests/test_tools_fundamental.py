"""
Tests for FundamentalDataTool.
yfinance is mocked — no network required.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


def _make_info(**overrides):
    base = {
        "longName": "Test Corp",
        "sector": "Technology",
        "industry": "Semiconductors",
        "fullTimeEmployees": 10000,
        "longBusinessSummary": "A test company that makes test products.",
        "website": "https://test.com",
        "marketCap": 1_000_000_000,
        "enterpriseValue": 1_100_000_000,
        "trailingPE": 25.5,
        "forwardPE": 20.0,
        "priceToBook": 5.0,
        "priceToSalesTrailing12Months": 8.0,
        "enterpriseToEbitda": 18.0,
        "fiftyTwoWeekHigh": 200.0,
        "fiftyTwoWeekLow": 100.0,
        "beta": 1.2,
        "grossMargins": 0.60,
        "operatingMargins": 0.25,
        "profitMargins": 0.20,
        "returnOnEquity": 0.30,
        "returnOnAssets": 0.15,
        "ebitda": 500_000_000,
        "revenueGrowth": 0.15,
        "earningsGrowth": 0.20,
        "trailingEps": 5.0,
        "forwardEps": 6.0,
        "totalDebt": 200_000_000,
        "totalCash": 500_000_000,
        "debtToEquity": 0.4,
        "currentRatio": 2.5,
        "quickRatio": 2.0,
        "bookValue": 50.0,
        "dividendYield": 0.01,
        "payoutRatio": 0.20,
        "dividendRate": 2.0,
        "regularMarketPrice": 150.0,
    }
    base.update(overrides)
    return base


def _make_financials():
    return pd.DataFrame(
        {"2023": [2_000_000_000, 400_000_000]},
        index=["Total Revenue", "Net Income"]
    )


def _make_cashflow():
    return pd.DataFrame(
        {"2023": [600_000_000, -100_000_000]},
        index=["Operating Cash Flow", "Capital Expenditure"]
    )


def _make_ticker(info=None, financials=None, cashflow=None):
    ticker = MagicMock()
    ticker.info = info if info is not None else _make_info()
    ticker.financials = financials if financials is not None else _make_financials()
    ticker.cashflow = cashflow if cashflow is not None else _make_cashflow()
    return ticker


# ── Tool structure ────────────────────────────────────────────────────────────

class TestFundamentalDataToolStructure:

    def test_tool_name(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        assert FundamentalDataTool().name == "fetch_fundamental_data"

    def test_description_is_not_empty(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        assert len(FundamentalDataTool().description) > 20


# ── Successful fetch ──────────────────────────────────────────────────────────

class TestFundamentalDataSuccess:

    @pytest.fixture(autouse=True)
    def mock_yf(self):
        with patch("yfinance.Ticker", return_value=_make_ticker()):
            yield

    def test_top_level_sections_present(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        result = FundamentalDataTool()._run("NVDA")
        for section in ("ticker", "meta", "valuation", "profitability",
                        "growth", "balance_sheet", "dividend"):
            assert section in result, f"Missing section: {section}"

    def test_ticker_is_uppercased(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        result = FundamentalDataTool()._run("nvda")
        assert result["ticker"] == "NVDA"

    def test_meta_section_fields(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        meta = FundamentalDataTool()._run("NVDA")["meta"]
        for field in ("company_name", "sector", "industry"):
            assert field in meta

    def test_valuation_section_fields(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        val = FundamentalDataTool()._run("NVDA")["valuation"]
        for field in ("market_cap", "pe_ratio", "pb_ratio", "ps_ratio"):
            assert field in val

    def test_profitability_section_fields(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        prof = FundamentalDataTool()._run("NVDA")["profitability"]
        for field in ("gross_margin", "operating_margin", "net_margin",
                      "return_on_equity", "return_on_assets"):
            assert field in prof

    def test_growth_section_fields(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        growth = FundamentalDataTool()._run("NVDA")["growth"]
        for field in ("revenue_growth_yoy", "earnings_growth_yoy",
                      "revenue_ttm", "net_income_ttm"):
            assert field in growth

    def test_balance_sheet_section_fields(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        bs = FundamentalDataTool()._run("NVDA")["balance_sheet"]
        for field in ("total_debt", "total_cash", "debt_to_equity",
                      "current_ratio", "free_cash_flow"):
            assert field in bs

    def test_free_cash_flow_is_computed(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        bs = FundamentalDataTool()._run("NVDA")["balance_sheet"]
        assert bs["free_cash_flow"] == pytest.approx(500_000_000.0)

    def test_revenue_ttm_from_financials(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        growth = FundamentalDataTool()._run("NVDA")["growth"]
        assert growth["revenue_ttm"] == pytest.approx(2_000_000_000.0)

    def test_net_income_ttm_from_financials(self):
        from utils.fundamental_data_tool import FundamentalDataTool
        growth = FundamentalDataTool()._run("NVDA")["growth"]
        assert growth["net_income_ttm"] == pytest.approx(400_000_000.0)

    def test_description_snippet_truncated_at_400_chars(self):
        long_desc = "x" * 600
        ticker = _make_ticker(info=_make_info(longBusinessSummary=long_desc))
        with patch("yfinance.Ticker", return_value=ticker):
            from utils.fundamental_data_tool import FundamentalDataTool
            meta = FundamentalDataTool()._run("NVDA")["meta"]
            assert len(meta["description_snippet"]) <= 402  # 400 + ellipsis


# ── None / missing values ─────────────────────────────────────────────────────

class TestFundamentalDataMissingValues:

    def test_none_values_are_returned_as_none(self):
        info = _make_info(trailingPE=None, dividendYield=None)
        with patch("yfinance.Ticker", return_value=_make_ticker(info=info)):
            from utils.fundamental_data_tool import FundamentalDataTool
            result = FundamentalDataTool()._run("NVDA")
            assert result["valuation"]["pe_ratio"] is None
            assert result["dividend"]["dividend_yield"] is None

    def test_missing_financials_still_returns_result(self):
        empty_fin = pd.DataFrame()
        with patch("yfinance.Ticker",
                   return_value=_make_ticker(financials=empty_fin)):
            from utils.fundamental_data_tool import FundamentalDataTool
            result = FundamentalDataTool()._run("NVDA")
            assert "error" not in result
            assert result["growth"]["revenue_ttm"] is None


# ── Error handling ────────────────────────────────────────────────────────────

class TestFundamentalDataErrors:

    def test_no_market_price_returns_error(self):
        info = _make_info(regularMarketPrice=None, currentPrice=None)
        with patch("yfinance.Ticker", return_value=_make_ticker(info=info)):
            from utils.fundamental_data_tool import FundamentalDataTool
            result = FundamentalDataTool()._run("FAKE")
            assert "error" in result

    def test_empty_info_dict_returns_error(self):
        ticker = _make_ticker(info={})
        with patch("yfinance.Ticker", return_value=ticker):
            from utils.fundamental_data_tool import FundamentalDataTool
            result = FundamentalDataTool()._run("FAKE")
            assert "error" in result

    def test_exception_returns_error_dict(self):
        with patch("yfinance.Ticker", side_effect=Exception("network timeout")):
            from utils.fundamental_data_tool import FundamentalDataTool
            result = FundamentalDataTool()._run("NVDA")
            assert "error" in result
            assert "ticker" in result
