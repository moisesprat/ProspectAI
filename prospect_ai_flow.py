import json
import logging
import warnings
from datetime import datetime
from typing import Any, Callable, Dict, Optional, cast

from crewai import Crew
from crewai.crews.crew_output import CrewOutput
from crewai.flow.flow import Flow, and_, listen, start
from pydantic import BaseModel

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
    market_output: str = ""
    technical_output: str = ""
    fundamental_output: str = ""
    draft_output: str = ""
    critique_output: str = ""
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

    # ── Context slim helpers ──────────────────────────────────────────────────
    # Each helper strips fields that downstream agents don't use.
    # All fall back to the full raw output if JSON parsing fails.
    # Output keys match the tasks.yaml format that agent descriptions reference.

    def _slim_market_for_analysis(self) -> str:
        """Ticker + sentiment only — enough for Technical/Fundamental to know what to analyze."""
        try:
            data = json.loads(self.state.market_output)
            return json.dumps({
                "sector": data.get("sector"),
                "candidate_stocks": [
                    {
                        "ticker": s["ticker"],
                        "average_sentiment": s.get("average_sentiment"),
                        "relevance_score": s.get("relevance_score"),
                    }
                    for s in data.get("candidate_stocks", [])
                ],
            })
        except Exception:
            return self.state.market_output

    def _slim_market_for_strategy(self) -> str:
        """Ticker + sentiment + mention_count + rationale — needed by Draft/Critic/Final."""
        try:
            data = json.loads(self.state.market_output)
            return json.dumps({
                "sector": data.get("sector"),
                "candidate_stocks": [
                    {
                        "ticker": s["ticker"],
                        "mention_count": s.get("mention_count"),
                        "average_sentiment": s.get("average_sentiment"),
                        "relevance_score": s.get("relevance_score"),
                        "rationale": s.get("rationale"),
                    }
                    for s in data.get("candidate_stocks", [])
                ],
            })
        except Exception:
            return self.state.market_output

    def _slim_technical(self) -> str:
        """Key signals per ticker — strips ATR, Bollinger Band, EMA, and other indicators
        not referenced in draft/critic/final task descriptions.
        Normalises both output formats (tasks.yaml: stock_analyses; Pydantic: technical_analysis)
        to the tasks.yaml layout that downstream descriptions expect.
        """
        try:
            data = json.loads(self.state.technical_output)
            # Support both tasks.yaml key (stock_analyses) and Pydantic key (technical_analysis)
            analyses = data.get("stock_analyses") or data.get("technical_analysis") or []
            slim = []
            for a in analyses:
                interp = a.get("interpretation") or {}
                mom = a.get("momentum_analysis") or {}          # Pydantic schema path
                sr = mom.get("support_resistance") or {}
                raw = a.get("raw_indicators") or {}

                slim.append({
                    "ticker": a.get("ticker"),
                    "current_price": a.get("current_price"),
                    "price_data_error": a.get("price_data_error") or a.get("error"),
                    "raw_indicators": {
                        "rsi": raw.get("rsi"),
                        "stochastic_status": raw.get("stochastic_status"),
                        "macd_status": raw.get("macd_status"),
                        "ma_status": raw.get("ma_status"),
                        "adx": raw.get("adx"),
                    },
                    "interpretation": {
                        "overall_signal": interp.get("overall_signal"),
                        "key_signals": interp.get("key_signals") or mom.get("key_signals"),
                        "entry_zone_low": (
                            interp.get("entry_zone_low") or sr.get("support")
                        ),
                        "entry_zone_high": (
                            interp.get("entry_zone_high") or sr.get("resistance")
                        ),
                        "entry_zone_status": interp.get("entry_zone_status"),
                        "regime": interp.get("regime"),
                        "momentum_score": (
                            interp.get("momentum_score") or mom.get("momentum_score")
                        ),
                        "risk_level": (
                            interp.get("risk_level") or mom.get("risk_level")
                        ),
                        "trend_strength": (
                            interp.get("trend_strength") or mom.get("trend_strength")
                        ),
                    },
                })
            return json.dumps({"sector": data.get("sector"), "stock_analyses": slim})
        except Exception:
            return self.state.technical_output

    def _slim_fundamental(self) -> str:
        """Graded fields per ticker — strips raw financial ratios (P/E, margins, etc.)
        that are not used by Draft/Critic/Final.
        Normalises both output formats to the tasks.yaml layout.
        """
        _quality_map = {"High": "STRONG", "Medium": "ADEQUATE", "Low": "WEAK"}
        _growth_map = {
            "High Growth": "HIGH", "Moderate Growth": "MODERATE",
            "Stable": "LOW", "Declining": "DECLINING",
        }
        try:
            data = json.loads(self.state.fundamental_output)
            # Support both tasks.yaml key (stock_analyses) and Pydantic key (fundamental_analysis)
            analyses = data.get("stock_analyses") or data.get("fundamental_analysis") or []
            slim = []
            for a in analyses:
                assessment = a.get("assessment") or {}
                fr = a.get("fundamental_rating") or {}          # Pydantic schema path

                slim.append({
                    "ticker": a.get("ticker"),
                    "assessment": {
                        "valuation_grade": (
                            assessment.get("valuation_grade") or fr.get("valuation")
                        ),
                        "financial_health": (
                            assessment.get("financial_health")
                            or _quality_map.get(fr.get("quality", ""), "UNKNOWN")
                        ),
                        "growth_outlook": (
                            assessment.get("growth_outlook")
                            or _growth_map.get(fr.get("growth", ""), "UNKNOWN")
                        ),
                        "fundamental_component": assessment.get("fundamental_component"),
                        "fundamental_unknown": assessment.get("fundamental_unknown", False),
                        "fundamental_summary": (
                            assessment.get("fundamental_summary") or a.get("investment_thesis")
                        ),
                        "risk_factors": (
                            assessment.get("risk_factors") or a.get("key_risks")
                        ),
                        "catalysts": (
                            assessment.get("catalysts") or a.get("key_strengths")
                        ),
                    },
                })
            return json.dumps({"sector": data.get("sector"), "stock_analyses": slim})
        except Exception:
            return self.state.fundamental_output

    def _slim_draft(self) -> str:
        """Draft positions for Critic/Final — truncates per-position rationale to 150 chars
        and overall_strategy to 200 chars.  All structural fields (action, composite_score,
        allocation_pct, trade_setup, scaled_entry_setups, triggers) are kept in full.
        This prevents the Critic from quoting long prose verbatim in its findings,
        which causes deeply-nested JSON escaping that blows the output token budget.
        """
        try:
            data = json.loads(self.state.draft_output)
            slim_positions = []
            for p in data.get("positions", []):
                slim_positions.append({
                    "ticker": p.get("ticker"),
                    "action": p.get("action"),
                    "composite_score": p.get("composite_score"),
                    "allocation_pct": p.get("allocation_pct"),
                    "current_price": p.get("current_price"),
                    "trade_setup": p.get("trade_setup"),
                    "scaled_entry_setups": p.get("scaled_entry_setups"),
                    "monitoring_triggers": p.get("monitoring_triggers"),
                    "review_frequency": p.get("review_frequency"),
                    "rationale": (p.get("rationale") or "")[:150],
                })
            return json.dumps({
                "sector": data.get("sector"),
                "positions": slim_positions,
                "deployed_pct": data.get("deployed_pct"),
                "reserved_pct": data.get("reserved_pct"),
                "total_allocated_pct": data.get("total_allocated_pct"),
                "cash_reserve_pct": data.get("cash_reserve_pct"),
                "overall_strategy": (data.get("overall_strategy") or "")[:200],
                "risk_level": data.get("risk_level"),
            })
        except Exception:
            return self.state.draft_output

    def _slim_critique(self) -> str:
        """Directives + per-ticker critiques — strips approved_positions (not actionable)."""
        try:
            data = json.loads(self.state.critique_output)
            return json.dumps({
                "sector": data.get("sector"),
                "draft_assessment": data.get("draft_assessment"),
                "per_ticker_critiques": data.get("per_ticker_critiques"),
                "revision_directives": data.get("revision_directives"),
            })
        except Exception:
            return self.state.critique_output

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
        self.state.market_output = result.raw or ""
        self._emit_progress(0, self.state.market_output)
        return self.state.market_output

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
        self.state.technical_output = result.raw or ""
        self._emit_progress(1, self.state.technical_output)
        return self.state.technical_output

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
        self.state.fundamental_output = result.raw or ""
        self._emit_progress(2, self.state.fundamental_output)
        return self.state.fundamental_output

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
        self.state.draft_output = result.raw or ""
        self._emit_progress(3, self.state.draft_output)
        return self.state.draft_output

    @listen(draft_strategy)
    async def critique_review(self):
        self._check_error()
        ctx = "\n\n".join([
            self._fmt_ctx("Market Analysis Output", self._slim_market_for_strategy()),
            self._fmt_ctx("Technical Analysis Output", self._slim_technical()),
            self._fmt_ctx("Fundamental Analysis Output", self._slim_fundamental()),
            self._fmt_ctx("Draft Strategy Output", self._slim_draft()),
        ])
        task = self._factory.build_task("critique_review", self.state.sector, self.state.today, ctx)
        if self._tracker:
            self._tracker.start_phase("critique_review")
        result = cast(CrewOutput, await self._make_crew(task).akickoff())
        if self._tracker:
            self._tracker.finish_phase("critique_review", result.token_usage, self._model_id(task))
        self.state.critique_output = result.raw or ""
        self._emit_progress(4, self.state.critique_output)
        return self.state.critique_output

    @listen(critique_review)
    async def final_strategy(self):
        self._check_error()
        ctx = "\n\n".join([
            self._fmt_ctx("Market Analysis Output", self._slim_market_for_strategy()),
            self._fmt_ctx("Technical Analysis Output", self._slim_technical()),
            self._fmt_ctx("Fundamental Analysis Output", self._slim_fundamental()),
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
