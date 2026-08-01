"""Tests for candidate_universe_filter (change deterministic-enforcement-v1-9-1)."""

from utils.candidate_universe_filter import excluded_tickers_for_sector, filter_candidates


class _Stock:
    def __init__(self, ticker):
        self.ticker = ticker


def test_excluded_tickers_includes_sector_benchmark():
    excluded = excluded_tickers_for_sector("Energy")
    assert "XLE" in excluded


def test_excluded_tickers_includes_broad_market_etfs():
    excluded = excluded_tickers_for_sector("Energy")
    assert "SPY" in excluded
    assert "QQQ" in excluded


def test_filter_candidates_drops_sector_benchmark_etf():
    stocks = [_Stock("XOM"), _Stock("XLE"), _Stock("CVX")]
    kept, dropped = filter_candidates(stocks, "Energy")
    assert [s.ticker for s in kept] == ["XOM", "CVX"]
    assert dropped == ["XLE"]


def test_filter_candidates_drops_broad_market_etf_regardless_of_sector():
    stocks = [_Stock("AAPL"), _Stock("SPY")]
    kept, dropped = filter_candidates(stocks, "Technology")
    assert [s.ticker for s in kept] == ["AAPL"]
    assert dropped == ["SPY"]


def test_filter_candidates_is_case_insensitive():
    stocks = [_Stock("xle"), _Stock("XOM")]
    kept, dropped = filter_candidates(stocks, "Energy")
    assert [s.ticker for s in kept] == ["XOM"]
    assert dropped == ["xle"]


def test_filter_candidates_keeps_all_when_no_etf_present():
    stocks = [_Stock("XOM"), _Stock("CVX")]
    kept, dropped = filter_candidates(stocks, "Energy")
    assert len(kept) == 2
    assert dropped == []


def test_unknown_sector_still_excludes_broad_market_etfs():
    excluded = excluded_tickers_for_sector("NotASector")
    assert "SPY" in excluded
