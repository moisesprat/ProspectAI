import json
import logging
import os
import warnings
from datetime import datetime
from crewai import Crew, LLM, Task
from typing import Any, Callable, Dict, List, Optional

from crewai_tools import SerperDevTool
from agents.market_analyst_agent import MarketAnalystAgent
from agents.technical_analyst_agent import TechnicalAnalystAgent
from agents.fundamental_analyst_agent import FundamentalAnalystAgent
from agents.investor_strategic_agent import InvestorStrategicAgent
from agents.critic_agent import CriticAgent
from config.config import Config
from config.task_config_loader import TaskConfigLoader

from utils.reddit_sentiment_tool import RedditSentimentTool
from utils.technical_analysis_tool import TechnicalAnalysisTool
from utils.fundamental_data_tool import FundamentalDataTool
from utils.fundamental_grader_tool import FundamentalGraderTool
from utils.composite_score_tool import CompositeScoreTool
from utils.portfolio_allocator_tool import PortfolioAllocatorTool
from utils.recommendation_validator import validate_portfolio
from utils import yfinance_cache
from schemas.agent_outputs import (
    MarketAnalysisOutput,
    TechnicalAnalysisOutput,
    FundamentalAnalysisOutput,
    InvestorStrategicOutput,
    CriticOutput,
)

logger = logging.getLogger(__name__)


class TaskFactory:
    """Agent and task factory used by ProspectAIFlow — no deprecation warning."""

    def __init__(self):
        self.config = Config()

        # Agents (created once, reused across build_task calls)
        self.market_analyst = MarketAnalystAgent()
        self.technical_analyst = TechnicalAnalystAgent()
        self.fundamental_analyst = FundamentalAnalystAgent()
        self.investor_strategist = InvestorStrategicAgent()
        self.critic = CriticAgent()

        self.search_tool = SerperDevTool()

        # Phase config built once; tools are shared instances
        self._phase_config = {
            "market_analysis": {
                "agent":  self.market_analyst.get_agent(),
                "tools":  [RedditSentimentTool(), self.search_tool],
                "schema": MarketAnalysisOutput,
            },
            "technical_analysis": {
                "agent":  self.technical_analyst.get_agent(),
                "tools":  [TechnicalAnalysisTool()],
                "schema": TechnicalAnalysisOutput,
            },
            "fundamental_analysis": {
                "agent":  self.fundamental_analyst.get_agent(),
                "tools":  [FundamentalDataTool(), FundamentalGraderTool()],
                "schema": FundamentalAnalysisOutput,
            },
            "draft_strategy": {
                "agent":  self.investor_strategist.get_agent(),
                "tools":  [CompositeScoreTool(), PortfolioAllocatorTool()],
                "schema": InvestorStrategicOutput,
            },
            "critique_review": {
                "agent":  self.critic.get_agent(),
                "tools":  [],
                "schema": CriticOutput,
            },
            "final_strategy": {
                "agent":  self.investor_strategist.get_agent(),
                "tools":  [],
                "schema": InvestorStrategicOutput,
            },
        }

    def build_task(self, phase: str, sector: str, today: str, prior_context: str = "", risk_profile: str = "conservative") -> Task:
        """Build a single Task for `phase`. prior_context is appended to the description."""
        if phase not in self._phase_config:
            raise ValueError(f"Unknown pipeline phase: {phase!r}")
        pc = self._phase_config[phase]
        cfg = TaskConfigLoader().render(phase, sector=sector, today=today, risk_profile=risk_profile)
        description = cfg["description"]
        if prior_context:
            description = description + "\n\n" + prior_context
        return Task(
            description=description,
            agent=pc["agent"],
            tools=pc["tools"],
            expected_output=cfg["expected_output"],
            output_pydantic=pc["schema"],
        )


# DEPRECATED: ProspectAICrew will be removed in a future release.
# Use ProspectAIFlow (prospect_ai_flow.py) for all new code.
class ProspectAICrew(TaskFactory):
    """
    Single-Crew sequential orchestrator for ProspectAI.

    .. deprecated::
        Use :class:`prospect_ai_flow.ProspectAIFlow` instead.
        ProspectAICrew is retained as a task/agent factory and for
        backward-compatibility; it will be removed in a future release.
    """

    def __init__(self, task_callback=None, step_callback=None):
        warnings.warn(
            "ProspectAICrew is deprecated; use ProspectAIFlow instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__()
        self.task_callback = task_callback
        self.step_callback = step_callback
        self.crew = None

    # ─────────────────────────────────────────────────────────────────────────
    # LLM helper (used at the Crew level as a fallback default)
    # ─────────────────────────────────────────────────────────────────────────
    def _get_llm(self):
        provider = os.getenv("MODEL_PROVIDER", "anthropic")
        mid = self.config.effective_default_model_id
        if provider == "ollama":
            return LLM(
                model=f"ollama/{mid}",
                base_url=self.config.OLLAMA_BASE_URL,
                temperature=0.1,
            )
        return LLM(
            model=f"anthropic/{mid}",
            api_key=self.config.ANTHROPIC_API_KEY,
            temperature=0.1,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Task definitions (legacy single-Crew path — deprecated)
    # ─────────────────────────────────────────────────────────────────────────
    def create_tasks(self, market_criteria: Dict[str, Any]) -> List[Task]:
        sector = market_criteria.get("sector", "Technology")
        today = datetime.now().strftime("%Y-%m-%d")

        loader = TaskConfigLoader()

        risk_profile = market_criteria.get("risk_profile", "conservative")

        def cfg(key: str) -> Dict[str, str]:
            return loader.render(key, sector=sector, today=today, risk_profile=risk_profile)

        # ── Task 1: Market Sentiment Analysis ────────────────────────────────
        market_cfg = cfg("market_analysis")
        market_analysis_task = Task(
            description=market_cfg["description"],
            agent=self.market_analyst.get_agent(),
            tools=[RedditSentimentTool(), self.search_tool],
            expected_output=market_cfg["expected_output"],
            output_pydantic=MarketAnalysisOutput,
        )

        # ── Task 2: Technical Analysis ────────────────────────────────────────
        technical_cfg = cfg("technical_analysis")
        technical_analysis_task = Task(
            description=technical_cfg["description"],
            agent=self.technical_analyst.get_agent(),
            tools=[TechnicalAnalysisTool()],
            expected_output=technical_cfg["expected_output"],
            context=[market_analysis_task],
            output_pydantic=TechnicalAnalysisOutput,
        )

        # ── Task 3: Fundamental Analysis ──────────────────────────────────────
        fundamental_cfg = cfg("fundamental_analysis")
        fundamental_analysis_task = Task(
            description=fundamental_cfg["description"],
            agent=self.fundamental_analyst.get_agent(),
            tools=[FundamentalDataTool(), FundamentalGraderTool()],
            expected_output=fundamental_cfg["expected_output"],
            context=[market_analysis_task, technical_analysis_task],
            output_pydantic=FundamentalAnalysisOutput,
        )

        # ── Task 4: Draft Strategy ────────────────────────────────────────────
        draft_cfg = cfg("draft_strategy")
        draft_strategy_task = Task(
            description=draft_cfg["description"],
            agent=self.investor_strategist.get_agent(),
            tools=[CompositeScoreTool(), PortfolioAllocatorTool()],
            expected_output=draft_cfg["expected_output"],
            context=[
                market_analysis_task,
                technical_analysis_task,
                fundamental_analysis_task,
            ],
            output_pydantic=InvestorStrategicOutput,
        )

        # ── Task 5: Critic Review ─────────────────────────────────────────────
        critique_cfg = cfg("critique_review")
        critique_task = Task(
            description=critique_cfg["description"],
            agent=self.critic.get_agent(),
            tools=[],
            expected_output=critique_cfg["expected_output"],
            context=[
                market_analysis_task,
                technical_analysis_task,
                fundamental_analysis_task,
                draft_strategy_task,
            ],
            output_pydantic=CriticOutput,
        )

        # ── Task 6: Final Strategy ────────────────────────────────────────────
        final_cfg = cfg("final_strategy")
        final_strategy_task = Task(
            description=final_cfg["description"],
            agent=self.investor_strategist.get_agent(),
            tools=[CompositeScoreTool(), PortfolioAllocatorTool()],
            expected_output=final_cfg["expected_output"],
            context=[
                market_analysis_task,
                technical_analysis_task,
                fundamental_analysis_task,
                draft_strategy_task,
                critique_task,
            ],
            output_pydantic=InvestorStrategicOutput,
        )

        return [
            market_analysis_task,
            technical_analysis_task,
            fundamental_analysis_task,
            draft_strategy_task,
            critique_task,
            final_strategy_task,
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # Run the full pipeline
    # ─────────────────────────────────────────────────────────────────────────
    def run_analysis(
        self,
        market_criteria: Dict[str, Any],
        progress_callback: Optional[Callable[[Dict], None]] = None,
    ) -> Dict[str, Any]:
        """
        Run the complete investment analysis pipeline.

        Args:
            market_criteria: Dict with at least 'sector' key.
            progress_callback: Optional callable(event_dict) for streaming progress.
                               Reserved for future web-UI integration.

        Returns:
            Dict with 'status', 'result' (structured dict), and 'summary' keys.
        """
        yfinance_cache.clear()
        tasks = self.create_tasks(market_criteria)

        # Build unified callbacks that fire both the instance-level hooks
        # (used in tests / programmatic callers) and the per-run progress_callback
        # (used by the Modal streaming endpoint).
        _task_index = {"n": 0}
        _agent_names = ["MarketAnalyst", "TechnicalAnalyst", "FundamentalAnalyst", "DraftStrategist", "Critic", "FinalStrategist"]

        def _on_task_done(task_output):
            if self.task_callback:
                self.task_callback(task_output)
            if progress_callback:
                idx = _task_index["n"]
                progress_callback({
                    "event": "task_complete",
                    "task_index": idx,
                    "agent": _agent_names[idx] if idx < len(_agent_names) else "unknown",
                    "output_snippet": (task_output.raw or "")[:300],
                })
                _task_index["n"] += 1

        def _on_step(step_output):
            if self.step_callback:
                self.step_callback(step_output)

        self.crew = Crew(
            agents=[
                self.market_analyst.get_agent(),
                self.technical_analyst.get_agent(),
                self.fundamental_analyst.get_agent(),
                self.investor_strategist.get_agent(),
                self.critic.get_agent(),
            ],
            tasks=tasks,
            task_callback=_on_task_done,
            step_callback=_on_step,
            verbose=True,
            cache=True,
        )

        crew_result = self.crew.kickoff()

        # Parse the final agent's output into a structured dict
        structured = self._parse_result(crew_result)

        # Post-generation validation — log issues and include in result
        validation_issues = validate_portfolio(structured)
        if validation_issues:
            for issue in validation_issues:
                log_fn = logger.error if issue.severity == "critical" else logger.warning
                log_fn("[%s] %s — %s: %s", issue.severity.upper(), issue.ticker, issue.field, issue.message)
            structured["validation_warnings"] = [
                {
                    "severity": i.severity,
                    "ticker":   i.ticker,
                    "field":    i.field,
                    "message":  i.message,
                }
                for i in validation_issues
            ]

        summary = (
            structured.get("overall_strategy", "")
            or structured.get("portfolio_summary", {}).get("portfolio_rationale", "")
            or str(structured)[:300]
        )

        return {
            "status": "success",
            "workflow_completed": True,
            "result": structured,
            "summary": summary,
            "validation_warnings": [
                {"severity": i.severity, "ticker": i.ticker, "field": i.field, "message": i.message}
                for i in validation_issues
            ],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Output parsing
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_result(crew_result) -> Dict[str, Any]:
        """
        Extract a JSON dict from the CrewAI result object.
        Handles markdown code fences and plain JSON strings.
        Falls back to a minimal error dict on parse failure.
        """
        # CrewAI >= 0.30 exposes result.json_dict (dict | None) when output is JSON
        if hasattr(crew_result, "json_dict") and crew_result.json_dict:
            return crew_result.json_dict

        # Mini-Crews (ProspectAIFlow) store the result in tasks_output, not on the
        # CrewOutput directly. Check the last task's pydantic/json_dict first.
        tasks_output = getattr(crew_result, "tasks_output", None)
        if tasks_output:
            last = tasks_output[-1]
            if getattr(last, "pydantic", None):
                return last.pydantic.model_dump(mode="json")
            if getattr(last, "json_dict", None):
                return last.json_dict

        raw = getattr(crew_result, "raw", None) or str(crew_result)

        # Strip markdown code fences if the LLM wrapped the output
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
            # Return raw text in a wrapper so callers can still display it
            return {
                "pipeline_version": "2.0",
                "parse_error": True,
                "raw_output": raw,
                "portfolio_summary": {
                    "portfolio_rationale": raw[:500],
                },
            }
