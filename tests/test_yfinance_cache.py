"""
Tests for utils/yfinance_cache.py.
yfinance is mocked — no network required.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

import utils.yfinance_cache as cache


@pytest.fixture(autouse=True)
def reset_cache():
    cache.clear()
    yield
    cache.clear()


def _mock_ticker(history_df=None, info_dict=None, financials_df=None, cashflow_df=None):
    ticker = MagicMock()
    ticker.history.return_value = history_df if history_df is not None else pd.DataFrame()
    ticker.info = info_dict if info_dict is not None else {}
    ticker.financials = financials_df if financials_df is not None else pd.DataFrame()
    ticker.cashflow = cashflow_df if cashflow_df is not None else pd.DataFrame()
    return ticker


# ── Deduplication ──────────────────────────────────────────────────────────────

def test_get_history_fetches_once():
    mock = _mock_ticker()
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        r1 = cache.get_history("AAPL", "1mo")
        r2 = cache.get_history("AAPL", "1mo")
    mock_cls.assert_called_once()
    assert r1 is r2


def test_get_info_fetches_once():
    mock = _mock_ticker(info_dict={"symbol": "AAPL"})
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        r1 = cache.get_info("AAPL")
        r2 = cache.get_info("AAPL")
    mock_cls.assert_called_once()
    assert r1 is r2


def test_get_financials_fetches_once():
    mock = _mock_ticker()
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        r1 = cache.get_financials("AAPL")
        r2 = cache.get_financials("AAPL")
    mock_cls.assert_called_once()
    assert r1 is r2


def test_get_cashflow_fetches_once():
    mock = _mock_ticker()
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        r1 = cache.get_cashflow("AAPL")
        r2 = cache.get_cashflow("AAPL")
    mock_cls.assert_called_once()
    assert r1 is r2


# ── Case-insensitivity ─────────────────────────────────────────────────────────

def test_get_info_case_insensitive():
    mock = _mock_ticker(info_dict={"symbol": "AAPL"})
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        cache.get_info("aapl")
        cache.get_info("AAPL")
    mock_cls.assert_called_once()


# ── clear() ────────────────────────────────────────────────────────────────────

def test_clear_forces_refetch():
    mock = _mock_ticker(info_dict={"symbol": "AAPL"})
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        cache.get_info("AAPL")
        cache.clear()
        cache.get_info("AAPL")
    assert mock_cls.call_count == 2
