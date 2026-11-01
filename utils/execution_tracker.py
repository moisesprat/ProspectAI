import copy
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class PhaseMetrics:
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0           # cache READS (cache_read_input_tokens)
    cache_creation_tokens: int = 0   # cache WRITES (cache_creation_input_tokens)
    cache_creation_snapshot: int = 0  # snapshot of LLM cumulative writes at phase start
    model_token_map: Dict[str, Dict[str, int]] = field(default_factory=dict)
    attempts: int = 0                # schema attempts run_phase needed (0 = not recorded)

    @property
    def elapsed_sec(self) -> float:
        if self.end_time and self.start_time:
            return round(self.end_time - self.start_time, 3)
        return 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ToolCallRecord:
    """One tool invocation. Holds only non-sensitive facts: timing, outcome, size.

    ``error`` is the exception CLASS NAME only and ``output_chars`` is a length;
    messages, arguments and output text are never stored because execution
    metrics are public (SSE, R2 report JSON, SPA).
    """

    phase: str
    tool: str
    start: float
    end: float
    ok: bool
    error: Optional[str] = None
    output_chars: Optional[int] = None

    @property
    def elapsed_sec(self) -> float:
        return round(max(0.0, self.end - self.start), 3)


_PHASE_ORDER = [
    "market_analysis",
    "technical_analysis",
    "fundamental_analysis",
    "draft_strategy",
    "critique_review",
    "final_strategy",
]


def _union_sec(intervals: List[tuple]) -> float:
    """Length covered by the union of (start, end) pairs; overlaps count once.

    Technical and fundamental analysis run concurrently, and crewai may run
    several native tool calls in parallel, so plain sums of durations can
    exceed wall time. Subtracting such a sum from an elapsed time goes
    negative; the union does not.
    """
    spans = sorted((s, e) for s, e in intervals if e > s)
    total = 0.0
    cur_start: Optional[float] = None
    cur_end = 0.0
    for start, end in spans:
        if cur_start is None:
            cur_start, cur_end = start, end
        elif start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            total += cur_end - cur_start
            cur_start, cur_end = start, end
    if cur_start is not None:
        total += cur_end - cur_start
    return total


class ExecutionTracker:
    """Tracks per-phase wall-clock timing and LLM token usage for a single pipeline run.

    Token counts are read directly from CrewOutput.token_usage (a UsageMetrics object)
    after each akickoff() call — no LiteLLM callbacks required.

    Usage:
        tracker = ExecutionTracker()
        tracker.set_sector(sector)
        tracker.start()
        try:
            tracker.start_phase("market_analysis")
            result = await crew.akickoff()
            tracker.finish_phase("market_analysis", result.token_usage, model_id)
            ...
        finally:
            tracker.finish()
        metrics = tracker.to_dict()

    ``market_corpus`` is an additive field of metrics contract v2 (the version number does
    not change): the size-capped record of what the market phase's model saw
    (``utils.market_records.corpus_record``). It appears only after ``set_market_corpus``,
    so a run without a market phase looks exactly as before, and it is part of the partial
    snapshot of a failed run. Like the rest of the metrics it is public (SSE, stored
    report), which is why the record holds link hosts only.
    """

    def __init__(self) -> None:
        self._sector: str = ""
        self._run_at: Optional[datetime] = None
        self._pipeline_start: float = 0.0
        self._pipeline_end: float = 0.0
        self._phases: Dict[str, PhaseMetrics] = {}
        self._model_totals: Dict[str, Dict[str, int]] = {}
        self._tool_calls: List[ToolCallRecord] = []
        self._market_corpus: Optional[Dict[str, Any]] = None
        self._lock = threading.Lock()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._run_at = datetime.now(timezone.utc)
        self._pipeline_start = time.perf_counter()

    def finish(self) -> None:
        self._pipeline_end = time.perf_counter()

    def set_sector(self, sector: str) -> None:
        self._sector = sector

    def set_market_corpus(self, record: Optional[Dict[str, Any]]) -> None:
        """Store the market corpus record (None clears it)."""
        with self._lock:
            self._market_corpus = copy.deepcopy(record) if record is not None else None

    # ── Tool calls ─────────────────────────────────────────────────────────────

    def record_tool_call(
        self,
        phase: str,
        tool: str,
        start: float,
        end: float,
        ok: bool,
        error: Optional[str] = None,
        output_chars: Optional[int] = None,
    ) -> None:
        """Record one tool call. Thread-safe: the wrapper runs in crewai executor threads."""
        record = ToolCallRecord(phase, tool, start, end, ok, error, output_chars)
        with self._lock:
            self._tool_calls.append(record)

    def tool_call_count(self, phase: str) -> int:
        """Number of tool calls recorded for ``phase`` (failed calls count; 0 when none)."""
        with self._lock:
            return sum(1 for c in self._tool_calls if c.phase == phase)

    def record_phase_attempts(self, phase: str, attempts: int) -> None:
        """Store how many schema attempts ``phase`` needed (1 = first-try success, STALL-04)."""
        pm = self._phases.get(phase)
        if pm is None:
            pm = PhaseMetrics(name=phase)
            self._phases[phase] = pm
        pm.attempts = attempts

    def _tool_call_dicts(self) -> List[Dict[str, Any]]:
        with self._lock:
            calls = list(self._tool_calls)
        calls.sort(key=lambda c: c.start)
        if self._pipeline_start:
            origin = self._pipeline_start
        elif calls:
            origin = calls[0].start
        else:
            origin = 0.0
        return [
            {
                "phase": c.phase,
                "tool": c.tool,
                "start_offset_sec": round(c.start - origin, 3),
                "elapsed_sec": c.elapsed_sec,
                "ok": c.ok,
                "error": c.error,
                "output_chars": c.output_chars,
            }
            for c in calls
        ]

    # ── Phase hooks ────────────────────────────────────────────────────────────

    @staticmethod
    def _llm_cache_creation(llm: Any) -> int:
        """Read cumulative cache_creation_tokens counter from an LLM instance.

        AnthropicCachingCompletion stores it in `_token_usage["cache_creation_tokens"]`.
        Returns 0 for vanilla LLMs (Ollama, non-caching Anthropic) which lack the field.
        """
        if llm is None:
            return 0
        usage = getattr(llm, "_token_usage", None)
        if not isinstance(usage, dict):
            return 0
        return usage.get("cache_creation_tokens", 0) or 0

    def start_phase(self, name: str, llm: Any = None) -> None:
        """Start timing a phase. Pass the agent's LLM to snapshot its cumulative
        cache_creation counter so finish_phase can compute the per-phase delta.
        """
        self._phases[name] = PhaseMetrics(
            name=name,
            start_time=time.perf_counter(),
            cache_creation_snapshot=self._llm_cache_creation(llm),
        )

    def finish_phase(
        self,
        name: str,
        token_usage: Any,
        model_id: str = "unknown",
        llm: Any = None,
    ) -> None:
        """Record end time and token counts for a completed phase.

        Args:
            name: Phase name matching one of _PHASE_ORDER.
            token_usage: CrewOutput.token_usage (UsageMetrics) from akickoff().
            model_id: Model identifier string (e.g. "anthropic/claude-sonnet-4-6").
            llm: Same LLM instance passed to start_phase; used to read the
                cumulative cache_creation_tokens counter and derive the delta
                for this phase. Optional — falls back to 0 if absent.
        """
        pm = self._phases.get(name)
        if pm is None:
            pm = PhaseMetrics(name=name)
            self._phases[name] = pm
        pm.end_time = time.perf_counter()

        # Cache-write delta — computed from per-LLM cumulative counter because
        # CrewOutput.token_usage does not surface cache_creation_input_tokens.
        cache_write_tok = max(
            0, self._llm_cache_creation(llm) - pm.cache_creation_snapshot
        )
        pm.cache_creation_tokens += cache_write_tok

        if token_usage is None:
            if cache_write_tok:
                self._add_to_buckets(pm, model_id, 0, 0, 0, cache_write_tok)
            return

        input_tok = getattr(token_usage, "prompt_tokens", 0) or 0
        output_tok = getattr(token_usage, "completion_tokens", 0) or 0
        # On Anthropic models this is sourced from `cache_read_input_tokens` —
        # i.e. tokens served from Anthropic's prompt cache. See
        # crewai/llms/providers/anthropic/completion.py::_extract_anthropic_token_usage.
        cached_tok = getattr(token_usage, "cached_prompt_tokens", 0) or 0

        pm.input_tokens += input_tok
        pm.output_tokens += output_tok
        pm.cached_tokens += cached_tok

        self._add_to_buckets(pm, model_id, input_tok, output_tok, cached_tok, cache_write_tok)

    def _add_to_buckets(
        self,
        pm: PhaseMetrics,
        model_id: str,
        input_tok: int,
        output_tok: int,
        cached_tok: int,
        cache_write_tok: int,
    ) -> None:
        def _empty() -> Dict[str, int]:
            return {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cached_tokens": 0,
                "cache_creation_tokens": 0,
            }

        bucket = pm.model_token_map.setdefault(model_id, _empty())
        bucket["input_tokens"] += input_tok
        bucket["output_tokens"] += output_tok
        bucket["total_tokens"] += input_tok + output_tok
        bucket["cached_tokens"] += cached_tok
        bucket["cache_creation_tokens"] += cache_write_tok

        global_bucket = self._model_totals.setdefault(model_id, _empty())
        global_bucket["input_tokens"] += input_tok
        global_bucket["output_tokens"] += output_tok
        global_bucket["total_tokens"] += input_tok + output_tok
        global_bucket["cached_tokens"] += cached_tok
        global_bucket["cache_creation_tokens"] += cache_write_tok

    # ── Output ─────────────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return self._build(now=None, partial=False)

    def snapshot(self) -> Dict[str, Any]:
        """Partial view for a run that is running or has failed (partial=True).

        Running phases report elapsed_sec up to now, and an unfinished pipeline
        reports pipeline_elapsed_sec up to now.
        """
        return self._build(now=time.perf_counter(), partial=True)

    def _build(self, now: Optional[float], partial: bool) -> Dict[str, Any]:
        """Build the execution_metrics dict (contract v2, additive over v1).

        now=None gives the final view: running phases keep elapsed_sec 0.0 as
        before. A float `now` gives a snapshot view where running phases and
        an unfinished pipeline are measured up to `now`.
        """
        if self._pipeline_start and self._pipeline_end:
            pipeline_elapsed = round(max(0.0, self._pipeline_end - self._pipeline_start), 3)
        elif self._pipeline_start and now is not None:
            pipeline_elapsed = round(max(0.0, now - self._pipeline_start), 3)
        else:
            pipeline_elapsed = 0.0

        with self._lock:
            records = list(self._tool_calls)
            market_corpus = copy.deepcopy(self._market_corpus)
        by_phase: Dict[str, List[ToolCallRecord]] = {}
        for rec in records:
            by_phase.setdefault(rec.phase, []).append(rec)

        phases = []
        phase_intervals = []
        for name in _PHASE_ORDER:
            pm = self._phases.get(name)
            if pm is None:
                status = "not_started"
            elif pm.end_time:
                status = "completed"
            elif pm.start_time:
                status = "running"
            else:
                status = "not_started"
            pm = pm if pm is not None else PhaseMetrics(name=name)

            if status == "running" and now is not None:
                elapsed = round(max(0.0, now - pm.start_time), 3)
            else:
                elapsed = pm.elapsed_sec

            if pm.start_time:
                if pm.end_time:
                    phase_intervals.append((pm.start_time, pm.end_time))
                elif now is not None:
                    phase_intervals.append((pm.start_time, now))

            calls = by_phase.get(name, [])
            if status == "not_started":
                tool_total = tool_wall = overhead = None
            else:
                tool_total = round(sum(max(0.0, c.end - c.start) for c in calls), 3)
                tool_wall_raw = _union_sec([(c.start, c.end) for c in calls])
                tool_wall = round(tool_wall_raw, 3)
                overhead = round(max(0.0, elapsed - tool_wall_raw), 3)

            phases.append({
                "name": name,
                "elapsed_sec": elapsed,
                "input_tokens": pm.input_tokens,
                "output_tokens": pm.output_tokens,
                "cached_tokens": pm.cached_tokens,
                "cache_creation_tokens": pm.cache_creation_tokens,
                "total_tokens": pm.total_tokens,
                "status": status,
                "attempts": pm.attempts,
                "tool_call_count": len(calls),
                "tool_total_sec": tool_total,
                "tool_wall_sec": tool_wall,
                "llm_overhead_sec": overhead,
                "tools": self._tool_rollup(calls),
            })

        totals = {
            "input_tokens": sum(p["input_tokens"] for p in phases),
            "output_tokens": sum(p["output_tokens"] for p in phases),
            "cached_tokens": sum(p["cached_tokens"] for p in phases),
            "cache_creation_tokens": sum(p["cache_creation_tokens"] for p in phases),
            "total_tokens": sum(p["total_tokens"] for p in phases),
        }

        if phase_intervals:
            union = _union_sec(phase_intervals)
            phases_union: Optional[float] = round(union, 3)
            unattributed: Optional[float] = round(max(0.0, pipeline_elapsed - union), 3)
        else:
            phases_union = None
            unattributed = None

        timed_phases = [p for p in phases if p["status"] != "not_started" and p["elapsed_sec"] > 0]
        slowest_phase = None
        if timed_phases:
            top = max(timed_phases, key=lambda p: p["elapsed_sec"])
            slowest_phase = {"name": top["name"], "elapsed_sec": top["elapsed_sec"]}
        slowest_call = None
        if records:
            top_rec = max(records, key=lambda c: c.end - c.start)
            slowest_call = {
                "phase": top_rec.phase,
                "tool": top_rec.tool,
                "elapsed_sec": top_rec.elapsed_sec,
                "ok": top_rec.ok,
            }

        metrics: Dict[str, Any] = {
            "run_at": self._run_at.strftime("%Y-%m-%dT%H:%M:%SZ") if self._run_at else "",
            "sector": self._sector,
            "pipeline_elapsed_sec": pipeline_elapsed,
            "phases": phases,
            "totals": totals,
            "by_model": self._model_totals,
            "metrics_version": 2,
            "partial": partial,
            "tool_calls": self._tool_call_dicts(),
            "phases_union_sec": phases_union,
            "unattributed_sec": unattributed,
            "slowest_phase": slowest_phase,
            "slowest_tool_call": slowest_call,
        }
        if market_corpus is not None:
            metrics["market_corpus"] = market_corpus
        return metrics

    @staticmethod
    def _tool_rollup(calls: List[ToolCallRecord]) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[ToolCallRecord]] = {}
        for c in calls:
            grouped.setdefault(c.tool, []).append(c)
        rollup = []
        for tool, recs in grouped.items():
            durations = [max(0.0, c.end - c.start) for c in recs]
            rollup.append({
                "tool": tool,
                "count": len(recs),
                "total_sec": round(sum(durations), 3),
                "max_sec": round(max(durations), 3),
                "error_count": sum(1 for c in recs if not c.ok),
                "output_chars_total": sum(c.output_chars or 0 for c in recs),
            })
        rollup.sort(key=lambda r: r["total_sec"], reverse=True)
        return rollup
