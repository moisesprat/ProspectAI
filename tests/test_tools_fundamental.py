"""
Tests for FundamentalDataTool and FundamentalGraderTool.
yfinance is mocked — no network required.
"""

import json
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from utils.fundamental_data_tool import FundamentalDataTool
from utils.fundamental_grader_tool import FundamentalGraderTool, fundamentals_status
from schemas.agent_outputs import FundamentalRating, StockFundamentalAnalysis


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


def _fetch_one(tickers=None, **yf_kwargs):
    """Call FundamentalDataTool with a batch and return the first (or only) result dict."""
    if tickers is None:
        tickers = ["NVDA"]
    with patch("yfinance.Ticker", return_value=_make_ticker(**yf_kwargs)):
        raw = json.loads(FundamentalDataTool()._run(json.dumps(tickers)))
    return raw["fundamentals"][0]


# ── FundamentalDataTool — structure ───────────────────────────────────────────

def test_fetch_tool_name():
    assert FundamentalDataTool().name == "fetch_fundamental_data"


def test_fetch_returns_batch_wrapper():
    with patch("yfinance.Ticker", return_value=_make_ticker()):
        raw = json.loads(FundamentalDataTool()._run('["NVDA"]'))
    assert "fundamentals" in raw
    assert len(raw["fundamentals"]) == 1


def test_fetch_returns_all_tickers_in_batch():
    with patch("yfinance.Ticker", return_value=_make_ticker()):
        raw = json.loads(FundamentalDataTool()._run('["NVDA", "AAPL"]'))
    assert len(raw["fundamentals"]) == 2


def test_fetch_invalid_json_returns_error():
    raw = json.loads(FundamentalDataTool()._run("not-json"))
    assert "error" in raw


def test_fetch_empty_array_returns_error():
    raw = json.loads(FundamentalDataTool()._run("[]"))
    assert "error" in raw


class TestFundamentalDataSuccess:

    @pytest.fixture(autouse=True)
    def mock_yf(self):
        with patch("yfinance.Ticker", return_value=_make_ticker()):
            yield

    def test_top_level_sections_present(self):
        result = _fetch_one()
        for section in ("ticker", "meta", "valuation", "profitability",
                        "growth", "balance_sheet", "dividend"):
            assert section in result, f"Missing section: {section}"

    def test_ticker_is_uppercased(self):
        result = _fetch_one(["nvda"])
        assert result["ticker"] == "NVDA"

    def test_meta_section_fields(self):
        meta = _fetch_one()["meta"]
        for field in ("company_name", "sector", "industry"):
            assert field in meta

    def test_valuation_section_fields(self):
        val = _fetch_one()["valuation"]
        for field in ("market_cap", "pe_ratio", "pb_ratio", "ps_ratio"):
            assert field in val

    def test_profitability_section_fields(self):
        prof = _fetch_one()["profitability"]
        for field in ("gross_margin", "operating_margin", "net_margin",
                      "return_on_equity", "return_on_assets"):
            assert field in prof

    def test_growth_section_fields(self):
        growth = _fetch_one()["growth"]
        for field in ("revenue_growth_yoy", "earnings_growth_yoy",
                      "revenue_ttm", "net_income_ttm"):
            assert field in growth

    def test_balance_sheet_section_fields(self):
        bs = _fetch_one()["balance_sheet"]
        for field in ("total_debt", "total_cash", "debt_to_equity",
                      "current_ratio", "free_cash_flow"):
            assert field in bs

    def test_free_cash_flow_is_op_cf_plus_capex(self):
        # op_cf=600M, capex=-100M → FCF = 500M
        bs = _fetch_one()["balance_sheet"]
        assert bs["free_cash_flow"] == pytest.approx(500_000_000.0)

    def test_revenue_ttm_from_financials(self):
        growth = _fetch_one()["growth"]
        assert growth["revenue_ttm"] == pytest.approx(2_000_000_000.0)

    def test_net_income_ttm_from_financials(self):
        growth = _fetch_one()["growth"]
        assert growth["net_income_ttm"] == pytest.approx(400_000_000.0)

    def test_debt_to_equity_normalised(self):
        # yfinance returns 40.0 (percentage-scaled); tool divides by 100 → 0.40
        bs = _fetch_one()["balance_sheet"]
        assert bs["debt_to_equity"] == pytest.approx(0.40)

    def test_description_snippet_truncated_at_400_chars(self):
        long_desc = "x" * 600
        ticker_mock = _make_ticker(info=_make_info(longBusinessSummary=long_desc))
        with patch("yfinance.Ticker", return_value=ticker_mock):
            raw = json.loads(FundamentalDataTool()._run('["NVDA"]'))
        meta = raw["fundamentals"][0]["meta"]
        assert len(meta["description_snippet"]) <= 402  # 400 chars + "…"


class TestFundamentalDataMissingValues:

    def test_none_values_are_returned_as_none(self):
        info = _make_info(trailingPE=None, dividendYield=None)
        with patch("yfinance.Ticker", return_value=_make_ticker(info=info)):
            raw = json.loads(FundamentalDataTool()._run('["NVDA"]'))
        result = raw["fundamentals"][0]
        assert result["valuation"]["pe_ratio"] is None
        assert result["dividend"]["dividend_yield"] is None

    def test_missing_financials_does_not_crash(self):
        with patch("yfinance.Ticker", return_value=_make_ticker(financials=pd.DataFrame())):
            raw = json.loads(FundamentalDataTool()._run('["NVDA"]'))
        result = raw["fundamentals"][0]
        assert "error" not in result
        assert result["growth"]["revenue_ttm"] is None

    def test_missing_cashflow_does_not_crash(self):
        with patch("yfinance.Ticker", return_value=_make_ticker(cashflow=pd.DataFrame())):
            raw = json.loads(FundamentalDataTool()._run('["NVDA"]'))
        result = raw["fundamentals"][0]
        assert "error" not in result
        assert result["balance_sheet"]["free_cash_flow"] is None


class TestFundamentalDataErrors:

    def test_no_market_price_returns_error_entry(self):
        info = _make_info(regularMarketPrice=None, currentPrice=None)
        with patch("yfinance.Ticker", return_value=_make_ticker(info=info)):
            raw = json.loads(FundamentalDataTool()._run('["FAKE"]'))
        assert "error" in raw["fundamentals"][0]

    def test_empty_info_dict_returns_error_entry(self):
        with patch("yfinance.Ticker", return_value=_make_ticker(info={})):
            raw = json.loads(FundamentalDataTool()._run('["FAKE"]'))
        assert "error" in raw["fundamentals"][0]

    def test_exception_returns_error_entry_with_ticker(self):
        with patch("yfinance.Ticker", side_effect=Exception("network timeout")):
            raw = json.loads(FundamentalDataTool()._run('["NVDA"]'))
        entry = raw["fundamentals"][0]
        assert "error" in entry
        assert "ticker" in entry

    def test_one_failing_ticker_does_not_abort_batch(self):
        good_ticker = _make_ticker()
        bad_info = _make_info(regularMarketPrice=None, currentPrice=None)
        bad_ticker = _make_ticker(info=bad_info)

        call_count = {"n": 0}
        def side_effect(symbol):
            call_count["n"] += 1
            return bad_ticker if symbol.upper() == "FAKE" else good_ticker

        with patch("yfinance.Ticker", side_effect=side_effect):
            raw = json.loads(FundamentalDataTool()._run('["NVDA", "FAKE"]'))

        assert len(raw["fundamentals"]) == 2
        good = next(e for e in raw["fundamentals"] if e["ticker"] == "NVDA")
        bad  = next(e for e in raw["fundamentals"] if e["ticker"] == "FAKE")
        assert "error" not in good
        assert "error" in bad


# ── FundamentalGraderTool ─────────────────────────────────────────────────────

def test_grader_tool_name():
    assert FundamentalGraderTool().name == "grade_fundamental_data"


def _make_raw_entry(ticker="TEST", error=None, **metric_overrides):
    """Build a fake fetch_fundamental_data entry for use in grader tests."""
    if error:
        return {"ticker": ticker, "error": error}
    metrics = {
        "pe_ratio": None, "ps_ratio": None, "current_ratio": None,
        "debt_to_equity": None, "free_cash_flow": None, "revenue_growth_yoy": None,
    }
    metrics.update(metric_overrides)
    return {
        "ticker": ticker,
        "valuation":    {"pe_ratio": metrics["pe_ratio"], "ps_ratio": metrics["ps_ratio"]},
        "balance_sheet": {
            "current_ratio": metrics["current_ratio"],
            "debt_to_equity": metrics["debt_to_equity"],
            "free_cash_flow": metrics["free_cash_flow"],
        },
        "growth":       {"revenue_growth_yoy": metrics["revenue_growth_yoy"]},
        "meta": {}, "profitability": {}, "dividend": {},
    }


def _grade(ticker="TEST", **kwargs) -> dict:
    """Grade a single ticker by wrapping it in a batch."""
    entry = _make_raw_entry(ticker=ticker, **kwargs)
    batch = json.dumps({"fundamentals": [entry]})
    result = json.loads(FundamentalGraderTool()._run(batch))
    return result["grades"][0]


class TestValuationGrade:

    def test_pe_below_15_is_cheap(self):
        assert _grade(pe_ratio=12.0)["valuation"] == "CHEAP"

    def test_pe_15_to_25_is_fair(self):
        assert _grade(pe_ratio=20.0)["valuation"] == "FAIR"

    def test_pe_25_to_40_is_expensive(self):
        assert _grade(pe_ratio=32.0)["valuation"] == "EXPENSIVE"

    def test_pe_above_40_is_very_expensive(self):
        assert _grade(pe_ratio=65.0)["valuation"] == "VERY_EXPENSIVE"

    def test_ps_used_when_pe_missing(self):
        assert _grade(ps_ratio=2.0)["valuation"] == "CHEAP"
        assert _grade(ps_ratio=4.5)["valuation"] == "FAIR"
        assert _grade(ps_ratio=8.0)["valuation"] == "EXPENSIVE"

    def test_no_pe_no_ps_is_unknown(self):
        # CORR-11: absence of data is UNKNOWN, never a rewarded FAIR.
        assert _grade()["valuation"] == "UNKNOWN"


class TestQuality:

    def test_high_when_all_three_metrics_healthy(self):
        result = _grade(current_ratio=2.0, debt_to_equity=0.5, free_cash_flow=1_000_000)
        assert result["quality"] == "High"
        assert result["quality_score"] == 20

    def test_all_none_balance_sheet_is_unknown(self):
        result = _grade()
        assert result["quality"] == "UNKNOWN"
        assert result["quality_score"] is None

    def test_high_quality_needs_all_three_metrics(self):
        # Two strong metrics present, one missing: Medium, never High.
        assert _grade(current_ratio=2.0, debt_to_equity=0.5)["quality"] == "Medium"
        assert _grade(current_ratio=2.0, free_cash_flow=10)["quality"] == "Medium"
        assert _grade(debt_to_equity=0.5, free_cash_flow=10)["quality"] == "Medium"

    def test_one_weak_metric_is_low(self):
        # Any present weak metric gives Low even when the others are missing.
        assert _grade(current_ratio=0.8)["quality"] == "Low"
        assert _grade(debt_to_equity=3.5)["quality"] == "Low"
        assert _grade(free_cash_flow=-500_000)["quality"] == "Low"
        assert _grade(current_ratio=0.8)["quality_score"] == 5

    def test_medium_when_metrics_middling(self):
        result = _grade(current_ratio=1.2, debt_to_equity=1.5, free_cash_flow=100)
        assert result["quality"] == "Medium"
        assert result["quality_score"] == 10


class TestGrowth:

    def test_high_growth_when_revenue_above_15_pct(self):
        assert _grade(revenue_growth_yoy=0.20)["growth"] == "High Growth"

    def test_moderate_growth_when_revenue_5_to_15_pct(self):
        assert _grade(revenue_growth_yoy=0.10)["growth"] == "Moderate Growth"

    def test_stable_when_revenue_0_to_5_pct(self):
        assert _grade(revenue_growth_yoy=0.03)["growth"] == "Stable"

    def test_declining_when_revenue_negative(self):
        assert _grade(revenue_growth_yoy=-0.05)["growth"] == "Declining"

    def test_none_growth_is_unknown(self):
        result = _grade(current_ratio=2.0, debt_to_equity=0.5, free_cash_flow=1)
        assert result["growth"] == "UNKNOWN"
        assert result["growth_score"] is None
        assert result["fundamental_component"] is None
        assert result["fundamental_unknown"] is True


class TestFundamentalComponent:

    def test_grader_returns_fundamental_component_field(self):
        result = _grade(current_ratio=2.0, debt_to_equity=0.5,
                        free_cash_flow=1_000_000, revenue_growth_yoy=0.20)
        assert result["fundamental_component"] == 30  # High + High Growth
        assert result["fundamental_unknown"] is False

    def test_fundamental_component_never_below_6(self):
        # Worst case: Low + Declining = 5 + 1 = 6
        result = _grade(current_ratio=0.5, free_cash_flow=-1, revenue_growth_yoy=-0.5)
        assert result["fundamental_component"] == 6

    def test_unknown_quality_nulls_the_component(self):
        result = _grade(revenue_growth_yoy=0.20)
        assert result["quality"] == "UNKNOWN"
        assert result["fundamental_component"] is None
        assert result["fundamental_unknown"] is True


class TestDataStatus:

    def test_full_payload_is_ok(self):
        result = _grade(pe_ratio=20.0, current_ratio=2.0, debt_to_equity=0.5,
                        free_cash_flow=1, revenue_growth_yoy=0.1)
        assert result["data_status"] == "ok"

    def test_ps_instead_of_pe_still_ok(self):
        result = _grade(ps_ratio=2.0, current_ratio=2.0, debt_to_equity=0.5,
                        free_cash_flow=1, revenue_growth_yoy=0.1)
        assert result["data_status"] == "ok"

    def test_partial_payload_is_partial(self):
        assert _grade(pe_ratio=20.0)["data_status"] == "partial"
        assert _grade()["data_status"] == "partial"

    def test_fetch_error_is_failed(self):
        result = _grade(error="no data")
        assert result["data_status"] == "failed"
        assert result["valuation"] == result["quality"] == result["growth"] == "UNKNOWN"
        assert result["quality_score"] is None
        assert result["growth_score"] is None
        assert result["fundamental_component"] is None
        assert result["fundamental_unknown"] is True


class TestSchemaRoundTrip:
    """Tracer: raw fetch payload -> real grader -> schema FundamentalRating (CORR-02)."""

    @pytest.mark.parametrize("kwargs,status", [
        (dict(pe_ratio=20.0, current_ratio=2.0, debt_to_equity=0.5,
              free_cash_flow=1, revenue_growth_yoy=0.1), "ok"),
        (dict(pe_ratio=20.0), "partial"),
        (dict(error="no data"), "failed"),
    ])
    def test_grades_validate_against_schema(self, kwargs, status):
        g = _grade(**kwargs)
        rating = FundamentalRating(
            valuation=g["valuation"], quality=g["quality"], growth=g["growth"],
        )
        assert rating.valuation == g["valuation"]
        assert g["data_status"] == status
        analysis = StockFundamentalAnalysis(
            ticker=g["ticker"], company_name="Test Corp",
            valuation_metrics={}, fundamental_rating=rating,
            key_strengths=["s"], key_risks=["r"], investment_thesis="a thesis text",
            data_status=g["data_status"],
        )
        assert analysis.data_status == status


class TestFundamentalsStatusHelper:

    def test_available_when_both_known(self):
        assert fundamentals_status("Medium", "Stable") == "AVAILABLE"

    def test_unknown_when_either_unknown(self):
        assert fundamentals_status("UNKNOWN", "Stable") == "UNKNOWN"
        assert fundamentals_status("High", "UNKNOWN") == "UNKNOWN"
        assert fundamentals_status("UNKNOWN", "UNKNOWN") == "UNKNOWN"


class TestGraderBatch:

    def test_grades_all_tickers_in_batch(self):
        entries = [_make_raw_entry("AAPL", pe_ratio=20.0), _make_raw_entry("NVDA", pe_ratio=65.0)]
        batch = json.dumps({"fundamentals": entries})
        result = json.loads(FundamentalGraderTool()._run(batch))
        assert len(result["grades"]) == 2
        tickers = {g["ticker"] for g in result["grades"]}
        assert tickers == {"AAPL", "NVDA"}

    def test_error_ticker_gets_unknown_grades(self):
        entries = [_make_raw_entry("GOOD", pe_ratio=20.0), _make_raw_entry("BAD", error="no data")]
        batch = json.dumps({"fundamentals": entries})
        result = json.loads(FundamentalGraderTool()._run(batch))
        grades = {g["ticker"]: g for g in result["grades"]}
        assert grades["GOOD"]["valuation"] != "UNKNOWN"
        assert grades["BAD"]["fundamental_unknown"] is True
        assert grades["BAD"]["valuation"] == "UNKNOWN"

    def test_invalid_json_returns_error(self):
        result = json.loads(FundamentalGraderTool()._run("not-json"))
        assert "error" in result
