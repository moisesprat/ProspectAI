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


# ─── Fail open: lookup problems keep the pick (D-04, D-05, D-06) ──────────────

SOFTWARE = {"sector": "Technology", "industry": "Software - Application"}


def _serper_corpus(sector="Technology", *tickers):
    from utils.market_records import build_market_corpus
    texts = [f"{t} beats estimates" for t in tickers] or ["AAA beats estimates"]
    return build_market_corpus(_organic(*texts), sector)


def _narrative(*tickers):
    return MarketNarrativeOutput.model_validate(mkt_payload(*[mkt_entry(t) for t in tickers]))


def _skip_lines(caplog):
    return [r.getMessage() for r in caplog.records if "sector_check_skipped" in r.getMessage()]


def _sequence_ticker(outcomes):
    """yf.Ticker replacement whose successive ``.info`` reads yield ``outcomes`` (an exception is raised)."""
    queue = list(outcomes)
    constructed = []
    lock = threading.Lock()

    class FakeTicker:
        def __init__(self, symbol):
            with lock:
                constructed.append(symbol)

        @property
        def info(self):
            with lock:
                outcome = queue.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

    FakeTicker.constructed = constructed
    return FakeTicker


def _sequence_get_info(monkeypatch, outcomes):
    queue = list(outcomes)
    calls = []

    def get_info(ticker):
        calls.append(ticker)
        outcome = queue.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(yfinance_cache, "get_info", get_info)
    return calls


def test_exception_then_answer_is_retried_once(flow, caplog, monkeypatch, real_sector_check):
    wire_tools(flow, market_tools(serper=_organic("AAA beats estimates", "AAA again")), phase=MARKET_PHASE)
    calls = _sequence_get_info(monkeypatch, [ConnectionError("down"), SOFTWARE])
    corpora = _capture_corpus(monkeypatch)

    with caplog.at_level("WARNING"):
        run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"))))

    assert calls == ["AAA", "AAA"]
    assert corpora[0]["sector_check"]["AAA"]["verdict"] == "member"
    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["AAA"]
    assert _skip_lines(caplog) == []


def test_two_exceptions_keep_the_pick_and_log_the_class_only(flow, caplog, monkeypatch, real_sector_check):
    wire_tools(flow, market_tools(serper=_organic("AAA beats estimates", "AAA again")), phase=MARKET_PHASE)
    calls = _sequence_get_info(monkeypatch, [
        ConnectionError("token=SECRET-MARKER"), ConnectionError("token=SECRET-MARKER")])
    corpora = _capture_corpus(monkeypatch)

    with caplog.at_level("WARNING"):
        run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"))))

    assert len(calls) == 2
    entry = corpora[0]["sector_check"]["AAA"]
    assert (entry["verdict"], entry["reason"]) == ("skipped", "lookup_error")
    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["AAA"]
    assert _skip_lines(caplog) == ["market_analysis: sector_check_skipped (lookup_error): 'AAA'; error ConnectionError"]
    assert "SECRET-MARKER" not in caplog.text


@pytest.mark.parametrize("first", [{}, None], ids=["empty-dict", "none"])
def test_empty_answer_is_forgotten_and_retried_once(flow, caplog, monkeypatch, real_sector_check, first):
    wire_tools(flow, market_tools(serper=_organic("AAA beats estimates", "AAA again")), phase=MARKET_PHASE)
    fake = _sequence_ticker([first, SOFTWARE])
    monkeypatch.setattr(yfinance_cache.yf, "Ticker", fake)
    corpora = _capture_corpus(monkeypatch)

    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"))))

    assert corpora[0]["sector_check"]["AAA"]["verdict"] == "member"
    assert len(fake.constructed) == 2
    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["AAA"]


def test_two_empty_answers_keep_the_pick(flow, caplog, monkeypatch, real_sector_check):
    wire_tools(flow, market_tools(serper=_organic("AAA beats estimates", "AAA again")), phase=MARKET_PHASE)
    fake = _sequence_ticker([{}, {}])
    monkeypatch.setattr(yfinance_cache.yf, "Ticker", fake)
    corpora = _capture_corpus(monkeypatch)

    with caplog.at_level("WARNING"):
        run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"))))

    entry = corpora[0]["sector_check"]["AAA"]
    assert (entry["verdict"], entry["reason"]) == ("skipped", "empty_info")
    assert _skip_lines(caplog) == ["market_analysis: sector_check_skipped (empty_info): 'AAA'"]
    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["AAA"]
    # The second empty answer stays cached: the fundamentals phase does not refetch it.
    assert yfinance_cache.get_info("AAA") == {}
    assert len(fake.constructed) == 2


@pytest.mark.parametrize("answer", [
    {"trailingPegRatio": None},
    {"longName": "X", "sector": None, "industry": None},
    {"sector": 3, "industry": "  "},
], ids=["unknown-symbol", "none-labels", "non-string-labels"])
def test_missing_labels_keep_the_pick_without_a_retry(
        flow, caplog, monkeypatch, real_sector_check, answer):
    wire_tools(flow, market_tools(serper=_organic("AAA beats estimates", "AAA again")), phase=MARKET_PHASE)
    calls = _sequence_get_info(monkeypatch, [answer])
    corpora = _capture_corpus(monkeypatch)

    with caplog.at_level("WARNING"):
        run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"))))

    assert calls == ["AAA"]
    entry = corpora[0]["sector_check"]["AAA"]
    assert (entry["verdict"], entry["reason"]) == ("skipped", "no_sector_data")
    assert _skip_lines(caplog) == ["market_analysis: sector_check_skipped (no_sector_data): 'AAA'"]
    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["AAA"]


def test_long_and_multiline_labels_are_cut_and_escaped(flow, caplog, monkeypatch, real_sector_check):
    flow.state.sector = "Financials"
    wire_tools(flow, market_tools(serper=_organic("AAA beats estimates", "JPM and AAA")), phase=MARKET_PHASE)
    fake_info(monkeypatch, {"AAA": {"sector": "Technology", "industry": "Consumer Electronics\n" + "x" * 100}})
    corpora = _capture_corpus(monkeypatch)

    with caplog.at_level("WARNING"):
        run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("JPM"))))

    assert len(corpora[0]["sector_check"]["AAA"]["industry"]) == 40
    lines = _drop_lines(caplog, "not_in_sector")
    assert len(lines) == 1 and "\n" not in lines[0] and "\\n" in lines[0]


def test_no_value_is_invented_for_a_skipped_pick(monkeypatch, real_sector_check):
    from datetime import datetime, timezone
    from utils.market_records import merge_market
    corpus = _serper_corpus("Technology", "AAA", "AAA")
    narrative = _narrative("AAA")
    _sequence_get_info(monkeypatch, [{}, {}])

    asyncio.run(check_sector_membership(narrative, corpus))

    entry = corpus["sector_check"]["AAA"]
    assert (entry["verdict"], entry["sector"], entry["industry"]) == ("skipped", None, None)
    now = datetime(2026, 4, 29, tzinfo=timezone.utc)
    with_check = merge_market("Technology", corpus, narrative, now).candidate_stocks[0]
    without = {k: v for k, v in corpus.items() if k != "sector_check"}
    plain = merge_market("Technology", without, narrative, now).candidate_stocks[0]
    assert (with_check.mention_count, with_check.relevance_score) == (plain.mention_count, plain.relevance_score)
