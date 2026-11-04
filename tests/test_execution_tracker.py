"""
Unit tests for utils/execution_tracker.py.
Token usage is injected via mock UsageMetrics objects matching crewai.types.usage_metrics.UsageMetrics.
"""

import time
from unittest.mock import MagicMock

from utils.execution_tracker import ExecutionTracker, PhaseMetrics, _PHASE_ORDER


def _make_usage(prompt_tokens: int, completion_tokens: int, cached: int = 0):
    """Create a mock UsageMetrics object matching CrewAI's interface."""
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.cached_prompt_tokens = cached
    usage.total_tokens = prompt_tokens + completion_tokens
    return usage


class TestPhaseMetrics:

    def test_elapsed_sec_zero_when_not_started(self):
        pm = PhaseMetrics(name="market_analysis")
        assert pm.elapsed_sec == 0.0

    def test_elapsed_sec_positive_after_end(self):
        pm = PhaseMetrics(name="market_analysis", start_time=1000.0, end_time=1005.5)
        assert pm.elapsed_sec == 5.5

    def test_total_tokens_is_sum(self):
        pm = PhaseMetrics(name="market_analysis", input_tokens=300, output_tokens=100)
        assert pm.total_tokens == 400


class TestExecutionTrackerTiming:

    def test_pipeline_elapsed_populated_after_finish(self):
        tracker = ExecutionTracker()
        tracker.start()
        time.sleep(0.01)
        tracker.finish()
        d = tracker.to_dict()
        assert d["pipeline_elapsed_sec"] > 0.0

    def test_phase_elapsed_populated_after_finish_phase(self):
        tracker = ExecutionTracker()
        tracker.start()
        tracker.start_phase("market_analysis")
        time.sleep(0.01)
        tracker.finish_phase("market_analysis", _make_usage(0, 0))
        tracker.finish()
        d = tracker.to_dict()
        phase = next(p for p in d["phases"] if p["name"] == "market_analysis")
        assert phase["elapsed_sec"] > 0.0

    def test_missing_phases_have_zero_elapsed(self):
        tracker = ExecutionTracker()
        tracker.start()
        tracker.finish()
        d = tracker.to_dict()
        for phase in d["phases"]:
            assert phase["elapsed_sec"] == 0.0

    def test_all_six_phases_always_present(self):
        tracker = ExecutionTracker()
        tracker.start()
        tracker.finish()
        d = tracker.to_dict()
        names = [p["name"] for p in d["phases"]]
        assert names == _PHASE_ORDER


class TestExecutionTrackerTokens:

    def test_tokens_attributed_to_phase(self):
        tracker = ExecutionTracker()
        tracker.start()
        tracker.start_phase("market_analysis")
        tracker.finish_phase("market_analysis", _make_usage(100, 50), "anthropic/claude-sonnet-4-6")
        tracker.finish()

        d = tracker.to_dict()
        phase = next(p for p in d["phases"] if p["name"] == "market_analysis")
        assert phase["input_tokens"] == 100
        assert phase["output_tokens"] == 50
        assert phase["total_tokens"] == 150

    def test_tokens_aggregated_in_totals(self):
        tracker = ExecutionTracker()
        tracker.start()
        for phase_name in ["market_analysis", "technical_analysis"]:
            tracker.start_phase(phase_name)
            tracker.finish_phase(phase_name, _make_usage(200, 80), "anthropic/claude-sonnet-4-6")
        tracker.finish()

        d = tracker.to_dict()
        assert d["totals"]["input_tokens"] == 400
        assert d["totals"]["output_tokens"] == 160
        assert d["totals"]["total_tokens"] == 560

    def test_totals_equal_sum_of_phases(self):
        tracker = ExecutionTracker()
        tracker.start()
        for i, name in enumerate(_PHASE_ORDER):
            tracker.start_phase(name)
            tracker.finish_phase(name, _make_usage(100 * (i + 1), 50 * (i + 1)), "anthropic/claude-sonnet-4-6")
        tracker.finish()

        d = tracker.to_dict()
        phase_total = sum(p["total_tokens"] for p in d["phases"])
        assert d["totals"]["total_tokens"] == phase_total

    def test_tokens_split_by_model(self):
        tracker = ExecutionTracker()
        tracker.start()
        tracker.start_phase("market_analysis")
        tracker.finish_phase("market_analysis", _make_usage(100, 40), "anthropic/claude-sonnet-4-6")
        tracker.start_phase("technical_analysis")
        tracker.finish_phase("technical_analysis", _make_usage(200, 60), "anthropic/claude-opus-4-7")
        tracker.finish()

        d = tracker.to_dict()
        assert "anthropic/claude-sonnet-4-6" in d["by_model"]
        assert "anthropic/claude-opus-4-7" in d["by_model"]
        assert d["by_model"]["anthropic/claude-sonnet-4-6"]["input_tokens"] == 100
        assert d["by_model"]["anthropic/claude-opus-4-7"]["input_tokens"] == 200

    def test_zero_tokens_when_usage_is_none(self):
        tracker = ExecutionTracker()
        tracker.start()
        tracker.start_phase("market_analysis")
        tracker.finish_phase("market_analysis", None)
        tracker.finish()

        d = tracker.to_dict()
        phase = next(p for p in d["phases"] if p["name"] == "market_analysis")
        assert phase["total_tokens"] == 0

    def test_cached_tokens_tracked(self):
        tracker = ExecutionTracker()
        tracker.start()
        tracker.start_phase("draft_strategy")
        tracker.finish_phase("draft_strategy", _make_usage(500, 200, cached=300), "anthropic/claude-sonnet-4-6")
        tracker.finish()

        d = tracker.to_dict()
        phase = next(p for p in d["phases"] if p["name"] == "draft_strategy")
        assert phase["cached_tokens"] == 300
        assert d["totals"]["cached_tokens"] == 300


class TestExecutionTrackerMetadata:

    def test_sector_in_output(self):
        tracker = ExecutionTracker()
        tracker.set_sector("Healthcare")
        tracker.start()
        tracker.finish()
        d = tracker.to_dict()
        assert d["sector"] == "Healthcare"

    def test_run_at_is_iso_format(self):
        tracker = ExecutionTracker()
        tracker.start()
        tracker.finish()
        d = tracker.to_dict()
        assert "T" in d["run_at"]
        assert d["run_at"].endswith("Z")

    def test_run_at_empty_before_start(self):
        tracker = ExecutionTracker()
        d = tracker.to_dict()
        assert d["run_at"] == ""


# ─── Tool calls, rollups and interval unions (STALL-01) ───────────────────────

def _tracker_with_pipeline(start: float = 1.0, end: float = 41.0) -> ExecutionTracker:
    tracker = ExecutionTracker()
    tracker._pipeline_start = start
    tracker._pipeline_end = end
    return tracker


def _set_phase(tracker, name, start, end=0.0):
    tracker._phases[name] = PhaseMetrics(name=name, start_time=start, end_time=end)


def _phase(metrics, name):
    return next(p for p in metrics["phases"] if p["name"] == name)


class TestToolCalls:

    def test_record_and_export_fields(self):
        tracker = _tracker_with_pipeline(start=100.0, end=140.0)
        tracker.record_tool_call("market_analysis", "Search", 102.0, 104.5, True, None, 321)
        calls = tracker.to_dict()["tool_calls"]
        assert calls == [{
            "phase": "market_analysis", "tool": "Search", "start_offset_sec": 2.0,
            "elapsed_sec": 2.5, "ok": True, "error": None, "output_chars": 321,
        }]

    def test_calls_sorted_by_start(self):
        tracker = _tracker_with_pipeline(start=1.0, end=50.0)
        tracker.record_tool_call("a", "late", 10.0, 11.0, True)
        tracker.record_tool_call("a", "early", 3.0, 4.0, True)
        assert [c["tool"] for c in tracker.to_dict()["tool_calls"]] == ["early", "late"]

    def test_offset_measured_from_earliest_call_without_pipeline_start(self):
        tracker = ExecutionTracker()
        tracker.record_tool_call("a", "t1", 50.0, 51.0, True)
        tracker.record_tool_call("a", "t2", 52.0, 53.0, True)
        offsets = [c["start_offset_sec"] for c in tracker.to_dict()["tool_calls"]]
        assert offsets == [0.0, 2.0]

    def test_v1_keys_unchanged_and_v2_markers_present(self):
        d = _tracker_with_pipeline().to_dict()
        for key in ("run_at", "sector", "pipeline_elapsed_sec", "phases", "totals", "by_model"):
            assert key in d
        assert d["metrics_version"] == 2
        assert d["partial"] is False
        assert d["tool_calls"] == []
        for p in d["phases"]:
            for key in ("name", "elapsed_sec", "input_tokens", "output_tokens",
                        "cached_tokens", "cache_creation_tokens", "total_tokens"):
                assert key in p

    def test_concurrent_recording_is_thread_safe(self):
        import threading

        tracker = ExecutionTracker()

        def worker():
            for i in range(50):
                tracker.record_tool_call("technical_analysis", "t", float(i), float(i) + 0.1, True)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(tracker.to_dict()["tool_calls"]) == 400


class TestToolUnions:

    def test_overlapping_tool_calls_split_tool_and_llm_time(self):
        tracker = _tracker_with_pipeline()
        _set_phase(tracker, "technical_analysis", 10.0, 14.0)
        tracker.record_tool_call("technical_analysis", "T", 10.0, 12.0, True)
        tracker.record_tool_call("technical_analysis", "T", 11.0, 13.0, True)
        p = _phase(tracker.to_dict(), "technical_analysis")
        assert p["tool_total_sec"] == 4.0
        assert p["tool_wall_sec"] == 3.0
        assert p["llm_overhead_sec"] == 1.0

    def test_overhead_never_negative(self):
        tracker = _tracker_with_pipeline()
        _set_phase(tracker, "technical_analysis", 10.0, 11.0)
        tracker.record_tool_call("technical_analysis", "T", 9.0, 12.0, True)
        p = _phase(tracker.to_dict(), "technical_analysis")
        assert p["llm_overhead_sec"] == 0.0

    def test_overlapping_phases_counted_once(self):
        tracker = _tracker_with_pipeline(start=1.0, end=41.0)
        _set_phase(tracker, "technical_analysis", 10.0, 20.0)
        _set_phase(tracker, "fundamental_analysis", 12.0, 25.0)
        d = tracker.to_dict()
        assert d["phases_union_sec"] == 15.0
        assert d["unattributed_sec"] == 25.0
        assert d["unattributed_sec"] >= 0

    def test_unattributed_never_negative(self):
        tracker = _tracker_with_pipeline(start=1.0, end=5.0)
        _set_phase(tracker, "market_analysis", 1.0, 3.0)
        _set_phase(tracker, "draft_strategy", 3.0, 9.0)
        assert tracker.to_dict()["unattributed_sec"] == 0.0

    def test_no_phases_gives_null_union_and_unattributed(self):
        d = _tracker_with_pipeline().to_dict()
        assert d["phases_union_sec"] is None
        assert d["unattributed_sec"] is None


class TestRollupAndStatus:

    def test_per_tool_rollup_and_sorting(self):
        tracker = _tracker_with_pipeline()
        _set_phase(tracker, "fundamental_analysis", 10.0, 30.0)
        tracker.record_tool_call("fundamental_analysis", "Data", 10.0, 11.0, True, None, 10)
        tracker.record_tool_call("fundamental_analysis", "Data", 12.0, 15.0, False, "TimeoutError", None)
        tracker.record_tool_call("fundamental_analysis", "Data", 16.0, 18.0, True, None, 5)
        tracker.record_tool_call("fundamental_analysis", "Grader", 19.0, 19.5, True, None, 1)
        tools = _phase(tracker.to_dict(), "fundamental_analysis")["tools"]
        assert [t["tool"] for t in tools] == ["Data", "Grader"]
        assert tools[0] == {
            "tool": "Data", "count": 3, "total_sec": 6.0, "max_sec": 3.0,
            "error_count": 1, "output_chars_total": 15,
        }

    def test_status_completed_running_not_started(self):
        tracker = _tracker_with_pipeline()
        _set_phase(tracker, "market_analysis", 2.0, 8.0)
        _set_phase(tracker, "technical_analysis", 8.0, 0.0)
        d = tracker.to_dict()
        assert _phase(d, "market_analysis")["status"] == "completed"
        assert _phase(d, "technical_analysis")["status"] == "running"
        assert _phase(d, "final_strategy")["status"] == "not_started"

    def test_not_started_phase_has_null_splits_and_zero_elapsed(self):
        p = _phase(_tracker_with_pipeline().to_dict(), "critique_review")
        assert p["tool_total_sec"] is None
        assert p["tool_wall_sec"] is None
        assert p["llm_overhead_sec"] is None
        assert p["elapsed_sec"] == 0.0
        assert p["tools"] == []
        assert p["tool_call_count"] == 0

    def test_slowest_phase_and_tool_call(self):
        tracker = _tracker_with_pipeline()
        _set_phase(tracker, "market_analysis", 2.0, 5.0)
        _set_phase(tracker, "technical_analysis", 5.0, 20.0)
        tracker.record_tool_call("market_analysis", "Search", 2.0, 4.0, True)
        tracker.record_tool_call("technical_analysis", "Tech", 6.0, 16.0, False, "ValueError")
        d = tracker.to_dict()
        assert d["slowest_phase"] == {"name": "technical_analysis", "elapsed_sec": 15.0}
        assert d["slowest_tool_call"] == {
            "phase": "technical_analysis", "tool": "Tech", "elapsed_sec": 10.0, "ok": False,
        }

    def test_slowest_fields_none_when_empty(self):
        d = _tracker_with_pipeline().to_dict()
        assert d["slowest_phase"] is None
        assert d["slowest_tool_call"] is None


# ─── Per-phase token deltas (gap review CR-01) ───

class _FakeLLM:
    """Stands in for a crewai LLM: lifetime counters in a real ``_token_usage`` dict."""

    def __init__(self) -> None:
        self._token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "successful_requests": 0,
            "cached_prompt_tokens": 0,
            "cache_creation_tokens": 0,
        }

    def grow(self, prompt: int, completion: int, cached: int = 0, cache_write: int = 0) -> None:
        u = self._token_usage
        u["prompt_tokens"] += prompt
        u["completion_tokens"] += completion
        u["total_tokens"] += prompt + completion
        u["successful_requests"] += 1
        u["cached_prompt_tokens"] += cached
        u["cache_creation_tokens"] += cache_write


def _lifetime_usage(llm: _FakeLLM):
    """What CrewOutput.token_usage holds in production: the LLM's lifetime summary."""
    u = llm._token_usage
    return _make_usage(u["prompt_tokens"], u["completion_tokens"], u["cached_prompt_tokens"])


def _tracked_phase(tracker: ExecutionTracker, name: str) -> dict:
    return next(p for p in tracker.to_dict()["phases"] if p["name"] == name)


class TestPhaseTokenDeltas:

    def test_shared_llm_final_reports_only_its_own_tokens(self):
        model = "anthropic/claude-sonnet-5-5"
        llm = _FakeLLM()
        tracker = ExecutionTracker()
        tracker.start()

        tracker.start_phase("draft_strategy", llm=llm)
        llm.grow(8571, 1485)
        tracker.finish_phase("draft_strategy", _lifetime_usage(llm), model, llm=llm)

        tracker.start_phase("final_strategy", llm=llm)
        llm.grow(15356, 1502)
        tracker.finish_phase("final_strategy", _lifetime_usage(llm), model, llm=llm)
        tracker.finish()

        draft = _tracked_phase(tracker, "draft_strategy")
        final = _tracked_phase(tracker, "final_strategy")
        assert (draft["input_tokens"], draft["output_tokens"]) == (8571, 1485)
        assert (final["input_tokens"], final["output_tokens"]) == (15356, 1502)

        d = tracker.to_dict()
        assert d["totals"]["input_tokens"] == 23927
        assert d["totals"]["output_tokens"] == 2987
        assert d["by_model"][model]["input_tokens"] == 23927
        assert d["by_model"][model]["output_tokens"] == 2987

    def test_retry_attempts_are_counted_once(self):
        llm = _FakeLLM()
        tracker = ExecutionTracker()
        tracker.start()
        tracker.start_phase("market_analysis", llm=llm)
        llm.grow(1000, 100)   # failed attempt
        llm.grow(1200, 120)   # accepted attempt
        tracker.finish_phase("market_analysis", _lifetime_usage(llm), "m", llm=llm)

        phase = _tracked_phase(tracker, "market_analysis")
        assert (phase["input_tokens"], phase["output_tokens"]) == (2200, 220)

    def test_second_finish_adds_only_new_growth(self):
        llm = _FakeLLM()
        tracker = ExecutionTracker()
        tracker.start()
        tracker.start_phase("technical_analysis", llm=llm)
        llm.grow(500, 50)
        tracker.finish_phase("technical_analysis", _lifetime_usage(llm), "m", llm=llm)
        llm.grow(300, 30)
        tracker.finish_phase("technical_analysis", _lifetime_usage(llm), "m", llm=llm)

        phase = _tracked_phase(tracker, "technical_analysis")
        assert (phase["input_tokens"], phase["output_tokens"]) == (800, 80)
        assert tracker.to_dict()["totals"]["input_tokens"] == 800

    def test_cached_and_cache_write_are_deltas(self):
        llm = _FakeLLM()
        llm.grow(9999, 999, cached=400, cache_write=700)   # earlier work on this LLM
        tracker = ExecutionTracker()
        tracker.start()
        tracker.start_phase("final_strategy", llm=llm)
        llm.grow(100, 10, cached=40, cache_write=70)
        tracker.finish_phase("final_strategy", _lifetime_usage(llm), "m", llm=llm)

        phase = _tracked_phase(tracker, "final_strategy")
        assert phase["input_tokens"] == 100
        assert phase["output_tokens"] == 10
        assert phase["cached_tokens"] == 40
        assert phase["cache_creation_tokens"] == 70

    def test_concurrent_phases_on_separate_llms(self):
        tech_llm, fund_llm = _FakeLLM(), _FakeLLM()
        tracker = ExecutionTracker()
        tracker.start()
        tracker.start_phase("technical_analysis", llm=tech_llm)
        tracker.start_phase("fundamental_analysis", llm=fund_llm)
        tech_llm.grow(100, 10)
        fund_llm.grow(700, 70)
        tech_llm.grow(200, 20)
        tracker.finish_phase("technical_analysis", _lifetime_usage(tech_llm), "m", llm=tech_llm)
        fund_llm.grow(50, 5)
        tracker.finish_phase("fundamental_analysis", _lifetime_usage(fund_llm), "m", llm=fund_llm)

        tech = _tracked_phase(tracker, "technical_analysis")
        fund = _tracked_phase(tracker, "fundamental_analysis")
        assert (tech["input_tokens"], tech["output_tokens"]) == (300, 30)
        assert (fund["input_tokens"], fund["output_tokens"]) == (750, 75)

    def test_llm_without_counter_dict_falls_back_to_token_usage(self):
        for llm in (MagicMock(), None):
            tracker = ExecutionTracker()
            tracker.start()
            tracker.start_phase("market_analysis", llm=llm)
            tracker.finish_phase("market_analysis", _make_usage(100, 50), "m", llm=llm)

            phase = _tracked_phase(tracker, "market_analysis")
            assert (phase["input_tokens"], phase["output_tokens"]) == (100, 50)
