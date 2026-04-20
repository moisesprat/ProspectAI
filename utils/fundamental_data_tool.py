#!/usr/bin/env python3
"""
Fundamental Data Tool — fetches real financial data for a batch of tickers via yfinance.
Call ONCE with all tickers; the tool loops internally and returns all results.
"""

import json
from typing import Any, Dict
from crewai.tools import BaseTool


class FundamentalDataTool(BaseTool):
    """
    Fetches fundamental financial data for a batch of stock tickers using yfinance.
    Accepts a JSON array of ticker strings; returns all results in one call.
    Per-ticker errors are included inline — they never abort the batch.
    """

    name: str = "fetch_fundamental_data"
    description: str = """Fetch fundamental financial data for a list of stock tickers using yfinance.

    Call this tool ONCE with ALL tickers as a JSON array. The tool loops internally
    and returns all results together — no need to call it per ticker.

    Args:
        tickers_json: JSON array of ticker strings, e.g. '["AAPL","NVDA","MSFT"]'

    Returns JSON: {"fundamentals": [one entry per ticker]}
    Each entry contains sections: meta, valuation, profitability, growth,
    balance_sheet, dividend — or {"ticker": "X", "error": "..."} on failure.
    """

    def _run(self, tickers_json: str) -> str:
        try:
            tickers = json.loads(tickers_json)
        except (json.JSONDecodeError, TypeError) as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

        if not isinstance(tickers, list) or len(tickers) == 0:
            return json.dumps({"error": "tickers_json must be a non-empty JSON array of ticker strings"})

        return json.dumps({"fundamentals": [self._fetch_one(t) for t in tickers]})

    def _fetch_one(self, ticker: str) -> Dict[str, Any]:
        try:
            import yfinance as yf
        except ImportError:
            return {"ticker": ticker, "error": "yfinance not installed. Run: pip install yfinance"}

        try:
            stock = yf.Ticker(ticker.upper())
            info = stock.info

            if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
                return {
                    "ticker": ticker,
                    "error": f"No data returned by yfinance for ticker '{ticker}'. "
                             "Verify the symbol is correct and listed.",
                }

            def safe(key: str, default=None):
                val = info.get(key)
                return val if val is not None else default

            revenue_ttm = None
            net_income_ttm = None
            try:
                fin = stock.financials
                if fin is not None and not fin.empty:
                    if "Total Revenue" in fin.index:
                        revenue_ttm = float(fin.loc["Total Revenue"].iloc[0])
                    if "Net Income" in fin.index:
                        net_income_ttm = float(fin.loc["Net Income"].iloc[0])
            except Exception:
                pass

            free_cash_flow = None
            try:
                cf = stock.cashflow
                if cf is not None and not cf.empty:
                    op_cf = None
                    capex = None
                    if "Operating Cash Flow" in cf.index:
                        op_cf = float(cf.loc["Operating Cash Flow"].iloc[0])
                    if "Capital Expenditure" in cf.index:
                        capex = float(cf.loc["Capital Expenditure"].iloc[0])
                    if op_cf is not None and capex is not None:
                        free_cash_flow = op_cf + capex  # capex is negative in yfinance
            except Exception:
                pass

            description = safe("longBusinessSummary", "")
            description_snippet = description[:400] + "…" if len(description) > 400 else description

            return {
                "ticker": ticker.upper(),
                "meta": {
                    "company_name": safe("longName", ticker),
                    "sector": safe("sector"),
                    "industry": safe("industry"),
                    "employees": safe("fullTimeEmployees"),
                    "description_snippet": description_snippet,
                    "website": safe("website"),
                },
                "valuation": {
                    "market_cap": safe("marketCap"),
                    "enterprise_value": safe("enterpriseValue"),
                    "pe_ratio": safe("trailingPE"),
                    "forward_pe": safe("forwardPE"),
                    "pb_ratio": safe("priceToBook"),
                    "ps_ratio": safe("priceToSalesTrailing12Months"),
                    "ev_ebitda": safe("enterpriseToEbitda"),
                    "price_52w_high": safe("fiftyTwoWeekHigh"),
                    "price_52w_low": safe("fiftyTwoWeekLow"),
                    "beta": safe("beta"),
                },
                "profitability": {
                    "gross_margin": safe("grossMargins"),
                    "operating_margin": safe("operatingMargins"),
                    "net_margin": safe("profitMargins"),
                    "return_on_equity": safe("returnOnEquity"),
                    "return_on_assets": safe("returnOnAssets"),
                    "ebitda": safe("ebitda"),
                },
                "growth": {
                    "revenue_growth_yoy": safe("revenueGrowth"),
                    "earnings_growth_yoy": safe("earningsGrowth"),
                    "revenue_ttm": revenue_ttm,
                    "net_income_ttm": net_income_ttm,
                    "earnings_per_share_ttm": safe("trailingEps"),
                    "forward_eps": safe("forwardEps"),
                },
                "balance_sheet": {
                    "total_debt": safe("totalDebt"),
                    "total_cash": safe("totalCash"),
                    # yfinance returns debtToEquity as a percentage-scaled number
                    # (e.g. 150.0 for a D/E ratio of 1.5). Divide by 100 to
                    # normalise to a plain ratio, consistent with the tool contract.
                    "debt_to_equity": (
                        safe("debtToEquity") / 100
                        if safe("debtToEquity") is not None else None
                    ),
                    "current_ratio": safe("currentRatio"),
                    "quick_ratio": safe("quickRatio"),
                    "free_cash_flow": free_cash_flow,
                    "book_value_per_share": safe("bookValue"),
                },
                "dividend": {
                    "dividend_yield": safe("dividendYield"),
                    "payout_ratio": safe("payoutRatio"),
                    "dividend_rate": safe("dividendRate"),
                },
            }

        except Exception as e:
            return {"ticker": ticker, "error": f"Unexpected error fetching data for '{ticker}': {str(e)}"}
