"""One test per phase proving LLM-echoed numbers and grades never reach published output (CORR-10, D-15).

Plan 02-13 covers the fundamental phase. The other phases are added by plans
02-15 (technical), 02-16 (market), 02-17 (draft) and 02-18 (critique, final);
see .planning/phases/02-stall-elimination-schema-valid-output/02-LLM-ROLE-AUDIT.md.
"""
import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prospect_ai_flow import ProspectAIFlow
from schemas.agent_outputs import (
    CandidateStock,
    FundamentalAnalysisOutput,
    FundamentalNarrative,
    FundamentalNarrativeOutput,
    MarketAnalysisOutput,
    ValuationMetrics,
)
from utils.execution_tracker import ExecutionTracker
from utils.flow_tools import call_tool
from utils.fundamental_records import (
    UNAVAILABLE_STRENGTHS,
    UNAVAILABLE_THESIS,
    build_fundamental_records,
    merge_fundamental,
    require_narrative_coverage,
)
from utils.phase_runner import PhaseOutputError, PhaseSchemaError
from utils.tool_timing import instrument_tool

ANTHROPIC_ENV = {
    "ANTHROPIC_API_KEY": "test-key",
    "MODEL": "claude-haiku-4-5-20251001",
    "REDDIT_CLIENT_ID": "test-id",
    "REDDIT_CLIENT_SECRET": "test-secret",
}

PHASE = "fundamental_analysis"


# ─── Shared fixtures and stubs ─────────────────────────────────────────────────

def _candidate(ticker):
    return CandidateStock(
        ticker=ticker, mention_count=10, average_sentiment=0.2, relevance_score=0.8,
        rationale="r" * 60,
    )


def market_output(*tickers):
    return MarketAnalysisOutput(
        sector="Technology",
        candidate_stocks=[_candidate(t) for t in (tickers or ("AAA", "BBB"))],
        summary="s" * 120,
    )


FETCH_AAA = {
    "ticker": "AAA",
    "meta": {"company_name": "Alpha Corp"},
    "valuation": {"pe_ratio": 20.0, "pb_ratio": 3.0, "ps_ratio": 4.0, "ev_ebitda": 12.0},
    "profitability": {"return_on_equity": 0.25},
    "growth": {"revenue_growth_yoy": 0.10, "earnings_growth_yoy": 0.12},
    "balance_sheet": {"debt_to_equity": 0.5, "free_cash_flow": 1_000_000_000.0},
    "dividend": {"dividend_yield": 0.01},
}
FETCH_JSON = json.dumps({"fundamentals": [FETCH_AAA, {"ticker": "BBB", "error": "No data returned"}]})
GRADES_JSON = json.dumps({"grades": [
    {"ticker": "AAA", "valuation": "FAIR", "quality": "High", "growth": "Moderate Growth",
     "data_status": "ok", "quality_score": 3, "growth_score": 2,
     "fundamental_component": 5, "fundamental_unknown": False},
    {"ticker": "BBB", "valuation": "UNKNOWN", "quality": "UNKNOWN", "growth": "UNKNOWN",
     "data_status": "failed", "quality_score": None, "growth_score": None,
     "fundamental_component": None, "fundamental_unknown": True},
]})


class StubTool:
    """Stand-in for a crewai tool: records the calling thread and the kwargs."""

    def __init__(self, name, output):
        self.name = name
        self.output = output
        self.idents = []
        self.calls = []

    def _run(self, **kwargs):
        self.idents.append(threading.get_ident())
        self.calls.append(kwargs)
        return self.output


def stub_tools(fetch_json=FETCH_JSON, grades_json=GRADES_JSON):
    return {
        "fetch_fundamental_data": StubTool("fetch_fundamental_data", fetch_json),
        "grade_fundamental_data": StubTool("grade_fundamental_data", grades_json),
    }


def narrative_entry(ticker, **extra):
    entry = {
        "ticker": ticker,
        "key_strengths": [f"{ticker} strength"],
        "key_risks": [f"{ticker} risk"],
        "investment_thesis": f"{ticker} thesis written by the model.",
    }
    entry.update(extra)
    return entry


def narrative_payload(*entries, **extra):
    payload = {"analyses": list(entries), "summary": "n" * 120}
    payload.update(extra)
    return payload


def narrative_result(payload):
    """Crew result carrying the narrative as raw JSON (parsed by extract_model)."""
    task_out = SimpleNamespace(pydantic=None, json_dict=None)
    return SimpleNamespace(raw=json.dumps(payload), tasks_output=[task_out], token_usage=MagicMock())


def make_task():
    task = MagicMock()
    task.agent.llm.model = "claude-haiku-4-5-20251001"
    task.tools = []
    return task


@pytest.fixture
def flow():
    """ProspectAIFlow with TaskFactory patched out: no live LLM or network calls."""
    with patch.dict("os.environ", ANTHROPIC_ENV), \
         patch("prospect_ai_flow.TaskFactory") as MockFactory:
        MockFactory.return_value = MagicMock()
        f = ProspectAIFlow()
        f._tracker = None
        f.state.sector = "Technology"
        f.state.today = "2026-04-29"
        f.state.market_output = market_output()
        f._factory.build_task.return_value = make_task()
        yield f


def wire_tools(flow, tools, instrument=False):
    if instrument:
        for tool in tools.values():
            instrument_tool(tool, PHASE, lambda: flow._tracker)
    flow._factory.flow_tool.side_effect = lambda phase, name: tools[name]


def run_fundamental(flow, *results):
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=list(results))
        asyncio.run(flow.fundamental_analysis())
    return mc.return_value.akickoff


# ─── fundamental_analysis (plan 02-13) ─────────────────────────────────────────

def test_fundamental_llm_numbers_and_grades_overwritten(flow):
    """D-15: hostile numbers, grades and data_status in the answer are ignored."""
    tools = stub_tools()
    wire_tools(flow, tools)
    hostile = {
        "fundamental_rating": {"valuation": "CHEAP", "quality": "High", "growth": "High Growth"},
        "valuation_metrics": {"pe_ratio": 1.0, "roe": 9.9},
        "data_status": "ok",
        "company_name": "Hacked Inc",
    }
    payload = narrative_payload(
        narrative_entry("AAA", **hostile),
        narrative_entry("BBB", **hostile),
    )
    run_fundamental(flow, narrative_result(payload))

    out = flow.state.fundamental_output
    assert isinstance(out, FundamentalAnalysisOutput)
    by_ticker = {a.ticker: a for a in out.fundamental_analysis}
    assert [a.ticker for a in out.fundamental_analysis] == ["AAA", "BBB"]

    aaa = by_ticker["AAA"]
    assert aaa.company_name == "Alpha Corp"
    assert (aaa.fundamental_rating.valuation, aaa.fundamental_rating.quality,
            aaa.fundamental_rating.growth) == ("FAIR", "High", "Moderate Growth")
    assert aaa.data_status == "ok"
    assert aaa.valuation_metrics.pe_ratio == 20.0
    assert aaa.valuation_metrics.roe == 0.25
    assert aaa.valuation_metrics.price_to_sales == 4.0
    assert aaa.valuation_metrics.dividend_yield == 0.01
    assert aaa.key_strengths == ["AAA strength"]
    assert aaa.key_risks == ["AAA risk"]
    assert aaa.investment_thesis == "AAA thesis written by the model."

    bbb = by_ticker["BBB"]
    assert bbb.data_status == "failed"
    assert (bbb.fundamental_rating.valuation, bbb.fundamental_rating.quality,
            bbb.fundamental_rating.growth) == ("UNKNOWN", "UNKNOWN", "UNKNOWN")
    assert bbb.valuation_metrics == ValuationMetrics()
    assert bbb.company_name == "BBB"
    assert bbb.key_strengths == UNAVAILABLE_STRENGTHS
    assert bbb.key_risks == UNAVAILABLE_STRENGTHS
    assert bbb.investment_thesis == UNAVAILABLE_THESIS
    assert "BBB thesis" not in out.model_dump_json()
    assert "Hacked Inc" not in out.model_dump_json()


def test_narrative_model_has_no_number_or_grade_fields():
    """The LLM-facing model cannot even carry a number or a grade."""
    fields = set(FundamentalNarrative.model_fields) | set(FundamentalNarrativeOutput.model_fields)
    assert fields == {"ticker", "key_strengths", "key_risks", "investment_thesis", "analyses", "summary"}
    parsed = FundamentalNarrativeOutput.model_validate(
        narrative_payload(narrative_entry("AAA", valuation_metrics={"pe_ratio": 1.0}))
    )
    assert "valuation_metrics" not in parsed.analyses[0].model_dump()


def test_missing_narrative_is_retried(flow):
    # Unit: the coverage check names the missing ticker.
    records = build_fundamental_records(FETCH_JSON, GRADES_JSON)
    only_bbb = FundamentalNarrativeOutput.model_validate(narrative_payload(narrative_entry("BBB")))
    with pytest.raises(PhaseOutputError) as info:
        require_narrative_coverage(only_bbb, records)
    assert info.value.fields == ["analyses[AAA]"]

    # Flow: an incomplete first answer spends the budget; the second one is accepted.
    wire_tools(flow, stub_tools())
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    akickoff = run_fundamental(
        flow,
        narrative_result(narrative_payload(narrative_entry("BBB"))),
        narrative_result(narrative_payload(narrative_entry("AAA"))),
    )
    assert akickoff.await_count == 2
    calls = flow._factory.build_task.call_args_list
    assert "feedback" not in calls[0].kwargs
    assert "analyses[AAA]" in calls[1].kwargs["feedback"]
    phase = next(p for p in flow._tracker.to_dict()["phases"] if p["name"] == PHASE)
    assert phase["attempts"] == 2
    assert flow.state.fundamental_output is not None


def test_missing_narrative_exhausts_the_budget(flow):
    wire_tools(flow, stub_tools())
    bad = narrative_result(narrative_payload(narrative_entry("BBB")))
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=[bad, bad, bad, bad])
        with pytest.raises(PhaseSchemaError) as info:
            asyncio.run(flow.fundamental_analysis())
    assert mc.return_value.akickoff.await_count == 3
    assert "analyses[AAA]" in str(info.value)
    assert flow.state.fundamental_output is None


def test_flow_tools_off_loop(flow):
    tools = stub_tools()
    wire_tools(flow, tools)
    loop_thread = threading.get_ident()
    run_fundamental(flow, narrative_result(narrative_payload(narrative_entry("AAA"))))
    for tool in tools.values():
        assert len(tool.idents) == 1
        assert tool.idents[0] != loop_thread


def test_flow_tool_timing_recorded(flow):
    tools = stub_tools()
    wire_tools(flow, tools, instrument=True)
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    run_fundamental(flow, narrative_result(narrative_payload(narrative_entry("AAA"))))
    calls = flow._tracker.to_dict()["tool_calls"]
    assert [(c["phase"], c["tool"]) for c in calls] == [
        (PHASE, "fetch_fundamental_data"),
        (PHASE, "grade_fundamental_data"),
    ]
    assert all(c["ok"] for c in calls)
    assert flow._tracker.tool_call_count(PHASE) == 2


def test_flow_passes_the_fetch_result_to_the_grader_and_tickers_to_fetch(flow):
    tools = stub_tools()
    wire_tools(flow, tools)
    run_fundamental(flow, narrative_result(narrative_payload(narrative_entry("AAA"))))
    assert json.loads(tools["fetch_fundamental_data"].calls[0]["tickers_json"]) == ["AAA", "BBB"]
    assert tools["grade_fundamental_data"].calls[0]["fundamentals_batch_json"] == FETCH_JSON


def test_fundamental_agent_has_no_tools(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "dummy-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "dummy-secret")
    from prospect_ai_crew import TaskFactory

    factory = TaskFactory()
    task = factory.build_task(PHASE, "Technology", "2026-04-29", "=== ctx ===")
    assert list(task.tools or []) == []
    assert task.output_pydantic is FundamentalNarrativeOutput
    fetch = factory.flow_tool(PHASE, "fetch_fundamental_data")
    grade = factory.flow_tool(PHASE, "grade_fundamental_data")
    assert fetch.name == "fetch_fundamental_data"
    assert grade.name == "grade_fundamental_data"
    # Same instrumented instances the phase config holds (timings reach the tracker).
    assert fetch is factory._phase_config[PHASE]["flow_tools"]["fetch_fundamental_data"]
    assert factory._phase_config[PHASE]["agent_tools"] == []
    with pytest.raises(KeyError):
        factory.flow_tool(PHASE, "no_such_tool")


def test_every_failed_ticker_skips_the_llm(flow):
    """No data for any ticker: nothing for the model to write, and no model-invented prose."""
    failed = json.dumps({"grades": [
        {"ticker": t, "valuation": "UNKNOWN", "quality": "UNKNOWN", "growth": "UNKNOWN",
         "data_status": "failed", "quality_score": None, "growth_score": None,
         "fundamental_component": None, "fundamental_unknown": True}
        for t in ("AAA", "BBB")
    ]})
    fetch = json.dumps({"fundamentals": [
        {"ticker": "AAA", "error": "x"}, {"ticker": "BBB", "error": "y"},
    ]})
    wire_tools(flow, stub_tools(fetch, failed))
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=AssertionError("LLM must not be called"))
        asyncio.run(flow.fundamental_analysis())
    out = flow.state.fundamental_output
    assert [a.data_status for a in out.fundamental_analysis] == ["failed", "failed"]
    assert len(out.summary) >= 100
    flow._factory.build_task.assert_not_called()


def test_no_candidates_fails_clearly(flow):
    flow.state.market_output = None
    wire_tools(flow, stub_tools())
    with pytest.raises(RuntimeError, match="fundamental_analysis"):
        asyncio.run(flow.fundamental_analysis())


# ─── Record builder ────────────────────────────────────────────────────────────

class TestBuildFundamentalRecords:
    def test_keyed_by_upper_case_ticker_with_grades_and_metrics(self):
        records = build_fundamental_records(FETCH_JSON, GRADES_JSON)
        assert list(records) == ["AAA", "BBB"]
        assert records["AAA"]["company_name"] == "Alpha Corp"
        assert records["AAA"]["data_status"] == "ok"
        assert records["AAA"]["valuation_metrics"].debt_to_equity == 0.5
        assert records["AAA"]["valuation_metrics"].free_cash_flow == 1_000_000_000.0
        assert records["BBB"]["data_status"] == "failed"
        assert records["BBB"]["valuation_metrics"] == ValuationMetrics()

    def test_whole_call_error_yields_no_records(self):
        """No per-ticker entries: merge_fundamental treats every ticker as failed."""
        records = build_fundamental_records(
            json.dumps({"error": "Invalid JSON"}), json.dumps({"grades": []}),
        )
        assert records == {}

    def test_whole_call_error_publishes_every_ticker_as_failed(self):
        out = merge_fundamental("Technology", ["AAA", "BBB"], {}, None)
        assert [a.data_status for a in out.fundamental_analysis] == ["failed", "failed"]

    def test_ticker_missing_from_grades_is_failed(self):
        grades = json.dumps({"grades": [json.loads(GRADES_JSON)["grades"][1]]})
        records = build_fundamental_records(FETCH_JSON, grades)
        assert records["AAA"]["data_status"] == "failed"
        assert records["AAA"]["valuation_metrics"] == ValuationMetrics()
        assert records["AAA"]["fundamental_rating"].quality == "UNKNOWN"

    def test_unparseable_fetch_yields_no_records(self):
        assert build_fundamental_records("not json", GRADES_JSON) == {}

    def test_unparseable_grades_fail_every_fetched_ticker(self):
        records = build_fundamental_records(FETCH_JSON, "not json")
        assert {t: r["data_status"] for t, r in records.items()} == {"AAA": "failed", "BBB": "failed"}
        assert records["AAA"]["valuation_metrics"] == ValuationMetrics()

    def test_missing_or_bad_numbers_are_null_never_zero(self):
        entry = {
            "ticker": "CCC",
            "meta": {"company_name": None},
            "valuation": {"pe_ratio": "n/a", "pb_ratio": True, "ps_ratio": float("nan")},
            "dividend": {"dividend_yield": -1.0},
        }
        grades = {"ticker": "CCC", "valuation": "UNKNOWN", "quality": "UNKNOWN",
                  "growth": "UNKNOWN", "data_status": "partial"}
        records = build_fundamental_records(
            json.dumps({"fundamentals": [entry]}), json.dumps({"grades": [grades]}),
        )
        rec = records["CCC"]
        assert rec["company_name"] == "CCC"
        assert rec["valuation_metrics"] == ValuationMetrics()
        assert rec["data_status"] == "partial"


class TestMergeFundamental:
    def test_unknown_ticker_in_narrative_is_ignored(self, caplog):
        records = build_fundamental_records(FETCH_JSON, GRADES_JSON)
        narrative = FundamentalNarrativeOutput.model_validate(
            narrative_payload(narrative_entry("AAA"), narrative_entry("ZZZ"))
        )
        with caplog.at_level("INFO"):
            out = merge_fundamental("Technology", ["AAA", "BBB"], records, narrative)
        assert [a.ticker for a in out.fundamental_analysis] == ["AAA", "BBB"]
        assert "ZZZ" in caplog.text

    def test_candidate_order_is_kept(self):
        records = build_fundamental_records(FETCH_JSON, GRADES_JSON)
        narrative = FundamentalNarrativeOutput.model_validate(narrative_payload(narrative_entry("AAA")))
        out = merge_fundamental("Technology", ["BBB", "AAA"], records, narrative)
        assert [a.ticker for a in out.fundamental_analysis] == ["BBB", "AAA"]


# ─── call_tool ─────────────────────────────────────────────────────────────────

class TestCallTool:
    def test_emits_step_with_tool_input_and_log_before_running(self):
        order = []
        tool = StubTool("fetch_fundamental_data", "OUT")
        tool_run = tool._run

        def run(**kw):
            order.append("run")
            return tool_run(**kw)

        tool._run = run
        steps = []

        def cb(index, step):
            order.append("step")
            steps.append((index, step))

        out = asyncio.run(call_tool(
            tool, phase_index=2, step_callback=cb, thought="Fetching", tickers_json='["AAA"]',
        ))
        assert out == "OUT"
        assert order == ["step", "run"]
        index, step = steps[0]
        assert index == 2
        assert step.tool == "fetch_fundamental_data"
        assert isinstance(step.tool_input, str) and "AAA" in step.tool_input
        assert step.log == "Fetching"

    def test_tool_input_is_cut_to_400_chars(self):
        tool = StubTool("grade_fundamental_data", "OUT")
        steps = []
        asyncio.run(call_tool(
            tool, phase_index=2, step_callback=lambda i, s: steps.append(s),
            thought="Grading", fundamentals_batch_json="x" * 5000,
        ))
        assert len(steps[0].tool_input) <= 400

    def test_callback_failure_is_swallowed_and_logged_by_class_name(self, caplog):
        tool = StubTool("fetch_fundamental_data", "OUT")

        def boom(i, s):
            raise ValueError("secret-in-message")

        with caplog.at_level("WARNING"):
            out = asyncio.run(call_tool(tool, phase_index=2, step_callback=boom, thought="t"))
        assert out == "OUT"
        assert "ValueError" in caplog.text
        assert "secret-in-message" not in caplog.text

    def test_no_callback_still_runs_the_tool(self):
        tool = StubTool("fetch_fundamental_data", "OUT")
        assert asyncio.run(call_tool(tool, phase_index=2, step_callback=None, thought="t")) == "OUT"
