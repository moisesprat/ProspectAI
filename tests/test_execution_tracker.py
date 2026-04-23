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
