#!/usr/bin/env python3
"""
Fundamental Data Tool - Fetches real financial data for a stock ticker via yfinance.
Provides valuation metrics, profitability ratios, growth figures, and balance sheet data.
"""

from typing import Any, Dict, Optional
from crewai.tools import BaseTool


class FundamentalDataTool(BaseTool):
    """
    Fetches fundamental financial data for a single stock ticker using yfinance.
    All returned values come directly from the API — nothing is estimated or inferred.
    Returns an error key (instead of raising) when data is unavailable.
    """

    name: str = "fetch_fundamental_data"
    description: str = """Fetch fundamental financial data for a stock ticker using yfinance.

    Args:
        ticker: Stock ticker symbol (e.g. 'AAPL', 'NVDA', 'JPM')

    Returns a nested dict with sections:
        meta          - company_name, sector, industry, employees, description_snippet
        valuation     - market_cap, enterprise_value, pe_ratio, forward_pe,
                        pb_ratio, ps_ratio, ev_ebitda
        profitability - gross_margin, operating_margin, net_margin,
                        return_on_equity, return_on_assets
        growth        - revenue_growth_yoy, earnings_growth_yoy,
                        revenue_ttm, net_income_ttm
        balance_sheet - total_debt, total_cash, debt_to_equity,
                        current_ratio, quick_ratio, free_cash_flow
        dividend      - dividend_yield, payout_ratio

    On failure returns: {ticker, error: str}
    All monetary values are in USD. Ratios and margins are decimal (e.g. 0.25 = 25%).
    """

    def _run(self, ticker: str) -> Dict[str, Any]:
        """Fetch and return fundamental data for the given ticker."""
        try:
            import yfinance as yf
        except ImportError:
            return {
                "ticker": ticker,
                "error": "yfinance not installed. Run: pip install yfinance",
            }

        try:
            stock = yf.Ticker(ticker.upper())
            info = stock.info

            if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
                # Ticker not found or delisted
                return {
                    "ticker": ticker,
                    "error": f"No data returned by yfinance for ticker '{ticker}'. "
                             "Verify the symbol is correct and listed.",
                }

            def safe(key: str, default=None):
                """Return info[key] if present and not None, else default."""
                val = info.get(key)
                return val if val is not None else default

            # --- Income statement (trailing twelve months) ---
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

            # --- Free cash flow from cash flow statement ---
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

            # --- Company description (truncated for token efficiency) ---
            description = safe("longBusinessSummary", "")
            description_snippet = (
                description[:400] + "…" if len(description) > 400 else description
            )

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
                    "debt_to_equity": safe("debtToEquity"),
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
            return {
                "ticker": ticker,
                "error": f"Unexpected error fetching data for '{ticker}': {str(e)}",
            }
