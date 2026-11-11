"""
Per-run yfinance data cache, scoped to one run_analysis() call.

TechnicalAnalysisTool and FundamentalDataTool share this cache so that
repeated lookups for the same ticker within a single pipeline run hit the
network only once.

The cache belongs to one run, not to the process (CORR-08). The backend runs
several analyses in one process, each in its own plain thread, so module-level
dictionaries would let one run's clear() wipe another run's data mid-flight.
Instead the cache lives in a ContextVar:

- A plain thread starts with an empty context. run_analysis() calls clear()
  first, which installs a fresh cache in that thread's own context.
- asyncio.run() and asyncio.to_thread() copy the current context, so every
  Flow phase and every tool call of that run reads and fills the same cache.
- clear() only replaces the object in the current context. It never mutates
  a cache another run holds.
- run_in_executor() and executor worker threads do not copy the context and
  keep theirs between tasks. Outside a run (CLI, direct tool use) each getter
  call therefore gets a throwaway uncached object that is never stored in the
  context, so nothing leaks from one task to the next task on the same worker.
  Only clear() installs a cache.
- The cache ends with the run's context, so memory no longer grows across runs.

An empty answer from Yahoo (no rows, no keys, None) is logged once per run per
key, on the fetch path only: the empty value is cached, so a cache hit never
warns again. The warning names the dataset and the ticker cut to 20 characters
and escaped with repr(); it carries no data. The caller decides what an empty
answer means (the technical phase excludes the ticker, plan 02-15; phase 4
CORR-07).
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# prospectai-backend reads this through getattr() to decide whether concurrent
# runs in one process are safe (CORR-08). An older engine without it is run one
# analysis at a time.
RUN_SCOPED = True


class _RunCache:
    """The four per-run dictionaries. One instance belongs to one run."""

    __slots__ = ("history", "info", "financials", "cashflow")

    def __init__(self) -> None:
        # (ticker_upper, period, interval) → DataFrame
        self.history: Dict[Tuple[str, str, str], pd.DataFrame] = {}
        # ticker_upper → dict  (from yf.Ticker.info)
        self.info: Dict[str, Dict[str, Any]] = {}
        # ticker_upper → DataFrame  (from yf.Ticker.financials)
        self.financials: Dict[str, Any] = {}
        # ticker_upper → DataFrame  (from yf.Ticker.cashflow)
        self.cashflow: Dict[str, Any] = {}


_run_cache: ContextVar[Optional[_RunCache]] = ContextVar("yfinance_run_cache", default=None)


def clear() -> None:
    """Install a fresh cache for the current run. Call once at the start of each run_analysis()."""
    _run_cache.set(_RunCache())


def _cache() -> _RunCache:
    """Return the current run's cache, or a throwaway one when no run installed it.

    The throwaway is never stored with ContextVar.set(): a worker thread keeps
    its context between tasks, so a stored cache would be shared by later tasks.
    """
    cache = _run_cache.get()
    if cache is None:
        return _RunCache()
    return cache


def _yf_symbol(ticker: str) -> str:
    """Normalize a display ticker to the symbol yfinance/Yahoo Finance expects.

    Share-class tickers are commonly written with a dot (BRK.B, BF.B) in
    prose and search results, but Yahoo Finance's own symbol uses a dash
    (BRK-B, BF-B). Passing the dotted form doesn't raise -- it silently
    returns empty data, which previously surfaced several steps downstream
    as a null TechnicalAnalysisOutput entry failing schema validation.
    """
    return ticker.strip().upper().replace(".", "-")


def _warn_if_empty(dataset: str, ticker: str, value: Any) -> None:
    """Log one WARNING when yfinance answered with nothing for this dataset.

    Empty means None, an empty DataFrame or Series, or an empty dict. Any other
    type logs nothing. Only the dataset name and repr() of the first 20
    characters of the ticker are logged, never the contents of the value.
    """
    if value is None:
        empty = True
    elif isinstance(value, (pd.DataFrame, pd.Series)):
        empty = value.empty
    elif isinstance(value, dict):
        empty = not value
    else:
        empty = False
    if empty:
        logger.warning("yfinance returned no %s for %s", dataset, repr(str(ticker)[:20]))


def get_history(ticker: str, period: str, interval: str = "1d") -> pd.DataFrame:
    """Return OHLCV history DataFrame, fetching from yfinance on first access."""
    cache = _cache()
    key = (ticker.upper(), period, interval)
    if key not in cache.history:
        frame = yf.Ticker(_yf_symbol(ticker)).history(period=period, interval=interval)
        _warn_if_empty("price history", ticker, frame)
        cache.history[key] = frame
    return cache.history[key]


def get_info(ticker: str) -> Dict[str, Any]:
    """Return the ticker info dict, fetching from yfinance on first access."""
    cache = _cache()
    key = ticker.upper()
    if key not in cache.info:
        info = yf.Ticker(_yf_symbol(ticker)).info
        _warn_if_empty("company info", ticker, info)
        cache.info[key] = info
    return cache.info[key]


def get_financials(ticker: str) -> Any:
    """Return the income-statement DataFrame, fetching from yfinance on first access."""
    cache = _cache()
    key = ticker.upper()
    if key not in cache.financials:
        financials = yf.Ticker(_yf_symbol(ticker)).financials
        _warn_if_empty("income statement", ticker, financials)
        cache.financials[key] = financials
    return cache.financials[key]


def get_cashflow(ticker: str) -> Any:
    """Return the cash-flow DataFrame, fetching from yfinance on first access."""
    cache = _cache()
    key = ticker.upper()
    if key not in cache.cashflow:
        cashflow = yf.Ticker(_yf_symbol(ticker)).cashflow
        _warn_if_empty("cash flow", ticker, cashflow)
        cache.cashflow[key] = cashflow
    return cache.cashflow[key]
