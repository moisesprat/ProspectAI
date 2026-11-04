"""Tests for sector validation and scrubbed stored queries (gap review WR-03)."""
import json
from unittest.mock import patch

import pytest

from tests.test_llm_role_audit import (  # noqa: F401
    MARKET_PHASE,
    REDDIT_FALLBACK,
    SERPER_OK,
    SERPER_TOOL,
    flow,
    market_tools,
    mkt_entry,
    mkt_payload,
    narrative_result,
    run_market,
    wire_tools,
)
from utils.execution_tracker import ExecutionTracker
from utils.market_records import (
    SUPPORTED_SECTORS,
    build_market_corpus,
    corpus_record,
    is_supported_sector,
)
from utils.reddit_sentiment_tool import RedditSentimentTool

# The nine sector names the web app offers (prospectai-web ui/data.js SECTORS).
WEB_APP_SECTORS = (
    "Technology", "Semiconductors", "Healthcare", "Energy", "Financials",
    "Consumer Discretionary", "Industrials", "Real Estate", "Utilities",
)


# ─── Supported sectors ─────────────────────────────────────────────────────────

def test_supported_sectors_are_the_package_sectors_plus_the_web_app_names():
    assert SUPPORTED_SECTORS == set(RedditSentimentTool.SECTOR_TICKERS) | {"Financials", "Consumer Discretionary"}
    assert set(WEB_APP_SECTORS) <= SUPPORTED_SECTORS


@pytest.mark.parametrize("value", [
    "Garbage", "technology", " Technology", "https://evil.example/x?t=SECRET", "", None, 5, ["Technology"],
])
def test_is_supported_sector_rejects(value):
    assert is_supported_sector(value) is False


def test_is_supported_sector_accepts_every_member():
    for sector in SUPPORTED_SECTORS:
        assert is_supported_sector(sector) is True


# ─── run_analysis gate ─────────────────────────────────────────────────────────

def test_run_analysis_rejects_unsupported_sector_before_any_work(flow):
    with patch.object(flow, "kickoff") as kickoff:
        with pytest.raises(ValueError) as excinfo:
            flow.run_analysis({"sector": "https://evil.example/x?t=SECRET"})
    kickoff.assert_not_called()
    assert flow._tracker is None
    assert "evil" not in str(excinfo.value) and "SECRET" not in str(excinfo.value)


@pytest.mark.parametrize("sector", ["Financials", "Consumer Discretionary", "Finance", "Real Estate"])
def test_run_analysis_accepts_web_app_and_package_names(flow, sector):
    with patch.object(flow, "kickoff", side_effect=RuntimeError("reached kickoff")):
        with pytest.raises(RuntimeError, match="reached kickoff"):
            flow.run_analysis({"sector": sector})


# ─── market_analysis backstop ──────────────────────────────────────────────────

def test_market_phase_skips_serper_for_unsupported_sector(flow):
    flow.state.sector = "Garbage"
    tools = market_tools(reddit=REDDIT_FALLBACK, serper=SERPER_OK)
    wire_tools(flow, tools, phase=MARKET_PHASE)
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAPL"))))

    assert len(tools[SERPER_TOOL].calls) == 0
    record = flow._tracker.to_dict()["market_corpus"]
    assert record["source"] == "unavailable" and record["universe"] == []
    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["AAPL"]


# ─── Scrubbed queries ──────────────────────────────────────────────────────────

def test_corpus_record_scrubs_urls_from_queries():
    corpus = build_market_corpus(
        REDDIT_FALLBACK, SERPER_OK, "Technology",
        queries=["Technology https://evil.example/x?t=SECRET stocks", "see www.evil.example/y now"],
    )
    record = corpus_record(corpus)
    assert record["queries"] == ["Technology stocks", "see now"]
    dumped = json.dumps(record)
    assert "http" not in dumped and "www." not in dumped and "SECRET" not in dumped
