"""
Sentiment-availability sentinel propagation through ProspectAIFlow context
builders (change deterministic-enforcement-v1-9-1).
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prospect_ai_flow import ProspectAIFlow
from schemas.agent_outputs import CandidateStock, MarketAnalysisOutput

ANTHROPIC_ENV = {
    "ANTHROPIC_API_KEY": "test-key",
    "MODEL": "claude-haiku-4-5-20251001",
}


@pytest.fixture
def flow():
    with patch.dict("os.environ", ANTHROPIC_ENV), \
         patch("prospect_ai_flow.TaskFactory") as MockFactory:
        MockFactory.return_value = MagicMock()
        f = ProspectAIFlow()
        f._tracker = None
        f.state.sector = "Technology"
        f.state.today = "2026-04-29"
        yield f


def _unavailable_market_output():
    return MarketAnalysisOutput(
        sector="Technology",
        sentiment_available=False,
        candidate_stocks=[CandidateStock(
            ticker="AAPL", mention_count=0, average_sentiment=None, relevance_score=0.5,
            rationale="Sentiment data unavailable this run; falling back to a well-known sector leader.",
        )],
        summary="S" * 150,
    )


def test_slim_market_for_analysis_surfaces_sentiment_unavailable(flow):
    import json
    flow.state.market_output = _unavailable_market_output()
    ctx = json.loads(flow._slim_market_for_analysis())
    assert ctx["sentiment_available"] is False
    assert ctx["candidate_stocks"][0]["average_sentiment"] is None


def test_slim_market_for_strategy_surfaces_sentiment_unavailable(flow):
    import json
    flow.state.market_output = _unavailable_market_output()
    ctx = json.loads(flow._slim_market_for_strategy())
    assert ctx["sentiment_available"] is False
    assert ctx["candidate_stocks"][0]["average_sentiment"] is None


def test_critic_task_description_scopes_out_sentiment_when_unavailable():
    tasks_yaml = Path(__file__).parent.parent / "config" / "tasks.yaml"
    text = tasks_yaml.read_text()
    critique_section = text.split("critique_review:")[1].split("final_strategy:")[0]
    assert "sentiment_available=false" in critique_section
    assert "do NOT raise any" in critique_section or "do NOT raise any\n" in critique_section


def test_critic_task_description_no_longer_checks_deterministically_enforced_items():
    # As of reasoning-depth-action-selection, the Critic checklist drops items
    # already enforced deterministically downstream (PortfolioBoundsValidator,
    # schema validation) -- WAIT_ENTRY_ZERO_ALLOC, CONCENTRATION_BREACH, and
    # BUCKET_SUM_ERROR among them -- since the Final Strategist has no authority
    # to fix a numeric field regardless of what the Critic finds.
    tasks_yaml = Path(__file__).parent.parent / "config" / "tasks.yaml"
    text = tasks_yaml.read_text()
    critique_section = text.split("critique_review:")[1].split("final_strategy:")[0]
    for removed_item in ("WAIT_ENTRY_ZERO_ALLOC", "CONCENTRATION_BREACH", "BUCKET_SUM_ERROR",
                          "COMPOSITE_SCORE_MISMATCH", "INVALID_ACTION", "ALLOCATION_MISMATCH"):
        assert removed_item not in critique_section


# ─── Corpus-backed scores (phase 3.1 D-04, D-10, decision 02-17) ───────────────

def _published_market(news_sentiment):
    """The market output the Flow publishes for picks AAA and BBB when the news lookup returned these scores."""
    from datetime import datetime, timezone

    from schemas.agent_outputs import MarketNarrativeOutput
    from tests.test_llm_role_audit import SERPER_OK, mkt_entry, mkt_payload
    from utils.market_records import build_market_corpus, merge_market

    corpus = build_market_corpus(SERPER_OK, "Technology")
    corpus["news_sentiment"] = news_sentiment
    narrative = MarketNarrativeOutput.model_validate(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB")))
    return merge_market("Technology", corpus, narrative, datetime.now(timezone.utc))


def test_composite_gets_every_news_score_when_all_picks_are_scored(flow):
    from tests.test_llm_role_audit import prime_draft
    from utils.strategy_assembly import composite_inputs

    prime_draft(flow)
    market = _published_market({"AAA": 0.3, "BBB": -0.5})
    assert market.sentiment_available is True
    sent = composite_inputs(market, flow.state.technical_output, flow.state.fundamental_output)
    assert {s["ticker"]: s["average_sentiment"] for s in sent} == {"AAA": 0.3, "BBB": -0.5}


def test_composite_gets_null_for_every_ticker_when_one_pick_is_unscored(flow):
    from tests.test_llm_role_audit import prime_draft
    from utils.strategy_assembly import composite_inputs

    prime_draft(flow)
    market = _published_market({"AAA": 0.3, "BBB": None})
    assert market.sentiment_available is False
    assert {c.ticker: c.average_sentiment for c in market.candidate_stocks} == {"AAA": 0.3, "BBB": None}
    sent = composite_inputs(market, flow.state.technical_output, flow.state.fundamental_output)
    assert [s["average_sentiment"] for s in sent] == [None, None]


def test_a_real_neutral_news_score_is_a_score_not_missing(flow):
    from tests.test_llm_role_audit import prime_draft
    from utils.strategy_assembly import composite_inputs

    prime_draft(flow)
    market = _published_market({"AAA": 0.0, "BBB": 0.0})
    assert market.sentiment_available is True
    sent = composite_inputs(market, flow.state.technical_output, flow.state.fundamental_output)
    assert [s["average_sentiment"] for s in sent] == [0.0, 0.0]
