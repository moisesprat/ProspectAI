"""Tests for the sector-membership check on search-grounded market picks (phase 4.1, D-01 to D-11)."""
import asyncio
import threading

import pytest

from tests.test_llm_role_audit import (  # noqa: F401  (flow is a fixture)
    MARKET_PHASE, _log_has_no_corpus_text, _organic, flow, market_tools, mkt_entry, mkt_payload,
    narrative_result, run_market, run_technical, tech_entry, tech_narrative_entry, tech_payload,
    tech_tools, wire_tools,
)
import prospect_ai_flow
from schemas.agent_outputs import MarketNarrativeOutput
from utils import sector_membership, yfinance_cache
from utils.market_records import _picks
from utils.sector_membership import check_sector_membership, classify


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


# ─── Curated short-circuit, scope and memo (D-03, D-07) ───────────────────────

def _capture_corpus(monkeypatch):
    """Pass-through recorder around the Flow's validate callback: the corpus the market phase used."""
    seen = []
    real = prospect_ai_flow.validate_market_picks

    async def recorder(narrative, corpus):
        seen.append(corpus)
        return await real(narrative, corpus)

    monkeypatch.setattr(prospect_ai_flow, "validate_market_picks", recorder)
    return seen


@pytest.mark.parametrize("sector,picks", [
    pytest.param("Technology", ["AMZN", "TSLA"], id="Technology-AMZN-TSLA"),
    pytest.param("Financials", ["BRK.B"], id="Financials-BRKB"),
    pytest.param("Consumer Discretionary", ["AMZN"], id="ConsumerDiscretionary-AMZN"),
])
def test_curated_pick_is_kept_without_a_lookup(flow, monkeypatch, real_sector_check, sector, picks):
    """D-03: grounded curated picks are published, no yfinance call is made, every verdict is curated."""
    flow.state.sector = sector
    serper = _organic(*[f"{t} beats estimates" for t in picks], "Markets steady")
    wire_tools(flow, market_tools(serper=serper), phase=MARKET_PHASE)
    calls = fake_info(monkeypatch, {})
    corpora = _capture_corpus(monkeypatch)

    run_market(flow, narrative_result(mkt_payload(*[mkt_entry(t) for t in picks])))

    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == picks
    assert calls == []
    memo = corpora[0]["sector_check"]
    assert sorted(memo) == sorted(picks)
    assert {entry["verdict"] for entry in memo.values()} == {"curated"}


def test_unmapped_sector_is_not_checked(monkeypatch, real_sector_check):
    calls = fake_info(monkeypatch, {})
    corpus = {"source": "serper", "sector": "Basket Weaving", "snippets": [{"text": "AAA beats estimates"}]}
    narrative = MarketNarrativeOutput.model_validate(mkt_payload(mkt_entry("AAA")))

    asyncio.run(check_sector_membership(narrative, corpus))

    assert calls == []
    assert "sector_check" not in corpus


def test_unavailable_path_is_never_checked(flow, monkeypatch, real_sector_check):
    """D-07: the unavailable and open paths are untouched. Asserts the absence of the check only."""
    flow.state.sector = "Financials"
    wire_tools(flow, market_tools(serper=None), phase=MARKET_PHASE)
    calls = fake_info(monkeypatch, {})
    entered = []
    real_check = sector_membership.check_sector_membership

    async def recording_check(*args, **kwargs):
        entered.append(args)
        return await real_check(*args, **kwargs)

    monkeypatch.setattr(sector_membership, "check_sector_membership", recording_check)
    corpora = _capture_corpus(monkeypatch)

    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAPL"), mkt_entry("JPM"))))

    assert corpora[0]["source"] == "unavailable"
    assert calls == []
    assert entered == []
    assert "sector_check" not in corpora[0]


def test_ungrounded_and_etf_picks_are_never_looked_up(flow, caplog, monkeypatch, real_sector_check):
    wire_tools(flow, market_tools(serper=_organic("AAA beats, XLK up", "XLK and AAA", "AAA again")),
               phase=MARKET_PHASE)
    calls = fake_info(monkeypatch, {"AAA": {"sector": "Technology", "industry": "Software - Infrastructure"}})

    with caplog.at_level("WARNING"):
        run_market(flow, narrative_result(mkt_payload(mkt_entry("ZZZ"), mkt_entry("XLK"), mkt_entry("AAA"))))

    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["AAA"]
    assert [t for t, _ in calls] == ["AAA"]
    assert _drop_lines(caplog, "not_in_search_results") == [
        "market_analysis: pick dropped (not_in_search_results): 'ZZZ'"]
    assert _drop_lines(caplog, "excluded_etf") == ["market_analysis: pick dropped (excluded_etf): 'XLK'"]
    assert _drop_lines(caplog, "not_in_sector") == []


def test_picks_reads_the_memo_on_the_serper_path_only():
    memo = {"AAA": {"verdict": "not_in_sector", "reason": "label_mismatch", "sector": "Technology", "industry": None}}
    narrative = MarketNarrativeOutput.model_validate(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB")))
    snippets = [{"text": "AAA and BBB lead the market"}]

    serper = {"source": "serper", "sector": "Financials", "snippets": snippets, "sector_check": memo}
    kept, dropped = _picks(narrative, serper)
    assert [t for t, _ in kept] == ["BBB"] and dropped == [("AAA", "not_in_sector")]

    unavailable = {"source": "unavailable", "sector": "Technology", "universe": [], "sector_check": memo}
    kept, dropped = _picks(narrative, unavailable)
    assert [t for t, _ in kept] == ["AAA", "BBB"] and dropped == []

    without_memo = {"source": "serper", "sector": "Financials", "snippets": snippets}
    kept, dropped = _picks(narrative, without_memo)
    assert [t for t, _ in kept] == ["AAA", "BBB"] and dropped == []

    malformed = {**serper, "sector_check": {"AAA": "not_in_sector", "BBB": {"verdict": None}}}
    kept, dropped = _picks(narrative, malformed)
    assert [t for t, _ in kept] == ["AAA", "BBB"] and dropped == []
