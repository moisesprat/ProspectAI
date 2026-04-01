import json
import os
from datetime import datetime
from crewai import Crew, LLM, Task
from typing import Any, Callable, Dict, List, Optional

from crewai_tools import SerperDevTool
from agents.market_analyst_agent import MarketAnalystAgent
from agents.technical_analyst_agent import TechnicalAnalystAgent
from agents.fundamental_analyst_agent import FundamentalAnalystAgent
from agents.investor_strategic_agent import InvestorStrategicAgent
from config.config import Config
from config.task_config_loader import TaskConfigLoader

from utils.reddit_sentiment_tool import RedditSentimentTool
from utils.technical_analysis_tool import TechnicalAnalysisTool
from utils.fundamental_data_tool import FundamentalDataTool


class ProspectAICrew:
    """Main orchestrator for ProspectAI multi-agent investment analysis."""

    def __init__(self, task_callback=None):
        self.config = Config()
        self.task_callback = task_callback


        # Agents
        self.market_analyst = MarketAnalystAgent()
        self.technical_analyst = TechnicalAnalystAgent()
        self.fundamental_analyst = FundamentalAnalystAgent()
        self.investor_strategist = InvestorStrategicAgent()

        # Tools (only what each task actually uses)
        self.search_tool = SerperDevTool()  # Serper fallback for market analyst
        self.crew = None

    # ─────────────────────────────────────────────────────────────────────────
    # LLM helper (used at the Crew level as a fallback default)
    # ─────────────────────────────────────────────────────────────────────────
    def _get_llm(self):
        provider = os.getenv("MODEL_PROVIDER", "anthropic")
        if provider == "ollama":
            return LLM(
                model=f"ollama/{self.config.OLLAMA_MODEL}",
                base_url=self.config.OLLAMA_BASE_URL,
                temperature=0.1,
            )
        return LLM(
            model=f"anthropic/{self.config.ANTHROPIC_MODEL}",
            api_key=self.config.ANTHROPIC_API_KEY,
            temperature=0.1,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Task definitions
    # ─────────────────────────────────────────────────────────────────────────
    def create_tasks(self, market_criteria: Dict[str, Any]) -> List[Task]:
        sector = market_criteria.get("sector", "Technology")
        today = datetime.now().strftime("%Y-%m-%d")

        loader = TaskConfigLoader()

        def cfg(key: str) -> Dict[str, str]:
            return loader.render(key, sector=sector, today=today)

        # ── Task 1: Market Sentiment Analysis ────────────────────────────────
        market_cfg = cfg("market_analysis")
        market_analysis_task = Task(
            description=market_cfg["description"],
            agent=self.market_analyst.get_agent(),
            tools=[RedditSentimentTool(), self.search_tool],
            expected_output=market_cfg["expected_output"],
        )

        # ── Task 2: Technical Analysis ────────────────────────────────────────
        technical_cfg = cfg("technical_analysis")
        technical_analysis_task = Task(
            description=technical_cfg["description"],
            agent=self.technical_analyst.get_agent(),
            tools=[TechnicalAnalysisTool()],
            expected_output=technical_cfg["expected_output"],
            context=[market_analysis_task],
        )

        # ── Task 3: Fundamental Analysis ──────────────────────────────────────
        fundamental_cfg = cfg("fundamental_analysis")
        fundamental_analysis_task = Task(
            description=fundamental_cfg["description"],
            agent=self.fundamental_analyst.get_agent(),
            tools=[FundamentalDataTool()],
            expected_output=fundamental_cfg["expected_output"],
            context=[market_analysis_task, technical_analysis_task],
        )

        # ── Task 4: Investment Strategy ───────────────────────────────────────
        strategy_cfg = cfg("investment_strategy")
        investment_strategy_task = Task(
            description=strategy_cfg["description"],
            agent=self.investor_strategist.get_agent(),
            tools=[],
            expected_output=strategy_cfg["expected_output"],
            context=[
                market_analysis_task,
                technical_analysis_task,
                fundamental_analysis_task,
            ],
        )

        return [
            market_analysis_task,
            technical_analysis_task,
            fundamental_analysis_task,
            investment_strategy_task,
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
        tasks = self.create_tasks(market_criteria)

        # Build a unified task_callback that fires both the instance-level hook
        # (used in tests / programmatic callers) and the per-run progress_callback
        # (used by the Modal streaming endpoint).
        _task_index = {"n": 0}
        _agent_names = ["MarketAnalyst", "TechnicalAnalyst", "FundamentalAnalyst", "InvestorStrategic"]

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

        self.crew = Crew(
            agents=[
                self.market_analyst.get_agent(),
                self.technical_analyst.get_agent(),
                self.fundamental_analyst.get_agent(),
                self.investor_strategist.get_agent(),
            ],
            tasks=tasks,
            task_callback=_on_task_done,
            verbose=True,
        )

        crew_result = self.crew.kickoff()

        # Parse the final agent's output into a structured dict
        structured = self._parse_result(crew_result)

        summary = (
            structured.get("portfolio_summary", {}).get("portfolio_rationale", "")
            or str(structured)[:300]
        )

        return {
            "status": "success",
            "workflow_completed": True,
            "result": structured,
            "summary": summary,
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
