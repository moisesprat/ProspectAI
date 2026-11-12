"""
Tests for utils/yfinance_cache.py.
yfinance is mocked — no network required.
"""

import ast
import pathlib

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


# ── Dotted share-class ticker normalization ─────────────────────────────────────

def test_get_info_normalizes_dotted_ticker_for_yfinance_call():
    mock = _mock_ticker(info_dict={"symbol": "BRK-B"})
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        cache.get_info("BRK.B")
    mock_cls.assert_called_once_with("BRK-B")


def test_get_history_normalizes_dotted_ticker_for_yfinance_call():
    mock = _mock_ticker()
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        cache.get_history("brk.b", "1mo")
    mock_cls.assert_called_once_with("BRK-B")


def test_get_financials_normalizes_dotted_ticker_for_yfinance_call():
    mock = _mock_ticker()
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        cache.get_financials("BF.B")
    mock_cls.assert_called_once_with("BF-B")


def test_get_cashflow_normalizes_dotted_ticker_for_yfinance_call():
    mock = _mock_ticker()
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        cache.get_cashflow("BF.B")
    mock_cls.assert_called_once_with("BF-B")


def test_dotted_and_dashed_forms_still_share_one_cache_entry_when_identical_input():
    # Cache key remains the display ticker as passed in (unnormalized) --
    # this only fixes the argument sent to yfinance, not cache identity.
    mock = _mock_ticker(info_dict={"symbol": "BRK-B"})
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        cache.get_info("BRK.B")
        cache.get_info("BRK.B")
    mock_cls.assert_called_once_with("BRK-B")


# ── clear() ────────────────────────────────────────────────────────────────────

def test_clear_forces_refetch():
    mock = _mock_ticker(info_dict={"symbol": "AAPL"})
    with patch("utils.yfinance_cache.yf.Ticker", return_value=mock) as mock_cls:
        cache.get_info("AAPL")
        cache.clear()
        cache.get_info("AAPL")
    assert mock_cls.call_count == 2


# ── Per-run isolation (CORR-08) ────────────────────────────────────────────────
#
# The backend runs each analysis in its own plain thread (empty context), so a
# ContextVar installed by clear() is private to that run. These tests drive two
# such threads against the module; yf.Ticker is patched to return a distinct
# object per call so identity and call counts prove isolation.

import asyncio
import itertools
import threading
from concurrent.futures import ThreadPoolExecutor

from crewai.flow.flow import Flow, listen, start

_JOIN_TIMEOUT = 20


def _numbered_ticker_factory():
    """Return (factory, calls): each yf.Ticker(...) call yields a ticker whose info is unique."""
    counter = itertools.count(1)
    calls = []
    lock = threading.Lock()

    def factory(symbol):
        with lock:
            n = next(counter)
            calls.append(symbol)
        t = MagicMock()
        t.info = {"fetch_number": n}
        return t

    return factory, calls


def _run_in_thread(fn):
    """Run fn in a plain thread (empty context); return its result or raise its error."""
    box = {}

    def target():
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller
            box["error"] = exc

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(_JOIN_TIMEOUT)
    assert not th.is_alive(), "thread did not finish (possible deadlock)"
    if "error" in box:
        raise box["error"]
    return box.get("value")


def test_clear_in_one_run_keeps_another_runs_cache():
    factory, calls = _numbered_ticker_factory()
    with patch("utils.yfinance_cache.yf.Ticker", side_effect=factory):
        a_ready, a_resume = threading.Event(), threading.Event()
        b_done = threading.Event()
        out = {}

        def run_a():
            cache.clear()
            out["a1"] = cache.get_info("AAPL")
            a_ready.set()
            assert b_done.wait(_JOIN_TIMEOUT)
            out["a2"] = cache.get_info("AAPL")

        def run_b():
            assert a_ready.wait(_JOIN_TIMEOUT)
            cache.clear()
            out["b1"] = cache.get_info("AAPL")
            b_done.set()

        ta = threading.Thread(target=run_a, daemon=True)
        tb = threading.Thread(target=run_b, daemon=True)
        ta.start(); tb.start()
        ta.join(_JOIN_TIMEOUT); tb.join(_JOIN_TIMEOUT)
        assert not ta.is_alive() and not tb.is_alive()

    assert len(calls) == 2
    assert out["a2"] is out["a1"]
    assert out["b1"] is not out["a1"]


def test_each_thread_gets_its_own_cache_object():
    def grab():
        cache.clear()
        return cache._run_cache.get()

    first = _run_in_thread(grab)
    second = _run_in_thread(grab)
    assert first is not None and second is not None
    assert first is not second


def test_to_thread_child_shares_the_run_cache():
    factory, calls = _numbered_ticker_factory()

    def run():
        cache.clear()
        first = cache.get_info("AAPL")

        async def child():
            return await asyncio.to_thread(cache.get_info, "AAPL")

        return first, asyncio.run(child())

    with patch("utils.yfinance_cache.yf.Ticker", side_effect=factory):
        first, second = _run_in_thread(run)
    assert first is second
    assert len(calls) == 1


class _ProbeFlow(Flow):
    """Minimal Flow: @start and @listen each read through asyncio.to_thread."""

    def __init__(self, barrier, sink):
        super().__init__()
        self._barrier = barrier
        self._sink = sink

    @start()
    async def first(self):
        self._sink["first"] = await asyncio.to_thread(cache.get_info, "AAPL")
        # Both runs have fetched before either reads again.
        await asyncio.to_thread(self._barrier.wait, _JOIN_TIMEOUT)
        return "go"

    @listen(first)
    async def second(self, _):
        self._sink["second"] = await asyncio.to_thread(cache.get_info, "AAPL")


def test_concurrent_flow_runs_keep_their_own_cache():
    factory, calls = _numbered_ticker_factory()
    barrier = threading.Barrier(2)
    sinks = [{}, {}]

    def run(sink):
        def go():
            cache.clear()
            _ProbeFlow(barrier, sink).kickoff()
        return go

    with patch("utils.yfinance_cache.yf.Ticker", side_effect=factory):
        threads = [threading.Thread(target=run(s), daemon=True) for s in sinks]
        for th in threads:
            th.start()
        for th in threads:
            th.join(_JOIN_TIMEOUT)
        assert not any(th.is_alive() for th in threads)

    assert len(calls) == 2
    for sink in sinks:
        assert sink["first"] is sink["second"]
    assert sinks[0]["first"] is not sinks[1]["first"]


def test_lazy_cache_outside_a_run():
    factory, calls = _numbered_ticker_factory()

    def run():
        # No clear(): CLI/tool use outside run_analysis.
        info = cache.get_info("AAPL")
        return info, cache._run_cache.get()

    with patch("utils.yfinance_cache.yf.Ticker", side_effect=factory):
        info, held = _run_in_thread(run)
    assert info == {"fetch_number": 1}
    assert held is None
    assert len(calls) == 1


def test_executor_worker_gets_a_fresh_lazy_cache_per_task():
    factory, calls = _numbered_ticker_factory()
    with patch("utils.yfinance_cache.yf.Ticker", side_effect=factory):
        with ThreadPoolExecutor(max_workers=1) as pool:
            one = pool.submit(cache.get_info, "AAPL").result(_JOIN_TIMEOUT)
            two = pool.submit(cache.get_info, "AAPL").result(_JOIN_TIMEOUT)
    assert len(calls) == 2
    assert one is not two


def test_run_scoped_marker():
    assert cache.RUN_SCOPED is True


# ── Empty-answer warning (CORR-07, phase 4 D-06) ───────────────────────────────

def _cache_warnings(caplog):
    return [r for r in caplog.records if r.name == "utils.yfinance_cache" and r.levelname == "WARNING"]


def test_empty_history_warns_once_per_run(caplog):
    mock = _mock_ticker()
    with caplog.at_level("WARNING", logger="utils.yfinance_cache"):
        with patch("utils.yfinance_cache.yf.Ticker", return_value=mock):
            cache.get_history("ZZZ", "1y")
            cache.get_history("ZZZ", "1y")
    warnings = _cache_warnings(caplog)
    assert len(warnings) == 1
    msg = warnings[0].getMessage()
    assert "price history" in msg
    assert "'ZZZ'" in msg


def test_non_empty_history_does_not_warn(caplog):
    frame = pd.DataFrame({"Close": [1.0, 2.0]})
    with caplog.at_level("WARNING", logger="utils.yfinance_cache"):
        with patch("utils.yfinance_cache.yf.Ticker", return_value=_mock_ticker(history_df=frame)):
            cache.get_history("AAPL", "1y")
    assert _cache_warnings(caplog) == []


def test_warning_cuts_a_long_ticker_to_20_characters_in_repr_quotes(caplog):
    long_ticker = "A" * 40
    with caplog.at_level("WARNING", logger="utils.yfinance_cache"):
        with patch("utils.yfinance_cache.yf.Ticker", return_value=_mock_ticker()):
            cache.get_history(long_ticker, "1y")
    msg = _cache_warnings(caplog)[0].getMessage()
    assert repr("A" * 20) in msg
    assert "A" * 21 not in msg


def test_warning_escapes_newlines_in_the_ticker(caplog):
    with caplog.at_level("WARNING", logger="utils.yfinance_cache"):
        with patch("utils.yfinance_cache.yf.Ticker", return_value=_mock_ticker()):
            cache.get_history("AB\nCD", "1y")
    msg = _cache_warnings(caplog)[0].getMessage()
    assert "\n" not in msg


@pytest.mark.parametrize(
    "getter, dataset, empty_kwargs, full_kwargs",
    [
        ("get_info", "company info", {"info_dict": {}}, {"info_dict": {"symbol": "AAPL"}}),
        ("get_financials", "income statement", {}, {"financials_df": pd.DataFrame({"2023": [1.0]})}),
        ("get_cashflow", "cash flow", {}, {"cashflow_df": pd.DataFrame({"2023": [1.0]})}),
    ],
)
def test_other_getters_warn_once_on_empty_answer(caplog, getter, dataset, empty_kwargs, full_kwargs):
    with caplog.at_level("WARNING", logger="utils.yfinance_cache"):
        with patch("utils.yfinance_cache.yf.Ticker", return_value=_mock_ticker(**empty_kwargs)):
            getattr(cache, getter)("ZZZ")
            getattr(cache, getter)("ZZZ")
    warnings = _cache_warnings(caplog)
    assert len(warnings) == 1
    msg = warnings[0].getMessage()
    assert dataset in msg
    assert "'ZZZ'" in msg

    caplog.clear()
    cache.clear()
    with caplog.at_level("WARNING", logger="utils.yfinance_cache"):
        with patch("utils.yfinance_cache.yf.Ticker", return_value=_mock_ticker(**full_kwargs)):
            getattr(cache, getter)("AAPL")
    assert _cache_warnings(caplog) == []


def test_get_info_none_warns(caplog):
    mock = MagicMock()
    mock.info = None
    with caplog.at_level("WARNING", logger="utils.yfinance_cache"):
        with patch("utils.yfinance_cache.yf.Ticker", return_value=mock):
            cache.get_info("ZZZ")
    assert len(_cache_warnings(caplog)) == 1


def test_mock_values_do_not_warn(caplog):
    """A MagicMock answer is not a recognised empty type and must not warn."""
    mock = MagicMock()
    with caplog.at_level("WARNING", logger="utils.yfinance_cache"):
        with patch("utils.yfinance_cache.yf.Ticker", return_value=mock):
            cache.get_info("AAPL")
            cache.get_financials("AAPL")
    assert _cache_warnings(caplog) == []


# ── Import guard: yfinance stays in one module (CORR-07, T-04-13) ──────────────

def test_only_yfinance_cache_imports_yfinance():
    root = pathlib.Path(__file__).resolve().parent.parent
    files = []
    for sub in ("utils", "agents", "schemas", "config"):
        files.extend((root / sub).rglob("*.py"))
    files.extend(root / name for name in ("prospect_ai_flow.py", "prospect_ai_crew.py", "main.py"))
    offenders = []
    for path in files:
        if path.name == "yfinance_cache.py" and path.parent.name == "utils":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "yfinance" for a in node.names):
                offenders.append(str(path.relative_to(root)))
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "yfinance":
                offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"only utils/yfinance_cache.py may import yfinance, found: {offenders}"
