"""
Module-level yfinance data cache, scoped to one run_analysis() call.

TechnicalAnalysisTool and FundamentalDataTool share this cache so that
repeated lookups for the same ticker within a single pipeline run hit the
network only once.  Call clear() at the start of each run_analysis() to
discard stale data from the previous run.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

import pandas as pd
import yfinance as yf

# (ticker_upper, period, interval) → DataFrame
_history_cache: Dict[Tuple[str, str, str], pd.DataFrame] = {}
# ticker_upper → dict  (from yf.Ticker.info)
_info_cache: Dict[str, Dict[str, Any]] = {}
# ticker_upper → DataFrame  (from yf.Ticker.financials)
_financials_cache: Dict[str, Any] = {}
# ticker_upper → DataFrame  (from yf.Ticker.cashflow)
_cashflow_cache: Dict[str, Any] = {}


def clear() -> None:
    """Discard all cached data. Call once at the start of each run_analysis()."""
    _history_cache.clear()
    _info_cache.clear()
    _financials_cache.clear()
    _cashflow_cache.clear()


def get_history(ticker: str, period: str, interval: str = "1d") -> pd.DataFrame:
    """Return OHLCV history DataFrame, fetching from yfinance on first access."""
    key = (ticker.upper(), period, interval)
    if key not in _history_cache:
        _history_cache[key] = yf.Ticker(ticker).history(period=period, interval=interval)
    return _history_cache[key]


def get_info(ticker: str) -> Dict[str, Any]:
    """Return the ticker info dict, fetching from yfinance on first access."""
    key = ticker.upper()
    if key not in _info_cache:
        _info_cache[key] = yf.Ticker(ticker).info
    return _info_cache[key]


def get_financials(ticker: str) -> Any:
    """Return the income-statement DataFrame, fetching from yfinance on first access."""
    key = ticker.upper()
    if key not in _financials_cache:
        _financials_cache[key] = yf.Ticker(ticker).financials
    return _financials_cache[key]


def get_cashflow(ticker: str) -> Any:
    """Return the cash-flow DataFrame, fetching from yfinance on first access."""
    key = ticker.upper()
    if key not in _cashflow_cache:
        _cashflow_cache[key] = yf.Ticker(ticker).cashflow
    return _cashflow_cache[key]
