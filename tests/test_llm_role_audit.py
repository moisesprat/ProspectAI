"""One test per phase proving LLM-echoed numbers and grades never reach published output (CORR-10, D-15).

Plan 02-13 covers the fundamental phase, plan 02-15 the technical phase, plan 02-16
the market phase, plan 02-17 the draft phase and plan 02-18 the critique and final
phases (all six phases are covered);
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
    CriticOutput,
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


def wire_tools(flow, tools, instrument=False, phase=PHASE):
    if instrument:
        for tool in tools.values():
            instrument_tool(tool, phase, lambda: flow._tracker)
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


# ─── technical_analysis (plan 02-15) ───────────────────────────────────────────

TECH_PHASE = "technical_analysis"


def tech_entry(ticker, price=99.0, adx=32.0, **interp):
    """One successful calculate_technical_indicators entry, in the tool's documented shape."""
    interpretation = {
        "ticker": ticker, "entry_zone_low": 95.0, "entry_zone_high": 98.0,
        "entry_zone_status": "CURRENT_ENTRY", "regime": "TRENDING",
        "momentum_score": 7.1, "risk_level": "High",
    }
    interpretation.update(interp)
    return {
        "ticker": ticker,
        "stock_data": {"current_price": price},
        "technical_indicators": {
            "momentum": {
                "rsi": {"current": 58.0},
                "stochastic": {"status": "Neutral"},
                "macd": {"status": "Bullish"},
            },
            "trend": {
                "moving_averages": {"status": "Strong Uptrend"},
                "adx": {"current": adx, "status": "Moderate Trend"},
            },
        },
        "interpretation": interpretation,
    }


TECH_RESULT = {"technical_analysis": [tech_entry("AAA"), {"ticker": "BBB", "error": "No data found for BBB"}]}


def tech_tools(result=TECH_RESULT):
    return {"calculate_technical_indicators": StubTool("calculate_technical_indicators", result)}


def tech_narrative_entry(ticker, **extra):
    entry = {
        "ticker": ticker,
        "overall_signal": "BULLISH",
        "key_signals": [f"{ticker} RSI at 58 is neutral", f"{ticker} MACD is bullish"],
        "comprehensive_analysis": f"{ticker} trades in an uptrend with MACD bullish and RSI neutral. " * 2,
        "investment_recommendation": f"{ticker} is technically constructive; wait for the zone. " * 2,
    }
    entry.update(extra)
    return entry


def tech_payload(*entries, **extra):
    payload = {"analyses": list(entries), "summary": "t" * 120}
    payload.update(extra)
    return payload


def run_technical(flow, *results):
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=list(results))
        asyncio.run(flow.technical_analysis())
    return mc.return_value.akickoff


def test_technical_llm_numbers_and_labels_overwritten(flow):
    """D-15: hostile numbers and labels in the technical answer never reach the output."""
    import schemas.agent_outputs as schemas
    from schemas.agent_outputs import FailedTicker, TechnicalAnalysisOutput

    assert not hasattr(schemas, "TechnicalScore")
    wire_tools(flow, tech_tools(), phase=TECH_PHASE)
    hostile = {
        "momentum_score": 9.9, "trend_strength": "Moderate", "entry_zone_low": 1.0,
        "entry_zone_high": 2.0, "entry_zone_status": "BELOW_ZONE", "regime": "REVERTING",
        "risk_level": "Low", "current_price": 5.0, "raw_indicators": {"rsi": 99.0},
        "support_resistance": {"support": 1.0, "resistance": 2.0},
        "technical_score": {"percentage": 99.0, "grade": "A", "recommendation": "Strong Buy"},
    }
    payload = tech_payload(
        tech_narrative_entry("AAA", overall_signal="MIXED", **hostile),
        tech_narrative_entry("BBB", **hostile),
    )
    run_technical(flow, narrative_result(payload))

    out = flow.state.technical_output
    assert isinstance(out, TechnicalAnalysisOutput)
    assert [a.ticker for a in out.technical_analysis] == ["AAA"]
    aaa = out.technical_analysis[0]
    assert aaa.current_price == 99.0
    ri = aaa.raw_indicators
    assert (ri.rsi, ri.stochastic_status, ri.macd_status, ri.ma_status, ri.adx) == (
        58.0, "Neutral", "Bullish", "Strong Uptrend", 32.0)
    ma = aaa.momentum_analysis
    assert (ma.momentum_score, ma.risk_level) == (7.1, "High")
    assert ma.trend_strength == "Strong"
    assert (ma.entry_zone_low, ma.entry_zone_high) == (95.0, 98.0)
    assert (ma.entry_zone_status, ma.regime) == ("CURRENT_ENTRY", "TRENDING")
    assert ma.support_resistance is None
    assert not hasattr(aaa, "technical_score")
    assert "technical_score" not in out.model_dump_json()
    # What the LLM does own.
    assert ma.overall_signal == "MIXED"
    assert ma.key_signals == ["AAA RSI at 58 is neutral", "AAA MACD is bullish"]
    assert "AAA trades in an uptrend" in ma.comprehensive_analysis
    assert "AAA is technically constructive" in aaa.investment_recommendation
    assert out.summary == "t" * 120
    # BBB failed: only in failed_tickers, nothing the model wrote about it.
    assert out.failed_tickers == [FailedTicker(ticker="BBB", error="No data found for BBB")]
    assert "BBB" not in {a.ticker for a in out.technical_analysis}
    assert "BBB trades" not in out.model_dump_json()


@pytest.mark.parametrize("adx,label", [
    (0.0, "Very Weak"), (10, "Very Weak"), (14.99, "Very Weak"), (15, "Weak"), (19.9, "Weak"),
    (20, "Neutral"), (24.9, "Neutral"), (25, "Strong"), (39.9, "Strong"), (40, "Very Strong"),
    (80, "Very Strong"), (None, None),
])
def test_trend_strength_thresholds(adx, label):
    from utils.technical_records import trend_strength_from_adx

    assert trend_strength_from_adx(adx) == label


@pytest.mark.parametrize("bad", ["x", True, float("nan"), float("inf"), [1]])
def test_trend_strength_is_null_for_unusable_adx(bad):
    from utils.technical_records import trend_strength_from_adx

    assert trend_strength_from_adx(bad) is None


def test_overall_signal_strict():
    from pydantic import ValidationError
    from schemas.agent_outputs import TechnicalNarrative

    ok = tech_narrative_entry("AAA")
    assert TechnicalNarrative.model_validate(ok).overall_signal == "BULLISH"
    for bad in ("bullish", "Bullish", " BULLISH", "UP"):
        with pytest.raises(ValidationError):
            TechnicalNarrative.model_validate({**ok, "overall_signal": bad})


def test_all_failed_raises(flow):
    result = {"technical_analysis": [{"ticker": "AAA", "error": "x"}, {"ticker": "BBB", "error": "y"}]}
    wire_tools(flow, tech_tools(result), phase=TECH_PHASE)
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=AssertionError("LLM must not be called"))
        with pytest.raises(RuntimeError, match="technical_analysis"):
            asyncio.run(flow.technical_analysis())
    flow._factory.build_task.assert_not_called()
    assert flow.state.technical_output is None


def test_whole_call_error_raises(flow):
    wire_tools(flow, tech_tools({"error": "tickers_json array is empty"}), phase=TECH_PHASE)
    with pytest.raises(RuntimeError, match="technical_analysis"):
        asyncio.run(flow.technical_analysis())


def test_missing_narrative_retried(flow):
    from utils.technical_records import build_technical_records, require_technical_coverage
    from schemas.agent_outputs import TechnicalNarrativeOutput

    records, failed = build_technical_records(TECH_RESULT)
    assert list(records) == ["AAA"] and [f.ticker for f in failed] == ["BBB"]
    only_bbb = TechnicalNarrativeOutput.model_validate(tech_payload(tech_narrative_entry("BBB")))
    with pytest.raises(PhaseOutputError) as info:
        require_technical_coverage(only_bbb, records)
    assert info.value.fields == ["analyses[AAA]"]

    wire_tools(flow, tech_tools(), phase=TECH_PHASE)
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    akickoff = run_technical(
        flow,
        narrative_result(tech_payload(tech_narrative_entry("BBB"))),
        narrative_result(tech_payload(tech_narrative_entry("AAA"))),
    )
    assert akickoff.await_count == 2
    calls = flow._factory.build_task.call_args_list
    assert "feedback" not in calls[0].kwargs
    assert "analyses[AAA]" in calls[1].kwargs["feedback"]
    phase = next(p for p in flow._tracker.to_dict()["phases"] if p["name"] == TECH_PHASE)
    assert phase["attempts"] == 2
    assert flow.state.technical_output is not None


def test_failed_tickers_logged_with_warning(flow, caplog):
    wire_tools(flow, tech_tools(), phase=TECH_PHASE)
    with caplog.at_level("WARNING"):
        run_technical(flow, narrative_result(tech_payload(tech_narrative_entry("AAA"))))
    assert "BBB" in caplog.text and "technical_analysis" in caplog.text


def test_technical_flow_tool_off_loop_and_timed(flow):
    tools = tech_tools()
    wire_tools(flow, tools, instrument=True, phase=TECH_PHASE)
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    loop_thread = threading.get_ident()
    run_technical(flow, narrative_result(tech_payload(tech_narrative_entry("AAA"))))
    tool = tools["calculate_technical_indicators"]
    assert len(tool.idents) == 1 and tool.idents[0] != loop_thread
    assert json.loads(tool.calls[0]["tickers_json"]) == ["AAA", "BBB"]
    calls = flow._tracker.to_dict()["tool_calls"]
    assert [(c["phase"], c["tool"]) for c in calls] == [(TECH_PHASE, "calculate_technical_indicators")]
    assert flow._tracker.tool_call_count(TECH_PHASE) == 1


def test_technical_agent_has_no_tools(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "dummy-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "dummy-secret")
    from prospect_ai_crew import TaskFactory
    from schemas.agent_outputs import TechnicalNarrativeOutput

    factory = TaskFactory()
    task = factory.build_task(TECH_PHASE, "Technology", "2026-04-29", "=== ctx ===")
    assert list(task.tools or []) == []
    assert task.output_pydantic is TechnicalNarrativeOutput
    tool = factory.flow_tool(TECH_PHASE, "calculate_technical_indicators")
    assert tool is factory._phase_config[TECH_PHASE]["flow_tools"]["calculate_technical_indicators"]
    assert factory._phase_config[TECH_PHASE]["agent_tools"] == []


class TestBuildTechnicalRecords:
    def test_record_values_come_only_from_the_tool(self):
        from utils.technical_records import build_technical_records

        records, failed = build_technical_records(TECH_RESULT, ["AAA", "BBB"])
        rec = records["AAA"]
        assert rec["current_price"] == 99.0
        assert rec["trend_strength"] == "Strong"
        assert rec["momentum_analysis"]["momentum_score"] == 7.1
        assert failed[0].ticker == "BBB"

    def test_missing_adx_is_null_trend_strength_not_a_guess(self):
        from utils.technical_records import build_technical_records

        entry = tech_entry("AAA")
        entry["technical_indicators"]["trend"]["adx"] = {"current": None, "status": None}
        records, _ = build_technical_records({"technical_analysis": [entry]})
        assert records["AAA"]["trend_strength"] is None
        assert records["AAA"]["raw_indicators"].adx is None

    @pytest.mark.parametrize("break_it", [
        lambda e: e.pop("interpretation"),
        lambda e: e["interpretation"].update(error="Computation error: x"),
        lambda e: e["interpretation"].pop("momentum_score"),
        lambda e: e["interpretation"].update(momentum_score=float("nan")),
        lambda e: e["interpretation"].update(momentum_score=11.0),
        lambda e: e["interpretation"].update(risk_level="HIGH"),
        lambda e: e["interpretation"].update(entry_zone_status="SOMEWHERE"),
        lambda e: e["interpretation"].update(regime="WILD"),
        lambda e: e["interpretation"].pop("entry_zone_low"),
        lambda e: e["stock_data"].update(current_price=0),
    ])
    def test_an_unusable_entry_is_failed_never_defaulted(self, break_it):
        from utils.technical_records import build_technical_records

        entry = tech_entry("AAA")
        break_it(entry)
        records, failed = build_technical_records({"technical_analysis": [entry]})
        assert records == {}
        assert [f.ticker for f in failed] == ["AAA"]

    def test_error_text_is_cut_to_200_chars(self):
        from utils.technical_records import build_technical_records

        _, failed = build_technical_records(
            {"technical_analysis": [{"ticker": "AAA", "error": "e" * 500}]})
        assert len(failed[0].error) == 200

    def test_requested_ticker_the_tool_never_returned_is_failed(self):
        from utils.technical_records import build_technical_records

        records, failed = build_technical_records(
            {"technical_analysis": [tech_entry("AAA")]}, ["AAA", "ZZZ"])
        assert list(records) == ["AAA"]
        assert [f.ticker for f in failed] == ["ZZZ"]

    def test_whole_call_error_fails_every_requested_ticker(self):
        from utils.technical_records import build_technical_records

        records, failed = build_technical_records({"error": "boom"}, ["AAA", "BBB"])
        assert records == {}
        assert [(f.ticker, f.error) for f in failed] == [("AAA", "boom"), ("BBB", "boom")]


class TestMergeTechnical:
    def test_market_order_is_kept_and_unknown_narrative_ignored(self, caplog):
        from schemas.agent_outputs import TechnicalNarrativeOutput
        from utils.technical_records import build_technical_records, merge_technical

        result = {"technical_analysis": [tech_entry("AAA"), tech_entry("CCC")]}
        records, failed = build_technical_records(result)
        narrative = TechnicalNarrativeOutput.model_validate(tech_payload(
            tech_narrative_entry("CCC"), tech_narrative_entry("AAA"), tech_narrative_entry("ZZZ")))
        with caplog.at_level("INFO"):
            out = merge_technical("Technology", ["CCC", "AAA"], records, narrative, failed)
        assert [a.ticker for a in out.technical_analysis] == ["CCC", "AAA"]
        assert "ZZZ" in caplog.text


# ─── market_analysis (plan 02-16) ──────────────────────────────────────────────

MARKET_PHASE = "market_analysis"
REDDIT_TOOL = "analyze_sector_reddit_sentiment"
SERPER_TOOL = "Search the internet with Serper"

REDDIT_OK = {
    "sector": "Technology",
    "candidate_stocks": [
        {"ticker": "AAA", "mention_count": 12, "average_sentiment": 0.31, "relevance_score": 1.0,
         "sample_posts": ["AAA beats estimates", "Why AAA is a buy"]},
        {"ticker": "BBB", "mention_count": 7, "average_sentiment": -0.12, "relevance_score": 0.92,
         "sample_posts": ["BBB guidance cut"]},
    ],
    "raw_post_count": 80,
    "subreddits_searched": ["stocks"],
    "fallback_required": False,
}
REDDIT_FALLBACK = {
    "sector": "Technology", "candidate_stocks": [], "raw_post_count": 0,
    "subreddits_searched": [], "fallback_required": True,
    "error": "All Reddit public endpoint requests failed. Serper fallback required.",
}


def _organic(*texts):
    return {"organic": [
        {"title": f"Headline {i}", "link": f"https://news{i}.example.com/a/b?q=1", "snippet": text, "position": i}
        for i, text in enumerate(texts, 1)
    ]}


SERPER_OK = _organic(
    "AAA surges while BBB lags", "AAA and AAA again lead the rally",
    "Analysts like AAA this week", "Nothing about tickers here",
)


class RaisingTool(StubTool):
    """A StubTool whose call raises ``output`` (an exception instance), recording the thread first."""

    def _run(self, **kwargs):
        self.idents.append(threading.get_ident())
        self.calls.append(kwargs)
        raise self.output


def market_tools(reddit=REDDIT_OK, serper=SERPER_OK):
    maker = lambda name, out: (RaisingTool if isinstance(out, Exception) else StubTool)(name, out)  # noqa: E731
    return {REDDIT_TOOL: maker(REDDIT_TOOL, reddit), SERPER_TOOL: maker(SERPER_TOOL, serper)}


def mkt_entry(ticker, **extra):
    entry = {"ticker": ticker, "rationale": f"{ticker} is widely discussed this week, with a clear catalyst. " * 2}
    entry.update(extra)
    return entry


def mkt_payload(*entries, **extra):
    payload = {"candidates": list(entries), "summary": "m" * 120}
    payload.update(extra)
    return payload


def run_market(flow, *results):
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=list(results))
        asyncio.run(flow.market_analysis())
    return mc.return_value.akickoff


def _by_ticker(output):
    return {c.ticker: c for c in output.candidate_stocks}


def test_market_llm_numbers_overwritten(flow, caplog):
    """D-15: hostile numbers, flags and timestamp in the market answer never reach the output."""
    from datetime import datetime

    tools = market_tools()
    wire_tools(flow, tools, phase=MARKET_PHASE)
    hostile = {
        "mention_count": 999, "average_sentiment": 0.99, "relevance_score": 1.0,
        "data_source": "reddit", "sentiment_available": False,
        "analysis_timestamp": "1999-01-01T00:00:00",
    }
    payload = mkt_payload(mkt_entry("AAA", **hostile), mkt_entry("ZZZ", **hostile), **hostile)
    with caplog.at_level("WARNING"):
        run_market(flow, narrative_result(payload))

    out = flow.state.market_output
    assert isinstance(out, MarketAnalysisOutput)
    stocks = _by_ticker(out)
    assert list(stocks) == ["AAA"]
    aaa = stocks["AAA"]
    assert (aaa.mention_count, aaa.average_sentiment, aaa.relevance_score) == (12, 0.31, 1.0)
    assert out.sentiment_available is True
    assert isinstance(out.analysis_timestamp, datetime) and out.analysis_timestamp.year >= 2026
    assert out.analysis_timestamp.tzinfo is not None
    assert "ZZZ" in caplog.text and "market_analysis" in caplog.text
    # Reddit answered, so Serper was never called.
    assert tools[SERPER_TOOL].calls == []
    assert tools[REDDIT_TOOL].calls == [{"sector": "Technology"}]


def test_serper_path_counts(flow):
    tools = market_tools(reddit=REDDIT_FALLBACK, serper=SERPER_OK)
    wire_tools(flow, tools, phase=MARKET_PHASE)
    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB"))))

    out = flow.state.market_output
    stocks = _by_ticker(out)
    assert (stocks["AAA"].mention_count, stocks["BBB"].mention_count) == (4, 1)
    assert (stocks["AAA"].relevance_score, stocks["BBB"].relevance_score) == (1.0, 0.25)
    # Option A (operator decision, plan 02-16 task 1): no sentiment on the Serper path.
    assert all(c.average_sentiment is None for c in out.candidate_stocks)
    assert out.sentiment_available is False
    assert tools[SERPER_TOOL].calls == [
        {"search_query": "Technology sector stocks investors discussing 2026-04-29"}
    ]


def test_serper_counts_are_counts_of_the_symbol_in_titles_and_snippets(flow):
    """AAA appears in 3 snippets (4 times); BBB once: relevance is count over the largest count."""
    serper = _organic("AAA up", "AAA down, AAA flat", "AAA and BBB", "other")
    wire_tools(flow, market_tools(reddit=REDDIT_FALLBACK, serper=serper), phase=MARKET_PHASE)
    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB"))))
    stocks = _by_ticker(flow.state.market_output)
    assert (stocks["AAA"].mention_count, stocks["BBB"].mention_count) == (4, 1)
    assert stocks["BBB"].relevance_score == 0.25
    serper = _organic("AAA up", "AAA flat", "AAA and BBB again", "BBB too is up", "CCC")
    wire_tools(flow, market_tools(reddit=REDDIT_FALLBACK, serper=serper), phase=MARKET_PHASE)
    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB"))))
    stocks = _by_ticker(flow.state.market_output)
    assert (stocks["AAA"].mention_count, stocks["BBB"].mention_count) == (3, 2)
    assert (stocks["AAA"].relevance_score, stocks["BBB"].relevance_score) == (1.0, 0.67)


def test_serper_one_to_three_example_gives_one_and_a_third(flow):
    serper = _organic("AAA one", "AAA two", "AAA three and BBB")
    wire_tools(flow, market_tools(reddit=REDDIT_FALLBACK, serper=serper), phase=MARKET_PHASE)
    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB"))))
    stocks = _by_ticker(flow.state.market_output)
    assert (stocks["AAA"].mention_count, stocks["BBB"].mention_count) == (3, 1)
    assert (stocks["AAA"].relevance_score, stocks["BBB"].relevance_score) == (1.0, 0.33)


@pytest.mark.parametrize("serper", [
    __import__("requests").exceptions.ConnectionError("net down"),
    {"organic": []},
    {},
    None,
])
def test_both_sources_down(flow, serper, caplog):
    wire_tools(flow, market_tools(reddit=REDDIT_FALLBACK, serper=serper), phase=MARKET_PHASE)
    with caplog.at_level("WARNING"):
        run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB"))))
    out = flow.state.market_output
    assert [c.ticker for c in out.candidate_stocks] == ["AAA", "BBB"]
    for c in out.candidate_stocks:
        assert c.mention_count is None and c.relevance_score is None and c.average_sentiment is None
    assert out.sentiment_available is False
    if isinstance(serper, Exception):
        assert "ConnectionError" in caplog.text and "net down" not in caplog.text


def test_reddit_tool_exception_falls_back_to_serper(flow, caplog):
    tools = market_tools(reddit=RuntimeError("secret detail"), serper=SERPER_OK)
    wire_tools(flow, tools, phase=MARKET_PHASE)
    with caplog.at_level("WARNING"):
        run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"))))
    assert len(tools[SERPER_TOOL].calls) == 1
    assert _by_ticker(flow.state.market_output)["AAA"].mention_count == 4
    assert "RuntimeError" in caplog.text and "secret detail" not in caplog.text


def test_no_valid_pick_is_retried(flow):
    wire_tools(flow, market_tools(), phase=MARKET_PHASE)
    only_unlisted = narrative_result(mkt_payload(mkt_entry("ZZZ"), mkt_entry("YYY")))
    valid = narrative_result(mkt_payload(mkt_entry("BBB")))
    kickoff = run_market(flow, only_unlisted, valid)
    assert kickoff.await_count == 2
    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == ["BBB"]


def test_require_market_picks_names_candidates():
    from schemas.agent_outputs import MarketNarrativeOutput
    from utils.market_records import build_market_corpus, require_market_picks

    corpus = build_market_corpus(REDDIT_OK, None, "Technology")
    bad = MarketNarrativeOutput.model_validate(mkt_payload(mkt_entry("ZZZ")))
    with pytest.raises(PhaseOutputError) as info:
        require_market_picks(bad, corpus)
    assert info.value.fields == ["candidates"]
    assert "market_analysis" in str(info.value) and "candidates" in str(info.value)
    require_market_picks(MarketNarrativeOutput.model_validate(mkt_payload(mkt_entry("aaa"))), corpus)
    # Only the Reddit path restricts the picks.
    serper_corpus = build_market_corpus(REDDIT_FALLBACK, SERPER_OK, "Technology")
    require_market_picks(bad, serper_corpus)
    require_market_picks(bad, build_market_corpus(REDDIT_FALLBACK, None, "Technology"))


def test_market_tools_off_loop_and_timed(flow):
    tools = market_tools(reddit=REDDIT_FALLBACK, serper=SERPER_OK)
    wire_tools(flow, tools, instrument=True, phase=MARKET_PHASE)
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    loop_thread = threading.get_ident()
    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"))))
    for tool in tools.values():
        assert len(tool.idents) == 1 and tool.idents[0] != loop_thread
    calls = flow._tracker.to_dict()["tool_calls"]
    assert [(c["phase"], c["tool"]) for c in calls] == [(MARKET_PHASE, REDDIT_TOOL), (MARKET_PHASE, SERPER_TOOL)]
    assert flow._tracker.tool_call_count(MARKET_PHASE) == 2


def test_market_emits_steps_start_and_one_task_complete(flow):
    events, steps = [], []
    flow._progress_callback = events.append
    flow._step_callback = lambda idx, step: steps.append((idx, step.tool, step.log))
    wire_tools(flow, market_tools(reddit=REDDIT_FALLBACK, serper=SERPER_OK), phase=MARKET_PHASE)
    run_market(flow, narrative_result(mkt_payload(mkt_entry("AAA"))))
    assert [s[:2] for s in steps] == [(0, REDDIT_TOOL), (0, SERPER_TOOL)]
    assert steps[0][2] == "Reading Reddit discussion for Technology"
    kinds = [e["event"] for e in events]
    assert kinds.count("agent_start") == 1 and kinds.count("task_complete") == 1
    assert kinds.index("agent_start") < kinds.index("task_complete")


def test_market_agent_has_no_tools(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "dummy-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "dummy-secret")
    from prospect_ai_crew import TaskFactory
    from schemas.agent_outputs import MarketNarrativeOutput

    factory = TaskFactory()
    task = factory.build_task(MARKET_PHASE, "Technology", "2026-04-29", "=== ctx ===")
    assert list(task.tools or []) == []
    assert task.output_pydantic is MarketNarrativeOutput
    assert factory._phase_config[MARKET_PHASE]["agent_tools"] == []
    for name in (REDDIT_TOOL, SERPER_TOOL):
        assert factory.flow_tool(MARKET_PHASE, name).name == name


# ─── Serper-path sentiment seam (operator decision A, plug-in for SEED-261030-nun) ──

class TestSerperSentimentSeam:
    def test_returns_none_for_every_ticker_today(self):
        from utils.market_records import build_market_corpus, serper_sentiment_by_ticker

        corpus = build_market_corpus(REDDIT_FALLBACK, SERPER_OK, "Technology")
        assert corpus["source"] == "serper"
        assert serper_sentiment_by_ticker(corpus, ["AAA", "BBB"]) == {"AAA": None, "BBB": None}
        assert serper_sentiment_by_ticker(corpus, []) == {}

    def test_never_returns_zero_for_unmeasured(self):
        from utils.market_records import build_market_corpus, serper_sentiment_by_ticker

        corpus = build_market_corpus(REDDIT_FALLBACK, SERPER_OK, "Technology")
        assert all(v is None for v in serper_sentiment_by_ticker(corpus, ["AAA"]).values())

    def test_merge_uses_the_seam_so_a_classifier_can_plug_in(self, monkeypatch):
        """A function returning scores flips sentiment_available with no other change."""
        import utils.market_records as mr
        from schemas.agent_outputs import MarketNarrativeOutput

        monkeypatch.setattr(mr, "serper_sentiment_by_ticker", lambda corpus, tickers: {t: 0.4 for t in tickers})
        corpus = mr.build_market_corpus(REDDIT_FALLBACK, SERPER_OK, "Technology")
        narrative = MarketNarrativeOutput.model_validate(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB")))
        from datetime import datetime, timezone

        out = mr.merge_market("Technology", corpus, narrative, datetime.now(timezone.utc))
        assert [c.average_sentiment for c in out.candidate_stocks] == [0.4, 0.4]
        assert out.sentiment_available is True
        assert [c.mention_count for c in out.candidate_stocks] == [4, 1]

    def test_partial_sentiment_is_not_available(self, monkeypatch):
        import utils.market_records as mr
        from schemas.agent_outputs import MarketNarrativeOutput
        from datetime import datetime, timezone

        monkeypatch.setattr(mr, "serper_sentiment_by_ticker", lambda corpus, tickers: {"AAA": 0.4, "BBB": None})
        corpus = mr.build_market_corpus(REDDIT_FALLBACK, SERPER_OK, "Technology")
        narrative = MarketNarrativeOutput.model_validate(mkt_payload(mkt_entry("AAA"), mkt_entry("BBB")))
        out = mr.merge_market("Technology", corpus, narrative, datetime.now(timezone.utc))
        assert out.sentiment_available is False

    def test_no_network_or_classifier_dependency(self):
        import inspect
        import utils.market_records as mr

        source = inspect.getsource(mr.serper_sentiment_by_ticker)
        for forbidden in ("requests", "http", "anthropic", "api_key", "socket"):
            assert forbidden not in source


# ─── market records (plan 02-16) ───────────────────────────────────────────────

class TestSymbolMentionCounts:
    def test_counts_symbol_not_substring(self):
        from utils.market_records import symbol_mention_counts

        counts = symbol_mention_counts(["AAA", "AA"], ["AAA rises", "AAAB is not AAA", "AA, AA and $AA"])
        assert counts == {"AAA": 2, "AA": 3}

    def test_cashtag_and_dotted_ticker(self):
        from utils.market_records import symbol_mention_counts

        counts = symbol_mention_counts(["BRK.B", "NVDA"], ["Buy BRK.B now", "$nvda moons", "BRKXB is not it"])
        assert counts == {"BRK.B": 1, "NVDA": 1}

    def test_bare_lowercase_word_is_not_a_symbol(self):
        """A one-letter ticker must not match the article 'a' (deviation from the Reddit regex)."""
        from utils.market_records import symbol_mention_counts

        assert symbol_mention_counts(["A"], ["a stock a day", "Shares of A rose", "$a too"]) == {"A": 2}

    def test_no_snippets_gives_zero_counts(self):
        from utils.market_records import symbol_mention_counts

        assert symbol_mention_counts(["AAA"], []) == {"AAA": 0}


class TestBuildMarketCorpus:
    def test_reddit_source(self):
        from utils.market_records import build_market_corpus

        corpus = build_market_corpus(REDDIT_OK, SERPER_OK, "Technology")
        assert corpus["source"] == "reddit"
        assert [c["ticker"] for c in corpus["candidates"]] == ["AAA", "BBB"]

    def test_serper_source_keeps_title_snippet_and_link_host_only(self):
        from utils.market_records import build_market_corpus

        corpus = build_market_corpus(REDDIT_FALLBACK, SERPER_OK, "Technology")
        assert corpus["source"] == "serper"
        first = corpus["snippets"][0]
        assert first == {"text": "Headline 1 AAA surges while BBB lags", "host": "news1.example.com"}
        assert "https://" not in json.dumps(corpus)

    def test_unavailable_source_carries_the_static_universe_when_known(self):
        from utils.market_records import build_market_corpus

        known = build_market_corpus(REDDIT_FALLBACK, None, "Semiconductors")
        assert known["source"] == "unavailable" and "NVDA" in known["universe"]
        unknown = build_market_corpus(REDDIT_FALLBACK, None, "Financials")
        assert unknown["source"] == "unavailable" and unknown["universe"] == []

    @pytest.mark.parametrize("serper", [None, {}, {"organic": []}, {"organic": [{"title": "", "snippet": ""}]},
                                        {"organic": "oops"}, "text"])
    def test_unusable_serper_is_unavailable(self, serper):
        from utils.market_records import build_market_corpus

        assert build_market_corpus(REDDIT_FALLBACK, serper, "Technology")["source"] == "unavailable"

    def test_snippets_are_capped(self):
        from utils.market_records import build_market_corpus

        serper = _organic(*(["x" * 5000] * 50))
        corpus = build_market_corpus(REDDIT_FALLBACK, serper, "Technology")
        assert len(corpus["snippets"]) <= 10
        assert all(len(s["text"]) <= 500 for s in corpus["snippets"])

    def test_reddit_flagged_fallback_is_not_used_even_with_candidates(self):
        from utils.market_records import build_market_corpus

        flagged = dict(REDDIT_OK, fallback_required=True)
        assert build_market_corpus(flagged, None, "Technology")["source"] == "unavailable"


class TestMergeMarket:
    def _merge(self, picks, reddit=REDDIT_OK, serper=None):
        from datetime import datetime, timezone

        from schemas.agent_outputs import MarketNarrativeOutput
        from utils.market_records import build_market_corpus, merge_market

        corpus = build_market_corpus(reddit, serper, "Technology")
        narrative = MarketNarrativeOutput.model_validate(mkt_payload(*[mkt_entry(t) for t in picks]))
        return merge_market("Technology", corpus, narrative, datetime(2026, 4, 29, tzinfo=timezone.utc))

    def test_timestamp_is_the_one_passed_by_the_flow(self):
        out = self._merge(["AAA"])
        assert out.analysis_timestamp.isoformat() == "2026-04-29T00:00:00+00:00"

    def test_order_follows_the_llm_picks_and_duplicates_collapse(self):
        out = self._merge(["bbb", "AAA", "BBB"])
        assert [c.ticker for c in out.candidate_stocks] == ["BBB", "AAA"]

    def test_bad_reddit_numbers_become_null_never_clamped_or_zeroed(self):
        bad = {**REDDIT_OK, "candidate_stocks": [
            {"ticker": "AAA", "mention_count": -3, "average_sentiment": 7.0, "relevance_score": "high",
             "sample_posts": []},
        ]}
        out = self._merge(["AAA"], reddit=bad)
        c = out.candidate_stocks[0]
        assert (c.mention_count, c.average_sentiment, c.relevance_score) == (None, None, None)
        assert out.sentiment_available is False

    def test_all_picks_with_zero_mentions_have_null_relevance(self):
        serper = _organic("nothing relevant", "still nothing")
        out = self._merge(["AAA"], reddit=REDDIT_FALLBACK, serper=serper)
        c = out.candidate_stocks[0]
        assert c.mention_count == 0 and c.relevance_score is None

    def test_nothing_valid_left_raises(self):
        with pytest.raises(PhaseOutputError):
            self._merge(["ZZZ"])


# ─── market schema (plan 02-16) ────────────────────────────────────────────────

class TestMarketSchema:
    def test_narrative_model_has_no_number_field(self):
        from schemas.agent_outputs import MarketCandidateNarrative, MarketNarrativeOutput

        assert set(MarketCandidateNarrative.model_fields) == {"ticker", "rationale"}
        assert set(MarketNarrativeOutput.model_fields) == {"candidates", "summary"}

    def test_narrative_caps_picks_at_five(self):
        from pydantic import ValidationError
        from schemas.agent_outputs import MarketNarrativeOutput

        six = mkt_payload(*[mkt_entry(t) for t in ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")])
        with pytest.raises(ValidationError):
            MarketNarrativeOutput.model_validate(six)
        MarketNarrativeOutput.model_validate(mkt_payload(*[mkt_entry(t) for t in ("AAA", "BBB", "CCC", "DDD", "EEE")]))

    def test_candidate_counts_are_optional_but_bounded(self):
        from pydantic import ValidationError

        c = CandidateStock(ticker="AAA", mention_count=None, average_sentiment=None, relevance_score=None,
                           rationale="r" * 60)
        assert c.mention_count is None and c.relevance_score is None
        for bad in ({"mention_count": -1}, {"relevance_score": 1.5}):
            with pytest.raises(ValidationError):
                CandidateStock(ticker="AAA", rationale="r" * 60, **bad)


# ─── draft_strategy (plan 02-17) ───────────────────────────────────────────────

DRAFT_PHASE = "draft_strategy"
COMPOSITE_TOOL = "compute_composite_scores"
ALLOCATOR_TOOL = "allocate_portfolio"
DRAFT_TAIL = " Action set to MONITOR by policy: "


class RecordingTool(StubTool):
    """Wraps a real deterministic tool: records the calling thread and kwargs, returns its real output."""

    def __init__(self, real):
        super().__init__(real.name, None)
        self.real = real

    def _run(self, **kwargs):
        self.idents.append(threading.get_ident())
        self.calls.append(kwargs)
        return self.real._run(**kwargs)


def draft_tools(composite=None, allocator=None):
    """The two real deterministic tools the Flow calls itself in the draft phase."""
    from utils.composite_score_tool import CompositeScoreTool
    from utils.portfolio_allocator_tool import PortfolioAllocatorTool

    return {
        COMPOSITE_TOOL: composite or RecordingTool(CompositeScoreTool()),
        ALLOCATOR_TOOL: allocator or RecordingTool(PortfolioAllocatorTool()),
    }


def draft_entry(ticker, action="MONITOR", **extra):
    entry = {
        "ticker": ticker,
        "action": action,
        "rationale": f"{ticker} rationale written by the model, citing RSI and momentum. " * 2,
        "monitoring_triggers": [f"{ticker} RSI above 75"],
        "review_frequency": "WEEKLY",
    }
    entry.update(extra)
    return entry


def draft_payload(*entries, **extra):
    payload = {"positions": list(entries), "overall_strategy": "o" * 120}
    payload.update(extra)
    return payload


def run_draft(flow, *results):
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=list(results))
        asyncio.run(flow.draft_strategy())
    return mc.return_value.akickoff


def prime_draft(flow, *, sentiment=True, zones=None, fund_json=FETCH_JSON, grades_json=GRADES_JSON,
                risk_profile="conservative", market_tickers=("AAA", "BBB"), tech_entries=None):
    """Fill market, technical and fundamental state from the real record builders.

    AAA: price 99, momentum 7.1, risk High, quality High and growth Moderate Growth (AVAILABLE).
    BBB: price 50, momentum 5.0, risk Medium, fundamentals failed (UNKNOWN) unless overridden.
    """
    from schemas.agent_outputs import TechnicalNarrativeOutput
    from utils.technical_records import build_technical_records, merge_technical

    zones = {"AAA": "CURRENT_ENTRY", "BBB": "PULLBACK_ENTRY", **(zones or {})}
    entries = tech_entries if tech_entries is not None else [
        tech_entry("AAA", price=99.0, entry_zone_status=zones["AAA"], momentum_score=7.1, risk_level="High"),
        tech_entry("BBB", price=50.0, entry_zone_low=48.0, entry_zone_high=52.0,
                   entry_zone_status=zones["BBB"], momentum_score=5.0, risk_level="Medium"),
    ]
    tickers = [e["ticker"] for e in entries]
    records, failed = build_technical_records({"technical_analysis": entries}, tickers)
    flow.state.technical_output = merge_technical(
        "Technology", tickers, records,
        TechnicalNarrativeOutput.model_validate(tech_payload(*[tech_narrative_entry(t) for t in tickers])),
        failed,
    )
    frecords = build_fundamental_records(fund_json, grades_json)
    flow.state.fundamental_output = merge_fundamental(
        "Technology", tickers, frecords,
        FundamentalNarrativeOutput.model_validate(narrative_payload(*[narrative_entry(t) for t in tickers])),
    )
    if sentiment:
        flow.state.market_output = market_output(*market_tickers)
    else:
        flow.state.market_output = MarketAnalysisOutput(
            sector="Technology",
            candidate_stocks=[CandidateStock(ticker=t, mention_count=None, average_sentiment=None,
                                             relevance_score=None, rationale="r" * 60) for t in market_tickers],
            summary="s" * 120, sentiment_available=False,
        )
    flow.state.risk_profile = risk_profile
    return draft_tools()


def _positions(output):
    return {p.ticker: p for p in output.positions}


def test_draft_llm_numbers_overwritten(flow):
    """D-15: a hostile answer cannot set a score, allocation, setup, total or the risk level."""
    from schemas.agent_outputs import InvestorStrategicOutput
    from utils.composite_score_tool import CompositeScoreTool

    tools = prime_draft(flow)
    wire_tools(flow, tools, phase=DRAFT_PHASE)
    hostile = {
        "composite_score": 99.0, "allocation_pct": 50.0, "current_price": 1.0,
        "fundamentals_status": "AVAILABLE",
        "trade_setup": {"direction": "LONG-BUY", "entry_zone_low": 1.0, "entry_zone_high": 2.0,
                        "stop_loss": 0.5, "take_profit": 9.0},
    }
    payload = draft_payload(
        draft_entry("AAA", "LONG-BUY", **hostile),
        draft_entry("BBB", "MONITOR", **hostile),
        deployed_pct=80.0, reserved_pct=10.0, cash_reserve_pct=10.0, total_allocated_pct=90.0, risk_level="Low",
    )
    run_draft(flow, narrative_result(payload))

    out = flow.state.draft_output
    assert isinstance(out, InvestorStrategicOutput)
    assert [p.ticker for p in out.positions] == ["AAA", "BBB"]
    by = _positions(out)
    # Composite scores are the tool's: AAA 18.0 + 28.4 + 27 = 73.4, BBB 18.0 + 20.0 (fundamentals unknown) = 38.0.
    expected = json.loads(CompositeScoreTool()._run(json.dumps([
        {"ticker": "AAA", "average_sentiment": 0.2, "momentum_score": 7.1, "quality": "High", "growth": "Moderate Growth"},
        {"ticker": "BBB", "average_sentiment": 0.2, "momentum_score": 5.0, "quality": "UNKNOWN", "growth": "UNKNOWN"},
    ])))["scores"]
    assert (by["AAA"].composite_score, by["BBB"].composite_score) == (73.4, 38.0)
    assert [e["composite_score"] for e in expected] == [73.4, 38.0]
    # Allocation and setup are the allocator's: AAA is the only deployed position, capped at 15 percent.
    assert by["AAA"].allocation_pct == 15.0 and by["BBB"].allocation_pct == 0.0
    setup = by["AAA"].trade_setup
    assert setup is not None and (setup.entry_zone_low, setup.entry_zone_high) == (99.0, 99.0)
    assert setup.stop_loss == 96.03
    assert by["BBB"].trade_setup is None
    assert (out.deployed_pct, out.reserved_pct, out.cash_reserve_pct, out.total_allocated_pct) == (15.0, 0.0, 85.0, 15.0)
    # Prices and fundamentals_status come from the technical and fundamental records.
    assert (by["AAA"].current_price, by["BBB"].current_price) == (99.0, 50.0)
    assert (by["AAA"].fundamentals_status, by["BBB"].fundamentals_status) == ("AVAILABLE", "UNKNOWN")
    # The risk level is rule-derived: one deployed position whose technical risk is High (3.0 > 2.6).
    assert out.risk_level == "Very High"
    # What the LLM does own.
    assert by["AAA"].action == "LONG-BUY" and by["BBB"].action == "MONITOR"
    assert by["AAA"].review_frequency == "WEEKLY"
    assert by["AAA"].monitoring_triggers == ["AAA RSI above 75"]
    assert "AAA rationale written by the model" in by["AAA"].rationale
    assert out.overall_strategy == "o" * 120
    assert out.sector == "Technology" and out.risk_profile == "conservative"
    assert flow.state.policy_clamps == []
    assert flow.state.composite_scores["AAA"]["composite_score"] == 73.4


def test_draft_composite_called_before_the_llm_and_allocator_after(flow):
    tools = prime_draft(flow)
    wire_tools(flow, tools, phase=DRAFT_PHASE)
    order = []
    for name, tool in tools.items():
        real = tool._run
        tool._run = (lambda n, r: (lambda **kw: (order.append(n), r(**kw))[1]))(name, real)
    with patch.object(flow, "_make_crew") as mc:
        async def answer():
            order.append("llm")
            return narrative_result(draft_payload(draft_entry("AAA", "LONG-BUY"), draft_entry("BBB")))
        mc.return_value.akickoff = answer
        asyncio.run(flow.draft_strategy())
    assert order == [COMPOSITE_TOOL, "llm", ALLOCATOR_TOOL]


def test_clamp_unknown_fundamentals(flow):
    """D-08: LONG-BUY on a ticker whose quality is UNKNOWN becomes MONITOR, visibly."""
    wire_tools(flow, prime_draft(flow), phase=DRAFT_PHASE)
    run_draft(flow, narrative_result(draft_payload(draft_entry("AAA", "LONG-BUY"), draft_entry("BBB", "LONG-BUY"))))

    by = _positions(flow.state.draft_output)
    assert by["BBB"].action == "MONITOR"
    assert by["BBB"].allocation_pct == 0.0 and by["BBB"].trade_setup is None
    assert by["BBB"].rationale.endswith(".") and DRAFT_TAIL in by["BBB"].rationale
    assert "FUNDAMENTALS_UNKNOWN" in by["BBB"].rationale.split(DRAFT_TAIL)[1]
    assert by["AAA"].action == "LONG-BUY" and DRAFT_TAIL not in by["AAA"].rationale
    [clamp] = flow.state.policy_clamps
    assert clamp["ticker"] == "BBB" and clamp["from_action"] == "LONG-BUY" and clamp["to_action"] == "MONITOR"
    assert "FUNDAMENTALS_UNKNOWN" in clamp["rule"]


def test_clamp_wait_at_current_entry(flow):
    """Failure B class: WAIT-FOR-ENTRY at CURRENT_ENTRY becomes MONITOR before it can reach the validator."""
    wire_tools(flow, prime_draft(flow), phase=DRAFT_PHASE)
    run_draft(flow, narrative_result(draft_payload(draft_entry("AAA", "WAIT-FOR-ENTRY"), draft_entry("BBB"))))

    aaa = _positions(flow.state.draft_output)["AAA"]
    assert aaa.action == "MONITOR" and aaa.allocation_pct == 0.0 and aaa.trade_setup is None
    [clamp] = flow.state.policy_clamps
    assert clamp["ticker"] == "AAA" and clamp["from_action"] == "WAIT-FOR-ENTRY"
    assert "CURRENT_ENTRY" in clamp["rule"]
    assert "CURRENT_ENTRY" in aaa.rationale.split(DRAFT_TAIL)[1]


def test_allowed_action_untouched(flow):
    wire_tools(flow, prime_draft(flow), phase=DRAFT_PHASE)
    aaa_entry, bbb_entry = draft_entry("AAA", "LONG-BUY"), draft_entry("BBB", "AVOID")
    run_draft(flow, narrative_result(draft_payload(aaa_entry, bbb_entry)))
    by = _positions(flow.state.draft_output)
    assert (by["AAA"].action, by["BBB"].action) == ("LONG-BUY", "AVOID")
    assert by["AAA"].rationale == aaa_entry["rationale"] and by["BBB"].rationale == bbb_entry["rationale"]
    assert flow.state.policy_clamps == []


def test_aggressive_profile_reaches_the_allocator_and_the_clamp(flow):
    tools = prime_draft(flow, risk_profile="aggressive", zones={"BBB": "PULLBACK_ENTRY"},
                        grades_json=json.dumps({"grades": [
                            {"ticker": "AAA", "valuation": "FAIR", "quality": "High", "growth": "Moderate Growth",
                             "data_status": "ok"},
                            {"ticker": "BBB", "valuation": "FAIR", "quality": "Medium", "growth": "Stable",
                             "data_status": "ok"},
                        ]}), fund_json=json.dumps({"fundamentals": [FETCH_AAA, dict(FETCH_AAA, ticker="BBB")]}))
    wire_tools(flow, tools, phase=DRAFT_PHASE)
    run_draft(flow, narrative_result(draft_payload(draft_entry("AAA", "LONG-BUY"), draft_entry("BBB", "WAIT-FOR-ENTRY"))))
    sent = json.loads(tools[ALLOCATOR_TOOL].calls[0]["stocks_json"])
    assert sent["risk_profile"] == "aggressive"
    by = _positions(flow.state.draft_output)
    assert by["BBB"].action == "WAIT-FOR-ENTRY"            # PULLBACK_ENTRY, fundamentals known: eligible
    assert by["AAA"].allocation_pct > 15.0 and by["BBB"].allocation_pct > 0.0   # aggressive cap is 30
    assert flow.state.draft_output.reserved_pct == by["BBB"].allocation_pct


def test_serper_path_composite_renormalises_over_technical_and_fundamental(flow):
    """02-16 decision A: sentiment null and sentiment_available false on every candidate."""
    tools = prime_draft(flow, sentiment=False)
    wire_tools(flow, tools, phase=DRAFT_PHASE)
    run_draft(flow, narrative_result(draft_payload(draft_entry("AAA", "LONG-BUY"), draft_entry("BBB"))))

    sent = json.loads(tools[COMPOSITE_TOOL].calls[0]["stocks_json"])
    assert [s["average_sentiment"] for s in sent] == [None, None]
    by = _positions(flow.state.draft_output)
    # AAA: (28.4 + 27) * 100 / 70 = 79.1; BBB (fundamentals unknown): 20.0 * 100 / 40 = 50.0. Never 0 or 15 for sentiment.
    assert (by["AAA"].composite_score, by["BBB"].composite_score) == (79.1, 50.0)
    scores = flow.state.composite_scores
    assert scores["AAA"]["sentiment_unavailable"] is True and scores["AAA"]["sentiment_component"] is None
    prompt_context = flow._factory.build_task.call_args.args[3]
    assert '"sentiment": "no data"' in prompt_context


def test_partial_sentiment_is_not_mixed_into_the_scores(flow):
    """sentiment_available false: no ticker gets a sentiment term, so scores stay comparable."""
    from utils.strategy_assembly import composite_inputs

    prime_draft(flow, sentiment=False)
    flow.state.market_output.candidate_stocks[0].average_sentiment = 0.9
    inputs = composite_inputs(flow.state.market_output, flow.state.technical_output, flow.state.fundamental_output)
    assert [i["average_sentiment"] for i in inputs] == [None, None]


def test_context_shows_scores_eligible_actions_and_excluded_tickers(flow):
    prime_draft(flow, market_tickers=("AAA", "BBB", "CCC"))   # CCC failed technically: not in the technical output
    wire_tools(flow, draft_tools(), phase=DRAFT_PHASE)
    run_draft(flow, narrative_result(draft_payload(draft_entry("AAA", "LONG-BUY"), draft_entry("BBB"))))
    ctx = flow._factory.build_task.call_args.args[3]
    section = ctx.split("=== Scores and eligible actions (computed by the pipeline) ===")[1]
    data = json.loads(section.strip().split("\n\n=== ")[0])
    rows = {r["ticker"]: r for r in data["tickers"]}
    assert rows["AAA"]["composite_score"] == 73.4
    assert rows["AAA"]["eligible_actions"] == ["LONG-BUY", "MONITOR", "AVOID"]          # CURRENT_ENTRY: no WAIT-FOR-ENTRY
    assert rows["BBB"]["eligible_actions"] == ["MONITOR", "AVOID"]                       # fundamentals UNKNOWN
    assert rows["AAA"]["sentiment"] == 0.2
    assert [e["ticker"] for e in data["excluded"]] == ["CCC"]
    assert flow._factory.build_task.call_args.kwargs["risk_profile"] == "conservative"


def test_position_coverage_missing_and_duplicate_tickers_are_named():
    from schemas.agent_outputs import StrategyNarrativeOutput
    from utils.strategy_assembly import require_position_coverage

    missing = StrategyNarrativeOutput.model_validate(draft_payload(draft_entry("AAA")))
    with pytest.raises(PhaseOutputError) as info:
        require_position_coverage(missing, ["AAA", "BBB"])
    assert info.value.fields == ["positions[BBB]"] and "BBB" in str(info.value) and "draft_strategy" in str(info.value)
    twice = StrategyNarrativeOutput.model_validate(draft_payload(draft_entry("AAA"), draft_entry("aaa"), draft_entry("BBB")))
    with pytest.raises(PhaseOutputError) as info:
        require_position_coverage(twice, ["AAA", "BBB"])
    assert info.value.fields == ["positions[AAA]"] and "AAA" in str(info.value)
    ok = StrategyNarrativeOutput.model_validate(draft_payload(draft_entry("aaa"), draft_entry("BBB"), draft_entry("ZZZ")))
    require_position_coverage(ok, ["AAA", "BBB"])      # an extra ticker is not an error here


def test_missing_position_is_retried_and_exhausts_the_budget(flow):
    wire_tools(flow, prime_draft(flow), phase=DRAFT_PHASE)
    short = narrative_result(draft_payload(draft_entry("AAA")))
    full = narrative_result(draft_payload(draft_entry("AAA"), draft_entry("BBB")))
    kickoff = run_draft(flow, short, full)
    assert kickoff.await_count == 2
    assert [p.ticker for p in flow.state.draft_output.positions] == ["AAA", "BBB"]
    assert "positions[BBB]" in flow._factory.build_task.call_args_list[1].kwargs["feedback"]

    wire_tools(flow, prime_draft(flow), phase=DRAFT_PHASE)
    with pytest.raises(PhaseSchemaError) as info:
        run_draft(flow, short, short, short)
    assert info.value.phase == DRAFT_PHASE and "positions[BBB]" in str(info.value)


def test_narrative_for_an_unknown_ticker_is_ignored(flow, caplog):
    wire_tools(flow, prime_draft(flow), phase=DRAFT_PHASE)
    with caplog.at_level("INFO"):
        run_draft(flow, narrative_result(draft_payload(draft_entry("AAA"), draft_entry("BBB"), draft_entry("ZZZ", "LONG-BUY"))))
    assert [p.ticker for p in flow.state.draft_output.positions] == ["AAA", "BBB"]
    assert "ZZZ" in caplog.text


def test_composite_tool_error_raises_naming_the_phase(flow):
    tools = prime_draft(flow)
    tools[COMPOSITE_TOOL] = StubTool(COMPOSITE_TOOL, json.dumps({"error": "missing momentum_score for AAA"}))
    wire_tools(flow, tools, phase=DRAFT_PHASE)
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock()
        with pytest.raises(RuntimeError, match="draft_strategy") as info:
            asyncio.run(flow.draft_strategy())
    assert "missing momentum_score" in str(info.value)
    mc.return_value.akickoff.assert_not_awaited()


def test_composite_missing_a_ticker_raises(flow):
    tools = prime_draft(flow)
    only_aaa = json.dumps({"scores": [{"ticker": "AAA", "composite_score": 70.0, "sentiment_component": None,
                                       "technical_component": 28.0, "fundamental_component": 27,
                                       "sentiment_unavailable": True, "fundamental_unknown": False}]})
    tools[COMPOSITE_TOOL] = StubTool(COMPOSITE_TOOL, only_aaa)
    wire_tools(flow, tools, phase=DRAFT_PHASE)
    with pytest.raises(RuntimeError, match="BBB"):
        run_draft(flow, narrative_result(draft_payload(draft_entry("AAA"), draft_entry("BBB"))))


def test_allocator_error_raises_bounds_violation(flow):
    from utils.portfolio_bounds_validator import BoundsViolationError

    tools = prime_draft(flow)
    tools[ALLOCATOR_TOOL] = StubTool(ALLOCATOR_TOOL, json.dumps({"error": "Computation error: boom"}))
    wire_tools(flow, tools, phase=DRAFT_PHASE)
    with pytest.raises(BoundsViolationError):
        run_draft(flow, narrative_result(draft_payload(draft_entry("AAA"), draft_entry("BBB"))))
    assert flow.state.draft_output is None


def test_no_technical_data_fails_clearly(flow):
    wire_tools(flow, draft_tools(), phase=DRAFT_PHASE)
    flow.state.technical_output = None
    with pytest.raises(RuntimeError, match="draft_strategy"):
        asyncio.run(flow.draft_strategy())


def test_draft_tools_off_loop_and_timed(flow):
    tools = prime_draft(flow)
    wire_tools(flow, tools, instrument=True, phase=DRAFT_PHASE)
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    loop_thread = threading.get_ident()
    run_draft(flow, narrative_result(draft_payload(draft_entry("AAA"), draft_entry("BBB"))))
    for tool in tools.values():
        assert len(tool.idents) == 1 and tool.idents[0] != loop_thread
    calls = flow._tracker.to_dict()["tool_calls"]
    assert [(c["phase"], c["tool"]) for c in calls] == [(DRAFT_PHASE, COMPOSITE_TOOL), (DRAFT_PHASE, ALLOCATOR_TOOL)]


def test_draft_agent_has_no_tools_and_the_flow_holds_both(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "dummy-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "dummy-secret")
    from prospect_ai_crew import TaskFactory
    from schemas.agent_outputs import StrategyNarrativeOutput

    factory = TaskFactory()
    task = factory.build_task(DRAFT_PHASE, "Technology", "2026-04-29", "=== ctx ===")
    assert list(task.tools or []) == []
    assert task.output_pydantic is StrategyNarrativeOutput
    assert factory._phase_config[DRAFT_PHASE]["agent_tools"] == []
    for name in (COMPOSITE_TOOL, ALLOCATOR_TOOL):
        assert factory.flow_tool(DRAFT_PHASE, name).name == name


def test_run_analysis_adds_one_warning_per_clamp(flow):
    clamps = [
        {"ticker": "BBB", "from_action": "LONG-BUY", "to_action": "MONITOR", "rule": "FUNDAMENTALS_UNKNOWN row",
         "message": "BBB: draft action LONG-BUY set to MONITOR by policy: FUNDAMENTALS_UNKNOWN row"},
    ]

    def kickoff(inputs=None):
        flow.state.final_output = MagicMock(model_dump=lambda mode=None: {"positions": [], "overall_strategy": "x"})
        flow.state.policy_clamps = clamps

    flow.kickoff = kickoff
    with patch.object(flow, "_finalize_and_validate_portfolio", side_effect=lambda s, p: s):
        out = flow.run_analysis({"sector": "Technology"})
    warnings = [w for w in out["validation_warnings"] if w["field"] == "action"]
    assert warnings == [{"severity": "warning", "ticker": "BBB", "field": "action", "message": clamps[0]["message"]}]
    assert warnings[0] in out["result"]["validation_warnings"]


class TestStrategyAssemblyUnits:
    @staticmethod
    def _pos(ticker, action, rationale="x" * 60):
        from schemas.agent_outputs import PositionNarrative

        return PositionNarrative(ticker=ticker, action=action, rationale=rationale,
                                 monitoring_triggers=["t"], review_frequency="WEEKLY")

    def test_clamp_changes_only_ineligible_actions(self):
        from utils.strategy_assembly import clamp_actions

        positions = [self._pos("AAA", "LONG-BUY"), self._pos("BBB", "LONG-BUY")]
        eligible = {"AAA": frozenset({"LONG-BUY", "MONITOR", "AVOID"}), "BBB": frozenset({"MONITOR", "AVOID"})}
        context = {"AAA": {"entry_zone_status": "CURRENT_ENTRY", "risk_profile": "conservative", "fundamentals_status": "AVAILABLE"},
                   "BBB": {"entry_zone_status": "CURRENT_ENTRY", "risk_profile": "conservative", "fundamentals_status": "UNKNOWN"}}
        out, clamps = clamp_actions(positions, eligible, context)
        assert [p.action for p in out] == ["LONG-BUY", "MONITOR"]
        assert out[0] is positions[0] and positions[1].action == "LONG-BUY"     # inputs are not mutated
        assert out[1].rationale == "x" * 60 + " Action set to MONITOR by policy: " + clamps[0]["rule"] + "."
        assert [c["ticker"] for c in clamps] == ["BBB"]

    def test_both_rules_are_named_when_both_apply(self):
        from utils.strategy_assembly import policy_rule

        rule = policy_rule("WAIT-FOR-ENTRY", "CURRENT_ENTRY", "conservative", "UNKNOWN")
        assert "CURRENT_ENTRY" in rule and "FUNDAMENTALS_UNKNOWN" in rule

    def test_a_ticker_without_an_eligible_set_is_left_alone(self):
        from utils.strategy_assembly import clamp_actions

        out, clamps = clamp_actions([self._pos("AAA", "LONG-BUY")], {}, {})
        assert out[0].action == "LONG-BUY" and clamps == []

    def test_eligible_by_ticker_reads_the_policy_table(self):
        from utils.strategy_assembly import eligible_by_ticker

        prime = SimpleNamespace(state=SimpleNamespace())
        prime_draft(prime)
        got = eligible_by_ticker(prime.state.technical_output, {"AAA": "AVAILABLE", "BBB": "UNKNOWN"}, "conservative")
        assert got == {"AAA": frozenset({"LONG-BUY", "MONITOR", "AVOID"}), "BBB": frozenset({"MONITOR", "AVOID"})}
        # A missing fundamentals_status is permissive, as in the Critic gate.
        assert "WAIT-FOR-ENTRY" in eligible_by_ticker(prime.state.technical_output, {}, "conservative")["BBB"]


def _risk_position(ticker, action, pct):
    return SimpleNamespace(ticker=ticker, action=action, allocation_pct=pct)


def _risk_technical(**levels):
    return {t: SimpleNamespace(momentum_analysis=SimpleNamespace(risk_level=level)) for t, level in levels.items()}


@pytest.mark.parametrize("positions,levels,expected", [
    # No deployed capital at all: Low.
    ([_risk_position("A", "MONITOR", 0.0), _risk_position("B", "AVOID", 0.0)], dict(A="High", B="High"), "Low"),
    ([_risk_position("A", "LONG-BUY", 0.0)], dict(A="High"), "Low"),
    # Weighted mean 1.5 -> Low (inclusive).
    ([_risk_position("A", "LONG-BUY", 10.0), _risk_position("B", "LONG-BUY", 10.0)], dict(A="Low", B="Medium"), "Low"),
    # 2.0 -> Medium (inclusive); a WAIT-FOR-ENTRY position counts.
    ([_risk_position("A", "LONG-BUY", 10.0), _risk_position("B", "WAIT-FOR-ENTRY", 10.0)], dict(A="Medium", B="Medium"), "Medium"),
    ([_risk_position("A", "LONG-BUY", 12.0), _risk_position("B", "LONG-BUY", 8.0)], dict(A="Low", B="High"), "Medium"),   # 1.8
    # 2.5 -> High; exactly 2.6 -> High (inclusive).
    ([_risk_position("A", "LONG-BUY", 10.0), _risk_position("B", "LONG-BUY", 10.0)], dict(A="Medium", B="High"), "High"),
    ([_risk_position("A", "LONG-BUY", 40.0), _risk_position("B", "LONG-BUY", 60.0)], dict(A="Medium", B="High"), "High"),
    # Above 2.6 -> Very High.
    ([_risk_position("A", "LONG-BUY", 39.0), _risk_position("B", "LONG-BUY", 61.0)], dict(A="Medium", B="High"), "Very High"),
    ([_risk_position("A", "LONG-BUY", 15.0)], dict(A="High"), "Very High"),
    # MONITOR / AVOID never weigh in, whatever their risk.
    ([_risk_position("A", "LONG-BUY", 15.0), _risk_position("B", "AVOID", 0.0)], dict(A="Low", B="High"), "Low"),
])
def test_risk_level_rule(positions, levels, expected):
    from utils.strategy_assembly import derive_portfolio_risk_level

    assert derive_portfolio_risk_level(positions, _risk_technical(**levels)) == expected


def test_risk_level_needs_a_technical_record_for_a_deployed_position():
    from utils.strategy_assembly import derive_portfolio_risk_level

    with pytest.raises(ValueError, match="A"):
        derive_portfolio_risk_level([_risk_position("A", "LONG-BUY", 10.0)], {})


class TestStrictVocabulary:
    @pytest.mark.parametrize("field,value", [
        ("action", "long-buy"), ("action", "Long-Buy"), ("action", "LONG BUY"), ("action", " MONITOR"),
        ("review_frequency", "weekly"), ("review_frequency", "Weekly"), ("review_frequency", "WEEKLY "),
    ])
    def test_position_narrative_rejects_case_and_space_variants(self, field, value):
        from pydantic import ValidationError
        from schemas.agent_outputs import PositionNarrative

        entry = draft_entry("AAA")
        entry[field] = value
        with pytest.raises(ValidationError):
            PositionNarrative.model_validate(entry)

    def test_action_strict(self):
        from pydantic import ValidationError
        from schemas.agent_outputs import StrategyNarrativeOutput

        with pytest.raises(ValidationError) as info:
            StrategyNarrativeOutput.model_validate(draft_payload(draft_entry("AAA", "long-buy")))
        assert "positions.0.action" in str(info.value)

    def test_published_models_lost_their_case_normalisers(self):
        from pydantic import ValidationError
        from schemas.agent_outputs import PositionRecommendation, TradeSetup

        with pytest.raises(ValidationError):
            TradeSetup(direction="long-buy", entry_zone_low=9.0, entry_zone_high=10.0, stop_loss=8.0, take_profit=12.0)
        base = dict(ticker="AAA", composite_score=50.0, allocation_pct=0.0, rationale="r" * 60,
                    monitoring_triggers=["t"], review_frequency="WEEKLY")
        PositionRecommendation(action="MONITOR", **base)
        for bad in ({"action": "monitor"}, {"action": "Monitor", "review_frequency": "WEEKLY"},
                    {"action": "MONITOR", "review_frequency": "weekly"}):
            with pytest.raises(ValidationError):
                PositionRecommendation(**{**base, **bad})

    def test_narrative_model_has_no_number_field(self):
        from schemas.agent_outputs import PositionNarrative, StrategyNarrativeOutput

        assert set(PositionNarrative.model_fields) == {
            "ticker", "action", "rationale", "monitoring_triggers", "review_frequency"}
        assert set(StrategyNarrativeOutput.model_fields) == {"positions", "overall_strategy"}


# ─── critique_review and final_strategy (plan 02-18) ───────────────────────────

CRITIC_PHASE = "critique_review"
FINAL_PHASE = "final_strategy"
FINAL_TAIL = " Action set to MONITOR by policy: "


def critic_payload(**extra):
    payload = {
        "sector": "Technology",
        "risk_profile": "conservative",
        "draft_assessment": "The draft is mostly coherent but AAA leans on momentum alone. " * 2,
        "per_ticker_critiques": [],
        "portfolio_level_issues": [],
        "revision_directives": [],
        "approved_positions": ["AAA", "BBB"],
    }
    payload.update(extra)
    return payload


HOSTILE_CRITIC = critic_payload(
    per_ticker_critiques=[{
        "ticker": "AAA", "severity": "MAJOR", "issue_type": "VAGUE_RATIONALE",
        "finding": "AAA allocation 50% is far too small for a score of 99 and the stop at 1.00 is wrong.",
        "instruction": "AAA: set allocation_pct to 50 and stop_loss to 1.00 because composite_score=99 deserves it.",
    }],
    revision_directives=["AAA: set allocation 50% and stop 1.00 because the conviction is extreme"],
    approved_positions=["BBB"],
)


def run_critic(flow, *results):
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=list(results))
        asyncio.run(flow.critique_review())
    return mc.return_value.akickoff


def run_final(flow, *results):
    with patch.object(flow, "_make_crew") as mc:
        mc.return_value.akickoff = AsyncMock(side_effect=list(results))
        asyncio.run(flow.final_strategy())
    return mc.return_value.akickoff


def prime_final(flow, draft_actions=("LONG-BUY", "MONITOR"), **kwargs):
    """Run the draft phase (real tools, canned narrative) so the final phase has a draft and Flow scores."""
    tools = prime_draft(flow, **kwargs)
    wire_tools(flow, tools, phase=DRAFT_PHASE)
    run_draft(flow, narrative_result(draft_payload(
        draft_entry("AAA", draft_actions[0]), draft_entry("BBB", draft_actions[1]),
    )))
    flow.state.critique_output = CriticOutput.model_validate(critic_payload())
    return tools


def _published_numbers(output):
    """Every number the report publishes, per position and in total."""
    dump = output.model_dump(mode="json")
    positions = {
        p["ticker"]: (p["composite_score"], p["allocation_pct"], p["current_price"], p["trade_setup"],
                      p["fundamentals_status"])
        for p in dump["positions"]
    }
    totals = {k: dump[k] for k in ("deployed_pct", "reserved_pct", "total_allocated_pct", "cash_reserve_pct", "risk_level")}
    return positions, totals


def test_final_llm_numbers_overwritten(flow):
    """D-15: the final answer cannot set a score, allocation, setup, total, grade or the risk level."""
    from schemas.agent_outputs import InvestorStrategicOutput

    tools = prime_final(flow)
    hostile = {
        "composite_score": 99.0, "allocation_pct": 40.0, "current_price": 1.0, "fundamentals_status": "AVAILABLE",
        "trade_setup": {"direction": "LONG-BUY", "entry_zone_low": 1.0, "entry_zone_high": 2.0,
                        "stop_loss": 0.5, "take_profit": 9.0},
    }
    payload = draft_payload(
        draft_entry("AAA", "LONG-BUY", **hostile), draft_entry("BBB", "MONITOR", **hostile),
        deployed_pct=80.0, reserved_pct=10.0, cash_reserve_pct=10.0, total_allocated_pct=90.0, risk_level="Low",
        sector="Hostile", risk_profile="aggressive",
    )
    run_final(flow, narrative_result(payload))

    out = flow.state.final_output
    assert isinstance(out, InvestorStrategicOutput)
    by = _positions(out)
    assert (by["AAA"].composite_score, by["BBB"].composite_score) == (73.4, 38.0)      # the Flow's own scores
    assert (by["AAA"].allocation_pct, by["BBB"].allocation_pct) == (15.0, 0.0)          # the allocator's
    setup = by["AAA"].trade_setup
    assert setup is not None and setup.stop_loss == 96.03 and (setup.entry_zone_low, setup.entry_zone_high) == (99.0, 99.0)
    assert by["BBB"].trade_setup is None
    assert (by["AAA"].current_price, by["BBB"].current_price) == (99.0, 50.0)
    assert (by["AAA"].fundamentals_status, by["BBB"].fundamentals_status) == ("AVAILABLE", "UNKNOWN")
    assert (out.deployed_pct, out.reserved_pct, out.cash_reserve_pct, out.total_allocated_pct) == (15.0, 0.0, 85.0, 15.0)
    assert out.risk_level == "Very High"                                                  # rule-derived, not "Low"
    assert out.sector == "Technology" and out.risk_profile == "conservative"
    assert by["AAA"].action == "LONG-BUY" and "AAA rationale written by the model" in by["AAA"].rationale
    assert out.overall_strategy == "o" * 120
    # What publishes survives the Flow's own final repricing and the bounds validator unchanged.
    final = flow._finalize_and_validate_portfolio(out.model_dump(mode="json"), "conservative")
    assert final["positions"][0]["composite_score"] == 73.4 and final["positions"][0]["allocation_pct"] == 15.0
    assert tools[ALLOCATOR_TOOL].calls and len(tools[ALLOCATOR_TOOL].calls) == 2          # draft call + final call


def test_final_actions_are_the_ones_allocated(flow):
    """The allocator runs on the FINAL actions, not on the draft's."""
    tools = prime_final(flow)
    assert _positions(flow.state.draft_output)["AAA"].allocation_pct == 15.0
    run_final(flow, narrative_result(draft_payload(draft_entry("AAA", "MONITOR"), draft_entry("BBB", "AVOID"))))
    sent = json.loads(tools[ALLOCATOR_TOOL].calls[-1]["stocks_json"])
    assert [(s["ticker"], s["action"]) for s in sent["stocks"]] == [("AAA", "MONITOR"), ("BBB", "AVOID")]
    out = flow.state.final_output
    by = _positions(out)
    assert by["AAA"].allocation_pct == 0.0 and out.deployed_pct == 0.0 and out.risk_level == "Low"
    assert flow.state.draft_output.positions[0].action == "LONG-BUY"                       # the draft is untouched


def test_final_clamp(flow):
    """D-08: LONG-BUY on UNKNOWN fundamentals publishes MONITOR with a warning, never a BoundsViolationError."""
    prime_final(flow)
    run_final(flow, narrative_result(draft_payload(draft_entry("AAA", "LONG-BUY"), draft_entry("BBB", "LONG-BUY"))))
    by = _positions(flow.state.final_output)
    assert by["BBB"].action == "MONITOR" and by["BBB"].allocation_pct == 0.0
    assert FINAL_TAIL in by["BBB"].rationale and "FUNDAMENTALS_UNKNOWN" in by["BBB"].rationale.split(FINAL_TAIL)[1]
    assert by["AAA"].action == "LONG-BUY" and FINAL_TAIL not in by["AAA"].rationale
    [clamp] = flow.state.policy_clamps
    assert clamp["ticker"] == "BBB" and clamp["phase"] == FINAL_PHASE and clamp["to_action"] == "MONITOR"
    assert clamp["message"].startswith("BBB: final action LONG-BUY set to MONITOR by policy")

    # Through run_analysis: the warning reaches the result, and the bounds validator has nothing to reject.
    def kickoff(inputs=None):
        pass

    flow.kickoff = kickoff
    out = flow.run_analysis({"sector": "Technology"})
    assert [p["action"] for p in out["result"]["positions"]] == ["LONG-BUY", "MONITOR"]
    warned = [w for w in out["validation_warnings"] if w["field"] == "action"]
    assert [w["ticker"] for w in warned] == ["BBB"] and "final action LONG-BUY" in warned[0]["message"]


def test_final_clamp_appends_to_the_draft_clamps_and_warnings_name_the_published_action(flow):
    """A draft clamp then a different final action: each warning says which phase and what finally published."""
    prime_final(flow, draft_actions=("LONG-BUY", "LONG-BUY"))          # draft clamps BBB LONG-BUY -> MONITOR
    assert [c["phase"] for c in flow.state.policy_clamps] == [DRAFT_PHASE]
    run_final(flow, narrative_result(draft_payload(draft_entry("AAA", "WAIT-FOR-ENTRY"), draft_entry("BBB", "AVOID"))))
    # AAA WAIT-FOR-ENTRY at CURRENT_ENTRY is clamped again; BBB was changed by the draft clamp only.
    assert [(c["ticker"], c["phase"]) for c in flow.state.policy_clamps] == [("BBB", DRAFT_PHASE), ("AAA", FINAL_PHASE)]

    flow.kickoff = lambda inputs=None: None
    out = flow.run_analysis({"sector": "Technology"})
    published = {p["ticker"]: p["action"] for p in out["result"]["positions"]}
    assert published == {"AAA": "MONITOR", "BBB": "AVOID"}
    warned = {(w["ticker"]): w["message"] for w in out["validation_warnings"] if w["field"] == "action"}
    assert len(warned) == 2
    assert "draft action LONG-BUY set to MONITOR" in warned["BBB"] and "published action is AVOID" in warned["BBB"]
    assert "final action WAIT-FOR-ENTRY set to MONITOR" in warned["AAA"] and "published action" not in warned["AAA"]


def test_final_context_shows_the_draft_the_critic_and_the_eligible_actions(flow):
    prime_final(flow)
    run_final(flow, narrative_result(draft_payload(draft_entry("AAA", "LONG-BUY"), draft_entry("BBB"))))
    ctx = flow._factory.build_task.call_args.args[3]
    for heading in ("=== Draft Strategy Output ===", "=== Critic Review Output ===",
                    "=== Scores and eligible actions (computed by the pipeline) ==="):
        assert heading in ctx
    section = ctx.split("=== Scores and eligible actions (computed by the pipeline) ===")[1]
    rows = {r["ticker"]: r for r in json.loads(section.strip().split("\n\n=== ")[0])["tickers"]}
    assert rows["AAA"]["eligible_actions"] == ["LONG-BUY", "MONITOR", "AVOID"]
    assert rows["BBB"]["eligible_actions"] == ["MONITOR", "AVOID"]
    assert flow._factory.build_task.call_args.kwargs["risk_profile"] == "conservative"


def test_final_missing_position_is_retried_and_named(flow):
    prime_final(flow)
    short = narrative_result(draft_payload(draft_entry("AAA")))
    full = narrative_result(draft_payload(draft_entry("AAA"), draft_entry("BBB")))
    assert run_final(flow, short, full).await_count == 2
    assert "positions[BBB]" in flow._factory.build_task.call_args_list[-1].kwargs["feedback"]
    assert "final_strategy" in flow._factory.build_task.call_args_list[-1].kwargs["feedback"]
    with pytest.raises(PhaseSchemaError) as info:
        run_final(flow, short, short, short)
    assert info.value.phase == FINAL_PHASE and "positions[BBB]" in str(info.value)


def test_final_without_flow_scores_fails_closed(flow):
    from utils.portfolio_bounds_validator import BoundsViolationError

    prime_final(flow)
    flow.state.composite_scores = {}
    with pytest.raises(BoundsViolationError) as info:
        run_final(flow, narrative_result(draft_payload(draft_entry("AAA"), draft_entry("BBB"))))
    assert info.value.violations[0]["rule"] == "composite_score_missing"
    assert flow.state.final_output is None


def test_final_without_a_draft_fails_clearly(flow):
    prime_final(flow)
    flow.state.draft_output = None
    with pytest.raises(RuntimeError, match="final_strategy"):
        run_final(flow, narrative_result(draft_payload(draft_entry("AAA"), draft_entry("BBB"))))


def test_final_allocator_error_raises_bounds_violation(flow):
    from utils.portfolio_bounds_validator import BoundsViolationError

    tools = prime_final(flow)
    tools[ALLOCATOR_TOOL] = StubTool(ALLOCATOR_TOOL, json.dumps({"error": "Computation error: boom"}))
    wire_tools(flow, tools, phase=FINAL_PHASE)
    with pytest.raises(BoundsViolationError):
        run_final(flow, narrative_result(draft_payload(draft_entry("AAA"), draft_entry("BBB"))))
    assert flow.state.final_output is None


def test_final_emits_the_contract_sequence_and_times_the_allocator(flow):
    events, steps = [], []
    flow._progress_callback = events.append
    flow._step_callback = lambda idx, step: steps.append(idx)
    tools = prime_final(flow)
    wire_tools(flow, tools, instrument=True, phase=FINAL_PHASE)
    flow._tracker = ExecutionTracker()
    flow._tracker.start()
    events.clear()
    steps.clear()
    loop_thread = threading.get_ident()
    run_final(flow, narrative_result(draft_payload(draft_entry("AAA", "LONG-BUY"), draft_entry("BBB"))))
    assert [(e["event"], e["task_index"]) for e in events] == [("agent_start", 5), ("task_complete", 5)]
    assert steps == [5]                                               # one synthetic step: the allocation
    assert tools[ALLOCATOR_TOOL].idents[-1] != loop_thread
    assert flow._tracker.to_dict()["tool_calls"][-1]["phase"] == FINAL_PHASE


def test_final_agent_has_no_tools_and_the_flow_holds_the_allocator(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "dummy-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "dummy-secret")
    from prospect_ai_crew import TaskFactory
    from schemas.agent_outputs import StrategyNarrativeOutput

    factory = TaskFactory()
    task = factory.build_task(FINAL_PHASE, "Technology", "2026-04-29", "=== ctx ===")
    assert list(task.tools or []) == []
    assert task.output_pydantic is StrategyNarrativeOutput
    assert factory._phase_config[FINAL_PHASE]["agent_tools"] == []
    assert factory.flow_tool(FINAL_PHASE, ALLOCATOR_TOOL).name == ALLOCATOR_TOOL
    critic = factory.build_task(CRITIC_PHASE, "Technology", "2026-04-29", "=== ctx ===")
    assert list(critic.tools or []) == [] and factory._phase_config[CRITIC_PHASE]["flow_tools"] == {}


# ── critique_review: compliant by design (RESEARCH F10 row 5, D-14), pinned by D-15 ──

def test_critic_cannot_change_numbers(flow):
    """D-15: a Critic demanding allocation 50% and stop 1.00 changes nothing the report publishes."""
    from schemas.agent_outputs import CriticOutput

    final_answer = narrative_result(draft_payload(draft_entry("AAA", "LONG-BUY"), draft_entry("BBB", "MONITOR")))

    prime_final(flow)
    run_critic(flow, narrative_result(critic_payload()))
    assert isinstance(flow.state.critique_output, CriticOutput)
    run_final(flow, final_answer)
    control = _published_numbers(flow.state.final_output)

    prime_final(flow)
    run_critic(flow, narrative_result(HOSTILE_CRITIC))
    assert "allocation 50%" in flow.state.critique_output.revision_directives[0]
    run_final(flow, final_answer)
    hostile = _published_numbers(flow.state.final_output)

    assert hostile == control
    positions, totals = hostile
    assert positions["AAA"][1] == 15.0 and positions["AAA"][3]["stop_loss"] == 96.03       # the allocator's, not 50 / 1.00
    assert positions["AAA"][0] == 73.4
    assert totals["deployed_pct"] == 15.0


def test_critic_directive_for_an_ineligible_action_is_dropped_before_the_final_phase(flow):
    prime_final(flow)
    ctx_critic = critic_payload(
        revision_directives=["BBB: change action from MONITOR to LONG-BUY because the fundamentals look fine to me"],
    )
    run_critic(flow, narrative_result(ctx_critic))
    gated = json.loads(flow._gated_slim_critique())
    assert gated["revision_directives"] == []              # BBB is UNKNOWN: LONG-BUY is outside its eligible actions


def test_critic_reference_table_is_flow_built(flow):
    """The Critic's reference table is the technical and fundamental records, with the schema's labels."""
    prime_draft(flow)
    rows = {r["ticker"]: r for r in json.loads(flow._critic_reference_table())["reference_table"]}
    to, fo = flow.state.technical_output, flow.state.fundamental_output
    for a in to.technical_analysis:
        row = rows[a.ticker]
        assert row["rsi"] == a.raw_indicators.rsi
        assert row["stochastic_status"] == a.raw_indicators.stochastic_status
        assert row["macd_status"] == a.raw_indicators.macd_status
        assert row["entry_zone_status"] == a.momentum_analysis.entry_zone_status
        assert row["momentum_score"] == a.momentum_analysis.momentum_score
    for a in fo.fundamental_analysis:
        row, rating = rows[a.ticker], a.fundamental_rating
        assert (row["valuation"], row["quality"]) == (rating.valuation, rating.quality)
    assert rows["AAA"]["fundamentals_status"] == "AVAILABLE" and rows["BBB"]["fundamentals_status"] == "UNKNOWN"
    assert rows["AAA"]["average_sentiment"] == 0.2


# ── D-11 end state: no enum field has a case or whitespace normaliser ──────────

def test_severity_strict():
    from pydantic import ValidationError
    from schemas.agent_outputs import CritiqueItem

    base = {"ticker": "AAA", "issue_type": "VAGUE_RATIONALE", "finding": "f" * 40, "instruction": "i" * 40}
    CritiqueItem.model_validate({**base, "severity": "MAJOR"})
    for bad in ("major", "Major", " MAJOR", "MAJOR ", "SEVERE"):
        with pytest.raises(ValidationError):
            CritiqueItem.model_validate({**base, "severity": bad})
    with pytest.raises(ValidationError) as info:
        CriticOutput.model_validate(critic_payload(per_ticker_critiques=[{**base, "severity": "major"}]))
    assert "per_ticker_critiques.0.severity" in str(info.value)


def _momentum(**over):
    from schemas.agent_outputs import MomentumAnalysis, SupportResistance

    base = dict(
        momentum_score=7.0, risk_level="Medium", trend_strength="Strong", key_signals=["RSI neutral", "MACD up"],
        support_resistance=SupportResistance(support=48.0, resistance=52.0), comprehensive_analysis="C" * 60,
        entry_zone_status="PULLBACK_ENTRY", entry_zone_low=48.0, entry_zone_high=52.0, regime="REVERTING",
    )
    base.update(over)
    return MomentumAnalysis(**base)


@pytest.mark.parametrize("variant", ["lower", "padded"])
def test_d11_end_state_no_enum_normalisers(variant):
    """D-11: a lower-case or space-padded value fails each of the five fields that used to be normalised."""
    from pydantic import ValidationError
    from schemas.agent_outputs import CritiqueItem, PositionRecommendation, TradeSetup

    def bad(value):
        return value.lower() if variant == "lower" else f" {value} "

    _momentum()                                                      # the valid form constructs
    with pytest.raises(ValidationError):
        _momentum(risk_level=bad("Medium"))
    setup = dict(entry_zone_low=9.0, entry_zone_high=10.0, stop_loss=8.0, take_profit=12.0)
    TradeSetup(direction="LONG-BUY", **setup)
    with pytest.raises(ValidationError):
        TradeSetup(direction=bad("LONG-BUY"), **setup)
    pos = dict(ticker="AAA", composite_score=50.0, allocation_pct=0.0, rationale="r" * 60,
               monitoring_triggers=["t"], action="MONITOR", review_frequency="WEEKLY")
    PositionRecommendation(**pos)
    for field, value in (("action", "MONITOR"), ("review_frequency", "WEEKLY")):
        with pytest.raises(ValidationError):
            PositionRecommendation(**{**pos, field: bad(value)})
    crit = {"ticker": "AAA", "issue_type": "VAGUE_RATIONALE", "finding": "f" * 40, "instruction": "i" * 40}
    CritiqueItem(severity="MINOR", **crit)
    with pytest.raises(ValidationError):
        CritiqueItem(severity=bad("MINOR"), **crit)


def test_no_enum_field_carries_a_field_validator():
    """Structural form of D-11: no Literal field of any published or LLM-facing model has a field validator."""
    import typing

    from pydantic import BaseModel
    from schemas import agent_outputs

    def is_literal(annotation):
        if typing.get_origin(annotation) is typing.Literal:
            return True
        return any(is_literal(a) for a in typing.get_args(annotation))

    offenders = []
    for name, cls in vars(agent_outputs).items():
        if not (isinstance(cls, type) and issubclass(cls, BaseModel)) or cls.__module__ != agent_outputs.__name__:
            continue
        for decorator in cls.__pydantic_decorators__.field_validators.values():
            for field in decorator.info.fields:
                if field in cls.model_fields and is_literal(cls.model_fields[field].annotation):
                    offenders.append(f"{name}.{field}")
    assert offenders == []


def test_every_phase_has_a_d15_test():
    """ROADMAP SC7: one hostile-answer test per phase lives in this module."""
    import sys

    module = sys.modules[__name__]
    for name in ("test_market_llm_numbers_overwritten", "test_technical_llm_numbers_and_labels_overwritten",
                 "test_fundamental_llm_numbers_and_grades_overwritten", "test_draft_llm_numbers_overwritten",
                 "test_critic_cannot_change_numbers", "test_final_llm_numbers_overwritten"):
        assert callable(getattr(module, name)), name


class TestClampWarnings:
    def test_a_warning_names_the_published_action_only_when_it_differs(self):
        from utils.strategy_assembly import clamp_warnings

        clamps = [
            {"ticker": "AAA", "to_action": "MONITOR", "message": "AAA: final action LONG-BUY set to MONITOR by policy: r"},
            {"ticker": "BBB", "to_action": "MONITOR", "message": "BBB: draft action LONG-BUY set to MONITOR by policy: r"},
            {"ticker": "CCC", "to_action": "MONITOR", "message": "CCC: draft action LONG-BUY set to MONITOR by policy: r"},
        ]
        got = clamp_warnings(clamps, {"AAA": "MONITOR", "BBB": "AVOID"})
        assert [w["severity"] for w in got] == ["warning"] * 3 and [w["field"] for w in got] == ["action"] * 3
        assert got[0]["message"] == clamps[0]["message"]
        assert got[1]["message"] == clamps[1]["message"] + " The published action is AVOID."
        assert got[2]["message"] == clamps[2]["message"]                    # no published position: nothing to add

    def test_clamp_records_carry_their_phase(self):
        from utils.strategy_assembly import clamp_actions

        pos = TestStrategyAssemblyUnits._pos("AAA", "LONG-BUY")
        eligible = {"AAA": frozenset({"MONITOR", "AVOID"})}
        _, draft = clamp_actions([pos], eligible)
        _, final = clamp_actions([pos], eligible, phase="final_strategy")
        assert draft[0]["phase"] == "draft_strategy" and draft[0]["message"].startswith("AAA: draft action LONG-BUY")
        assert final[0]["phase"] == "final_strategy" and final[0]["message"].startswith("AAA: final action LONG-BUY")

    def test_require_position_coverage_names_the_phase(self):
        from schemas.agent_outputs import StrategyNarrativeOutput
        from utils.strategy_assembly import require_position_coverage

        short = StrategyNarrativeOutput.model_validate(draft_payload(draft_entry("AAA")))
        with pytest.raises(PhaseOutputError, match="final_strategy"):
            require_position_coverage(short, ["AAA", "BBB"], phase="final_strategy")
