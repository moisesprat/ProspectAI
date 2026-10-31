import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, cast

_M = TypeVar("_M", bound="BaseModel")

from crewai import Crew
from crewai.crews.crew_output import CrewOutput
from crewai.flow.flow import Flow, and_, listen, start
from pydantic import BaseModel

from schemas.agent_outputs import (
    MarketAnalysisOutput,
    MarketNarrativeOutput,
    TechnicalAnalysisOutput,
    TechnicalNarrativeOutput,
    FundamentalAnalysisOutput,
    FundamentalNarrativeOutput,
    InvestorStrategicOutput,
    CriticOutput,
)
from utils.execution_tracker import ExecutionTracker
from utils.flow_tools import call_tool
from utils.fundamental_records import (
    build_fundamental_records,
    merge_fundamental,
    narrative_context,
    require_narrative_coverage,
)
from utils.market_records import (
    REDDIT_TOOL_NAME,
    SERPER_TOOL_NAME,
    build_market_corpus,
    market_narrative_context,
    merge_market,
    reddit_fallback_required,
    require_market_picks,
    serper_query,
)
from utils.phase_runner import extract_model, run_phase
from utils.technical_records import (
    build_technical_records,
    merge_technical,
    narrative_context as technical_narrative_context,
    require_technical_coverage,
)
from utils.recommendation_validator import validate_portfolio
from utils.portfolio_allocator_tool import PortfolioAllocatorTool
from utils.portfolio_bounds_validator import BoundsViolationError, validate as validate_bounds
from utils.action_policy_gate import filter_directives, filter_critiques
from utils.candidate_universe_filter import filter_candidates
from utils.fundamental_grader_tool import fundamentals_status
from utils import yfinance_cache
from config.config import Config
from prospect_ai_crew import TaskFactory

logger = logging.getLogger(__name__)

_AGENT_NAMES = [
    "MarketAnalyst",
    "TechnicalAnalyst",
    "FundamentalAnalyst",
    "DraftStrategist",
    "Critic",
    "FinalStrategist",
]

PHASES = [
    "market_analysis",
    "technical_analysis",
    "fundamental_analysis",
    "draft_strategy",
    "critique_review",
    "final_strategy",
]


def _parse_crew_result(crew_result) -> Dict[str, Any]:
    """Extract a JSON dict from a CrewAI result object.

    Handles pydantic task output, json_dict shortcut, markdown fences, and
    plain JSON strings. Falls back to a minimal error dict on parse failure.
    """
    if hasattr(crew_result, "json_dict") and crew_result.json_dict:
        return crew_result.json_dict

    tasks_output = getattr(crew_result, "tasks_output", None)
    if tasks_output:
        last = tasks_output[-1]
        if getattr(last, "pydantic", None):
            return last.pydantic.model_dump(mode="json")
        if getattr(last, "json_dict", None):
            return last.json_dict

    raw = getattr(crew_result, "raw", None) or str(crew_result)
    cleaned = raw.strip()
    for fence in ("```json", "```python", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
            break
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "pipeline_version": "2.0",
            "parse_error": True,
            "raw_output": raw,
            "portfolio_summary": {"portfolio_rationale": raw[:500]},
        }


_VALID_PROFILES = frozenset({"conservative", "aggressive"})


class MissingToolCallError(RuntimeError):
    """A phase whose task carries tools finished without calling any of them.

    With thinking off, the model may skip a needed tool call when JSON output is
    also requested. Until a phase's tools move into the Flow, a skipped call
    would publish indicators or grades the model invented, so the run fails.
    """


class ProspectAIFlowState(BaseModel):
    sector: str = ""
    today: str = ""
    risk_profile: str = "conservative"
    market_output: Optional[MarketAnalysisOutput] = None
    technical_output: Optional[TechnicalAnalysisOutput] = None
    fundamental_output: Optional[FundamentalAnalysisOutput] = None
    draft_output: Optional[InvestorStrategicOutput] = None
    critique_output: Optional[CriticOutput] = None
    final_output: Optional[InvestorStrategicOutput] = None
    error: str = ""


class ProspectAIFlow(Flow[ProspectAIFlowState]):
    """CrewAI Flow orchestrator for ProspectAI.

    Runs Technical and Fundamental analysis in parallel after Market Analysis
    completes, then gates Draft Strategy on both finishing via and_().
    """

    def __init__(
        self,
        task_callback: Optional[Callable] = None,
        step_callback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        *,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        config: Optional[Config] = None,
    ):
        if config is not None and any(v is not None for v in (model, provider, ollama_base_url)):
            raise ValueError("Pass either config= or model/provider/ollama_base_url, not both")
        super().__init__()
        self._task_callback = task_callback
        self._step_callback = step_callback
        self._progress_callback = progress_callback
        self._tracker: Optional[ExecutionTracker] = None

        # Public: the backend reads pipeline_config.model_id_for_agent(k) for SSE model names.
        self.pipeline_config = (
            config if config is not None
            else Config(model=model, provider=provider, ollama_base_url=ollama_base_url)
        )
        self._factory = TaskFactory(config=self.pipeline_config, tracker_getter=lambda: self._tracker)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _emit_start(self, task_index: int) -> None:
        if self._progress_callback:
            self._progress_callback({
                "event": "agent_start",
                "task_index": task_index,
                "agent": _AGENT_NAMES[task_index] if task_index < len(_AGENT_NAMES) else "unknown",
            })

    def _emit_progress(self, task_index: int, result: CrewOutput) -> None:
        if self._progress_callback:
            raw = result.raw or ""
            task_out = result.tasks_output[0] if result.tasks_output else None
            if task_out and getattr(task_out, "json_dict", None):
                preview = json.dumps(task_out.json_dict, default=str)[:500]
            elif task_out and getattr(task_out, "pydantic", None):
                pydantic_obj = task_out.pydantic
                preview = json.dumps(pydantic_obj.model_dump(mode="json"))[:500]  # type: ignore[union-attr]
            else:
                preview = raw[:500]
            self._progress_callback({
                "event": "task_complete",
                "task_index": task_index,
                "agent": _AGENT_NAMES[task_index] if task_index < len(_AGENT_NAMES) else "unknown",
                "preview": preview,
                "tokens_est": max(1, len(raw) // 4),
                "output_len": len(raw),
            })

    def _emit_progress_model(self, task_index: int, model: BaseModel, result: Optional[CrewOutput]) -> None:
        """task_complete for a phase whose published output the Flow built itself.

        Same payload keys as _emit_progress, but the preview is the published
        model rather than the LLM's raw answer. ``result`` may be None when the
        phase made no LLM call.
        """
        if self._progress_callback:
            raw = (result.raw if result is not None else "") or ""
            self._progress_callback({
                "event": "task_complete",
                "task_index": task_index,
                "agent": _AGENT_NAMES[task_index] if task_index < len(_AGENT_NAMES) else "unknown",
                "preview": json.dumps(model.model_dump(mode="json"))[:500],
                "tokens_est": max(1, len(raw) // 4),
                "output_len": len(raw),
            })

    def _make_crew(self, task, phase_index: int) -> Crew:
        wrapped_step_cb: Optional[Callable] = None
        if self._step_callback:
            cb = self._step_callback

            def _step_wrapper(step_output, _idx=phase_index):
                cb(_idx, step_output)

            wrapped_step_cb = _step_wrapper
        return Crew(
            agents=[task.agent],
            tasks=[task],
            step_callback=wrapped_step_cb,
            verbose=True,
            cache=True,
        )

    @staticmethod
    def _model_id(task) -> str:
        try:
            return task.agent.llm.model
        except Exception:
            return "unknown"

    def agent_model_ids(self) -> List[str]:
        """Raw model id each phase LLM actually uses, in PHASES order.

        Read from the built agents, so AGENT_*_MODEL / MODEL overrides and the
        agents.yaml defaults are already resolved. A provider prefix
        (``ollama/qwen3``) is stripped.
        """
        ids: List[str] = []
        for phase in PHASES:
            model = str(self._factory._phase_config[phase]["agent"].llm.model)
            ids.append(model.split("/", 1)[1] if "/" in model else model)
        return ids

    def _require_tool_calls(self, phase: str, task, since: int = 0) -> None:
        """Fail the run when a tool phase recorded zero tool calls (no-op without a tracker).

        ``since`` is the phase's tool-call count before the attempt being checked, so
        a retry cannot pass on the tool calls of an earlier attempt.
        """
        if self._tracker is None:
            return
        tools = getattr(task, "tools", None) or []
        if not tools or self._tracker.tool_call_count(phase) - since > 0:
            return
        names = ", ".join(str(getattr(t, "name", type(t).__name__)) for t in tools)
        raise MissingToolCallError(
            f"{phase}: the agent finished without calling any of its tools ({names}); "
            "refusing to use model-invented data"
        )

    @staticmethod
    def _task_llm(task) -> Any:
        try:
            return task.agent.llm
        except Exception:
            return None

    def _phase_llm(self, phase: str) -> Any:
        """The phase agent's LLM, for phases that start the tracker before building a task."""
        try:
            return self._factory._phase_config[phase]["agent"].llm
        except Exception:
            return None

    def _fmt_ctx(self, label: str, content: str) -> str:
        return f"=== {label} ===\n{content}"

    def _check_error(self) -> None:
        if self.state.error:
            raise RuntimeError(self.state.error)

    @staticmethod
    def _extract_pydantic(result: CrewOutput, model_cls: Type[_M], phase: str) -> _M:
        """Validated Pydantic model from a mini-Crew result (see utils.phase_runner.extract_model).

        Kept under this name for existing callers. The error names the phase and the
        failing fields and never carries the raw model output.
        """
        return extract_model(result, model_cls, phase)

    async def _run_phase(
        self,
        phase: str,
        index: int,
        model_cls: Type[_M],
        build_args: tuple = (),
        build_kwargs: Optional[Dict[str, Any]] = None,
        validate: Optional[Callable[[_M], None]] = None,
        start_tracker: bool = True,
    ) -> "tuple[CrewOutput, _M]":
        """Run one phase through utils.phase_runner.run_phase (bounded, per-phase retries).

        Owns the tracker lifecycle: start_phase once before the first attempt,
        finish_phase once after the accepted attempt (tokens of failed attempts are
        not added, a known metrics gap). The tool-call guard runs per attempt, so a
        retry cannot pass on the tool calls of an earlier attempt.

        ``start_tracker=False`` is for a phase that already started its tracker
        phase because the Flow ran tools before the first attempt (CORR-10).
        """
        tracker = self._tracker
        box: Dict[str, Any] = {}

        def build(feedback: str):
            kwargs = dict(build_kwargs or {})
            if feedback:
                kwargs["feedback"] = feedback
            task = self._factory.build_task(
                phase, self.state.sector, self.state.today, *build_args, **kwargs,
            )
            if tracker and start_tracker and "task" not in box:
                tracker.start_phase(phase, llm=self._task_llm(task))
            box["task"] = task
            return task

        def finish(result: CrewOutput, task) -> None:
            if tracker:
                tracker.finish_phase(phase, result.token_usage, self._model_id(task), llm=self._task_llm(task))

        async def kickoff(task) -> CrewOutput:
            before = tracker.tool_call_count(phase) if tracker else 0
            result = cast(CrewOutput, await self._make_crew(task, index).akickoff())
            try:
                self._require_tool_calls(phase, task, since=before)
            except MissingToolCallError:
                finish(result, task)
                raise
            return result

        result, model = await run_phase(
            phase=phase,
            build_task=build,
            kickoff=kickoff,
            model_cls=model_cls,
            validate=validate,
            tracker=tracker,
        )
        finish(result, box["task"])
        return result, model

    # ── Context slim helpers ──────────────────────────────────────────────────
    # Each helper builds a slimmed JSON string from the typed model stored in
    # state. Output keys match the tasks.yaml format that agent descriptions
    # reference. Returns "" if the corresponding state field is None.

    def _slim_market_for_analysis(self) -> str:
        """Ticker + sentiment only — enough for Technical/Fundamental to know what to analyze."""
        mo = self.state.market_output
        if mo is None:
            return ""
        return json.dumps({
            "sector": mo.sector,
            "sentiment_available": mo.sentiment_available,
            "candidate_stocks": [
                {
                    "ticker": s.ticker,
                    "average_sentiment": s.average_sentiment,
                    "relevance_score": s.relevance_score,
                }
                for s in mo.candidate_stocks
            ],
        })

    def _slim_market_for_strategy(self) -> str:
        """Ticker + sentiment + mention_count + rationale — needed by Draft/Critic/Final."""
        mo = self.state.market_output
        if mo is None:
            return ""
        return json.dumps({
            "sector": mo.sector,
            "sentiment_available": mo.sentiment_available,
            "candidate_stocks": [
                {
                    "ticker": s.ticker,
                    "mention_count": s.mention_count,
                    "average_sentiment": s.average_sentiment,
                    "relevance_score": s.relevance_score,
                    "rationale": s.rationale,
                }
                for s in mo.candidate_stocks
            ],
        })

    def _slim_technical(self) -> str:
        """Key signals per ticker mapped to tasks.yaml layout (stock_analyses)."""
        to = self.state.technical_output
        if to is None:
            return ""
        slim = []
        for a in to.technical_analysis:
            ma = a.momentum_analysis
            sr = ma.support_resistance
            ri = a.raw_indicators
            slim.append({
                "ticker": a.ticker,
                "current_price": a.current_price,
                "price_data_error": a.price_data_error,
                "raw_indicators": {
                    "rsi": ri.rsi if ri else None,
                    "stochastic_status": ri.stochastic_status if ri else None,
                    "macd_status": ri.macd_status if ri else None,
                    "ma_status": ri.ma_status if ri else None,
                    "adx": ri.adx if ri else None,
                },
                "interpretation": {
                    "overall_signal": ma.overall_signal,
                    "key_signals": ma.key_signals,
                    # support_resistance is null in Flow-built output (no tool computes it).
                    "entry_zone_low": ma.entry_zone_low if ma.entry_zone_low is not None else (sr.support if sr else None),
                    "entry_zone_high": ma.entry_zone_high if ma.entry_zone_high is not None else (sr.resistance if sr else None),
                    "entry_zone_status": ma.entry_zone_status,
                    "regime": ma.regime,
                    "momentum_score": ma.momentum_score,
                    "risk_level": ma.risk_level,
                    "trend_strength": ma.trend_strength,
                },
            })
        return json.dumps({"sector": to.sector, "stock_analyses": slim})

    def _slim_fundamental(self) -> str:
        """Graded fields per ticker mapped to tasks.yaml layout (stock_analyses).
        Keys and values are the schema vocabulary, copied from the model with no
        translation (CORR-02, D-10). UNKNOWN labels and data_status pass through
        verbatim; fundamentals_status is derived from them by the grader helper.
        """
        fo = self.state.fundamental_output
        if fo is None:
            return ""
        slim = []
        for a in fo.fundamental_analysis:
            fr = a.fundamental_rating
            slim.append({
                "ticker": a.ticker,
                "assessment": {
                    "valuation": fr.valuation,
                    "quality": fr.quality,
                    "growth": fr.growth,
                    "data_status": a.data_status,
                    "fundamentals_status": fundamentals_status(fr.quality, fr.growth),
                    "fundamental_summary": a.investment_thesis,
                    "risk_factors": a.key_risks,
                    "catalysts": a.key_strengths,
                },
            })
        return json.dumps({"sector": fo.sector, "stock_analyses": slim})

    def _slim_draft(self) -> str:
        """Draft positions for Critic/Final — truncates per-position rationale to 150 chars
        and overall_strategy to 200 chars.  All structural fields (action, composite_score,
        allocation_pct, trade_setup, triggers) are kept in full.
        """
        do = self.state.draft_output
        if do is None:
            return ""
        slim_positions = []
        for p in do.positions:
            slim_positions.append({
                "ticker": p.ticker,
                "action": p.action,
                "composite_score": p.composite_score,
                "allocation_pct": p.allocation_pct,
                "current_price": p.current_price,
                "trade_setup": p.trade_setup.model_dump() if p.trade_setup else None,
                "monitoring_triggers": p.monitoring_triggers,
                "review_frequency": p.review_frequency,
                "rationale": (p.rationale or "")[:150],
            })
        return json.dumps({
            "sector": do.sector,
            "positions": slim_positions,
            "deployed_pct": do.deployed_pct,
            "reserved_pct": do.reserved_pct,
            "total_allocated_pct": do.total_allocated_pct,
            "cash_reserve_pct": do.cash_reserve_pct,
            "overall_strategy": (do.overall_strategy or "")[:200],
            "risk_level": do.risk_level,
        })

    def _critic_reference_table(self) -> str:
        """Compact per-ticker lookup for the Critic — only the fields its checklist references."""
        mo = self.state.market_output
        to = self.state.technical_output
        fo = self.state.fundamental_output

        if mo is None or to is None or fo is None:
            return json.dumps({"reference_table": []})

        sentiment_by_ticker = {s.ticker: s.average_sentiment for s in mo.candidate_stocks}
        tech_by_ticker      = {a.ticker: a for a in to.technical_analysis}
        fund_by_ticker      = {a.ticker: a for a in fo.fundamental_analysis}

        rows = []
        for ticker in tech_by_ticker:
            ta = tech_by_ticker[ticker]
            fa = fund_by_ticker.get(ticker)
            ri = ta.raw_indicators
            ma = ta.momentum_analysis
            fr = fa.fundamental_rating if fa else None
            rows.append({
                "ticker":            ticker,
                "rsi":               ri.rsi               if ri else None,
                "stochastic_status": ri.stochastic_status if ri else None,
                "macd_status":       ri.macd_status        if ri else None,
                "entry_zone_status": ma.entry_zone_status  if ma else None,
                "momentum_score":    ma.momentum_score      if ma else None,
                "average_sentiment": sentiment_by_ticker.get(ticker),
                "valuation":         fr.valuation          if fr else None,
                "quality":           fr.quality            if fr else None,
                # No fundamental row for this ticker is itself an unknown.
                "fundamentals_status": fundamentals_status(fr.quality, fr.growth) if fr else "UNKNOWN",
            })
        return json.dumps({"reference_table": rows})

    def _gate_position_context(self) -> Dict[str, Dict[str, Optional[str]]]:
        """ticker -> position context for ActionPolicyGate: entry_zone_status,
        risk_profile, fundamentals_status (None when the ticker has no
        fundamental record, D-08) and price_data_error.
        """
        to = self.state.technical_output
        if to is None:
            return {}
        fundamentals = self._fundamentals_status_by_ticker()
        return {
            t.ticker.upper(): {
                "entry_zone_status": t.momentum_analysis.entry_zone_status,
                "risk_profile": self.state.risk_profile,
                "fundamentals_status": fundamentals.get(t.ticker.upper()),
                "price_data_error": t.price_data_error,
            }
            for t in to.technical_analysis
        }

    def _fundamentals_status_by_ticker(self) -> Dict[str, str]:
        """ticker -> AVAILABLE | UNKNOWN from the deterministic fundamental
        output (UNKNOWN exactly when quality or growth is UNKNOWN). Tickers
        without a fundamental record are absent.
        """
        fo = self.state.fundamental_output
        if fo is None:
            return {}
        return {
            a.ticker.upper(): fundamentals_status(a.fundamental_rating.quality, a.fundamental_rating.growth)
            for a in fo.fundamental_analysis
        }

    def _gated_slim_critique(self) -> str:
        """Same shape as _slim_critique(), but with revision_directives that
        order an action outside the entry_zone_status/risk_profile policy
        table dropped and logged before the Final Strategist ever sees them.
        """
        co = self.state.critique_output
        if co is None:
            return ""

        position_context = self._gate_position_context()

        kept_directives, rejected_directives = filter_directives(
            co.revision_directives, position_context,
        )
        for r in rejected_directives:
            logger.warning(
                "ActionPolicyGate dropped directive for %s (requested %s): %s",
                r.ticker, r.rejected_action, r.reason,
            )

        raw_critiques = [
            {
                "ticker": c.ticker,
                "severity": c.severity,
                "issue_type": c.issue_type,
                "finding": c.finding,
                "instruction": c.instruction,
            }
            for c in co.per_ticker_critiques
        ]
        kept_critiques, rejected_critiques = filter_critiques(raw_critiques, position_context)
        for r in rejected_critiques:
            logger.warning(
                "ActionPolicyGate dropped per_ticker_critique for %s (requested %s): %s",
                r.ticker, r.rejected_action, r.reason,
            )

        return json.dumps({
            "sector": co.sector,
            "draft_assessment": co.draft_assessment,
            "per_ticker_critiques": kept_critiques,
            "revision_directives": kept_directives,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Flow methods
    # ─────────────────────────────────────────────────────────────────────────
    @start()
    async def market_analysis(self):
        """Flow-owned phase (CORR-10, D-14): the Flow calls Reddit and, when Reddit asks for
        fallback, Serper; the LLM only chooses up to 5 tickers from that corpus and writes
        their rationales and the summary.

        Both tools run off the event loop (call_tool, STALL-02), so their bounded sleeps never
        block it. Every number, the sentiment flag and the timestamp are built by
        utils.market_records.merge_market, never taken from the LLM. A tool that raises is
        logged by exception class and treated as no data, never as invented data.
        """
        self._check_error()
        self._emit_start(0)
        phase = "market_analysis"
        sector, today = self.state.sector, self.state.today

        tracker = self._tracker
        if tracker:
            tracker.start_phase(phase, llm=self._phase_llm(phase))
        try:
            reddit = await call_tool(
                self._factory.flow_tool(phase, REDDIT_TOOL_NAME),
                phase_index=0, step_callback=self._step_callback,
                thought=f"Reading Reddit discussion for {sector}",
                sector=sector,
            )
        except Exception as exc:
            logger.warning("%s: Reddit tool failed (%s); using the Serper fallback", phase, type(exc).__name__)
            reddit = None

        serper = None
        fallback_required = reddit_fallback_required(reddit)
        if fallback_required:
            try:
                serper = await call_tool(
                    self._factory.flow_tool(phase, SERPER_TOOL_NAME),
                    phase_index=0, step_callback=self._step_callback,
                    thought=f"Searching the web for {sector} sector stocks",
                    search_query=serper_query(sector, today),
                )
            except Exception as exc:
                logger.warning("%s: Serper search failed (%s); no market data this run", phase, type(exc).__name__)

        corpus = build_market_corpus(reddit, serper, sector)
        logger.info("%s: corpus source=%s", phase, corpus["source"])
        ctx = self._fmt_ctx("Market Data (collected by the pipeline)", market_narrative_context(corpus))
        result, narrative = await self._run_phase(
            phase, 0, MarketNarrativeOutput, build_args=(ctx,),
            validate=lambda n: require_market_picks(n, corpus),
            start_tracker=False,
        )
        self.state.market_output = merge_market(sector, corpus, narrative, datetime.now(timezone.utc))
        kept, dropped = filter_candidates(self.state.market_output.candidate_stocks, sector)
        if dropped:
            logger.warning("Excluded sector-benchmark/broad-market ETF candidates: %s", dropped)
            self.state.market_output.candidate_stocks = kept
        self._emit_progress_model(0, self.state.market_output, result)
        return result.raw or ""

    @listen(market_analysis)
    async def technical_analysis(self):
        """Flow-owned phase (CORR-10, D-14): the Flow calls the indicator tool and builds
        every number and label; the LLM writes only overall_signal, key_signals,
        comprehensive_analysis, investment_recommendation and the summary.

        The tool runs off the event loop (call_tool), so it overlaps the fundamental
        phase's tool calls (STALL-02). The agent has no tools, so the per-attempt
        tool-call guard has nothing to check: the Flow calls the tool unconditionally,
        and a failed ticker is recorded and excluded, never given invented indicators.
        """
        self._check_error()
        self._emit_start(1)
        phase = "technical_analysis"
        mo = self.state.market_output
        tickers = list(dict.fromkeys(
            c.ticker.strip().upper() for c in (mo.candidate_stocks if mo else []) if c.ticker.strip()
        ))
        if not tickers:
            raise RuntimeError(f"{phase}: no candidate tickers from market_analysis")

        tracker = self._tracker
        if tracker:
            tracker.start_phase(phase, llm=self._phase_llm(phase))
        tool_result = await call_tool(
            self._factory.flow_tool(phase, "calculate_technical_indicators"),
            phase_index=1, step_callback=self._step_callback,
            thought=f"Calculating indicators for {len(tickers)} tickers",
            tickers_json=json.dumps(tickers),
        )
        records, failed = build_technical_records(tool_result, tickers)
        if not records:
            reasons = "; ".join(f"{f.ticker}: {f.error}" for f in failed)[:300]
            raise RuntimeError(
                f"{phase}: no ticker has indicator data; refusing to publish invented indicators ({reasons})"
            )
        if failed:
            logger.warning(
                "%s: indicators failed for %s; excluded from later phases",
                phase, ", ".join(f.ticker for f in failed),
            )

        ctx = "\n\n".join([
            self._fmt_ctx("Market Analysis Output", self._slim_market_for_analysis()),
            self._fmt_ctx("Technical Data (computed by the pipeline)", technical_narrative_context(records, failed)),
        ])
        result, narrative = await self._run_phase(
            phase, 1, TechnicalNarrativeOutput, build_args=(ctx,),
            validate=lambda n: require_technical_coverage(n, records),
            start_tracker=False,
        )
        self.state.technical_output = merge_technical(self.state.sector, tickers, records, narrative, failed)
        self._emit_progress_model(1, self.state.technical_output, result)
        return result.raw or ""

    @listen(market_analysis)
    async def fundamental_analysis(self):
        """Flow-owned phase (CORR-10, D-06): the Flow fetches, grades and builds every
        record; the LLM writes only strengths, risks, thesis and summary.

        The tools run in this method (off the loop, with synthetic SSE steps), so
        the per-attempt tool-call guard has nothing to check: the agent has no
        tools, and a missing or failed call becomes a failed record, never a
        model-invented number.
        """
        self._check_error()
        self._emit_start(2)
        phase = "fundamental_analysis"
        mo = self.state.market_output
        tickers = list(dict.fromkeys(
            c.ticker.strip().upper() for c in (mo.candidate_stocks if mo else []) if c.ticker.strip()
        ))
        if not tickers:
            raise RuntimeError(f"{phase}: no candidate tickers from market_analysis")

        tracker = self._tracker
        if tracker:
            tracker.start_phase(phase, llm=self._phase_llm(phase))
        fetch_json = await call_tool(
            self._factory.flow_tool(phase, "fetch_fundamental_data"),
            phase_index=2, step_callback=self._step_callback,
            thought=f"Fetching fundamentals for {len(tickers)} tickers",
            tickers_json=json.dumps(tickers),
        )
        grades_json = await call_tool(
            self._factory.flow_tool(phase, "grade_fundamental_data"),
            phase_index=2, step_callback=self._step_callback,
            thought="Grading fundamentals",
            fundamentals_batch_json=fetch_json,
        )
        records = build_fundamental_records(fetch_json, grades_json)
        requested = {t: records[t] for t in tickers if t in records}

        result: Optional[CrewOutput] = None
        narrative: Optional[FundamentalNarrativeOutput] = None
        if any(r["data_status"] != "failed" for r in requested.values()):
            ctx = "\n\n".join([
                self._fmt_ctx("Market Analysis Output", self._slim_market_for_analysis()),
                self._fmt_ctx("Fundamental Data (computed by the pipeline)", narrative_context(tickers, requested)),
            ])
            result, narrative = await self._run_phase(
                phase, 2, FundamentalNarrativeOutput, build_args=(ctx,),
                validate=lambda n: require_narrative_coverage(n, requested),
                start_tracker=False,
            )
        else:
            # Nothing to write about: no LLM call, fixed text, every ticker UNKNOWN.
            logger.warning("%s: no fundamental data for any candidate; skipping the narrative call", phase)
            if tracker:
                tracker.finish_phase(phase, None, "none")

        self.state.fundamental_output = merge_fundamental(self.state.sector, tickers, records, narrative)
        self._emit_progress_model(2, self.state.fundamental_output, result)
        return (result.raw if result is not None else "") or ""

    @listen(and_(technical_analysis, fundamental_analysis))
    async def draft_strategy(self):
        self._check_error()
        self._emit_start(3)
        ctx = "\n\n".join([
            self._fmt_ctx("Market Analysis Output", self._slim_market_for_strategy()),
            self._fmt_ctx("Technical Analysis Output", self._slim_technical()),
            self._fmt_ctx("Fundamental Analysis Output", self._slim_fundamental()),
        ])
        result, self.state.draft_output = await self._run_phase(
            "draft_strategy", 3, InvestorStrategicOutput,
            build_args=(ctx,), build_kwargs={"risk_profile": self.state.risk_profile},
        )
        self._emit_progress(3, result)
        return result.raw or ""

    @listen(draft_strategy)
    async def critique_review(self):
        self._check_error()
        self._emit_start(4)
        ctx = "\n\n".join([
            self._fmt_ctx("Draft Strategy Output", self._slim_draft()),
            self._fmt_ctx("Ticker Reference Table", self._critic_reference_table()),
        ])
        result, self.state.critique_output = await self._run_phase(
            "critique_review", 4, CriticOutput,
            build_args=(ctx,), build_kwargs={"risk_profile": self.state.risk_profile},
        )
        self._emit_progress(4, result)
        return result.raw or ""

    @listen(critique_review)
    async def final_strategy(self):
        self._check_error()
        self._emit_start(5)
        ctx = "\n\n".join([
            self._fmt_ctx("Draft Strategy Output", self._slim_draft()),
            self._fmt_ctx("Critic Review Output", self._gated_slim_critique()),
        ])
        # Same schema validation and retry as every other phase; the validated
        # model is what run_analysis publishes (no lenient parse, D-12).
        result, self.state.final_output = await self._run_phase(
            "final_strategy", 5, InvestorStrategicOutput,
            build_args=(ctx,), build_kwargs={"risk_profile": self.state.risk_profile},
        )
        self._emit_progress(5, result)
        return result.raw or ""

    # ─────────────────────────────────────────────────────────────────────────
    # Flow-authoritative allocation (deterministic-enforcement-v1-9-1)
    # ─────────────────────────────────────────────────────────────────────────
    def _reprice_final_output(self, structured: Dict[str, Any], risk_profile: str) -> Dict[str, Any]:
        """Re-invoke allocate_portfolio against the Final Strategist's decided
        actions and overwrite all numeric allocation/trade-setup fields on the
        final output. Entry zones and current prices are read from the
        deterministic Phase-2 technical output, never from the LLM's own
        (possibly fabricated) trade_setup — only `action` and `composite_score`
        are trusted from the Final Strategist output. Runs unconditionally,
        even when no action changed relative to the draft.
        """
        technical_by_ticker: Dict[str, Any] = {}
        if self.state.technical_output:
            for t in self.state.technical_output.technical_analysis:
                technical_by_ticker[t.ticker.upper()] = t

        positions = structured.get("positions", [])
        stocks_payload = []
        for pos in positions:
            ticker = str(pos.get("ticker", "")).upper()
            technical = technical_by_ticker.get(ticker)
            if technical is not None:
                entry_zone_low = technical.momentum_analysis.entry_zone_low or 0.0
                entry_zone_high = technical.momentum_analysis.entry_zone_high or 0.0
                current_price = technical.current_price or pos.get("current_price") or 0.0
            else:
                # Ticker not found in the deterministic technical output (should
                # not normally happen) -- fall back to the LLM's own fields.
                setup = pos.get("trade_setup") or {}
                entry_zone_low = setup.get("entry_zone_low", 0.0)
                entry_zone_high = setup.get("entry_zone_high", 0.0)
                current_price = pos.get("current_price", 0.0)

            stocks_payload.append({
                "ticker":          ticker,
                "action":          pos.get("action", "MONITOR"),
                "composite_score": pos.get("composite_score", 0.0),
                "entry_zone_low":  entry_zone_low,
                "entry_zone_high": entry_zone_high,
                "current_price":   current_price,
            })

        payload = {"risk_profile": risk_profile, "stocks": stocks_payload}
        result = json.loads(PortfolioAllocatorTool()._run(json.dumps(payload)))
        if "error" in result:
            raise BoundsViolationError([{
                "ticker": None, "rule": "allocator_invocation_error",
                "expected": "successful allocate_portfolio result", "actual": result["error"],
            }])

        by_ticker_result = {o["ticker"]: o for o in result["stocks"]}
        repriced_positions = []
        for pos in positions:
            ticker = str(pos.get("ticker", "")).upper()
            o = by_ticker_result.get(ticker)
            new_pos = dict(pos)
            if o is not None:
                new_pos["allocation_pct"] = o["allocation_pct"]
                new_pos["trade_setup"] = o["trade_setup"]
            repriced_positions.append(new_pos)

        repriced = dict(structured)
        repriced["positions"]           = repriced_positions
        repriced["deployed_pct"]        = result["deployed_pct"]
        repriced["reserved_pct"]        = result["reserved_pct"]
        repriced["cash_reserve_pct"]    = result["cash_reserve_pct"]
        repriced["total_allocated_pct"] = result["total_allocated_pct"]
        if "reserved_allocations" in result:
            repriced["reserved_allocations"] = result["reserved_allocations"]
        return repriced

    def _entry_zone_status_by_ticker(self) -> Dict[str, str]:
        """ticker -> entry_zone_status from the deterministic Phase-2 technical
        output, for PortfolioBoundsValidator's CURRENT_ENTRY/WAIT-FOR-ENTRY check.
        """
        result: Dict[str, str] = {}
        if self.state.technical_output:
            for t in self.state.technical_output.technical_analysis:
                status = t.momentum_analysis.entry_zone_status if t.momentum_analysis else None
                if status:
                    result[t.ticker.upper()] = status
        return result

    @staticmethod
    def _stamp_fundamentals_status(output: Dict[str, Any], fundamentals: Dict[str, str]) -> Dict[str, Any]:
        """Set every position's fundamentals_status from the deterministic map,
        overwriting whatever the LLM wrote (None for a ticker with no
        fundamental record). The SPA renders UNKNOWN as "fundamentals unavailable".
        """
        stamped = dict(output)
        stamped["positions"] = [
            {**pos, "fundamentals_status": fundamentals.get(str(pos.get("ticker", "")).upper())}
            for pos in output.get("positions", [])
        ]
        return stamped

    def _finalize_and_validate_portfolio(self, structured: Dict[str, Any], risk_profile: str) -> Dict[str, Any]:
        """Flow-authoritative repricing + fail-closed bounds validation.

        Always re-invokes allocate_portfolio (Decision 1: the LLM never decides
        whether the tool runs). If the result fails PortfolioBoundsValidator,
        re-invokes once more; if it still fails, raises BoundsViolationError
        and the caller (run_analysis) does not return a result.

        fundamentals_status is stamped on every position from the deterministic
        fundamental output before validation (D-08), and the validator's
        buy_with_unknown_fundamentals rule fails closed on a buy for UNKNOWN.

        The CURRENT_ENTRY/WAIT-FOR-ENTRY invariant check is included here even
        though the retry cannot fix it (repricing never changes `action`) --
        the point is that a Final Strategist decision violating this invariant
        must never publish silently, matching the fail-closed intent of every
        other check in this validator.
        """
        zone_status = self._entry_zone_status_by_ticker()
        fundamentals = self._fundamentals_status_by_ticker()
        repriced = self._stamp_fundamentals_status(self._reprice_final_output(structured, risk_profile), fundamentals)
        violations = validate_bounds(repriced, risk_profile, zone_status, fundamentals)
        if violations:
            logger.warning(
                "Final output failed PortfolioBoundsValidator on first pass (%s); re-invoking allocator",
                violations,
            )
            repriced = self._stamp_fundamentals_status(self._reprice_final_output(structured, risk_profile), fundamentals)
            violations = validate_bounds(repriced, risk_profile, zone_status, fundamentals)
            if violations:
                raise BoundsViolationError(violations)
        return repriced

    # ─────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────────────
    def metrics_snapshot(self) -> Optional[Dict[str, Any]]:
        """Execution metrics so far (partial=True), or None before run_analysis starts."""
        if self._tracker is None:
            return None
        return self._tracker.snapshot()

    def run_analysis(
        self,
        market_criteria: Dict[str, Any],
        progress_callback: Optional[Callable[[Dict], None]] = None,
    ) -> Dict[str, Any]:
        """Run the full pipeline and return the structured result described in the module docstring."""
        yfinance_cache.clear()
        if progress_callback:
            self._progress_callback = progress_callback

        sector = market_criteria.get("sector", "Technology")
        today = datetime.now().strftime("%Y-%m-%d")

        risk_profile = market_criteria.get("risk_profile", "conservative")
        if risk_profile not in _VALID_PROFILES:
            raise ValueError(
                f"Invalid risk_profile {risk_profile!r}. Valid values: {sorted(_VALID_PROFILES)}"
            )

        tracker = ExecutionTracker()
        tracker.set_sector(sector)
        tracker.start()
        self._tracker = tracker
        try:
            self.kickoff(inputs={"sector": sector, "today": today, "risk_profile": risk_profile})

            final_output = self.state.final_output
            if final_output is None:
                raise RuntimeError("final_strategy completed without a validated output")
            structured = final_output.model_dump(mode="json")
            structured = self._finalize_and_validate_portfolio(structured, risk_profile)

            validation_issues = validate_portfolio(structured)
            if validation_issues:
                for issue in validation_issues:
                    log_fn = logger.error if issue.severity == "critical" else logger.warning
                    log_fn("[%s] %s — %s: %s", issue.severity.upper(), issue.ticker, issue.field, issue.message)
                structured["validation_warnings"] = [
                    {"severity": i.severity, "ticker": i.ticker, "field": i.field, "message": i.message}
                    for i in validation_issues
                ]
        except Exception as exc:
            tracker.finish()
            # Timing survives failure: the caller can read exc.partial_metrics. Some
            # exception types reject attributes; never let that mask the real error.
            try:
                exc.partial_metrics = tracker.snapshot()  # type: ignore[attr-defined]
            except Exception:
                logger.warning("could not attach partial_metrics to %s", type(exc).__name__)
            raise
        except BaseException:
            tracker.finish()
            raise
        # Finish after finalize/validate so their time lands in pipeline_elapsed_sec
        # (and in unattributed_sec, since no phase covers it).
        tracker.finish()

        summary = (
            structured.get("overall_strategy", "")
            or structured.get("portfolio_summary", {}).get("portfolio_rationale", "")
            or str(structured)[:300]
        )

        metrics = tracker.to_dict()

        if self._progress_callback:
            self._progress_callback({"event": "execution_complete", "metrics": metrics})

        return {
            "status": "success",
            "workflow_completed": True,
            "result": structured,
            "summary": summary,
            "execution_metrics": metrics,
            "validation_warnings": [
                {"severity": i.severity, "ticker": i.ticker, "field": i.field, "message": i.message}
                for i in validation_issues
            ],
        }
