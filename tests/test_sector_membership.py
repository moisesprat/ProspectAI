"""Tests for the sector-membership check on search-grounded market picks (phase 4.1, D-01 to D-11)."""
import asyncio
import json
import threading

import pytest

from tests.test_llm_role_audit import (  # noqa: F401  (flow is a fixture)
    MARKET_PHASE, NEWS_TOOL, StubTool, _log_has_no_corpus_text, _organic, flow, market_tools, mkt_entry, mkt_payload,
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

    async def recorder(narrative, corpus, **kwargs):
        seen.append(corpus)
        return await real(narrative, corpus, **kwargs)

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


# ─── Budget, pool, memo and run cache (D-08) ──────────────────────────────────

def test_hung_lookup_is_skipped_at_the_budget_and_the_pick_is_kept(caplog, monkeypatch, real_sector_check):
    import time
    from utils.market_records import require_market_picks, grounded_picks
    monkeypatch.setattr(sector_membership, "SECTOR_CHECK_BUDGET_SEC", 0.3)
    release = threading.Event()
    calls = []

    def get_info(ticker):
        calls.append(ticker)
        if ticker == "AAA":
            release.wait(10)
            return {}
        return SOFTWARE

    monkeypatch.setattr(yfinance_cache, "get_info", get_info)
    corpus = _serper_corpus("Technology", "AAA", "BBB")
    narrative = _narrative("AAA", "BBB")
    try:
        with caplog.at_level("WARNING"):
            started = time.monotonic()
            asyncio.run(check_sector_membership(narrative, corpus))
            elapsed = time.monotonic() - started
        assert elapsed < 2
        memo = corpus["sector_check"]
        assert (memo["AAA"]["verdict"], memo["AAA"]["reason"]) == ("skipped", "timeout")
        assert memo["BBB"]["verdict"] == "member"
        assert _skip_lines(caplog) == ["market_analysis: sector_check_skipped (timeout): 'AAA'"]
        require_market_picks(narrative, corpus)
        assert grounded_picks(narrative, corpus) == ["AAA", "BBB"]
    finally:
        release.set()


def test_spent_budget_skips_new_tickers_without_a_lookup(monkeypatch, real_sector_check):
    monkeypatch.setattr(sector_membership, "SECTOR_CHECK_BUDGET_SEC", 0.3)
    release = threading.Event()
    calls = []

    def get_info(ticker):
        calls.append(ticker)
        if ticker == "AAA":
            release.wait(10)
        return SOFTWARE

    monkeypatch.setattr(yfinance_cache, "get_info", get_info)
    corpus = _serper_corpus("Technology", "AAA", "BBB", "CCC")
    try:
        asyncio.run(check_sector_membership(_narrative("AAA", "BBB"), corpus))
        before = list(calls)
        asyncio.run(check_sector_membership(_narrative("CCC"), corpus))
    finally:
        release.set()

    assert calls == before and "CCC" not in calls
    entry = corpus["sector_check"]["CCC"]
    assert (entry["verdict"], entry["reason"]) == ("skipped", "timeout")


def test_each_ticker_is_looked_up_once_per_run(monkeypatch, real_sector_check):
    from datetime import datetime, timezone
    from utils.market_records import grounded_picks, merge_market
    calls = fake_info(monkeypatch, {"AAA": SOFTWARE, "BBB": SOFTWARE})
    corpus = _serper_corpus("Technology", "AAA", "BBB")
    narrative = _narrative("AAA", "BBB")

    asyncio.run(check_sector_membership(narrative, corpus))
    asyncio.run(check_sector_membership(narrative, corpus))
    grounded = grounded_picks(narrative, corpus)
    kept = [t for t, _ in _picks(narrative, corpus)[0]]
    published = [c.ticker for c in merge_market(
        "Technology", corpus, narrative, datetime(2026, 4, 29, tzinfo=timezone.utc)).candidate_stocks]

    assert sorted(t for t, _ in calls) == ["AAA", "BBB"]
    assert grounded == kept == published == ["AAA", "BBB"]


def test_lookups_run_in_parallel_on_at_most_five_workers(monkeypatch, real_sector_check):
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    barrier = threading.Barrier(5, timeout=2)
    names = set()
    lock = threading.Lock()

    def get_info(ticker):
        with lock:
            names.add(threading.current_thread().name)
        barrier.wait()
        return SOFTWARE

    monkeypatch.setattr(yfinance_cache, "get_info", get_info)
    corpus = _serper_corpus("Technology", *tickers)

    asyncio.run(check_sector_membership(_narrative(*tickers), corpus))

    assert {corpus["sector_check"][t]["verdict"] for t in tickers} == {"member"}
    assert names and all(n.startswith("sector-check") for n in names)
    assert len(names) <= 5


def test_lookups_fill_the_run_cache_the_fundamentals_phase_reads(monkeypatch, real_sector_check):
    fake = _sequence_ticker([SOFTWARE])
    monkeypatch.setattr(yfinance_cache.yf, "Ticker", fake)
    corpus = _serper_corpus("Technology", "AAA")

    asyncio.run(check_sector_membership(_narrative("AAA"), corpus))

    assert corpus["sector_check"]["AAA"]["verdict"] == "member"
    assert yfinance_cache.get_info("AAA") == SOFTWARE
    assert fake.constructed == ["AAA"]


# ─── execution_metrics.sector_check (plan 04.1-03, D-10) ──────────────────────

def _tracked(flow):
    from utils.execution_tracker import ExecutionTracker
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    return flow._tracker


def test_metrics_record_lists_the_drops_and_the_curated_kept(flow, monkeypatch, real_sector_check):
    flow.state.sector = "Financials"
    serper = _organic("JPM beats estimates", "AAPL and JPM lead the market", "NVDA and AAPL rally")
    wire_tools(flow, market_tools(serper=serper), phase=MARKET_PHASE)
    tracker = _tracked(flow)
    fake_info(monkeypatch, {
        "AAPL": {"sector": "Technology", "industry": "Consumer Electronics"},
        "NVDA": {"sector": "Technology", "industry": "Semiconductors"},
    })

    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAPL"), mkt_entry("NVDA"), mkt_entry("JPM"))))

    record = tracker.to_dict()["sector_check"]
    assert record["budget_sec"] == 15.0
    assert 0 <= record["spent_sec"] < 15
    assert record["curated_kept"] == 1
    assert record["members"] == 0
    assert record["dropped"] == [
        {"ticker": "AAPL", "reason": "not_in_sector", "sector": "Technology", "industry": "Consumer Electronics"},
        {"ticker": "NVDA", "reason": "not_in_sector", "sector": "Technology", "industry": "Semiconductors"},
    ]
    assert record["skipped"] == []
    assert tracker.to_dict()["metrics_version"] == 2


def test_metrics_record_lists_skips_with_their_reason(flow, monkeypatch, real_sector_check):
    wire_tools(flow, market_tools(serper=_organic("AAA beats estimates", "AAA again")), phase=MARKET_PHASE)
    tracker = _tracked(flow)
    fake_info(monkeypatch, {"AAA": {"sector": None, "industry": None}})

    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"))))

    record = tracker.to_dict()["sector_check"]
    assert record["skipped"] == [{"ticker": "AAA", "reason": "no_sector_data"}]
    assert record["members"] == 0
    assert record["dropped"] == []


def test_metrics_record_is_absent_off_the_serper_path(flow, monkeypatch, real_sector_check):
    flow.state.sector = "Financials"
    wire_tools(flow, market_tools(serper=None), phase=MARKET_PHASE)
    tracker = _tracked(flow)
    fake_info(monkeypatch, {})

    run_market(flow, narrative_result(mkt_payload(mkt_entry("JPM"))))

    assert "sector_check" not in tracker.to_dict()


def test_metrics_record_holds_no_corpus_text_and_is_bounded(flow, monkeypatch, real_sector_check):
    import json
    flow.state.sector = "Financials"
    serper = _organic("JPM beats estimates", "AAPL and JPM lead the market")
    wire_tools(flow, market_tools(serper=serper), phase=MARKET_PHASE)
    tracker = _tracked(flow)
    fake_info(monkeypatch, {"AAPL": {"sector": "Technology", "industry": "Consumer Electronics"}})
    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAPL"), mkt_entry("JPM"))))
    text = json.dumps(tracker.to_dict()["sector_check"])
    for forbidden in ("Headline", "http", "example.com"):
        assert forbidden not in text

    memo = {}
    for i in range(20):
        memo[f"D{i:02d}"] = {"verdict": "not_in_sector", "reason": "label_mismatch",
                             "sector": "S" * 40, "industry": "I" * 40}
        memo[f"K{i:02d}"] = {"verdict": "skipped", "reason": "no_sector_data", "sector": None, "industry": None}
    record = sector_membership.sector_check_record({"sector_check": memo})
    assert len(record["dropped"]) == 15
    assert len(record["skipped"]) == 15
    assert len(json.dumps(record)) < 4096


def test_a_schema_failure_on_the_last_attempt_still_fails_the_run_and_keeps_the_record(
        flow, monkeypatch, real_sector_check):
    """Replaces the partial-snapshot test that used three off-sector answers to get a failed run.

    Those answers now publish the curated fallback (phase 4.1 D-13), so the failed run is built from a
    last attempt that fails the schema (a too-short summary): the fallback exists for an unusable search
    corpus, not an unusable model answer, so this still raises and the record stays in the partial snapshot.
    """
    from utils.phase_runner import PhaseSchemaError
    flow.state.sector = "Financials"
    wire_tools(flow, market_tools(serper=_organic("AAPL beats estimates", "AAPL again")), phase=MARKET_PHASE)
    tracker = _tracked(flow)
    fake_info(monkeypatch, {"AAPL": {"sector": "Technology", "industry": "Consumer Electronics"}})
    off = lambda: narrative_result(mkt_payload(mkt_entry("AAPL")))  # noqa: E731
    short = narrative_result(mkt_payload(mkt_entry("AAPL"), summary="too short"))
    before = list(flow.state.market_output.candidate_stocks)

    with pytest.raises(PhaseSchemaError) as info:
        run_market(flow, off(), off(), short)

    assert "summary" in info.value.fields
    snap = tracker.snapshot()
    assert snap["partial"] is True
    assert [d["ticker"] for d in snap["sector_check"]["dropped"]] == ["AAPL"]
    assert flow.state.market_output.candidate_stocks == before


def test_offline_stub_accepts_the_tracker_keyword(monkeypatch):
    """The conftest stub of plan 04.1-01 takes (*args, **kwargs): a forwarded tracker looks nothing up."""
    from utils.execution_tracker import ExecutionTracker
    calls = fake_info(monkeypatch, {})
    corpus = _serper_corpus("Technology", "ZZZ")
    tracker = ExecutionTracker()

    asyncio.run(sector_membership.validate_market_picks(_narrative("ZZZ"), corpus, tracker=tracker))

    assert calls == []
    assert "sector_check" not in corpus
    assert "sector_check" not in tracker.to_dict()


# ─── Zero survivors: bounded retry, fixed feedback, no backfill (plan 04.1-03, D-11) ──────────

OFF_SECTOR = {
    "AAPL": {"sector": "Technology", "industry": "Consumer Electronics"},
    "NVDA": {"sector": "Technology", "industry": "Semiconductors"},
}
FINANCIALS_SERPER = ("JPM beats estimates", "AAPL and JPM lead the market", "NVDA and AAPL rally")


def test_all_off_sector_picks_spend_the_retry_and_the_second_answer_is_published(
        flow, caplog, monkeypatch, real_sector_check):
    flow.state.sector = "Financials"
    wire_tools(flow, market_tools(serper=_organic(*FINANCIALS_SERPER)), phase=MARKET_PHASE)
    calls = fake_info(monkeypatch, OFF_SECTOR)

    with caplog.at_level("WARNING"):
        kickoff = run_market(
            flow,
            narrative_result(mkt_payload(mkt_entry("AAPL"), mkt_entry("NVDA"))),
            narrative_result(mkt_payload(mkt_entry("JPM"))),
        )

    assert kickoff.await_count == 2
    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["JPM"]
    feedback = flow._factory.build_task.call_args_list[1].kwargs["feedback"]
    assert "candidates" in feedback
    assert "the company must belong to the requested sector" in feedback
    for forbidden in ("AAPL", "NVDA", "JPM", "Headline", "estimates", "rally"):
        assert forbidden not in feedback
    assert sorted(t for t, _ in calls) == ["AAPL", "NVDA"]
    assert len(_drop_lines(caplog, "not_in_sector")) == 2


def test_three_off_sector_answers_publish_the_curated_fallback(
        flow, caplog, monkeypatch, real_sector_check):
    """Replaces the test that pinned PhaseSchemaError for three dropped answers (D-11: no backfill).

    Phase 4.1 D-13 reverses that rule on the Serper path: the failure made visitor-facing Financials
    runs fail (two live runs on 1.13.2), so the Flow now publishes the five curated Finance stocks
    with null numbers and no news lookup, and the technical step receives them.
    """
    flow.state.sector = "Financials"
    news = StubTool(NEWS_TOOL, {"scores": {}})
    tools = {
        **market_tools(serper=_organic(*FINANCIALS_SERPER)),
        NEWS_TOOL: news,
        **tech_tools({"technical_analysis": [tech_entry(t) for t in ("JPM", "BAC", "WFC", "GS", "MS")]}),
    }
    wire_tools(flow, tools, phase=MARKET_PHASE)
    calls = fake_info(monkeypatch, OFF_SECTOR)
    off = lambda: narrative_result(mkt_payload(mkt_entry("AAPL")))  # noqa: E731

    with caplog.at_level("WARNING"):
        kickoff = run_market(flow, off(), off(), off())

    assert kickoff.await_count == 3
    output = flow.state.market_output
    assert [c.ticker for c in output.candidate_stocks] == ["JPM", "BAC", "WFC", "GS", "MS"]
    assert output.sector == "Financials"
    for c in output.candidate_stocks:
        assert (c.mention_count, c.relevance_score, c.average_sentiment) == (None, None, None)
    assert output.sentiment_available is False
    assert news.calls == []
    assert [t for t, _ in calls] == ["AAPL"]
    assert "curated" in output.summary
    assert [r for r in caplog.records if r.levelname == "WARNING" and "curated fallback" in r.getMessage()]

    run_technical(flow, narrative_result(tech_payload(*[
        tech_narrative_entry(t) for t in ("JPM", "BAC", "WFC", "GS", "MS")])))
    sent = tools["calculate_technical_indicators"].calls
    assert len(sent) == 1
    assert json.loads(sent[0]["tickers_json"]) == ["JPM", "BAC", "WFC", "GS", "MS"]


def test_a_partly_off_sector_answer_continues_with_the_survivors(flow, monkeypatch, real_sector_check):
    flow.state.sector = "Financials"
    wire_tools(flow, market_tools(serper=_organic(*FINANCIALS_SERPER)), phase=MARKET_PHASE)
    fake_info(monkeypatch, OFF_SECTOR)

    kickoff = run_market(flow, narrative_result(mkt_payload(mkt_entry("AAPL"), mkt_entry("JPM"))))

    assert kickoff.await_count == 1
    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["JPM"]


def test_serper_retry_hint_names_the_sector_rule():
    from utils.market_records import _SOURCE_HINTS, _no_picks_error, build_market_corpus
    corpus = build_market_corpus(_organic("AAA beats estimates"), "Technology")
    assert corpus["source"] == "serper"
    msg = _no_picks_error(corpus, []).errors[0]["msg"]
    assert "choose only tickers whose symbol itself appears in the search results" in msg
    assert msg.endswith("the company must belong to the requested sector")
    assert msg == _SOURCE_HINTS["serper"]
    for source in ("universe", "open"):
        assert "belong to the requested sector" not in _SOURCE_HINTS[source]
