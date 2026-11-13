"""Tests for the curated market fallback (phase 4.1 D-13, which revises D-11's no-backfill rule)."""
import json
import re
from datetime import datetime, timezone

import pytest

from tests.test_llm_role_audit import (  # noqa: F401  (flow is a fixture)
    MARKET_PHASE, NEWS_TOOL, SERPER_OK, StubTool, _organic, flow, market_tools, mkt_entry, mkt_payload,
    narrative_result, run_market, wire_tools,
)
from schemas.agent_outputs import MarketAnalysisOutput
from tests.test_sector_membership import FINANCIALS_SERPER, OFF_SECTOR, fake_info
from utils.candidate_universe_filter import excluded_tickers_for_sector
from utils.market_fallback import (
    FALLBACK_REASON, fallback_market_output, fallback_tickers, is_zero_survivor_failure,
)
from utils.market_records import DROP_REASONS, NoPicksError, build_market_corpus
from utils.phase_runner import PhaseOutputError, PhaseSchemaError
from utils.sector_universe import FALLBACK_PICKS, SECTOR_TICKERS, canonical_sector
from utils.ticker_matching import is_valid_ticker

STALE = {"SQ", "HES", "MRO", "CHK", "CTRA", "OTTER"}
NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


# ─── The curated tables ───────────────────────────────────────────────────────

def test_drop_reasons_are_the_closed_set():
    assert DROP_REASONS == (
        "invalid_format", "not_in_search_results", "not_in_sector_universe", "excluded_etf", "not_in_sector",
    )


@pytest.mark.parametrize("sector", list(SECTOR_TICKERS))
def test_fallback_picks_are_five_distinct_curated_stocks_per_sector(sector):
    assert list(FALLBACK_PICKS) == list(SECTOR_TICKERS)
    picks = FALLBACK_PICKS[sector]
    assert len(picks) == 5
    assert len(set(picks)) == 5
    for ticker in picks:
        assert is_valid_ticker(ticker)
        assert ticker in SECTOR_TICKERS[sector]
        assert ticker not in excluded_tickers_for_sector(sector)
        assert ticker not in STALE


@pytest.mark.parametrize("name", list(SECTOR_TICKERS) + ["Financials", "Consumer Discretionary"])
def test_fallback_output_satisfies_the_schema_for_every_sector_and_alias(name):
    out = fallback_market_output(name, NOW)
    assert isinstance(out, MarketAnalysisOutput)
    assert out.sector == name
    assert [c.ticker for c in out.candidate_stocks] == list(FALLBACK_PICKS[canonical_sector(name)])
    assert out.analysis_timestamp == NOW
    assert out.sentiment_available is False
    for c in out.candidate_stocks:
        assert (c.mention_count, c.relevance_score, c.average_sentiment) == (None, None, None)


def test_fallback_text_is_fixed_and_carries_no_number():
    first = fallback_market_output("Financials", NOW)
    second = fallback_market_output("Financials", NOW)
    assert first.summary == second.summary
    assert "curated" in first.summary
    assert not re.search(r"\d", first.summary)
    for a, b in zip(first.candidate_stocks, second.candidate_stocks):
        assert a.rationale == b.rationale
        assert "curated" in a.rationale
        assert "not found in the web search" in a.rationale
        assert not re.search(r"\d", a.rationale)


def test_fallback_for_an_unmapped_sector_is_refused():
    assert fallback_tickers("Basket Weaving") == []
    with pytest.raises(ValueError):
        fallback_market_output("Basket Weaving", NOW)


# ─── The zero-survivor rule ───────────────────────────────────────────────────

def _exhausted(cause, phase=MARKET_PHASE):
    exc = PhaseSchemaError(phase, ["candidates"], 3)
    exc.__cause__ = cause
    return exc


def test_zero_survivor_rule_unit():
    serper = build_market_corpus(_organic("AAA beats estimates"), "Technology")
    unavailable = build_market_corpus(None, "Technology")
    nopicks = NoPicksError("m", ["candidates"], [], [("ZZZ", "not_in_search_results")])
    assert is_zero_survivor_failure(_exhausted(nopicks), serper) is True
    assert is_zero_survivor_failure(_exhausted(PhaseOutputError("m", ["candidates"])), serper) is False
    assert is_zero_survivor_failure(_exhausted(nopicks), unavailable) is False
    assert is_zero_survivor_failure(_exhausted(nopicks, phase="technical_analysis"), serper) is False
    assert is_zero_survivor_failure(RuntimeError("x"), serper) is False
    assert is_zero_survivor_failure(_exhausted(nopicks), {**serper, "sector": "Basket Weaving"}) is False


# ─── The Flow ─────────────────────────────────────────────────────────────────

def test_all_ungrounded_answers_fall_back_to_the_curated_list_with_the_alias_sector(
        flow, real_sector_check, monkeypatch):
    """A Financials run (SPA alias) resolves to the Finance table and keeps the name as given."""
    flow.state.sector = "Financials"
    wire_tools(flow, market_tools(serper=_organic(*FINANCIALS_SERPER)), phase=MARKET_PHASE)
    fake_info(monkeypatch, OFF_SECTOR)
    junk = lambda: narrative_result(mkt_payload(mkt_entry("ZZZ")))  # noqa: E731

    kickoff = run_market(flow, junk(), junk(), junk())

    assert kickoff.await_count == 3
    assert flow.state.market_output.sector == "Financials"
    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["JPM", "BAC", "WFC", "GS", "MS"]


def test_unavailable_path_never_falls_back(flow):
    tools = market_tools(serper=RuntimeError("down"))
    wire_tools(flow, tools, phase=MARKET_PHASE)
    before = list(flow.state.market_output.candidate_stocks)
    junk = lambda: narrative_result(mkt_payload(mkt_entry("ZZZ")))  # noqa: E731

    with pytest.raises(PhaseSchemaError):
        run_market(flow, junk(), junk(), junk())

    assert flow.state.market_output.candidate_stocks == before


def test_a_surviving_pick_is_published_alone_with_no_top_up(flow, real_sector_check, monkeypatch):
    flow.state.sector = "Financials"
    wire_tools(flow, market_tools(serper=_organic(*FINANCIALS_SERPER)), phase=MARKET_PHASE)
    fake_info(monkeypatch, OFF_SECTOR)

    kickoff = run_market(flow, narrative_result(mkt_payload(mkt_entry("AAPL"), mkt_entry("JPM"))))

    assert kickoff.await_count == 1
    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["JPM"]
