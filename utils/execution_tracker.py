import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


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

    @property
    def elapsed_sec(self) -> float:
        if self.end_time and self.start_time:
            return round(self.end_time - self.start_time, 3)
        return 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


_PHASE_ORDER = [
    "market_analysis",
    "technical_analysis",
    "fundamental_analysis",
    "draft_strategy",
    "critique_review",
    "final_strategy",
]


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
    """

    def __init__(self) -> None:
        self._sector: str = ""
        self._run_at: Optional[datetime] = None
        self._pipeline_start: float = 0.0
        self._pipeline_end: float = 0.0
        self._phases: Dict[str, PhaseMetrics] = {}
        self._model_totals: Dict[str, Dict[str, int]] = {}

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._run_at = datetime.now(timezone.utc)
        self._pipeline_start = time.perf_counter()

    def finish(self) -> None:
        self._pipeline_end = time.perf_counter()

    def set_sector(self, sector: str) -> None:
        self._sector = sector

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
        pipeline_elapsed = (
            round(self._pipeline_end - self._pipeline_start, 3)
            if self._pipeline_end and self._pipeline_start
            else 0.0
        )
        phases = []
        for name in _PHASE_ORDER:
            pm = self._phases.get(name, PhaseMetrics(name=name))
            phases.append({
                "name": name,
                "elapsed_sec": pm.elapsed_sec,
                "input_tokens": pm.input_tokens,
                "output_tokens": pm.output_tokens,
                "cached_tokens": pm.cached_tokens,
                "cache_creation_tokens": pm.cache_creation_tokens,
                "total_tokens": pm.total_tokens,
            })
        totals = {
            "input_tokens": sum(p["input_tokens"] for p in phases),
            "output_tokens": sum(p["output_tokens"] for p in phases),
            "cached_tokens": sum(p["cached_tokens"] for p in phases),
            "cache_creation_tokens": sum(p["cache_creation_tokens"] for p in phases),
            "total_tokens": sum(p["total_tokens"] for p in phases),
        }
        return {
            "run_at": self._run_at.strftime("%Y-%m-%dT%H:%M:%SZ") if self._run_at else "",
            "sector": self._sector,
            "pipeline_elapsed_sec": pipeline_elapsed,
            "phases": phases,
            "totals": totals,
            "by_model": self._model_totals,
        }
