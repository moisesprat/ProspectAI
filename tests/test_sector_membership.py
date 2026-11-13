"""Tests for the sector-membership check on search-grounded market picks (phase 4.1, D-01 to D-11)."""
import threading

from tests.test_llm_role_audit import (  # noqa: F401  (flow is a fixture)
    MARKET_PHASE, _log_has_no_corpus_text, _organic, flow, market_tools, mkt_entry, mkt_payload,
    narrative_result, run_market, run_technical, tech_entry, tech_narrative_entry, tech_payload,
    tech_tools, wire_tools,
)
from utils import yfinance_cache
from utils.sector_membership import classify


def fake_info(monkeypatch, table):
    """Replace ``yfinance_cache.get_info`` with a thread-safe recorder answering ``table[TICKER]``.

    Returns the list of ``(ticker, thread name)`` calls. An unexpected ticker raises AssertionError
    (inside the lookup, which fails open), so the test also asserts the call list.
    """
    calls = []
    lock = threading.Lock()

    def get_info(ticker):
        with lock:
            calls.append((ticker, threading.current_thread().name))
        assert ticker.upper() in table, f"unexpected lookup {ticker!r}"
        return table[ticker.upper()]

    monkeypatch.setattr(yfinance_cache, "get_info", get_info)
    return calls


def _drop_lines(caplog, reason):
    return [r.getMessage() for r in caplog.records
            if r.levelname == "WARNING" and f"pick dropped ({reason})" in r.getMessage()]


# ─── The tracer: AAPL-in-Financials (04-VERIFICATION) ─────────────────────────

def test_financials_search_picks_outside_the_sector_are_not_published(
        flow, caplog, monkeypatch, real_sector_check):
    flow.state.sector = "Financials"
    serper = _organic("JPM beats estimates", "AAPL and JPM lead the market", "NVDA and AAPL rally")
    tools = {**market_tools(serper=serper), **tech_tools({"technical_analysis": [tech_entry("JPM")]})}
    wire_tools(flow, tools, phase=MARKET_PHASE)
    calls = fake_info(monkeypatch, {
        "AAPL": {"sector": "Technology", "industry": "Consumer Electronics"},
        "NVDA": {"sector": "Technology", "industry": "Semiconductors"},
    })

    with caplog.at_level("WARNING"):
        run_market(flow, narrative_result(mkt_payload(mkt_entry("AAPL"), mkt_entry("NVDA"), mkt_entry("JPM"))))

    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["JPM"]
    assert _drop_lines(caplog, "not_in_sector") == [
        "market_analysis: pick dropped (not_in_sector): 'AAPL'; yfinance sector 'Technology', industry 'Consumer Electronics'",
        "market_analysis: pick dropped (not_in_sector): 'NVDA'; yfinance sector 'Technology', industry 'Semiconductors'",
    ]
    assert _log_has_no_corpus_text(caplog.text)
    assert sorted(t for t, _ in calls) == ["AAPL", "NVDA"]
    assert all(name.startswith("sector-check") for _, name in calls)

    run_technical(flow, narrative_result(tech_payload(tech_narrative_entry("JPM"))))
    tool = tools["calculate_technical_indicators"]
    assert len(tool.calls) == 1
    assert tool.calls[0]["tickers_json"] == '["JPM"]'


def test_classify_rule():
    assert classify("Finance", "Technology", "Consumer Electronics") == "not_in_sector"
    assert classify("Semiconductors", "Technology", "Semiconductors") == "member"
    assert classify("Finance", None, None) == "unchecked"
