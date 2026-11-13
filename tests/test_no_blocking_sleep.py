"""No async flow phase blocks the event loop with a sleep (STALL-02, ROADMAP SC2).

The Serper tool keeps a bounded blocking sleep (retry backoff, plan 02-08, D-13). The
guarantee is where it runs: the Flow is the only caller and always goes through
``utils.flow_tools.call_tool`` (``asyncio.to_thread``), so every ``time.sleep`` happens on
a worker thread. These tests run the real Serper tool inside the six-phase Flow with only
the network, the other tools and the LLM faked, and record the thread of every sleep.
"""
import json
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from prospect_ai_flow import ProspectAIFlow
from schemas.agent_outputs import CriticOutput
from tests.test_llm_role_audit import (
    ANTHROPIC_ENV,
    SERPER_TOOL,
    draft_entry,
    draft_payload,
    draft_tools,
    make_task,
    mkt_entry,
    mkt_payload,
    narrative_entry,
    narrative_payload,
    narrative_result,
    stub_tools,
    tech_narrative_entry,
    tech_payload,
    tech_tools,
    wire_tools,
)
from utils.execution_tracker import ExecutionTracker
from utils.news_sentiment import API_KEY_ENV as NEWS_KEY_ENV, TOOL_NAME as NEWS_TOOL, NewsSentimentTool
from utils.patient_serper_tool import PatientSerperDevTool

SERPER_MODULE = "utils.patient_serper_tool"
NEWS_MODULE = "utils.news_sentiment"


# ─── Fakes ─────────────────────────────────────────────────────────────────────

def _serper_response(status, body=None):
    body = body if body is not None else {"organic": []}
    resp = MagicMock()
    resp.status_code = status
    resp.content = json.dumps(body).encode()
    resp.json.return_value = body
    if status >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    else:
        resp.raise_for_status.side_effect = None
    return resp


SERPER_BODY = {"organic": [
    {"title": "AAA leads the sector", "link": "https://news1.example.com/a", "snippet": "AAA and BBB rally", "position": 1},
    {"title": "BBB steady", "link": "https://news2.example.com/b", "snippet": "AAA again", "position": 2},
]}


def _sleep_recorder(calls):
    """Replacement for time.sleep: records (thread ident, calling module, seconds), never waits."""
    def sleep(seconds):
        calls.append((threading.get_ident(), sys._getframe(1).f_globals.get("__name__"), seconds))
    return sleep


def _crew_factory(results, loop_threads):
    """_make_crew replacement: each phase's kickoff records the event-loop thread, then answers."""
    def make_crew(task, index):
        async def akickoff():
            loop_threads.add(threading.get_ident())
            return results[index]

        crew = MagicMock()
        crew.akickoff = akickoff
        return crew

    return make_crew


def _json_result(model):
    task_out = SimpleNamespace(pydantic=None, json_dict=None)
    return SimpleNamespace(raw=model.model_dump_json(), tasks_output=[task_out], token_usage=MagicMock())


def _critic():
    return CriticOutput(
        sector="Technology", draft_assessment="d" * 60, portfolio_level_issues=[], approved_positions=[],
    )


@pytest.fixture
def flow(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-serper-key")
    monkeypatch.delenv(NEWS_KEY_ENV, raising=False)  # the news lookup is off unless a test sets a key
    with patch.dict("os.environ", ANTHROPIC_ENV), patch("prospect_ai_flow.TaskFactory") as MockFactory:
        MockFactory.return_value = MagicMock()
        f = ProspectAIFlow()
        f._tracker = ExecutionTracker()
        f._tracker.start()
        f._factory.build_task.return_value = make_task()
        tools = {
            **stub_tools(), **tech_tools(), **draft_tools(),
            SERPER_TOOL: PatientSerperDevTool(),
            NEWS_TOOL: NewsSentimentTool(),
        }
        wire_tools(f, tools, phase="market_analysis")
        yield f


# ─── Tests ─────────────────────────────────────────────────────────────────────

def test_no_sleep_on_loop_full_run(flow):
    """Every sleep in a full six-phase run, the real Serper tool included, is off the loop."""
    sleeps, loop_threads = [], set()
    results = {
        0: narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB"))),
        1: narrative_result(tech_payload(tech_narrative_entry("AAA"))),
        2: narrative_result(narrative_payload(narrative_entry("AAA"))),
        3: narrative_result(draft_payload(draft_entry("AAA"))),
        4: _json_result(_critic()),
        5: narrative_result(draft_payload(draft_entry("AAA"))),
    }
    # Three fixed queries: the first one hits a 503 and retries once, the other two answer at once.
    serper_posts = [_serper_response(503), _serper_response(200, SERPER_BODY),
                    _serper_response(200, SERPER_BODY), _serper_response(200, SERPER_BODY)]
    with patch.object(flow, "_make_crew", side_effect=_crew_factory(results, loop_threads)), \
         patch.object(flow, "_slim_draft", return_value=""), \
         patch.object(flow, "_critic_reference_table", return_value=""), \
         patch.object(flow, "_gated_slim_critique", return_value=""), \
         patch.object(time, "sleep", _sleep_recorder(sleeps)), \
         patch("requests.post", side_effect=serper_posts) as post:
        flow.kickoff(inputs={"sector": "Technology", "today": "2026-04-29", "risk_profile": "conservative"})

    # The run went all the way through, on one event-loop thread.
    assert flow.state.final_output is not None
    assert len(loop_threads) == 1
    # The market phase really took the Serper path, including the 503 retry.
    assert flow.state.market_output.sentiment_available is False
    assert post.call_count == 4
    # Non-vacuous: the Serper retry backoff slept at least once ...
    serper_sleeps = [s for s in sleeps if s[1] == SERPER_MODULE]
    assert len(serper_sleeps) >= 1
    # ... and none of them on the event-loop thread.
    on_loop = [(module, seconds) for ident, module, seconds in sleeps if ident in loop_threads]
    assert on_loop == []


@pytest.mark.usefixtures("real_sector_check")
def test_sector_lookup_never_runs_on_the_loop_thread(flow, monkeypatch):
    """Phase 4.1 D-08: the sector check's yfinance lookups run on worker threads, never the loop."""
    from utils import yfinance_cache

    sleeps, loop_threads, lookup_threads = [], set(), set()

    def get_info(ticker):
        lookup_threads.add(threading.get_ident())
        return {"sector": "Technology", "industry": "Software - Application"}

    monkeypatch.setattr(yfinance_cache, "get_info", get_info)
    results = {
        0: narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB"))),
        1: narrative_result(tech_payload(tech_narrative_entry("AAA"))),
        2: narrative_result(narrative_payload(narrative_entry("AAA"))),
        3: narrative_result(draft_payload(draft_entry("AAA"))),
        4: _json_result(_critic()),
        5: narrative_result(draft_payload(draft_entry("AAA"))),
    }
    serper_posts = [_serper_response(200, SERPER_BODY)] * 3
    with patch.object(flow, "_make_crew", side_effect=_crew_factory(results, loop_threads)), \
         patch.object(flow, "_slim_draft", return_value=""), \
         patch.object(flow, "_critic_reference_table", return_value=""), \
         patch.object(flow, "_gated_slim_critique", return_value=""), \
         patch.object(time, "sleep", _sleep_recorder(sleeps)), \
         patch("requests.post", side_effect=serper_posts):
        flow.kickoff(inputs={"sector": "Technology", "today": "2026-04-29", "risk_profile": "conservative"})

    assert flow.state.final_output is not None
    assert len(loop_threads) == 1
    assert lookup_threads
    assert lookup_threads.isdisjoint(loop_threads)
    assert [ident for ident, _, _ in sleeps if ident in loop_threads] == []


def test_news_sentiment_refusal_in_a_full_run_never_sleeps(flow, monkeypatch):
    """The news lookup answers a rate limit: the run completes with null sentiment, the lookup
    stops after one request, and it never sleeps (plan 03.1-09, D-07)."""
    monkeypatch.setenv(NEWS_KEY_ENV, "tok-SLEEP-GUARD-1")
    sleeps, loop_threads = [], set()
    results = {
        0: narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB"))),
        1: narrative_result(tech_payload(tech_narrative_entry("AAA"))),
        2: narrative_result(narrative_payload(narrative_entry("AAA"))),
        3: narrative_result(draft_payload(draft_entry("AAA"))),
        4: _json_result(_critic()),
        5: narrative_result(draft_payload(draft_entry("AAA"))),
    }
    refusal = MagicMock()
    refusal.status_code = 429
    refusal.json.return_value = {"error": {"code": "rate_limit_reached"}}
    serper_posts = [_serper_response(200, SERPER_BODY)] * 3
    with patch.object(flow, "_make_crew", side_effect=_crew_factory(results, loop_threads)), \
         patch.object(flow, "_slim_draft", return_value=""), \
         patch.object(flow, "_critic_reference_table", return_value=""), \
         patch.object(flow, "_gated_slim_critique", return_value=""), \
         patch.object(time, "sleep", _sleep_recorder(sleeps)), \
         patch("requests.post", side_effect=serper_posts), \
         patch(f"{NEWS_MODULE}.requests.get", return_value=refusal) as news_get:
        flow.kickoff(inputs={"sector": "Technology", "today": "2026-04-29", "risk_profile": "conservative"})

    assert flow.state.final_output is not None
    market = flow.state.market_output
    assert market.sentiment_available is False
    assert [c.average_sentiment for c in market.candidate_stocks] == [None, None]
    assert news_get.call_count == 1  # the refusal stops the lookup: no request for the second pick
    assert [ident for ident, module, _ in sleeps if module == NEWS_MODULE] == []
    assert [ident for ident, _, _ in sleeps if ident in loop_threads] == []


def test_detector_catches_a_sleep_on_the_loop_thread():
    """The detector is not blind: a sleep made directly in a coroutine is seen on the loop thread."""
    import asyncio

    sleeps, loop_threads = [], set()

    async def phase():
        loop_threads.add(threading.get_ident())
        time.sleep(0.5)

    with patch.object(time, "sleep", _sleep_recorder(sleeps)):
        asyncio.run(phase())
    assert [ident for ident, _, _ in sleeps if ident in loop_threads] != []


def test_serper_outage_spends_at_most_three_retry_budgets(flow):
    """A Serper outage (every request a 503) makes three queries, each inside its own 02-08 budget,
    every sleep on a worker thread, and the market phase still completes on the unavailable path."""
    import asyncio

    from utils.patient_serper_tool import MAX_RETRIES, RETRY_BUDGET_SECONDS

    sleeps, loop_threads = [], set()
    results = {0: narrative_result(mkt_payload(mkt_entry("AAPL")))}
    with patch.object(flow, "_make_crew", side_effect=_crew_factory(results, loop_threads)), \
         patch.object(time, "sleep", _sleep_recorder(sleeps)), \
         patch("requests.post", side_effect=lambda *a, **k: _serper_response(503)) as post:
        flow.state.sector, flow.state.today = "Technology", "2026-04-29"
        asyncio.run(flow.market_analysis())

    assert post.call_count == 3 * (MAX_RETRIES + 1)
    serper_sleeps = [(ident, seconds) for ident, module, seconds in sleeps if module == SERPER_MODULE]
    assert 0 < sum(seconds for _, seconds in serper_sleeps) <= 3 * RETRY_BUDGET_SECONDS
    assert [ident for ident, _ in serper_sleeps if ident in loop_threads] == []
    out = flow.state.market_output
    assert [c.ticker for c in out.candidate_stocks] == ["AAPL"]
    assert out.candidate_stocks[0].mention_count is None
    assert flow._tracker.to_dict()["market_corpus"]["source"] == "unavailable"
