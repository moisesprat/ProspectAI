"""No async flow phase blocks the event loop with a sleep (STALL-02, ROADMAP SC2).

The Reddit and Serper tools keep bounded blocking sleeps (Reddit pacing, Serper retry
backoff, plan 02-08, D-13). The guarantee is where they run: the Flow is the only
caller and always goes through ``utils.flow_tools.call_tool`` (``asyncio.to_thread``),
so every ``time.sleep`` happens on a worker thread. These tests run the real Reddit and
Serper tools inside the six-phase Flow with only the network, the other tools and the
LLM faked, and record the thread of every sleep.
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
from tests.fake_clock import FakeClock
from tests.test_llm_role_audit import (
    ANTHROPIC_ENV,
    REDDIT_TOOL,
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
from utils.patient_serper_tool import PatientSerperDevTool
from utils.reddit_sentiment_tool import RedditSentimentTool

REDDIT_MODULE = "utils.reddit_sentiment_tool"
SERPER_MODULE = "utils.patient_serper_tool"


# ─── Fakes ─────────────────────────────────────────────────────────────────────

def _reddit_posts_without_tickers():
    """A 200 response whose posts mention no ticker of the sector: Reddit then asks for fallback."""
    post = {
        "title": "What do you all think about the market today", "selftext": "", "score": 10,
        "upvote_ratio": 0.8, "url": "https://reddit.example/1", "permalink": "/r/stocks/1",
    }
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": {"children": [{"data": post}]}}
    return resp


def _status_response(status):
    resp = MagicMock()
    resp.status_code = status
    return resp


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
    with patch.dict("os.environ", ANTHROPIC_ENV), patch("prospect_ai_flow.TaskFactory") as MockFactory:
        MockFactory.return_value = MagicMock()
        f = ProspectAIFlow()
        f._tracker = ExecutionTracker()
        f._tracker.start()
        f._factory.build_task.return_value = make_task()
        tools = {
            **stub_tools(), **tech_tools(), **draft_tools(),
            REDDIT_TOOL: RedditSentimentTool(), SERPER_TOOL: PatientSerperDevTool(),
        }
        wire_tools(f, tools, phase="market_analysis")
        yield f


# ─── Tests ─────────────────────────────────────────────────────────────────────

def test_no_sleep_on_loop_full_run(flow):
    """Every sleep in a full six-phase run, real Reddit and Serper tools included, is off the loop."""
    sleeps, loop_threads = [], set()
    results = {
        0: narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB"))),
        1: narrative_result(tech_payload(tech_narrative_entry("AAA"))),
        2: narrative_result(narrative_payload(narrative_entry("AAA"))),
        3: narrative_result(draft_payload(draft_entry("AAA"))),
        4: _json_result(_critic()),
        5: narrative_result(draft_payload(draft_entry("AAA"))),
    }
    serper_posts = [_serper_response(503), _serper_response(200, SERPER_BODY)]
    with patch.object(flow, "_make_crew", side_effect=_crew_factory(results, loop_threads)), \
         patch.object(flow, "_slim_draft", return_value=""), \
         patch.object(flow, "_critic_reference_table", return_value=""), \
         patch.object(flow, "_gated_slim_critique", return_value=""), \
         patch.object(time, "sleep", _sleep_recorder(sleeps)), \
         patch("requests.get", return_value=_reddit_posts_without_tickers()), \
         patch("requests.post", side_effect=serper_posts) as post:
        flow.kickoff(inputs={"sector": "Technology", "today": "2026-04-29", "risk_profile": "conservative"})

    # The run went all the way through, on one event-loop thread.
    assert flow.state.final_output is not None
    assert len(loop_threads) == 1
    # The market phase really took the Reddit-then-Serper path, including the 503 retry.
    assert flow.state.market_output.sentiment_available is False
    assert post.call_count == 2
    # Non-vacuous: pacing sleeps (Reddit) and a backoff sleep (Serper) happened ...
    modules = {module for _, module, _ in sleeps}
    assert {REDDIT_MODULE, SERPER_MODULE} <= modules
    assert len(sleeps) >= 2
    # ... and none of them on the event-loop thread.
    on_loop = [(module, seconds) for ident, module, seconds in sleeps if ident in loop_threads]
    assert on_loop == []


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


def test_reddit_429_run_continues(flow):
    """Every Reddit request is a 429: the call skips fast, the Serper path runs, the phase completes."""
    clock = FakeClock()
    loop_threads = set()
    results = {0: narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB")))}
    get = clock.get_side_effect(_status_response(429), latency=0.5)
    import asyncio

    with patch.object(flow, "_make_crew", side_effect=_crew_factory(results, loop_threads)), \
         patch(f"{REDDIT_MODULE}.requests.get", side_effect=get), \
         patch(f"{REDDIT_MODULE}.time", clock), \
         patch("requests.post", return_value=_serper_response(200, SERPER_BODY)) as post:
        flow.state.sector, flow.state.today = "Technology", "2026-04-29"
        asyncio.run(flow.market_analysis())

    # Within the Reddit wall budget, no wait on a 429, and the breaker stopped the tool early.
    assert clock.now < RedditSentimentTool.TIME_BUDGET_SECONDS
    assert clock.sleeps == []
    assert clock.request_count == RedditSentimentTool.MAX_CONSECUTIVE_FAILURES
    # The run continued: Serper was asked and the market phase published from its results.
    assert post.call_count == 1
    out = flow.state.market_output
    assert [c.ticker for c in out.candidate_stocks] == ["AAA", "BBB"]
    assert out.candidate_stocks[0].mention_count == 3
    assert out.sentiment_available is False
