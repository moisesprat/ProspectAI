import json
import logging
import warnings
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Type, TypeVar, cast

_M = TypeVar("_M", bound="BaseModel")

from crewai import Crew
from crewai.crews.crew_output import CrewOutput
from crewai.flow.flow import Flow, and_, listen, start
from pydantic import BaseModel

from schemas.agent_outputs import (
    MarketAnalysisOutput,
    TechnicalAnalysisOutput,
    FundamentalAnalysisOutput,
    InvestorStrategicOutput,
    CriticOutput,
)
from utils.execution_tracker import ExecutionTracker
from utils.recommendation_validator import validate_portfolio
from utils import yfinance_cache

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


class ProspectAIFlowState(BaseModel):
    sector: str = ""
    today: str = ""
    market_output: Optional[MarketAnalysisOutput] = None
    technical_output: Optional[TechnicalAnalysisOutput] = None
    fundamental_output: Optional[FundamentalAnalysisOutput] = None
    draft_output: Optional[InvestorStrategicOutput] = None
    critique_output: Optional[CriticOutput] = None
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
    ):
        super().__init__()
        self._task_callback = task_callback
        self._step_callback = step_callback
        self._progress_callback = progress_callback
        self._final_crew_result = None
        self._tracker: Optional[ExecutionTracker] = None

        # Build the shared agent/tool factory, suppressing the deprecation
        # warning because this is internal infrastructure, not user code.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from prospect_ai_crew import ProspectAICrew
            self._factory = ProspectAICrew()

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _emit_progress(self, task_index: int, full_output: str = "") -> None:
        if self._progress_callback:
            self._progress_callback({
                "event": "task_complete",
                "task_index": task_index,
                "agent": _AGENT_NAMES[task_index] if task_index < len(_AGENT_NAMES) else "unknown",
                "output_snippet": full_output[:300],
                "output_len": len(full_output),
            })

    def _make_crew(self, task) -> Crew:
        return Crew(
            agents=[task.agent],
            tasks=[task],
            task_callback=self._task_callback,
            step_callback=self._step_callback,
            verbose=True,
        )

    @staticmethod
    def _model_id(task) -> str:
        try:
            return task.agent.llm.model
        except Exception:
            return "unknown"

    def _fmt_ctx(self, label: str, content: str) -> str:
        return f"=== {label} ===\n{content}"

    def _check_error(self) -> None:
        if self.state.error:
            raise RuntimeError(self.state.error)

    @staticmethod
    def _extract_pydantic(result: CrewOutput, model_cls: Type[_M], phase: str) -> _M:
        """Return validated Pydantic model from mini-Crew result.

        Tries result.tasks_output[0].pydantic first (set by CrewAI when
        output_pydantic validation succeeds), then falls back to parsing
        result.raw directly via model_validate_json.
        """
        pydantic_model = (
            result.tasks_output[0].pydantic
            if result.tasks_output
            else None
        )
        if pydantic_model is not None:
            return cast(_M, pydantic_model)
        raw = result.raw or ""
        try:
            return cast(_M, model_cls.model_validate_json(raw))
        except Exception as exc:
            raise RuntimeError(
                f"Pydantic validation failed for {phase}. "
                f"raw[:200]={raw[:200]!r}"
            ) from exc

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
                    "entry_zone_low": ma.entry_zone_low if ma.entry_zone_low is not None else sr.support,
                    "entry_zone_high": ma.entry_zone_high if ma.entry_zone_high is not None else sr.resistance,
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
        fundamental_component and fundamental_unknown are not in FundamentalAnalysisOutput
        schema — fundamental_unknown defaults to False.
        """
        _quality_map = {"High": "STRONG", "Medium": "ADEQUATE", "Low": "WEAK"}
        _growth_map = {
            "High Growth": "HIGH", "Moderate Growth": "MODERATE",
            "Stable": "LOW", "Declining": "DECLINING",
        }
        fo = self.state.fundamental_output
        if fo is None:
            return ""
        slim = []
        for a in fo.fundamental_analysis:
            fr = a.fundamental_rating
            slim.append({
                "ticker": a.ticker,
                "assessment": {
                    "valuation_grade": fr.valuation,
                    "financial_health": _quality_map.get(fr.quality, "UNKNOWN"),
                    "growth_outlook": _growth_map.get(fr.growth, "UNKNOWN"),
                    "fundamental_unknown": False,
                    "fundamental_summary": a.investment_thesis,
                    "risk_factors": a.key_risks,
                    "catalysts": a.key_strengths,
                },
            })
        return json.dumps({"sector": fo.sector, "stock_analyses": slim})

    def _slim_draft(self) -> str:
        """Draft positions for Critic/Final — truncates per-position rationale to 150 chars
        and overall_strategy to 200 chars.  All structural fields (action, composite_score,
        allocation_pct, trade_setup, scaled_entry_setups, triggers) are kept in full.
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
                "scaled_entry_setups": (
                    [s.model_dump() for s in p.scaled_entry_setups]
                    if p.scaled_entry_setups else None
                ),
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

    def _slim_critique(self) -> str:
        """Directives + per-ticker critiques — strips approved_positions (not actionable)."""
        co = self.state.critique_output
        if co is None:
            return ""
        return json.dumps({
            "sector": co.sector,
            "draft_assessment": co.draft_assessment,
            "per_ticker_critiques": [
                {
                    "ticker": c.ticker,
                    "severity": c.severity,
                    "issue_type": c.issue_type,
                    "finding": c.finding,
                    "instruction": c.instruction,
                }
                for c in co.per_ticker_critiques
            ],
            "revision_directives": co.revision_directives,
        })

    def _critic_reference_table(self) -> str:
        """Compact per-ticker lookup for the Critic — only the fields its checklist references."""
        mo = self.state.market_output
        to = self.state.technical_output
        fo = self.state.fundamental_output

        if mo is None or to is None or fo is None:
            return json.dumps({"reference_table": []})

        _quality_map = {"High": "STRONG", "Medium": "ADEQUATE", "Low": "WEAK"}

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
                "valuation_grade":   fr.valuation          if fr else None,
                "financial_health":  _quality_map.get(fr.quality, "UNKNOWN") if fr else None,
            })
        return json.dumps({"reference_table": rows})

    # ─────────────────────────────────────────────────────────────────────────
    # Flow methods
    # ─────────────────────────────────────────────────────────────────────────
    @start()
    async def market_analysis(self):
        self._check_error()
        task = self._factory.build_task("market_analysis", self.state.sector, self.state.today)
        if self._tracker:
            self._tracker.start_phase("market_analysis")
        result = cast(CrewOutput, await self._make_crew(task).akickoff())
        if self._tracker:
            self._tracker.finish_phase("market_analysis", result.token_usage, self._model_id(task))
        self.state.market_output = self._extract_pydantic(result, MarketAnalysisOutput, "market_analysis")
        self._emit_progress(0, result.raw or "")
        return result.raw or ""

    @listen(market_analysis)
    async def technical_analysis(self):
        self._check_error()
        ctx = self._fmt_ctx("Market Analysis Output", self._slim_market_for_analysis())
        task = self._factory.build_task("technical_analysis", self.state.sector, self.state.today, ctx)
        if self._tracker:
            self._tracker.start_phase("technical_analysis")
        result = cast(CrewOutput, await self._make_crew(task).akickoff())
        if self._tracker:
            self._tracker.finish_phase("technical_analysis", result.token_usage, self._model_id(task))
        self.state.technical_output = self._extract_pydantic(result, TechnicalAnalysisOutput, "technical_analysis")
        self._emit_progress(1, result.raw or "")
        return result.raw or ""

    @listen(market_analysis)
    async def fundamental_analysis(self):
        self._check_error()
        ctx = self._fmt_ctx("Market Analysis Output", self._slim_market_for_analysis())
        task = self._factory.build_task("fundamental_analysis", self.state.sector, self.state.today, ctx)
        if self._tracker:
            self._tracker.start_phase("fundamental_analysis")
        result = cast(CrewOutput, await self._make_crew(task).akickoff())
        if self._tracker:
            self._tracker.finish_phase("fundamental_analysis", result.token_usage, self._model_id(task))
        self.state.fundamental_output = self._extract_pydantic(result, FundamentalAnalysisOutput, "fundamental_analysis")
        self._emit_progress(2, result.raw or "")
        return result.raw or ""

    @listen(and_(technical_analysis, fundamental_analysis))
    async def draft_strategy(self):
        self._check_error()
        ctx = "\n\n".join([
            self._fmt_ctx("Market Analysis Output", self._slim_market_for_strategy()),
            self._fmt_ctx("Technical Analysis Output", self._slim_technical()),
            self._fmt_ctx("Fundamental Analysis Output", self._slim_fundamental()),
        ])
        task = self._factory.build_task("draft_strategy", self.state.sector, self.state.today, ctx)
        if self._tracker:
            self._tracker.start_phase("draft_strategy")
        result = cast(CrewOutput, await self._make_crew(task).akickoff())
        if self._tracker:
            self._tracker.finish_phase("draft_strategy", result.token_usage, self._model_id(task))
        self.state.draft_output = self._extract_pydantic(result, InvestorStrategicOutput, "draft_strategy")
        self._emit_progress(3, result.raw or "")
        return result.raw or ""

    @listen(draft_strategy)
    async def critique_review(self):
        self._check_error()
        ctx = "\n\n".join([
            self._fmt_ctx("Draft Strategy Output", self._slim_draft()),
            self._fmt_ctx("Ticker Reference Table", self._critic_reference_table()),
        ])
        task = self._factory.build_task("critique_review", self.state.sector, self.state.today, ctx)
        if self._tracker:
            self._tracker.start_phase("critique_review")
        result = cast(CrewOutput, await self._make_crew(task).akickoff())
        if self._tracker:
            self._tracker.finish_phase("critique_review", result.token_usage, self._model_id(task))
        self.state.critique_output = self._extract_pydantic(result, CriticOutput, "critique_review")
        self._emit_progress(4, result.raw or "")
        return result.raw or ""

    @listen(critique_review)
    async def final_strategy(self):
        self._check_error()
        ctx = "\n\n".join([
            self._fmt_ctx("Draft Strategy Output", self._slim_draft()),
            self._fmt_ctx("Critic Review Output", self._slim_critique()),
        ])
        task = self._factory.build_task("final_strategy", self.state.sector, self.state.today, ctx)
        if self._tracker:
            self._tracker.start_phase("final_strategy")
        result = cast(CrewOutput, await self._make_crew(task).akickoff())
        if self._tracker:
            self._tracker.finish_phase("final_strategy", result.token_usage, self._model_id(task))
        self._final_crew_result = result
        self._emit_progress(5, result.raw or "")
        return result.raw or ""

    # ─────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────────────
    def run_analysis(
        self,
        market_criteria: Dict[str, Any],
        progress_callback: Optional[Callable[[Dict], None]] = None,
    ) -> Dict[str, Any]:
        """Run the full pipeline and return the same result shape as ProspectAICrew.run_analysis()."""
        yfinance_cache.clear()
        if progress_callback:
            self._progress_callback = progress_callback

        sector = market_criteria.get("sector", "Technology")
        today = datetime.now().strftime("%Y-%m-%d")

        tracker = ExecutionTracker()
        tracker.set_sector(sector)
        tracker.start()
        self._tracker = tracker
        try:
            self.kickoff(inputs={"sector": sector, "today": today})
        finally:
            tracker.finish()

        from prospect_ai_crew import ProspectAICrew
        structured = ProspectAICrew._parse_result(self._final_crew_result)

        validation_issues = validate_portfolio(structured)
        if validation_issues:
            for issue in validation_issues:
                log_fn = logger.error if issue.severity == "critical" else logger.warning
                log_fn("[%s] %s — %s: %s", issue.severity.upper(), issue.ticker, issue.field, issue.message)
            structured["validation_warnings"] = [
                {"severity": i.severity, "ticker": i.ticker, "field": i.field, "message": i.message}
                for i in validation_issues
            ]

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
