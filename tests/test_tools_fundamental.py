"""
Tests for FundamentalDataTool and FundamentalGraderTool.
yfinance is mocked — no network required.
"""

import json
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from utils.fundamental_data_tool import FundamentalDataTool
from utils.fundamental_grader_tool import FundamentalGraderTool


# ── Fixtures ───────────────────────────────────────────────────────────────────

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
        # yfinance returns D/E percentage-scaled (150 = ratio of 1.5)
        "debtToEquity": 40.0,
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


# ── FundamentalDataTool — structure ───────────────────────────────────────────

def test_fetch_tool_name():
    assert FundamentalDataTool().name == "fetch_fundamental_data"


class TestFundamentalDataSuccess:

    @pytest.fixture(autouse=True)
    def mock_yf(self):
        with patch("yfinance.Ticker", return_value=_make_ticker()):
            yield

    def test_top_level_sections_present(self):
        result = FundamentalDataTool()._run("NVDA")
        for section in ("ticker", "meta", "valuation", "profitability",
                        "growth", "balance_sheet", "dividend"):
            assert section in result, f"Missing section: {section}"

    def test_ticker_is_uppercased(self):
        result = FundamentalDataTool()._run("nvda")
        assert result["ticker"] == "NVDA"

    def test_meta_section_fields(self):
        meta = FundamentalDataTool()._run("NVDA")["meta"]
        for field in ("company_name", "sector", "industry"):
            assert field in meta

    def test_valuation_section_fields(self):
        val = FundamentalDataTool()._run("NVDA")["valuation"]
        for field in ("market_cap", "pe_ratio", "pb_ratio", "ps_ratio"):
            assert field in val

    def test_profitability_section_fields(self):
        prof = FundamentalDataTool()._run("NVDA")["profitability"]
        for field in ("gross_margin", "operating_margin", "net_margin",
                      "return_on_equity", "return_on_assets"):
            assert field in prof

    def test_growth_section_fields(self):
        growth = FundamentalDataTool()._run("NVDA")["growth"]
        for field in ("revenue_growth_yoy", "earnings_growth_yoy",
                      "revenue_ttm", "net_income_ttm"):
            assert field in growth

    def test_balance_sheet_section_fields(self):
        bs = FundamentalDataTool()._run("NVDA")["balance_sheet"]
        for field in ("total_debt", "total_cash", "debt_to_equity",
                      "current_ratio", "free_cash_flow"):
            assert field in bs

    def test_free_cash_flow_is_op_cf_plus_capex(self):
        # op_cf=600M, capex=-100M → FCF = 500M
        bs = FundamentalDataTool()._run("NVDA")["balance_sheet"]
        assert bs["free_cash_flow"] == pytest.approx(500_000_000.0)

    def test_revenue_ttm_from_financials(self):
        growth = FundamentalDataTool()._run("NVDA")["growth"]
        assert growth["revenue_ttm"] == pytest.approx(2_000_000_000.0)

    def test_net_income_ttm_from_financials(self):
        growth = FundamentalDataTool()._run("NVDA")["growth"]
        assert growth["net_income_ttm"] == pytest.approx(400_000_000.0)

    def test_debt_to_equity_normalised(self):
        # yfinance returns 40.0 (percentage-scaled); tool divides by 100 → 0.40
        bs = FundamentalDataTool()._run("NVDA")["balance_sheet"]
        assert bs["debt_to_equity"] == pytest.approx(0.40)

    def test_description_snippet_truncated_at_400_chars(self):
        long_desc = "x" * 600
        ticker = _make_ticker(info=_make_info(longBusinessSummary=long_desc))
        with patch("yfinance.Ticker", return_value=ticker):
            meta = FundamentalDataTool()._run("NVDA")["meta"]
        assert len(meta["description_snippet"]) <= 402  # 400 chars + "…"


class TestFundamentalDataMissingValues:

    def test_none_values_are_returned_as_none(self):
        info = _make_info(trailingPE=None, dividendYield=None)
        with patch("yfinance.Ticker", return_value=_make_ticker(info=info)):
            result = FundamentalDataTool()._run("NVDA")
        assert result["valuation"]["pe_ratio"] is None
        assert result["dividend"]["dividend_yield"] is None

    def test_missing_financials_does_not_crash(self):
        with patch("yfinance.Ticker", return_value=_make_ticker(financials=pd.DataFrame())):
            result = FundamentalDataTool()._run("NVDA")
        assert "error" not in result
        assert result["growth"]["revenue_ttm"] is None

    def test_missing_cashflow_does_not_crash(self):
        with patch("yfinance.Ticker", return_value=_make_ticker(cashflow=pd.DataFrame())):
            result = FundamentalDataTool()._run("NVDA")
        assert "error" not in result
        assert result["balance_sheet"]["free_cash_flow"] is None


class TestFundamentalDataErrors:

    def test_no_market_price_returns_error(self):
        info = _make_info(regularMarketPrice=None, currentPrice=None)
        with patch("yfinance.Ticker", return_value=_make_ticker(info=info)):
            result = FundamentalDataTool()._run("FAKE")
        assert "error" in result

    def test_empty_info_dict_returns_error(self):
        with patch("yfinance.Ticker", return_value=_make_ticker(info={})):
            result = FundamentalDataTool()._run("FAKE")
        assert "error" in result

    def test_exception_returns_error_dict_with_ticker(self):
        with patch("yfinance.Ticker", side_effect=Exception("network timeout")):
            result = FundamentalDataTool()._run("NVDA")
        assert "error" in result
        assert "ticker" in result


# ── FundamentalGraderTool ─────────────────────────────────────────────────────

def test_grader_tool_name():
    assert FundamentalGraderTool().name == "grade_fundamental_data"


def _grade(ticker="TEST", **kwargs) -> dict:
    defaults = {
        "pe_ratio": None, "ps_ratio": None, "current_ratio": None,
        "debt_to_equity": None, "free_cash_flow": None, "revenue_growth_yoy": None,
    }
    defaults.update(kwargs)
    raw = json.dumps(defaults)
    return json.loads(FundamentalGraderTool()._run(ticker, raw))


class TestValuationGrade:

    def test_pe_below_15_is_cheap(self):
        assert _grade(pe_ratio=12.0)["valuation_grade"] == "CHEAP"

    def test_pe_15_to_25_is_fair(self):
        assert _grade(pe_ratio=20.0)["valuation_grade"] == "FAIR"

    def test_pe_25_to_40_is_expensive(self):
        assert _grade(pe_ratio=32.0)["valuation_grade"] == "EXPENSIVE"

    def test_pe_above_40_is_very_expensive(self):
        assert _grade(pe_ratio=65.0)["valuation_grade"] == "VERY_EXPENSIVE"

    def test_ps_used_when_pe_missing(self):
        assert _grade(ps_ratio=2.0)["valuation_grade"] == "CHEAP"
        assert _grade(ps_ratio=4.5)["valuation_grade"] == "FAIR"
        assert _grade(ps_ratio=8.0)["valuation_grade"] == "EXPENSIVE"

    def test_defaults_to_fair_when_no_data(self):
        assert _grade()["valuation_grade"] == "FAIR"


class TestFinancialHealth:

    def test_strong_when_all_metrics_healthy(self):
        result = _grade(current_ratio=2.0, debt_to_equity=0.5, free_cash_flow=1_000_000)
        assert result["financial_health"] == "STRONG"

    def test_weak_when_current_ratio_below_1(self):
        result = _grade(current_ratio=0.8)
        assert result["financial_health"] == "WEAK"

    def test_weak_when_de_above_3(self):
        result = _grade(debt_to_equity=3.5)
        assert result["financial_health"] == "WEAK"

    def test_weak_when_fcf_negative(self):
        result = _grade(free_cash_flow=-500_000)
        assert result["financial_health"] == "WEAK"

    def test_adequate_when_metrics_middling(self):
        result = _grade(current_ratio=1.2, debt_to_equity=1.5, free_cash_flow=100)
        assert result["financial_health"] == "ADEQUATE"


class TestGrowthOutlook:

    def test_high_when_revenue_above_15_pct(self):
        assert _grade(revenue_growth_yoy=0.20)["growth_outlook"] == "HIGH"

    def test_moderate_when_revenue_5_to_15_pct(self):
        assert _grade(revenue_growth_yoy=0.10)["growth_outlook"] == "MODERATE"

    def test_low_when_revenue_0_to_5_pct(self):
        assert _grade(revenue_growth_yoy=0.03)["growth_outlook"] == "LOW"

    def test_declining_when_revenue_negative(self):
        assert _grade(revenue_growth_yoy=-0.05)["growth_outlook"] == "DECLINING"

    def test_defaults_to_moderate_when_no_revenue_data(self):
        assert _grade()["growth_outlook"] == "MODERATE"


class TestFundamentalComponent:

    @pytest.mark.parametrize("health,growth,expected", [
        ("STRONG",   "HIGH",      30),   # 20 + 10
        ("STRONG",   "MODERATE",  27),   # 20 + 7
        ("ADEQUATE", "HIGH",      20),   # 10 + 10
        ("ADEQUATE", "LOW",       13),   # 10 + 3
        ("WEAK",     "DECLINING",  6),   # 5  + 1
        ("WEAK",     "MODERATE",  12),   # 5  + 7
    ])
    def test_component_sum(self, health, growth, expected):
        health_pts  = {"STRONG": 20, "ADEQUATE": 10, "WEAK": 5}[health]
        growth_pts  = {"HIGH": 10, "MODERATE": 7, "LOW": 3, "DECLINING": 1}[growth]
        assert health_pts + growth_pts == expected

    def test_grader_returns_fundamental_component_field(self):
        result = _grade(current_ratio=2.0, debt_to_equity=0.5,
                        free_cash_flow=1_000_000, revenue_growth_yoy=0.20)
        assert result["fundamental_component"] == 30  # STRONG + HIGH

    def test_fundamental_component_never_below_6(self):
        # Worst case: WEAK + DECLINING = 5 + 1 = 6
        result = _grade(current_ratio=0.5, free_cash_flow=-1, revenue_growth_yoy=-0.5)
        assert result["fundamental_component"] >= 6
